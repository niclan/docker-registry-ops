#!/usr/bin/env python3
#
# Script to garbage collect our (VGs) docker-registry by comparing the
# running kubernetes with the things in the registry.
#
# Copyright (C) 2024, Nicolai Langfeldt, Schibsted Products and Technology
#
# Prerequisites:
# - apt install python3-requests
# - pip install python-dateutil
# - run kubernetes-inventory.py FIRST to get a list of all
#   active images in our k8s clusters into images.json
# - After running this script let loose the docker-registry
#   garbage-collector inside the docker container:
#   `docker exec -it $CONTAINER /bin/registry garbage-collect /etc/docker/registry/config.yml`
#
# Bugs:
# - Does not support docker-registry request pagiation.
#   - Instead submitting n=10000
#
# Features:
# - Multiple tags can refer to the same manifest. The script does not
#   know and will delete the manifest if one tag is marked for
#   eviction.  The api does not support deleting tags...
#
# Usage:
#   With log:
#     PYTHONUNBUFFERED=TRUE ./registryevictor.py 2>&1 | tee eviction-$(date '+%F-%T').log
#   Without log:
#     ./registryevictor.py
# 

import re
import sys
import json
import datetime
import requests
import argparse
from Registry import Registry
from Spinner import Spinner
from dateutil import parser

# The registry to work on
REGISTRY="docker.vgnett.no"

spinner = Spinner()
reg = None
used_repo = {}
used_repo_tag = {}
repos = {}
debug = False
pause = False

## Catalogue all the repos and tags
    
def repo_lookup(repo_name):
    """Look up the needed information from each repository:
    - List of all tags
    - The manifest info for each tag
    - Creation date in order to sort by date
    """

    print("REPO %s" % repo_name)

    if repo_name.startswith("/"):
        sys.exit("Weirdness in repo_lookup")

    if repo_name not in repos:
        repos[repo_name] = {}

    tags = reg.get_tags(repo_name)
    if tags is None or len(tags) == 0:
        repos[repo_name]['_notags'] = True
        return

    problems = 0
    
    for tag in tags:
        tagkey = f'{repo_name}:{tag}'

        spinner.next()
        (tagdig, manifest) = reg.get_manifest(repo_name, tag)
        
        if len(manifest) == 0:
            problems += 1
            continue
        
        if "history" not in manifest:
            print("*E* Weird manifest: %s" % manifest)
            sys.exit(1)

        if tag not in repos[repo_name]:
            repos[repo_name][tag] = {}

        created = json.loads(manifest['history'][0]['v1Compatibility'])
        repos[repo_name][tag]["created"] = parser.parse(created['created'])
        repos[repo_name][tag]["digest"] = tagdig

    if problems > 0:
        print("*E* %d problem manifests with %s" % (problems, repo_name))

# Eviction logic

def delete_most_manifests(repo_name):
    """For repositories that are in use in kubernetes delete the tags we don't need.

    I.e., delete most tags, except:
       - The 3 newest
       - The ones in use
       - The 2 newsest before the ones in use
    """

    # List all actuall tags, this excludes the ones starting in underscore
    the_tags = list(filter(lambda x: not x.startswith("_"), \
                           repos[repo_name].keys()) )

    if len(the_tags) == 0:
        print("* No some tags to delete")
        return

    # Get the tags sorted by time
    tag_bytime = sorted(the_tags, key=lambda x: repos[repo_name][x]["created"])

    print("* Delete some tags in repo (newer last): %s" % tag_bytime)

    # Keep the 3 newest tags:
    tags_to_keep = { tag_bytime[-1]: True }
    try:
        tags_to_keep[tag_bytime[-2]] = True
        tags_to_keep[tag_bytime[-3]] = True
    except IndexError:
        pass

    # Want to delete all tags but the 3 newest before the ones in use
    used_tags = {}
    for tag in tag_bytime:
        repo_tag = f'{repo_name}:{tag}'
        if repo_tag not in used_repo_tag:
            continue

        if debug: print("  ! Tag %s is in use" % tag)
        used_idx = tag_bytime.index(tag)
        tags_to_keep[tag] = True
        try:
            tags_to_keep[tag_bytime[used_idx-1]] = True
            tags_to_keep[tag_bytime[used_idx-2]] = True
        except IndexError:
            pass

    print("* Tags to keep: %s" % list(tags_to_keep.keys()))
    if pause: any_key = input("Press enter to proceed")

    # Delete the tags, except the ones we want to keep
    for tag in tag_bytime:
        repo_tag = f'{repo_name}:{tag}'
        if tag in tags_to_keep:
            print("+ Keep %s" % repo_tag)
            continue
        
        print("? %s: %s" % (tag, repos[repo_name][tag]))
        print("- Delete %s" % repo_tag)
        reg.delete_manifest(repo_name, repos[repo_name][tag]['digest'])
    

def delete_all_manifests(repo_name):
    """Delete all manifests refered to all the tags in a repo.  This
    should only be used on repositories that are not used by k8s.
    """

    tags = list(repos[repo_name].keys())

    if len(tags) == 0:
        print("* No tags to delete")
        return

    print("* Delete all tags: %s" % tags)
    if pause: any_key = input("Press enter to proceed")

    for tag in repos[repo_name]:
        repo_tag = f'{repo_name}:{tag}'
        print("- Delete %s" % repo_tag)
        reg.delete_manifest(repo_name, repos[repo_name][tag]['digest'])


def evict_repo(repo_name):
    """Fint out how much should be deleted and call the apropriate function.
    For unused repos: all the tags
    For used repos: just some of the tags"""

    if "_notags" in repos[repo_name]:
        print(" * Repo %s has no tags, nothing to do" % repo_name)
        return

    if repo_name in used_repo:
        delete_most_manifests(repo_name)
        return

    delete_all_manifests(repo_name)


def load_image_list():
    """Load image list from json file previously written by
    kubernetes-inventory.py"""

    images = {}

    # This is the list of image:tags we use in kubernetes
    with open("images.json", "r") as f:
        images = json.loads(f.read())

    if len(images) < 10:
        sys.exit("The image list seems unreasonably short!")

    regPrefix = f'{REGISTRY}/'

    for i in images:
        if not i.startswith(regPrefix):
            continue
        
        repo_tag = i.replace(regPrefix,"",1)

        # A bit of paranoid sanity checking
        if repo_tag == i:
            sys.exit("That's weird!")
        i = None # Just to be sure we don't use it by mistake

        if repo_tag.startswith("/"):
            sys.exit("That's weird II!")

        (repo, tag) = repo_tag.split(":")
        used_repo[repo] = True
        used_repo_tag[repo_tag] = True

    return images


def main():
    parser = argparse.ArgumentParser(description='Evict tags/manifests from docker-registry')
    parser.add_argument('-d', '--delete', action='store_true', \
                        help='Actually delete the manifests', default=False)
    parser.add_argument('-r', '--repository', action='store', \
                        help='Only work on this repository instead of all')
    parser.add_argument('-D', '--debug', action='store_true', \
                        help='Debug', default=False)
    parser.add_argument('-p', '--pause', action='store_true', \
                        help='Pause before (possible) delete in each registry', default=False)
    args = parser.parse_args()

    global debug
    global pause
    debug = args.debug
    do_delete = args.delete

    images = load_image_list()

    global reg
    reg = Registry(REGISTRY, do_delete)
    reg.verbose = True
    reg.debug = debug

    if not do_delete:
        print("***Not deleting anything, just looking around***")
    else:
        print("***WILL DELETE MANIFESTS!!!!***")

    if args.repository:
        repo_lookup(args.repository)
        evict_repo(args.repository)
        return

    repos = reg.get_repositories()

    for repo_name in repos:
        repo_lookup(repo_name)
        evict_repo(repo_name)


if __name__ == "__main__":
    main()
