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
from dateutil import parser
import datetime
import requests

# The registry to work on
REGISTRY="docker.vgnett.no"

# Spinner to show progress
spinner = "|/-\\"
spinner_idx = 0

# But only if we have a tty
is_tty = sys.stdout.isatty()

def spinner_next():
    """Print the next spinner character and backspace to so that new output on the line
    will overwrite the spinner character"""
    global is_tty
    global spinner_idx
    global spinner

    # No progress unless we have a tty
    if not is_tty:
        return

    spinner_idx += 1
    if spinner_idx >= len(spinner):
        spinner_idx = 0

    print("%s\b" % spinner[spinner_idx], end="", flush=True)


# Some REST helpers
# We should have one that understands pagination, but whatever

def json_get(url):
    """Get URL and return json or empty list on error"""

    r = requests.get(url)

    if r.status_code == 200:
        return r.json()

    if r.status_code == 404:
        return []

    if r.status_code == 400:
        print("Error 400 on %s (%s), making empty return" % (url, r.text.rstrip()))
        return []

    print("Error: %s (%s) getting %s" % (r.status_code, r.text.rstrip(), url))
    sys.exit(1)
    

def get_repositories():
    return json_get("https://%s/v2/_catalog?n=10000" % REGISTRY)["repositories"]


def get_tags(repo):
    """Get all tags for a repo"""

    j = json_get("https://%s/v2/%s/tags/list?n=10000" % (REGISTRY, repo))
    if "tags" not in j:
        return []

    return j["tags"]


def get_manifest(repo, tag):
    """Get the manifest for a tag.  This requires two queries to the
    registry.  The first one gets the digest, the second one gets the
    manifest itself.  The digest is needed to delete the manifest."""

    r = requests.get("https://%s/v2/%s/manifests/%s" % (REGISTRY, repo, tag),
                     headers={"Accept": "application/vnd.docker.distribution.manifest.v2+json"})

    if r.status_code == 200:
        dcd = r.headers['Docker-Content-Digest']
        mani = json_get("https://%s/v2/%s/manifests/%s" % (REGISTRY, repo, tag))
        if r.status_code == 200:
            return dcd, mani
        # The error will already have been reported in json_get so don't bother
        # here

    return "", {}


## Delete functions

def delete_manifest(repo_tag):
    """Delete the manifest for a tag.  This requires lookup of the
    digest corresponding to the tag so that it can be passed to the
    API.
    """

    (repo, tag) = repo_tag.split(":")
    dig = repos[repo][tag]['digest']
    print("-- Deleting manifest for %s:%s" % (repo_tag, dig))
    r = requests.delete("https://%s/v2/%s/manifests/%s" % (REGISTRY, repo, dig))
    if r.status_code != 200 and r.status_code != 202:
        print("--- Result: %s: %s" % (r.status_code, r.text.rstrip()))

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

    tags = get_tags(repo_name)
    if tags is None or len(tags) == 0:
        repos[repo_name]['_notags'] = True
        return
    
    for tag in get_tags(repo_name):
        tagkey = f'{repo_name}:{tag}'

        spinner_next()
        (tagdig, manifest) = get_manifest(repo_name, tag)
        
        if len(manifest) == 0:
            no_manifest[tagkey] = True
            continue
        
        if "history" not in manifest:
            print("*E* Weird manifest: %s" % manifest)
            sys.exit(1)

        if tag not in repos[repo_name]:
            repos[repo_name][tag] = {}

        created = json.loads(manifest['history'][0]['v1Compatibility'])
        repos[repo_name][tag]["created"] = parser.parse(created['created'])
        repos[repo_name][tag]["digest"] = tagdig


# Eviction logic

def delete_most_manifests(repo_name):
    """For repositories that are in use in kubernetes delete the tags we don't need.

    I.e., delete most tags, except:
       - The 3 newest
       - The ones in use
       - The 2 newsest before the ones in use
    """
    global used_repo
    global used_repo_tag

    # List all actuall tags, this excludes the ones starting in underscore
    the_tags = list(filter(lambda x: not x.startswith("_"), \
                           repos[repo_name].keys()) )

    if len(the_tags) == 0:
        print("* No some tags to delete")
        return

    # Get the tags sorted by time
    tag_bytime = sorted(the_tags, key=lambda x: repos[repo_name][x]["created"])

    print("* Delete some tags in repo (by time): %s" % tag_bytime)

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

        used_idx = tag_bytime.index(tag)
        tags_to_keep[tag] = True
        try:
            tags_to_keep[tag_bytime[used_idx-1]] = True
            tags_to_keep[tag_bytime[used_idx-2]] = True
        except IndexError:
            pass

    print("* Tags to keep: %s" % list(tags_to_keep.keys()))
    # Delete the tags, except the ones we want to keep
    for tag in tag_bytime:
        repo_tag = f'{repo_name}:{tag}'
        print("? %s: %s" % (tag, repos[repo_name][tag]))
        if tag in tags_to_keep:
            print("+ Keep %s" % repo_tag)
            continue
        
        print("- Delete %s" % repo_tag)
        delete_manifest(repo_tag)
    

def delete_all_manifests(repo_name):
    """Delete all manifests refered to all the tags in a repo.  This
    should only be used on repositories that are not used by k8s.
    """

    tags = list(repos[repo_name].keys())

    if len(tags) == 0:
        print("* No tags to delete")
        return

    print("* Delete all tags: %s" % tags)
    # enter = input("Press enter to proceed")

    for tag in repos[repo_name]:
        repo_tag = f'{repo_name}:{tag}'
        print("- Delete %s" % repo_tag)
        delete_manifest(repo_tag)


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

    global images
    global used_repo
    global used_repo_tag

    # This is the list of image:tags we use in kubernetes
    with open("images.json", "r") as f:
        images = json.loads(f.read())

    if len(images) < 10:
        sys.exit("The image list seems unreasonably short!")

    regPrefix = f'{REGISTRY}/'

    for i in images:
        if not i.startswith(regPrefix):
            continue
        
        j = i.replace(regPrefix,"",1)

        # A bit of paranoid sanity checking
        if j == i:
            sys.exit("That's weird!")
        if j.startswith("/"):
            sys.exit("That's weird II!")

        (repo, tag) = j.split(":")
        used_repo[repo] = True
        used_repo_tag[i] = True


def main():

    load_image_list()

    repos = get_repositories()

    for repo_name in repos:
        repo_lookup(repo_name)
        evict_repo(repo_name)


no_manifest = {}
used_repo = {}
used_repo_tag = {}
images = {}
repos = {}

if __name__ == "__main__":
    main()