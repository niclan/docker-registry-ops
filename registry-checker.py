#!/usr/bin/env python3
#
# (C) 2024, Nicolai Langfeldt, Schibsted Products and Technology
#
# registry-checker: Script to check our docker registry for unhealthy
# tags and empty repositories.  Optionally refer to running images
# from images.json to see if the tag or repository is in use.
#
# Usage:
# - Run ./k8s-inventory.py to build the images.json file first
# - ./registry-checker.py docker.example.com
#
#   See -h for more options

import os
import re
import sys
import csv
import json
import curses
import requests
import argparse
from Spinner import Spinner
from os import mkdir, chdir
from datetime import datetime
from Registry import Registry

dirname = "check-report-%s" % datetime.now().strftime("%Y-%m-%d-%H:%M:%S")

clear_eol = "\n"

try:
    if sys.stdout.isatty():
        curses.setupterm()
        clear_eol = curses.tigetstr('el').decode('utf-8')

except:
    pass

used_repo = {}
used_repo_tag = {}


def get_manifest_health(repo, tag):
    """Get the manifest for a tag. This requires two calls to the
    registry.  The first one gets the digest, the second one gets the
    manifest itself.  The digest is needed to delete the manifest.

    This procedure variation is to check the health of the tag.  We
    have many tags w/o manifests and/or registries without (healthy)
    tags.

    """

    result = { 'digest': {}, 'manifest': {} }

    d = requests.get("https://%s/v2/%s/manifests/%s" % (registry, repo, tag),
                     headers={"Accept": "application/vnd.docker.distribution.manifest.v2+json"})

    m = requests.get("https://%s/v2/%s/manifests/%s" % (registry, repo, tag))

    return d, m


def find_image_by_repo(repo_name):
    """Find all the images in the report that are from a given repo"""

    search_string = f'{repo_name}:'
    return [ path for path in image_report if path.startswith(search_string) ]


def examine_by_report(image_report):
    regPrefix = f'{registry}/'

    errors = []

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

        (repo, tag) = repo_tag.split(":",1)

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

            # Doing this as a list comprehension hurts my head too much
            phases = []
            for ns in image_report[path]:
                if ns.startswith("_"):
                    continue
                for phase in image_report[path][ns]:
                    if not phase.startswith("_") and \
                      image_report[path][ns][phase]:
                        phases.append(phase)

            # Unique and sorted
            phases = list(set(phases))
            phases.sort()
            namespaces = list(set(namespaces))
            namespaces.sort()

            # NOTE! All errors that goes to the same file must have the
            # same fields, for the sake of the CSV writer.
            errors.append({ 'tag': path, 'wrongs': wrongs, 'namespaces': namespaces, 'phase': phases })

            print("  Examined %d/%d images, %d errors" % (i, len(image_report), len(errors)),
                  end="\r", flush=True)

    return errors


def examine_by_registry(image_report, only=None):
    """Loop over all the images in the registry and see if they are
    healthy or not. Also see if they are used or not."""

    errors = []

    reg = Registry(registry)

    if only is not None:
        repos = only
    else:
        repos = reg.get_repositories()

    if repos is None or len(repos) == 0:
        print("No repositories found")
        return []

    for repo in repos:
        print("  REPO: %s%s\r" % (repo, clear_eol), end="")

        num_tags = 0
        num_errors = 0
        repo_in_use = False

        tags = reg.get_tags(repo)

        # NOTE! All errors that goes to the same file must have the
        # same fields, for the sake of the CSV writer.

        if tags is None:
            if len(find_image_by_repo(repo)) > 0:
                errors.append({ 'kind': 'repository', 'name':
                                repo, 'wrongs': 'no tags - but in use',
                                'inuse': True })
            else:
                errors.append({ 'kind': 'repository', 'name': repo,
                                'wrongs': 'no tags', 'inuse': False })
            continue

        for tag in tags:
            spinner.next()
            num_tags += 1
            tag_errors = []

            (digest, manifest) = get_manifest_health(repo, tag)

            repo_tag = f'{repo}:{tag}'
            in_use = repo_tag in image_report
            if in_use: repo_in_use = True

            if digest.status_code != 200 or manifest.status_code != 200:
                num_errors += 1
                wrongs = []
                if digest.status_code != 200:
                    wrongs.append("no digest")
                if manifest.status_code != 200:
                    wrongs.append("no manifest")

                tag_errors.append({ 'kind': 'tag', 'name': repo_tag,
                                    'wrongs': wrongs, 'inuse': in_use })

        repo_wrongs = 'See tags above'

        if num_tags == num_errors:
            if not repo_in_use:
                repo_in_use = len(find_image_by_repo(repo)) > 0

            repo_wrongs = 'all tags unhealthy'
        else:
            errors.extend(tag_errors)

        errors.append({ 'kind': 'repository', 'name': repo,
                        'wrongs': repo_wrongs, 'inuse': repo_in_use })

    return errors


def main():
    parser = argparse.ArgumentParser(description='Check health of registry. By default only tags referenced in images.json')
    parser.add_argument('-R', '--by-registry', action='store_true',
                        help='Loop over the content of the registry instead of images.json. This finds errors like missing tags and manifests, e.g. registry corruption.',
                        default=False)
    parser.add_argument('-r', '--repository', action="append",
                        help='Work on this repository instead  of all (can be repeated)')
    parser.add_argument('-o', '--old-age', action="store", type=int, default=31,
                        help='Only check images this many days or younger, default is 31. 0 means all images')
    parser.add_argument('-s', '--spinner', action="store", type=int, default=None,
                        help='Select what kind of progress spinner you prefer, default random')
    parser.add_argument('server', help='Registry server to check')
    args = parser.parse_args()

    global spinner
    global registry
    global image_report
    global dirname

    spinner = Spinner(kind=args.spinner)
    registry = args.server

    savedir = os.environ.get('REPORTDIR', '.')
    print("Loading images list from %s/images.json" % savedir)
    with open(f'{savedir}/images.json', "r") as f:
        image_report = json.load(f)

    spinner.next()

    if args.by_registry:
        only=None
        if args.repository: only=args.repository
        errors = examine_by_registry(image_report, only)
    else:
        errors = examine_by_report(image_report)

    print()
    
    if len(errors) == 0:
        print("Nothing wrong here!")

    else:

        if savedir != '.':
            print("Saving reports to %s" % savedir)
            dirname = savedir
        else:
            mkdir(dirname)
            
        chdir(dirname)
        print("Found %d errors, writing reports" % len(errors))

        with open("registry-check.json", "w") as f:
            f.write(json.dumps(errors, indent=2, sort_keys=True))
        print("Wrote report to %s/%s" % (dirname, "registry-check.json"))

        with open("registry-check.csv", "w") as f:
            w = csv.DictWriter(f, errors[0].keys())
            w.writeheader()
            for e in errors:
                w.writerow(e)
        print("Wrote report to %s/%s" % (dirname, "registry-check.csv"))


if __name__ == "__main__":
    main()
