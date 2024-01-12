#!/usr/bin/env python3
#
# (C) 2024, Nicolai Langfeldt, Schibsted Products and Technology
#
# Script to garbage collect our (VGs) docker-registry by comparing the
# running kubernetes with the things in the registry.
#
# Prerequisites:
#

import argparse
import Registry
import Spinner

def main():
    parser = argparse.ArgumentParser(description='Count number of tags in registry')
    parser.add_argument('server', help='Registry server')
    args = parser.parse_args()

    spinner = Spinner.Spinner()

    spinner.next()

    all_tags = []
    num_repos = 0

    reg = Registry.Registry(args.server)

    for repo_name in reg.get_repositories():
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
