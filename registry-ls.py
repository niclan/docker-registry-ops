#!/usr/bin/env python3
#
# (C) 2024, Nicolai Langfeldt, Schibsted Products and Technology
#

import sys
import socket
import Spinner
import requests
import argparse
import Registry

def main():
    parser = argparse.ArgumentParser(description='Count number of tags in registry')
    parser.add_argument('-d', '--digest', action='store_true', help='Show digest of tags')
    parser.add_argument('-r', '--repository', action="append",
                        help='Work on this repository instead  of all (can be repeated)')

    parser.add_argument('server', help='Registry server')
    args = parser.parse_args()

    spinner = Spinner.Spinner()

    spinner.next()

    ntags = 0
    num_repos = 0

    try:
        reg = Registry.Registry(args.server)
    except requests.exceptions.ConnectionError:
        print("Failed to connect to %s" % args.server)
        sys.exit(1)

    if args.repository:
        repositories = args.repository
    else:
        repositories = reg.get_repositories()

    for repo_name in repositories:
        num_repos += 1
        spinner.next()
        tags = reg.get_tags(repo_name)
        if tags is None or len(tags) == 0:
            continue

        ntags += len(tags)

        for tag in tags:
            if args.digest:
                digest, manifest = reg.get_manifest(repo_name, tag)
                if digest == '':
                    print(f"{repo_name}:{tag} (no digest, tag probably corrupted)")
                else:
                    print(f"{repo_name}:{tag}@{digest}")
            else:
                print(f"{repo_name}:{tag}")

    print("Number of repositories: %d, tags: %d" % (num_repos, ntags))

if __name__ == "__main__":
    main()
