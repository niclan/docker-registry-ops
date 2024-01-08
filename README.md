# Docker registry evictor

This script takes a two stage approach.

1. Get a inventory of used images from your runtime environments.
   This is done by running `./k8s-inventory.py`.  It looks at the k8s
   clusters configured in the cli environment and loops over them all
   collecting the image list.  This list is saved in images.json.

   Please have a look at the documentation at the top of the script
   for information about how to run it and restrictions

2. Afterwards you can run `./registryevictor.py`. It will loop over
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

## `registry-ls.py`

This script just counts all the tags in the registry.  Planning to use
it to write a report of missing/corrupted manifests so that the
interventions we know can be applied to the file storage structure of
the docker-registry

## registry fixer

To be written. Would read the corrupted-manifest list and then do
interventions in the filesystem of the registry to fix the problems.

Registry issues seen:
- Corrupted manifests uploaded by docker which the registry accepts
  and saves.  If you ask for tags the upload will have a tag, but if
  you try to download it docker will simply give some error message.
- Someone saved space by deleting old files in the registry directory
  structure.  The tags will often still be listed but it's impossible
  to get manifests or to delete things to get rid of them.
