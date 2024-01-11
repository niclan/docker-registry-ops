#!/usr/bin/env python3
#
# Script to garbage collect our (VGs) docker-registry by comparing the
# running kubernetes with the things in the registry.
#
# Prerequisites:
#

import sys
import csv
import json
import requests
import argparse
from Spinner import Spinner
from os import mkdir, chdir
from datetime import datetime

REGISTRY="docker.vgnett.no"
DIRNAME = "check-report-%s" % datetime.now().strftime("%Y-%m-%d-%H:%M:%S")

used_repo = {}
used_repo_tag = {}


def get_manifest_health(repo, tag):
    """Get the manifest for a tag
    registry.  The first one gets the digest, the second one gets the
    manifest itself.  The digest is needed to delete the manifest."""

    result = { 'digest': {}, 'manifest': {} }

    d = requests.get("https://%s/v2/%s/manifests/%s" % (REGISTRY, repo, tag),
                     headers={"Accept": "application/vnd.docker.distribution.manifest.v2+json"})

    m = requests.get("https://%s/v2/%s/manifests/%s" % (REGISTRY, repo, tag))

    return d, m


def examine_by_report(image_report):
    regPrefix = f'{REGISTRY}/'

    i = 0

    for path in image_report:
        spinner.next()

        if not path.startswith(regPrefix):
            continue
        
        repo_tag = path.replace(regPrefix,"",1)

        # We only care about images that are running or pending, the
        # state of way too many dead pods is kept around.
        if not (image_report[path]['_phase']['Running'] or
                image_report[path]['_phase']['Pending'] or
                image_report[path]['_phase']['ImagePullBackOff']):
            continue

        i += 1

        (repo, tag) = repo_tag.split(":")

        (digest, manifest) = get_manifest_health(repo, tag)

        if digest.status_code != 200 or manifest.status_code != 200:

            wrongs = []
            if digest.status_code != 200:
                wrongs.append("no digest")
            if manifest.status_code != 200:
                wrongs.append("no manifest")
            if image_report[path]['_phase']['ImagePullBackOff']:
                wrongs.append("ImagePullBackOff")

            namespaces = [ ";".join(ns.split(";")[1:3])
                           for ns in image_report[path]
                             if not ns.startswith("_") and
                               (image_report[path][ns]['Running'] or
                                image_report[path][ns]['Pending'] or
                                image_report[path][ns]['ImagePullBackOff']) ]
            
            namespaces = list(set(namespaces))
            namespaces.sort()

            errors.append({ 'tag': repo_tag, 'wrongs': wrongs, 'namespaces': namespaces })

            print("  Examined %d/%d images, %d errors" % (i, len(image_report), len(errors)),
                  end="\r", flush=True)

        return errors

def main():
    errors = []

    global spinner
    spinner = Spinner()

    with open("images.json", "r") as f:
        image_report = json.load(f)

    mkdir(DIRNAME)
    chdir(DIRNAME)

    spinner.next()

    errors = examine_by_report(image_report)

    print("")
    
    if len(errors) == 0:
        print("Nothing wrong here!")

    with open("registry-check.json", "w") as f:
        f.write(json.dumps(errors, indent=2, sort_keys=True))
    print("Wrote report to %s/%s" % (DIRNAME, "registry-check.json"))

    with open("registry-check.csv", "w") as f:
        w = csv.DictWriter(f, errors[0].keys())
        w.writeheader()
        for e in errors:
            w.writerow(e)
    print("Wrote report to %s/%s" % (DIRNAME, "registry-check.csv"))

    # print("Image %s is used or wanted in %s" % (repo_tag, namespaces))

if __name__ == "__main__":
    main()
