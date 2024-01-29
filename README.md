# Some docker registry ops tools

Some ops tools for docker-registry.

## Limitations

This was made for our ops needs: We have multiple clusters configured
in our kubernetes contexts and all available contexts are searched to
find what docker images they use.

This suite is not made for installing, you run it from this directory
or in a kubernetes pod.  It will make report files and such here.

Please make PRs if you adapt it to your needs.

## Installing

This software is written in python.

You need:

- Python 3 and pip
- A docker registry
- One or more kubernetes clusters
- kubectl cli executable

Python needs some packages: see `requirements.txt`.  You can see if
your OS package manager provides them and install them using that or
you can try pip: `pip3 install -r requirements.txt`

## Included programs

The suite consists of these programs.

### `k8s-inventory.py`

This loops over all the kubernetes clusters you have configured in
contexts in your shell and collects a list of images used for the pods
in the clusters.  This list is saved in `images.json`.  If people are
doing continous deployment the file is of course instantly stale, but
the one script that tries to delete things does not delete your 3
newest things so this should be fine.

This is in a separate program because most of the scripts here need a
list of images in use and in our environment it takes almost half a
minute to run which I consider to be a drag.

### `registry-evictor.py`

**WARNING**: This program can do serious damage if it has a bug or if
it's assumptions about what is safe to delete is wrong for your site.
**Use at your own risk!**

This script needs the `images.json` file to work.  If the file is old
or trunkated it may delete the wrong things.  Once you have a
reasonably fresh one you can run `./registry-evictor.py`. It will loop
over all repositories and tags and:

   0. If there are less than 10 images listed it aborts
   1. For repositories which are not listed (as used) in `images.json`
      delete all the manifests.
   2. For repositories that are listed (as used) in `images.json` it
      will:
      - Keep the 3 last tags. "latest" is also a tag and is counted
      - Keep all referenced tags and the two before it (=3)
      - Delete everything else

    Please have a look at the documentation at the top of the script
    for information about how to run it and restrictions.

After this completes you can run the docker-registry garbage
collection routine to reclaim disk space.

### `registry-count.py`

This script just counts all the tags in the registry (no matter what
their health status is, see below).  Just to help keep count of how
many there was before and after eviction and garbage collection.

### `registry-checker.py`

This script checks the health of manifests, and also if repositories
have any tags at all, By health I mean: is it possible to retrieve the
manifest itself and it's digest?  All errors are saved in report files
stored in time stamped directories.

The default mode is that it reads the images.json file and tests all
the tags in the file and reports on that.  That way there is nothing
about unused tags in the report.

If you specify the `-R` option it will use the inventories in the
registry and check _everything_, annotating each thing it checks with
wether it's in use or not.

The error list is saved in both .json and CSV format.

### registry fixer

To be written. Would read the output from the registry-checker and do
interventions in the filesystem of the registry to fix the problems.

Registry issues we've seen:

- Corrupted manifests uploaded by docker which the registry accepts
  and saves.  If you ask for tags the upload will have a tag, but if
  you try to download it docker will simply give a error message about
  a corrupted manifest.
- Someone saved space by deleting old files in the registry directory
  structure.  The tags will often still be listed but it's impossible
  to get manifests or to delete things to get rid of them.
  
### Inside the docker container

Some relatively simple programs running inside the container in the
kubernetes pod:

#### cron.py

It turned out to be a bit of a bother to run something that needs the
kubernetes API from regular old cron -- in a container.  So this
little script replaces cron for our needs.

#### webserver.py

A quite trivial web server in python to answer the `/_health` calls
from kubernetes (NOTE to self: Remember to make a meaningful health
check)

Also serve the images.json file to outside agents so they can merge
the file from multiple clusters and run `registry-evictor.py` to
lighten the docker-registry storage needs.

Also provide a endpoint for a nagios (or similar) checker to call and
get the results of the registry-checker.  Which was the main idea
anyway.  We've seen that docker images go missing over time so we need
to keep an eye on that.

## Deploying to kubernetes

This requires that you have docker installed to build the needed
container.

The k8s-inventory/registry-checker programs can be deployed to
kubernetes to provide a API whereby some kind of checker (e.g. nagios
plugin?) can make a API call to determine which pods are running
without their images so that ops can keep an eye on this.

The deployment tool is [`skaffold`](https://skaffold.dev/) which is
both very nice for the development and also for production deployment.

The basic setup is defined in [`skaffold.yaml`](skaffold.yaml).

This is a standard deployment with a service account that has a
cluster role to get all pods across all namespaces.

To deploy to multiple environments skaffold profiles are used combined
with kustomize which is (now) a part kubectl.  If you have a look at
skaffold.yaml and the profiles part you'll see that the project is set
up to deploy to a namespace called "ops-dev" by default.

This is defined in [`kustomize/dev`](kustomize/dev).  When running
e.g. `skaffold run -p prod` the profile in `skaffold.yaml` overrides the
earlier settings and then uses the setup in
[`kustomize/prod`](kustomize/prod) and the namspace "ops-production".

To suit yourself you can edit skaffold.yaml to define your own
profiles and add them in the kustomize directory.

To develop on the contents of the pod: `make dev` (`skaffold dev`) -
this deploys to the "ops-dev" namespace and any changes you make in
your working directory is copied into the pod automatically.

To deploy to stage: `make stage` (alias `skaffold run -p stage` except
it also builds secrets and checks if git is up to date).

To deploy to prod: `make prod` (`skaffold run -p prod`, also builds
secrets and checks git).

Deploying to stage and prod requires that all git managed files are
comitted and up to date in git.  The Makefile checks this.

## Secrets

We use Hashicorp vault to store secrets.  To support getting secrets
from vault into the deployment the directory `vault` is provided with
a Makefile using `consul-template` to write a manifest file into the
kustomize/base directory.

The manifest file is is secret.yaml from secret-yaml.ctmpl.  This can
be used for secretRef to put the secrets into the pod environment.
This is defined in
[`kustomize/base/Deployment.yaml`](kustomize/base/Deployment.yaml)

The files that kustomize uses as input must reside within the
kustomize file hierarchy, therefore the Makefile writes to
../kustomize/base. If you use the secret.yaml file it will be subject
to kustomize's customizations.

The template files are only processed by `consul-template`, so you
have to make new ones to get it to collect keys from different vault
paths for each of the environments/namespaces you deploy to and
generate manifests into the correct directories and then update the
kustomization.yaml files to pick them up.

