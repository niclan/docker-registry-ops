#!/usr/bin/env python3

"""Simple web server to check the health of the docker registry vs the
running kubernets - in a pod."""

import os
import json
import requests
import argparse
from pathlib import Path
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

images = None


class Router:
    """Simple request router, using only the path part of the URL and
    just passing the query part to the handler."""

    def __init__(self):
        self.routes = {}
    
    def setup(self, path, handler):
        """Setup a route"""
        self.routes[path] = handler

    def route(self, path, request):
        """Route a request to the correct handler"""
        # 1 means split only once, making 2 elements
        (httppath) = path.split("?", 1)

        match len(httppath):
            case 1:
                path = httppath[0]
                query = ""
            case 2:
                path = httppath[0]
                query = httppath[1]
            case _:
                return None

        if path in self.routes:
            return self.routes[path](request, path, query)
        else:
            return None


class RegistryHealthHTTPD(BaseHTTPRequestHandler):
    """Simple HTTP server to serve a simple task, avoiding larger
    frameworks."""

    def send_response(self, code, message=None):
        """Superclass override: Send a response without a Server: header."""
        self.log_request(code)
        self.send_response_only(code, message)
        self.send_header('Date', self.date_time_string())


    def _HEAD(self, body, response=200):
        """Make apropriate headers for GET or HEAD requests"""
        self.send_response(response)
        self.send_header("Content-type", "text/plain;chatset=utf-8")
        self.send_header("Content-length", len(body))
        self.end_headers()


    def _GET(self):
        """Do the work common for HEAD and GET requests for getting
        and interpreting the response.

        Detect if there is a error or not by looking for the string
        "ERROR" in the response.  If we find it we return 503.  If we
        don't find the path or no content (Null) is returned by the
        handler we return 404. Otherwise we return 200.

        Some responses are for a nagios plugin.  The words "OK",
        "WARNING", "CRITICAL", "UNKNOWN" are used by the nagios
        plugwin to detect what to set the exit code to.  Do not use
        these words to signal anything to do with the HTTP protocol.

        """

        response_code = 200  # Assume it goes well!

        body = router.route(self.path, self)

        if body is None:
            body = "Not found"
            response_code = 404

        if "ERROR" in body:
            response_code = 503 # Service unavailable

        body = body + "\n\r"
        # This recodes the string to a byte array.  The things python
        # is particular about...
        body = bytes(body, "utf-8")

        return (body, response_code)


    def do_GET(self):
        (body, response_code) = self._GET()
        self._HEAD(body, response=response_code)
        if body is not None: self.wfile.write(body)


    def do_HEAD(self):
        (body, response_code) = self._GET()
        self._HEAD(body, response=response_code)


### Helper procedures ###

def load_images(text=None):
    """Load images from string"""

    global images

    if images is not None:
        return  # Already loaded

    if text is None: # Caller did not provide text
        text = Path(f"{report_dir}/images.json").read_text()

    images = json.loads(text)


def health_check(request, path, query):
    """Health check endpoint"""
    uptime = get_uptime()

    if uptime is None:
        return "ERROR: Can't get pod uptime"

    try:
        image_report = Path(f"{report_dir}/images.json").stat()
    except FileNotFoundError:
        image_report = None

    try:
        check_time = Path(f"{report_dir}/registry-check.json").stat()
    except FileNotFoundError:
        check_time = None

    # If the pod is young enough, we don't care about the report files
    if (image_report is None or check_time is None) and (uptime < 300):
        return "ERROR: Some report file is missing"

    # print("Uptime: %d, image_report: %s, check_time: %s" % \
    #       (uptime, image_report.st_mtime, check_time.st_mtime))
    return "OK"


def image_info(tag):
    """Get image info from the tag and images report"""

    global images

    if images is None:
        load_images()

    info = "%s is running on: " % tag
    run_nodes = []
    ran_nodes = []
    some_pod = ""

    tag_info = images[tag]

    for pod in tag_info.keys():
        if pod.startswith("_"):
            continue

        if tag_info[pod]["Running"]:
            some_pod = pod
            run_nodes.append(tag_info[pod]["_node"])

        if tag_info[pod]["Succeeded"] or tag_info[pod]["Failed"]:
            ran_nodes.append(tag_info[pod]["_node"])

    if len(run_nodes) > 0:
        return "is running on: %s" % ", ".join(run_nodes)

    if len(ran_nodes) > 0:
        return "has run on: %s" % ", ".join(ran_nodes)

    return None


def summarize(check):
    """Summarize the check"""
    image_pull_errors = 0
    prod_errors = 0
    stage_errors = 0
    all_errors = 0
    tags = []
    lesser_tags = []

    for error in check:
        if "prod" in "=".join(error["namespaces"]):
            prod_errors += 1

            if "ImagePullBackOff" in error["phase"]:
                image_pull_errors += 1
                prod_errors -= 1
                tag_info = image_info(error["tag"])
                if tag_info is None:
                    tags.append(f'ImagePullBackOff: {error["tag"]} (and not running anywhere)')
                else:
                    tags.append(f'ImagePullBackOff: {error["tag"]} (but {tag_info})')

            elif len(error["wrongs"]) > 0:
                tag_info = image_info(error["tag"])
                if tag_info is None:
                    lesser_tags.append(f'{error["wrongs"]}: {error["tag"]} (and not running anywhere)')
                else:
                    lesser_tags.append(f'{error["wrongs"]}: {error["tag"]} ({tag_info})')

    for error in check:
        # "stage" or "staging"
        if "stag" in "=".join(error["namespaces"]):
            stage_errors += 1

    for error in check:
        all_errors += 1

    all_errors -= (prod_errors + stage_errors)

    if image_pull_errors > 0:
        errormsg = [ f"CRITICAL: Missing images: {image_pull_errors} ImagePullBackOff errors in prod. Otherwise: {prod_errors} image problems in prod, {stage_errors} in staging, and {all_errors} in other namespaces" ]
        errormsg.extend(tags)
        errormsg.extend(lesser_tags)
        return "\n".join(errormsg)

    if prod_errors > 0:
        errormsg = [ f"WARNING: Missing images: 0 ImagePullBackOff errors in prod, {prod_errors} errors in prod, {stage_errors} in staging, and {all_errors} in other namespaces" ]
        errormsg.extend(lesser_tags)
        return "\n".join(errormsg)

    if stage_errors > 0:
        return f"WARNING: Missing images: {stage_errors} errors in stage and {all_errors} in other namespaces"

    if all_errors > 0:
        return f"OK: Missing images: {all_errors} errors in non-production, non-stage namespaces"

    return "OK: No missing images anywhere"


### HTTP endpoints ###

def ok(request, path, query):
    """OK endpoint"""
    return "OK - I'm here!"


def check_registry(request, path, query):
    """Check registry endpoint"""

    health = health_check(None, None, None)

    if "ERROR" in health and "report file" in health:
        return "OK: No registry check available yet"

    try:
        check = Path(f"{report_dir}/registry-check.json").read_text()
    except FileNotFoundError:
        return "ERROR: Registry check is unavailable and pod is old enough!"

    check = json.loads(check)

    return summarize(check)


def get_uptime():
    """Get pod uptime from kubernetes"""

    # Kubernetes API usage from a pod without the whole kubernetes module
    try:
        namespace = Path("/var/run/secrets/kubernetes.io/serviceaccount/namespace").read_text()
        token = Path("/var/run/secrets/kubernetes.io/serviceaccount/token").read_text()
    except FileNotFoundError:
        print("Hmm, we're not in kubernetes I think, faking uptime")
        return 600 # Fake that we have uptime

    pod_name = os.getenv('HOSTNAME')
    kube_api = os.getenv('KUBERNETES_SERVICE_HOST')
    kube_api_port = os.getenv('KUBERNETES_SERVICE_PORT')
    auth = "Bearer %s" % token

    r = requests.get('https://%s/api/v1/namespaces/%s/pods/%s' % \
                     (kube_api, namespace, pod_name),
                     headers={'Authorization': auth},
                     verify='/var/run/secrets/kubernetes.io/serviceaccount/ca.crt')

    if r.status_code == 200:
        start_time = r.json()['status']['startTime']
        start_time = datetime.strptime(start_time, '%Y-%m-%dT%H:%M:%SZ')
        seconds = (datetime.now() - start_time).total_seconds()
        return seconds

    print("Uptime query failed: %d" % r.status_code)
    return None


def main():
    parser = argparse.ArgumentParser(description='Docker registry health checker in a pod')
    parser.add_argument('-p', '--port', type=int, default=8000,
                        help='Port to listen on')
    args = parser.parse_args()

    global report_dir
    report_dir = os.getenv('REPORTDIR',
                           "check-report-%s" %
                           datetime.now().strftime("%Y-%m-%d-%H:%M:%S"))

    global router
    router = Router()
    router.setup("/", ok)
    router.setup("/health", health_check)
    router.setup("/nagios_check_registry", check_registry)

    web_server = HTTPServer(('', args.port), RegistryHealthHTTPD)
    print("Server started on http://%s:%s" %
          (web_server.server_name, web_server.server_port))

    try:
        web_server.serve_forever()
    except KeyboardInterrupt:
        pass
        
    web_server.server_close()
    print("Server stopped")


if __name__ == "__main__":
    main()
