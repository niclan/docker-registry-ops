#!/usr/bin/env python3
#
# Script to garbage collect our (VGs) docker-registry by comparing the
# running kubernetes with the things in the registry.
#
# Prerequisites:
#

import sys
import json
from registryevictor import get_repositories, get_tags, spinner_next, get_manifest, load_image_list

REGISTRY="docker.vgnett.no"
used_repo = {}
used_repo_tag = {}

def main():
    global images
    
    all_tags = []

    images = load_image_list()

    with open("images.json", "r") as f:
        image_report = json.load(f)

    # images = ['docker.vgnett.no/svp/live-api:2f7c1e6.466']

    spinner_next()
    
    regPrefix = f'{REGISTRY}/'

    for path in images:
        spinner_next()

        if not path.startswith(regPrefix):
            continue
        
        repo_tag = path.replace(regPrefix,"",1)
        
        # print("Repo-tag: %s" % repo_tag)
        
        (repo, tag) = repo_tag.split(":")

        (checksum, manifest) = get_manifest(repo, tag)
        if manifest is None or len(manifest) == 0 or checksum is None or len(checksum) == 0:
            print("Manifest for tag %s is wrong, cluster %s namespace %s" % \
                  (repo_tag, image_report[path]['cluster'], image_report[path]['namespace']))


if __name__ == "__main__":
    main()
