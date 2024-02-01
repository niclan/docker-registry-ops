#!/usr/bin/env python3

import os
import json
import requests
import argparse
from pathlib import Path
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

class Router:
    def __init__(self):
        self.routes = {}
    
    def setup(self, path, handler):
        self.routes[path] = handler

    def route(self, path, request):
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

router = Router()


class RegistryHealthHTTPD(BaseHTTPRequestHandler):
    def send_response(self, code, message=None):
        """Superclass override: Send a response without a Server: header."""
        self.log_request(code)
        self.send_response_only(code, message)
        self.send_header('Date', self.date_time_string())

    def _HEAD(self, body, response=200):
        self.send_response(response)
        self.send_header("Content-type", "text/plain;chatset=utf-8")
        self.send_header("Content-length", len(body))
        self.end_headers()

    def do_GET(self):
        body = router.route(self.path, self)

        response_code = 200

        if body is None:
            body = "Not found"
            response_code = 404

        if "ERROR" in body:
            response_code = 503 # Service unavailable

        body = body + "\n\r"
        body = bytes(body, "utf-8")
        self._HEAD(body, response=response_code)

        self.wfile.write(body)


    def do_HEAD(self):
        body = router.route(self.path, self)

        response_code = 200 # OK

        if body is None:
            body = "Not found"
            response_code = 404 # Not found

        if "ERROR" in body:
            response_code = 503 # Service unavailable

        self._HEAD(body, response=response_code)


def health_check(request, path, query):
    """Health check endpoint"""
    uptime = get_uptime()

    if uptime is None:
        return "ERROR: Can't get pod uptime"

    try:
        imageReport = Path("/app/report/images.json").stat()
    except FileNotFoundError:
        imageReport = None

    try:
        checkTime = Path("/app/report/registry-check.json").stat()
    except FileNotFoundError:
        checkTime = None

    if (imageReport is None) or (checkTime is None) and (uptime < 300):
        # NOTE: the error message string is checked in
        # check_registry()
        return "ERROR: Some report file is missing"

    print("Uptime: %d, imageReport: %s, checkTime: %s" % \
          (uptime, imageReport.mtime, checkTime.mtime))
    return "OK"


def ok():
    """OK endpoint"""
    return "OK - I'm here!"


def check_registry():
    """Check registry endpoint"""

    health = health_check()

    if "ERROR" in health and "report file" in health:
        return "OK: No registry check available yet"

    try:
        check = Path("/app/report/registry-check.json").read_text()
    except FileNotFoundError:
        return "ERROR: Registry check is unavailable and pod is old enough!"

    check = json.loads(check)


def get_uptime():
    """Get pod uptime from kubernetes"""

    namespace = Path("/var/run/secrets/kubernetes.io/serviceaccount/namespace").read_text()
    token = Path("/var/run/secrets/kubernetes.io/serviceaccount/token").read_text()
    pod_name = os.getenv('HOSTNAME')
    kube_api = os.getenv('KUBERNETES_SERVICE_HOST')
    kube_api_port = os.getenv('KUBERNETES_SERVICE_PORT')
    auth = "Bearer %s" % token

    r = requests.get('https://%s/api/v1/namespaces/%s/pods/%s' % \
                     (kube_api, namespace, pod_name),
                     headers={'Authorization': auth},
                     verify='/var/run/secrets/kubernetes.io/serviceaccount/ca.crt')

    if r.status_code == 200:
        startTime = r.json()['status']['startTime']
        print("Pod startTime: %s" % startTime)
        startTime = datetime.strptime(startTime, '%Y-%m-%dT%H:%M:%SZ')
        seconds = (datetime.now() - startTime).total_seconds()
        print("Pod uptime: %d seconds" % seconds)
        return seconds

    print("Uptime query failed: %d" % r.status_code)
    return None


def main():
    parser = argparse.ArgumentParser(description='Docker registry health checker in a pod')
    parser.add_argument('-p', '--port', type=int, default=8000, help='Port to listen on')
    args = parser.parse_args()

    global router
    router.setup("/", ok)
    router.setup("/health", health_check)
    router.setup("/nagios_check_registry", check_registry)

    web_server = HTTPServer(('', args.port), RegistryHealthHTTPD)
    print("Server started on http://%s:%s" % (web_server.server_name, web_server.server_port))

    try:
        web_server.serve_forever()
    except KeyboardInterrupt:
        pass
        
    web_server.server_close()
    print("Server stopped")


if __name__ == "__main__":
    main()
