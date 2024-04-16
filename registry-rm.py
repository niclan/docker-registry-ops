#!/usr/bin/env python3
#
# (C) 2024, Nicolai Langfeldt, Schibsted Products and Technology
#
# List tags in a docker registry.
#

import sys
import socket
import requests
import argparse
import Registry

def main():
    parser = argparse.ArgumentParser(description='Delete registry tags')
    parser.add_argument('server', help='Registry server')
    parser.add_argument('image', action='store', nargs='+', help='Image(s) to delete')
    args = parser.parse_args()

    ntags = 0
    num_repos = 0

    try:
        reg = Registry.Registry(args.server)

    except requests.exceptions.ConnectionError:
        print("Failed to connect to %s" % args.server)
        sys.exit(1)

    reg.do_delete = True
    reg.verbose = True

    for image_tag in args.image:

        if "@" in image_tag:
            (repository, digest) = image_tag.split("@")

        (repository, tag) = image_tag.split(":")
        digest, _, _ = reg.get_manifest(repository, tag)

        print(f"Deleting {repository}:{digest}")

        reg.delete_manifest(repository, digest)
        
if __name__ == "__main__":
    main()
