#!/usr/bin/env python3

import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer

class Router:
    def __init__(self):
        self.routes = {}
    
    def setup(self, path, handler):
        self.routes[path] = handler

    def route(self, path, request):
        (httppath) = path.split("?")

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

    def do_GET(self):
        body = router.route(self.path, self)

        response_code = 200

        if body is None:
            body = "Not found"
            response_code = 404

        body = body + "\n\r"
        body = bytes(body, "utf-8")
        self.do_HEAD(body, response=response_code)

        self.wfile.write(body)

    def _HEAD(self, body, response=200):
        self.send_response(response)
        self.send_header("Content-type", "text/plain;chatset=utf-8")
        self.send_header("Content-length", len(body))
        self.end_headers()

    def do_HEAD(self):
        body = router.route(self.path, self)

        response_code = 200

        if body is None:
            body = "Not found"
            response_code = 404

        self._HEAD(body, response=response_code)


def health_check(request, path, query):
    return "OK"


def main():
    parser = argparse.ArgumentParser(description='Docker registry health checker in a pod')
    parser.add_argument('-p', '--port', type=int, default=8000, help='Port to listen on')
    args = parser.parse_args()

    global router
    router.setup("/health", health_check)

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
