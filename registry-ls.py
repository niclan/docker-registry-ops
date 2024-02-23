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
    parser.add_argument('-r', '--repository', action="append",
                        help='Work on this repository instead  of all (can be repeated)')

    parser.add_argument('server', help='Registry server')
    args = parser.parse_args()

    spinner = Spinner.Spinner()

    spinner.next()

    ntags = 0
    num_repos = 0

    reg = Registry.Registry(args.server)

    try:
        # Note, we want to make this initial call to the registry even
        # if args.repository is set: to ensure that it resolves and
        # works, and catch any problems here in this try/except
        # stanza.
        repositories = reg.get_repositories()
    except requests.exceptions.ConnectionError as e:
        print("Failed to connect to %s" % args.server)
        sys.exit(1)

    if args.repository:
        repositories = args.repository

    for repo_name in repositories:
        num_repos += 1
        spinner.next()
        tags = reg.get_tags(repo_name)
        if tags is None or len(tags) == 0:
            continue

        ntags += len(tags)
        
        print("repo_name:", f"\n{repo_name}:".join(tags))

    print("Number of repositories: %d, tags: %d" % (num_repos, ntags))

if __name__ == "__main__":
    main()
