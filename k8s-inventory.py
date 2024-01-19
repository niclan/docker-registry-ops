#!/usr/bin/env python
#
# Script to collect images inventory from our kubernetes clusters.
# The script will use all the the configured contexts to collect lists
# of docker images in use and save the list to images.json in the CWD.
#
# Copyright (C) 2024, Nicolai Langfeldt, Schibsted Products and Technology
#
# Prerequisites:
# - apt install python3-kubernetes
#
# Usage:
# - Edit the "us" regular expression to match your registry, this
#   will be used to only save images from your registry to the images.json
#   file.
# - Have good credentials for all your clusters.
# - Log in to AWS if you have cluster(s) there
#
# Bugs:
# - Could use a common configuration file with the registryevictor.py
# - If you have clusters in more than one AWS account this script will
#   not work.  You have to devise a way to change AWS_PROFILE(?) before
#   interogating the clusters in AWS accounts.

import os
import re
import sys
import json
import pprint
from kubernetes import client, config
from kubernetes.client import configuration
from kubernetes.client.rest import ApiException
from kubernetes.config.config_exception import ConfigException

def load_from_kubernetes(k8s, context=None):
    # Kubernetes pod phases:
    # https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#pod-phase
    #
    # ImagePullBackOff is not a kubernetes phase, but for the registry-checker it's
    # interestng
    no_phase = { 'Running': False, 'Pending': False, 'Succeeded': False, \
                 'Failed':  False, 'Unknown': False, 'ImagePullBackOff': False }
    count = 0
    
    for i in k8s.list_pod_for_all_namespaces(watch=False).items:
        
        if i.status.container_statuses is None: continue

        for c in i.status.container_statuses:
            count += 1
            if c.image not in images:
                images[c.image] = { '_phase': no_phase.copy() }

            ipbo = c.state.waiting is not None and \
                c.state.waiting.reason == 'ImagePullBackOff'

            images[c.image]['_phase']['ImagePullBackOff'] = ipbo

            # We don't need to know the state of all the
            # individual pods, but we do need to know if the image
            # is used in a running pod. This is the
            # namespace-point of suffcient specificity to save if
            # the registry tag is running somewhere and where that
            # is.
            pod_name = f'k8s;{context};{i.metadata.namespace};{i.metadata.name}'

            if pod_name not in images[c.image]:
                images[c.image][pod_name] = no_phase.copy()

            images[c.image][pod_name][i.status.phase] = True
            images[c.image][pod_name]['ImagePullBackOff'] = ipbo
            images[c.image]['_phase'][i.status.phase] = True
                
    print("* Found %s pods" % count)
    print("* Images until now: %d" % len(images))


def main():
    try:
        contexts, active_context = config.list_kube_config_contexts()
        print("Loaded contexts from kube-config file")
    except ConfigException as e:
        try:
            config.load_incluster_config()
            contexts = [ { 'name': 'in-cluster' } ]
        except ConfigException as e:
            sys.exit("Cannot load kubernetes configuration: %s" % e)

    if not contexts:
        print("Cannot find any context in kube-config file.")
        return

    if contexts[0]['name'] == 'in-cluster':
        k8s = client.CoreV1Api()

        print("Running in cluster, only checking it")
        load_from_kubernetes(k8s, context='in-cluster')

    else:
        contexts = [context['name'] for context in contexts]

        print("Finding images in available contexts")
        for context in contexts:
            try:
                print("Loading from %s" % context)

                k8s = client.CoreV1Api(api_client=config.new_client_from_config(context=context))

                load_from_kubernetes(k8s, context=context)
            except ApiException as e:
                print()
                print("FATAL ERROR loading from %s" % context)
                print()
                print('API ERROR MESSAGE: """%s"""' % e)
                sys.exit(1)

    savedir = os.environ.get('REPORTDIR', '.')

    print("Saving images to %s/images.json" % savedir)

    with open(f'{savedir}/images.json', "w") as f:
        f.write(json.dumps(images, indent=2, sort_keys=True))

images = {}
        
if __name__ == '__main__':
    main()
