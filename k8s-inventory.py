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

no_phase = { 'Running': False, 'Pending': False, 'Succeeded': False, \
             'Failed':  False, 'Unknown': False, 'ImagePullBackOff': False }

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
    count = 0

    # Each container can be the origin of several different pods.  A
    # long running pod, a cronJob pod etc.  Therefore the outer key is
    # the container since we're all about the container images really.

    for i in k8s.list_pod_for_all_namespaces(watch=False).items:

        if i.status.container_statuses is None: continue

        # This is the namespace-point of suffcient specificity to save
        # if the registry tag is running somewhere and where that is.
        pod_name = f'k8s;{context};{i.metadata.namespace};{i.metadata.name}'

        pod_images = [c.image for c in i.spec.containers]

        # A image can be referenced as all of these things in various places:
        # - docker.vgnett.no/docker-registry-checker:50575d7@sha256:dadd36f816c87663fee16ff8f4e265e3feda064f7b2faa6426cb0b32c5ae0d0b
        # - docker.vgnett.no/docker-registry-checker@sha256:dadd36f816c87663fee16ff8f4e265e3feda064f7b2faa6426cb0b32c5ae0d0b
        # - docker.vgnett.no/docker-registry-checker:50575d7
        # - sha256:dadd36f816c87663fee16ff8f4e265e3feda064f7b2faa6426cb0b32c5ae0d0b
        #
        # The digest is fairly unique and we need to be able to find
        # registry:tag from the sha256-digit.
        image_by_digest = {}

        for im in pod_images:
            if "@" in im:
                ima, digest = im.split('@')
                image_by_digest[digest] = ima

        # Figure out when this pod was last wanted
        if i.status.phase in ['Pending', 'Running'] or ipbo:
            pod_age = 0 # now
        else:
            pod_age = (datetime.now(timezone.utc) - i.status.start_time).total_seconds()
            pod_age = pod_age / 60 / 60 / 24

        for c in i.status.container_statuses:
            # Figuring out what the registry/repository:tag format
            # without the digest is is a bit of a circus act. So here
            # are some heurstics to find the right one.
            digest = None

            if "/" in c.image:
                # If there is a registry name in the image name, use that
                image_name = c.image
            else:
                # This tends to be in registry/repository@digest
                # format which we don't like very much because the tag
                # format is most common in input to kubernetes and is
                # needed for pushing.  The digest format can be used
                # for pull but not push.
                image_name = c.image_id

            if image_name is None or image_name == "":
                # This happened once on a fluke, just ignore it if it happens
                print("No image_name for %s" % pod_name)
                next

            # Turns out there is a digest as well
            if "@" in image_name and len(image_by_digest) > 0:
                digest = image_name.split("@")[1]
                image_name = image_by_digest.get(digest, image_name)

            if "@" in image_name and len(pod_images) == 1:
                image_name = pod_images[0]

            ipbo = c.state.waiting is not None and \
                c.state.waiting.reason == 'ImagePullBackOff'

            c_age = pod_age

            if c.state.running is not None:
                c_age = 0 # now
            elif pod_age > 0 and c.state.terminated is not None:
                # Get the launch time of the container if it's
                # terminated, and then ignore it if it's older than
                # max_age
                c_age = datetime.now(timezone.utc) - c.state.terminated.started_at
                c_age = c_age.total_seconds() / 60 / 60 / 24
                if c_age > max_age:
                    # print("Skipping %s, too old at %d days" % (image_name, c_age) )
                    too_old += 1
                    continue

                # print("Container %s in pod %s is not running and is %d days old" % (c.name, i.metadata.name, c_age))

            count += 1
            if image_name not in images:
                images[image_name] = { '_phase': no_phase.copy() }

            ipbo = c.state.waiting is not None and \
                c.state.waiting.reason == 'ImagePullBackOff'

            images[image_name]['_phase']['ImagePullBackOff'] = ipbo

            # If we haven't seen this container/pod combination
            # before, make a new emtpy phase summary for it.
            if pod_name not in images[image_name]:
                images[image_name][pod_name] = no_phase.copy()

            # The outer nesting is the image - because we're concerned
            # with the images
            images[image_name][pod_name][i.status.phase] = True
            images[image_name][pod_name]['ImagePullBackOff'] = ipbo
            images[image_name][pod_name]['_last_wanted'] = c_age
            if digest is not None: images[image_name]['_digest'] = digest

            images[image_name]['_phase'][i.status.phase] = True

            if '_last_wanted' not in images[image_name] or \
               images[image_name]['_last_wanted'] > c_age:
                images[image_name]['_last_wanted'] = c_age

            if i.spec.node_name is not None:
                images[image_name][pod_name]['_node'] = i.spec.node_name

    print("* Found %s pods" % count)


def load_cronjobs_from_kubernetes(k8s, context=None):
    """Load image list from the cronjob specs in all the namespaces in
    the given cluster.
    """

    count = 0

    try:
        cronjobs = k8s.list_cron_job_for_all_namespaces()
    except ApiException as e:
        if e.status == 404:
            print("* No cronjobs found")
            return
        if e.status == 403:
            sys.exit("\nNo access to cronjobs. Terminating.")
        sys.exit("API ERROR: %s" % e)

    for i in cronjobs.items:

        for c in i.spec.job_template.spec.template.spec.containers:
            count += 1
            image_name = c.image
            if image_name is None or image_name == "":
                sys.exit("FATAL: No image for cronjob %s" % i.metadata.name)

            if image_name not in images:
                images[image_name] = { '_cronjob': True,
                                       '_last_wanted': 0,
                                       '_phase': no_phase.copy() }
            else:
                images[image_name]['_cronjob'] = True
                images[image_name]['_last_wanted'] = 0
                
    print("* Found %s cronjobs" % count)


def main():
    parser = argparse.ArgumentParser(description='Collect docker image inventory from kubernetes')
    parser.add_argument('-a', '--age', action='store', type=int, default=31, \
                        help='Only inlucde images younger than this many days, default is 31')
    parser.add_argument('-c', '--context', action='append', help='Check this context (can be repeated)')
    args = parser.parse_args()

    global max_age, too_old
    max_age = args.age
    too_old = 0

    print("Collecting images from kubernetes %s" % args.context)

    contexts = []

    if args.context:
        for c in args.context:
            contexts.append({ 'name': c })

    else:

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
        sys.exit("Cannot find any contexts? Exiting.")

    if contexts[0]['name'] == 'in-cluster':
        k8s = client.CoreV1Api()
        k8s_batch = client.BatchV1Api()

        print("Running in cluster, only checking it")
        load_from_kubernetes(k8s, context='in-cluster')
        load_cronjobs_from_kubernetes(k8s_batch)
        print("= Images until now: %d, and %d are too old" % (len(images), too_old))

    else:
        contexts = [context['name'] for context in contexts]

        print("Finding images in available contexts")
        for context in contexts:
            print("Loading from %s" % context)
            config.load_kube_config(context=context)
            k8s = client.CoreV1Api()
            k8s_batch = client.BatchV1beta1Api()

            try:
                load_from_kubernetes(k8s, context=context)
            except ApiException as e:
                print()
                print("FATAL ERROR loading from %s" % context)
                print()
                print('API ERROR MESSAGE: """%s"""' % e)
                sys.exit(1)

            load_cronjobs_from_kubernetes(k8s_batch, context=context)
            print("= Images until now: %d, and %d are too old" % (len(images), too_old))

    savedir = os.environ.get('REPORTDIR', '.')

    print("Saving images to %s/images.json" % savedir)

    with open(f'{savedir}/images.json', "w") as f:
        f.write(json.dumps(images, indent=2, sort_keys=True))

images = {}
        
if __name__ == '__main__':
    main()
