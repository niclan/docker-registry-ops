#!/usr/bin/env python
#
# Script to collect images inventory from our kubernetes clusters
#
# Prerequisites:
# - apt install python3-kubernetes
#
# Usage:
# - Have good credentials for all your clusters
# - Log in to aws if you have cluster(s) there

import re
import sys
import json
from kubernetes import client, config
from kubernetes.client import configuration

def load_from_kubernetes(context):
    # Change cluster context

    print("Loading from %s" % context)

    k8s = client.CoreV1Api(
        api_client=config.new_client_from_config(context=context))

    count = 0 

    for i in k8s.list_pod_for_all_namespaces(watch=False).items:
        if i.status.container_statuses is None:
            continue
        
        for c in i.status.container_statuses:
            # print(c)
            if us.match(c.image):
                count += 1
                images[c.image] = { "name": c.name, "image": c.image_id }

    print("Found %s pods in %s" % (count, context))
    print("Images until now: %d" % len(images))

def main():
    contexts, active_context = config.list_kube_config_contexts()
    if not contexts:
        print("Cannot find any context in kube-config file.")
        return

    contexts = [context['name'] for context in contexts]

    print("Finding images in available contexts")
    for context in contexts:
        load_from_kubernetes(context)

    with open("images.json", "w") as f:
        f.write(json.dumps(images, indent=2, sort_keys=True))

images = {}
us = re.compile(r"^docker.vgnett.no/")
        
if __name__ == '__main__':
    main()
