# Docker registry evictor

Some ops tools for docker-registry.

## Usage

This was made for our needs so: We have multiple clusters configured
in our kubernetes contexts.  Since those of us using it are ops we
have pretty wide rights.  Please make PRs if you adapt it to your
needs.

## Installing

Python needs a couple of packages: see requirements.txt.  You can see
if your OS package manager provides them and install them using that
or you can try pip: `pip install -r requirements.txt`

This suite is not made for installing, you run it from this directory.  It
will make report files and such here.

## `k8s-inventory.py`

This loops over all the kubernetes clusters you have configured in
contexts in your shell and collects a list of images used for the pods
in the clusters.  This list is saved in `images.json`.  If people are
doing continous deployment the file is of course instantly stale, but
the one script that tries to delete things does not delete your 3
newest things so this should be fine.

This is in a separate program because most of the scripts here need a
list of images in use and in our environment it takes almost half a
minute to run which I consider to be a drag.

## `registry-evictor.py`

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

## `registry-count.py`

This script just counts all the tags in the registry (no matter what
their health status is, see below).  Just to help keep count of how
many there was before and after eviction and garbage collection.

## `registry-checker.py`

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

## registry fixer

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

## Deploying to kubernetes

This requires that you have docker installed to build the needed
container.

The k8s-inventory/registry-checker programs can be deployed to
kubernetes to provide a API whereby some kind of checker (e.g. nagios
plugin?) can make a API call to determine which pods are running
without their images so that ops can keep an eye on this.

The deployment tool is [`skaffold`](https://skaffold.dev/) which is
both very nice for the development and also for production deployment.

The basic setup is defined in `[skaffold.yaml](skaffold.yaml)`.

This is a standard deployment with a service account that has
permissions to get all pods across all namespaces.

To deploy to multiple environments skaffold profiles are used combined
with kustomize which is (now) a part kubectl.  If you have a look at
skaffold.yaml and the profiles part you'll see that the project is set
up to deploy to a namespace called "ops-staging" by default.

This is defined in `[kustomize/base](kustomize/base)`.  When running
e.g. `skaffold run -p prod` the profile in skaffold.yaml overrides the
earlier settings and then uses the setup in
`[kustomize/prod](kustomize/prod)` and the namspace "ops-production".

To suit yourself you can edit skaffold.yaml to define your own
profiles and add them in the kustomize directory.

To develop on the contents of the pod: `skaffold dev` - this deploys
to the ops-stage namespace and any changes you make in your working
directory is copied into the pod automatically.

To deploy to stage: `skaffold run` (this uses the "dev" or "base"
profile)

To deploy to prod: `skaffold run -p prod`



