#!/usr/bin/env python3
#
# (C) 2024, Nicolai Langfeldt, Schibsted Products and Technology
#
# List tags in a docker registry.
#

import sys
import socket
import Spinner
import requests
import argparse
import Registry
from keeprules import *


def main():
    parser = argparse.ArgumentParser(description='List tags in registry')
    parser.add_argument('-d', '--digest', action='store_true', help='Show digest of tags')
    parser.add_argument('-r', '--repository', action="append",
                        help='Work on this repository instead  of all (can be repeated)')
    parser.add_argument('-R', '--repostory-pattern', action="append",
                        help='Work on repositories matching this pattern (can be repeated)')
    parser.add_argument('-k', '--list-keepers', action='store_true', help='List tags that should be kept according to keep-images.json')

    parser.add_argument('server', help='Registry server')
    args = parser.parse_args()

    if args.list_keepers:
        load_keep_list()

    spinner = Spinner.Spinner()

    spinner.next()

    ntags = 0
    num_repos = 0

    try:
        reg = Registry.Registry(args.server)

    except requests.exceptions.ConnectionError:
        sys.exit("Failed to connect to %s" % args.server)

    if args.repository:
        if args.repostory_pattern:
            sys.exit("Cannot use both --repository and --repository-pattern")

        repositories = args.repository
    else:
        print("Loading repositories from registry", file=sys.stderr)
        repositories = reg.get_repositories()

    if args.repostory_pattern:
        repositories = [r for r in repositories if any([rp in r for rp in args.repostory_pattern])]

    if args.list_keepers:
        repositories = [r for r in repositories if keep_repo_by_rule(r)]

    for repo_name in repositories:
        num_repos += 1
        spinner.next()
        tags = reg.get_tags(repo_name)
        if tags is None or len(tags) == 0:
            continue

        ntags += len(tags)

        for tag in tags:
            if args.digest or args.list_keepers:
                digest, _, mtype = reg.get_manifest(repo_name, tag)

            if args.list_keepers:
                if digest == '':
                    # The main use case for -k is collecting a list of
                    # tags that should be kept into a images.lst file
                    # so send error or informational messages
                    # somewhere else.
                    print(f"{repo_name}:{tag} (no digest, tag probably corrupted)", file=sys.stderr)
                if keep_by_rule(repo_name, tag):
                    print(f"{repo_name}:{tag}")

            elif args.digest:
                if digest == '':
                    print(f"{repo_name}:{tag} (no digest, tag probably corrupted)")
                else:
                    print(f"{repo_name}:{tag}@{digest} ({mtype})")
            else:
                print(f"{repo_name}:{tag}")

    print("Number of repositories: %d, tags: %d" % (num_repos, ntags), file=sys.stderr)

if __name__ == "__main__":
    main()
