#!/usr/bin/env python3
#
# (C) 2024, Nicolai Langfeldt, Schibsted Products and Technology
#
# Just count the tags in the registry.  This is useful to see if the
# registry is growing out of control.
#
# Prerequisites:
#

import sys
import socket
import Spinner
import requests
import argparse
import Registry

def main():
    parser = argparse.ArgumentParser(description='Count number of tags in registry')
    parser.add_argument('server', help='Registry server')
    args = parser.parse_args()

    spinner = Spinner.Spinner()

    spinner.next()

    all_tags = []
    num_repos = 0

    try:
        reg = Registry.Registry(args.server)
    except requests.exceptions.ConnectionError as e:
        print("Failed to connect to %s" % args.server)
        sys.exit(1)

    repositories = reg.get_repositories()

    for repo_name in repositories:
        num_repos += 1
        spinner.next()
        tags = reg.get_tags(repo_name)
        if tags is None or len(tags) == 0:
            continue
        
        all_tags.extend(tags)

        print("  Tags 'til now: %d  " % len(all_tags), end="\r", flush=True)

    print("Number of repositories: %d, tags: %d" % (num_repos, len(all_tags)))

if __name__ == "__main__":
    main()
