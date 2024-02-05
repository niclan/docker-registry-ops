#!/usr/bin/env python
#
# Script to collect images inventory from our kubernetes clusters.
# The script will use all the the configured contexts to collect lists
# of docker images in use and save the list to images.json in the CWD.
#
# Copyright (C) 2024, Nicolai Langfeldt, Schibsted Products and Technology
#
# Prerequisites:
# - apt install python3-kubernetes (or pip install kubernetes)
# - Have good credentials for all your clusters.
# - Log in to AWS if you have cluster(s) there
#
# Usage:
# - k8s-inventory.py
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
import argparse
from kubernetes import client, config
from datetime import datetime, timezone
from kubernetes.client import configuration
from kubernetes.client.rest import ApiException
from kubernetes.config.config_exception import ConfigException

def load_from_kubernetes(k8s, context=None):
    """Load image list from all the pods in all the namespaces in the
    given cluster.  The images and some status information are saved
    in the global images dictionary.

    Pods that are not running or pending and more than 31 days old
    will be ignored.
    """

    global too_old

    # Kubernetes pod phases:
    # https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#pod-phase
    #
    # ImagePullBackOff is not a kubernetes phase, but for the registry-checker it's
    # interesting
    no_phase = { 'Running': False, 'Pending': False, 'Succeeded': False, \
                 'Failed':  False, 'Unknown': False, 'ImagePullBackOff': False }
    count = 0

    # Each container can be the origin of several different pods.  A
    # long running pod, a cronJob pod etc.  Therefore the outer key is
    # the container since we're all about the container images really.
    
    for i in k8s.list_pod_for_all_namespaces(watch=False).items:
        
        if i.status.container_statuses is None: continue

        # This is the namespace-point of suffcient specificity to save
        # if the registry tag is running somewhere and where that is.
        pod_name = f'k8s;{context};{i.metadata.namespace};{i.metadata.name}'

        if i.metadata.name == 'elton-services-syncing-transaction-job-27963550-5gx5r':
            print("Found it")

        # Figure out when this pod was last wanted
        if i.status.phase in ['Pending', 'Running'] or ipbo:
            pod_age = 0 # now
        else:
            pod_age = (datetime.now(timezone.utc) - i.status.start_time).total_seconds()
            pod_age = pod_age / 60 / 60 / 24

        for c in i.status.container_statuses:
            ipbo = c.state.waiting is not None and \
                c.state.waiting.reason == 'ImagePullBackOff'

            c_age = pod_age

            if c.state.running is not None:
                c_age = 0 # now
            elif pod_age > 0 and c.state.terminated is not None:
                # Get the launch time of the container if it's terminated,
                # and then ignore it if it's older than max_age
                c_age = datetime.now(timezone.utc) - c.state.terminated.started_at
                c_age = c_age.total_seconds() / 60 / 60 / 24
                if c_age > max_age:
                    # print("Skipping %s, too old at %d days" % (c.image, c_age) )
                    too_old += 1
                    continue

                # print("Container %s in pod %s is not running and is %d days old" % (c.name, i.metadata.name, c_age))

            count += 1
            if c.image not in images:
                images[c.image] = { '_phase': no_phase.copy() }

            ipbo = c.state.waiting is not None and \
                c.state.waiting.reason == 'ImagePullBackOff'

            images[c.image]['_phase']['ImagePullBackOff'] = ipbo

            # If we haven't seen this container/pod combination
            # before, make a new emtpy phase summary for it.
            if pod_name not in images[c.image]:
                images[c.image][pod_name] = no_phase.copy()

                    # The outer nesting is the image - because we're concerned with the images
            images[c.image][pod_name][i.status.phase] = True
            images[c.image][pod_name]['ImagePullBackOff'] = ipbo
            images[c.image][pod_name]['_last_wanted'] = c_age

            images[c.image]['_phase'][i.status.phase] = True

            if '_last_wanted' not in images[c.image] or \
               images[c.image]['_last_wanted'] > c_age:
                images[c.image]['_last_wanted'] = c_age

            if i.spec.node_name is not None:
                images[c.image][pod_name]['_node'] = i.spec.node_name

    print("* Found %s pods" % count)
    print("* Images until now: %d, and %d are too old" % (len(images), too_old))


def main():
    parser = argparse.ArgumentParser(description='Collect docker image inventory from kubernetes')
    parser.add_argument('-a', '--age', action='store', type=int, default=31, \
                        help='Only inlucde images younger than this many days, default is 31')
    args = parser.parse_args()

    global max_age, too_old
    max_age = args.age
    too_old = 0

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
