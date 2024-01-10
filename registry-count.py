#!/usr/bin/env python3
#
# Script to garbage collect our (VGs) docker-registry by comparing the
# running kubernetes with the things in the registry.
#
# Prerequisites:
#

from registryevictor import get_repositories, get_tags, spinner_next

REGISTRY="docker.vgnett.no"

def main():
    all_tags = []

    spinner_next()

    num_repos = 0

    for repo_name in get_repositories():
        num_repos += 1
        spinner_next()
        tags = get_tags(repo_name)
        if tags is None or len(tags) == 0:
            continue
        
        all_tags.extend(tags)

        print("  Tags 'til now: %d  " % len(all_tags), end="\r", flush=True)
    # Print number of tags
    print("Number of repositories: %d, tags: %d" % (num_repos, len(all_tags)))

if __name__ == "__main__":
    main()
