# Some docker registry ops tools

Some ops tools for docker-registry management:

- `k8s-inventory.py` - Collects a list of images used in your
  kubernetes clusters and saves it in `images.json`
- `registry-evictor.py` - After collecting the image inventory from
  the clusters this program can delete (most of) the unreferenced
  ones.  See below for more information.
- `registry-count.py` - Just count the number of tags in your
  registry, for pre-eviction and post-eviction stats.  We went from
  400K tags to less than 10K the first time this was run.
- `registry-checker.py` - We've seen that some of our pods images have
  gone missing from our registry. Quite likely due to earlier cleanup
  attempts and bugs in early versions of the registry-evictor.  Since
  this has caused major headaches when we've had problems with our
  cluster nodes and the pods needs to respawn on new nodes without the
  image in the local docker cache we want to keep a firm eye on this.

More details below.

Libraries:

- Registry.py - I was unable to find a usable python library for
  docker-registry so I wrote a simple one myself to support the
  registry tools.
- Spinner.py - The simplest of progress indicators

## Monitoring

Still developing this:

There is a skaffold based kubernetes deployment in this repository
that will:

- Run k8s-inventory and registry-checker at startup and every 15
  minutes to make a report on missing image tags in the repository
- Provides a trivial web server to query the result of the check.

## AI support

There is no AI builtin in these tools.

When writing this github copilot has been sometimes a quite able
helper, sometimes quite helpless.  On the whole it's saved me some
percent of typing and some time on looking up things.  But it also
quite clearly hallucinates about REST endpoints that ought to exist
(in this project both kubernetes and docker-registry APIs). GPT4 has
also been of some help but it was easily confused about YAML
indentation.

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

- Python 3.7 or later and pip
- jq
- One or more docker registries
- One or more kubernetes clusters
- kubectl cli executable

If you want to deploy to kubernetes (only needed for monitoring) you
need:

- [skaffold](https://skaffold.dev/) for deploying to kubernetes
- [consul-template](https://github.com/hashicorp/consul-template) if
  you want to get secrets from vault into the kubernetes pod

Python needs some packages: see `requirements.txt`.  You can see if
your OS package manager provides them and install them using that or
you can try pip: `pip3 install -r requirements.txt`

## Included programs

The suite consists of these programs:

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

1. If there are less than 10 images listed it aborts
1. For repositories which are not listed (as used) in `images.json`
   delete all the manifests.
1. For repositories that are listed (as used) in `images.json` it
   will:
  - Keep the 3 last tags. "latest" is also a tag and is counted
  - Keep all referenced tags and the two before it (=3)
  - Delete everything else

Please have a look at the documentation at the top of the script for
information about how to run it and restrictions.

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

### `registry-ls.py`

This is a simple program to list the tags in a repository.

```
usage: registry-ls.py [-h] [-d] [-r REPOSITORY] server

Count number of tags in registry

positional arguments:
  server                Registry server

options:
  -h, --help            show this help message and exit
  -d, --digest          Show digest of tags
  -r REPOSITORY, --repository REPOSITORY
                        Work on this repository instead of all (can be repeated)
```

It can be combined with other shell utilities to do e.g. get a list
how many tags there are pr. repository:

```
./registry-ls.py docker.vgnett.no | cut -d: -f 1 | uniq -c | sort -n >tags-pr-repo.txt
```

### `image-list.sh`

A very simple shell script to grep out all the images associated with
a specific registry from images.json to images.lst.  The result file
just contains a list of images, one pr. line.

Usage example:

```console
$ image-list.sh docker.vgnett.no
676 images.lst
```

The line of output shows how many ended up `images.lst`.

The result is a list of the images of the images from the given that
are in actuall use in your clusters.  In a migration scenario these
are the images you need to copy from the old registry to the new
registry.

### `registry-migrate.sh`

A shell wrapper around skopeo to migrate the images listed in
`images.lst` (see above) from the origin registry to the destination
registry.

Before using it you have to install skopeo which is available in
Debian and many other distributions: `apt install skopeo`.  skopeo is
used to do the actuall migration.

Usage example:

1. `./k8s-invntory.py` to make images.json (see complete usage above)
1. `./image-list.sh docker.vgnett.no` to make images.lst
1. Review and images.lst in case you don't want to migrate everything
1. If needed: `skopeo login docker.vgnett.no`
1. If needed: `skopeo login harbor.vgnett.no`
1. `./registry-migrate.sh docker.vgnett.no harbor.vgnett.no`

### Registry issues

Registry issues we've seen:

- Corrupted manifests uploaded by docker which the registry accepts
  and saves.  If you ask for tags the upload will have a tag, but if
  you try to download it docker will simply give a error message about
  a corrupted manifest.
- Someone saved space by deleting old files in the registry directory
  structure.  The tags will often still be listed but it's impossible
  to get manifests or to delete things to get rid of them.
- Layers going missing. This is sometimes fixed by restarting the
  registry.  Sometimes it can be fixed by doing "docker rmi" on the
  tag and then re-uploading the tag from somewhere it's cached.

### Inside the docker container

Some relatively simple programs running inside the container in the
kubernetes pod:

#### cron.py

It turned out to be a bit of a bother to run something that needs the
kubernetes API from regular old cron -- in a container.  So this
little script replaces cron for our needs.

#### webserver.py

A quite trivial web server in python to answer the `/_health` calls
from kubernetes.

`/_nagios_check_registry` is for nagios (or similar) checker to call
and get the results of the registry-checker.  Which was the main idea
anyway.  We've seen that docker images go missing over time so we need
to keep an eye on that.  The endpoint returns a multi-line description
of what the issues are, if you click on the check in nagios all the
lines will be shown.

`/_images.json`, `/_report.csv` and `/_report.json` enables inspection
of the reports that goes into the check.

## Deploying to kubernetes

This requires that you have docker installed to build the needed
container.

The k8s-inventory/registry-checker programs can be deployed to
kubernetes to provide some endpoints to monitor needed and available
images as described above.

The deployment tool is [`skaffold`](https://skaffold.dev/) which is
both very nice for the development and also for production deployment.

The basic setup is defined in [`skaffold.yaml`](skaffold.yaml).

This is a standard deployment with a service account that has a
cluster role to get all pods across all namespaces.

To deploy to multiple environments skaffold profiles are used combined
with kustomize which is (now) a part kubectl.  If you have a look at
`skaffold.yaml` and the profiles part you'll see that the project is set
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
comitted and up to date in git.  The Makefile checks this.  This is
because the image is tagged with the git digest and the digest must
reflect all the actuall files that go into the image.

## Secrets

This turns out to be not actually useful for this project, unless you
want to requite a secret to get access to the endpoints.  The
webserver does not support using this.

We use Hashicorp vault to store secrets.  To support getting secrets
from vault into the deployment the directory `vault` is provided with
a Makefile using `consul-template` to write a manifest file into the
kustomize/base directory.

The manifest file is is `secret.yaml` from `secret-yaml.ctmpl`.  This
can be used for secretRef to put the secrets into the pod environment.
This is defined in
[`kustomize/base/Deployment.yaml`](kustomize/base/Deployment.yaml)

The files that kustomize uses as input must reside within the
kustomize file hierarchy, therefore the Makefile writes to
`../kustomize/base`. If you use the `secret.yaml` file it will be
subject to kustomize's customizations.

The template files are only processed by `consul-template`, so you
have to make new ones to get it to collect keys from different vault
paths for each of the environments/namespaces you deploy to and
generate manifests into the correct directories and then update the
`kustomization.yaml` files to pick them up.
