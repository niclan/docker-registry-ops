#!/bin/sh
#
# This script will grep out all the images from a specific registry.
#
# Copyright (C) 2024, Nicolai Langfeldt, Schibsted Products and Technology
#
# Prerequisites:
# - apt install jq

case $1 in
  ''|-h|--help)
    echo "Usage: $0 [REGISTRY]" >&2
    echo "  REGISTRY: The registry to search for images." >&2
    exit 0
    ;;
  */)
    echo "Please provide the registry without a trailing slash." >&2
    exit 1
    ;;
esac

if [ ! -f images.json ]; then
  echo "images.json not found. Please run './k8s-inventory.py' first to make the file." >&2
  exit 1
fi

REG=$1

jq -r '. |= keys | .[]' images.json | egrep -i "^$REG/" > images.lst

wc -l images.lst

