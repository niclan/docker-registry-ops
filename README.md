# Docker registry evictor

This script takes a two stage approach.

1. Get a inventory of used images from your runtime environments.
   This is done by running `./k8s-inventory.py`.  It looks at the k8s
   clusters configured in the cli environment and loops over them all
   collecting the image list.  This list is saved in images.json.

   Please have a look at the documentation at the top of the script
   for information about how to run it and restrictions

2. Afterwards you can run `./registry-evictor.py`. It will loop over
   all repositories and tags and

   1. For repositories which are not listed (as used) in `images.json`
      delete all the manifests.
   2. For repositories that are listed (as used) in `images.json` it
      will:
      - Keep the 3 last tags
      - Keep all referenced tags and the two before it
      - Delete everything else

    Please have a look at the documentation at the top of the script
    for information about how to run it and restrictions.

After this completes you can run the docker-registry garbage
collection routine to reclaim disk space.

## `registry-count.py`

This script just counts all the tags in the registry (no matter what
their health status is, see below).  Just to help keep count of how
many there was before

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
