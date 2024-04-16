#!/bin/bash

# This script will migrate all images from one registry to another.
#
# (C) 2024, Nicolai Langfeldt, Schibsted Products and Technology
#

# Prerequisites:
# - apt install jq

REMOVE=0

case $1 in
  ''|-h|--help)
    echo "Usage: $0 [-r] REGISTRY NEWREGISTRY" >&2
    echo "  REGISTRY: The registry to search for images." >&2
    echo "  NEWREGISTRY: The registry to migrate the images to." >&2
    echo "  -r: Remove the images from the source registry." >&2
    exit 0
    ;;
  '-r') REMOVE=1; shift ;;
esac

case $1$2 in
  */*)
    echo "Please provide the registry names without trailing slash." >&2
    exit 1
    ;;
esac

if [ ! -f images.lst ]; then
  echo "images.lst not found. Please run './image-list.sh' first to make the file." >&2
  exit 1
fi


OLDREG=$1; shift
NEWREG=$1; shift

# Exit at once if anything fails
set -e
while read -r IMAGE; do
    echo "Migrating $IMAGE from $OLDREG to $NEWREG"
    REPOTAG=$(cut -d/ -f2- <<< $IMAGE)
    skopeo copy docker://$OLDREG/$REPOTAG docker://$NEWREG/$REPOTAG
    ./repository-rm.py -s $OLDREG $REPOTAG
done < images.lst

