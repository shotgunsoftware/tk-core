# Copyright (c) 2023 Autodesk.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Unit tests for Unified Login Flow 2 authentication.
"""

import errno
import http.client
import http.server
import json
import logging
import os
import random
import sys
import threading
import urllib.parse

from tank.authentication import app_session_launcher
from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import ShotgunTestBase, mock


class AppSessionLauncherTests(ShotgunTestBase):
    def test_process_parameters(self):
        pass
    def test_build_proxy_addr(self):
        pass
    @mock.patch.dict(os.environ)
    def test_get_product_name(self):
        pass
class AppSessionLauncherAPITests(ShotgunTestBase):
    def setUp(self):
        self.httpd = MyTCPServer()
        self.httpd.start()

        self.api_url = "http://{fqdn}:{port}".format(
            fqdn=self.httpd.server_address[0],
            port=self.httpd.server_address[1],
        )

    def tearDown(self):
        if self.httpd:
            self.httpd.stop()

    @mock.patch("time.sleep")
    def test_valid(self, *mocks):
        pass
    @mock.patch("time.sleep")
    def test_not_reachable(self, *mocks):
        pass
    @mock.patch("time.sleep")
    def test_fault_tolerance(self, *mocks):
        pass
    @mock.patch("time.sleep")
    def test_post_request(self, *mocks):
        pass
    def test_browser_error(self):
        pass
    @mock.patch.dict(os.environ)
    def test_param_product(self):
        pass
    @mock.patch("time.sleep")
    def test_put_request(self, *mocks):
        pass
class MyTCPServer(http.server.HTTPServer):
    """
    Random port listen
    Specific handler (router)
    Thread
    """

    def __init__(self):
        super().__init__(
            ("localhost", 8000),  # server_address
            MyHttpHandler,  # RequestHandlerClass
            bind_and_activate=False,
        )

        bound = False
        port_tries = 0
        while not bound:
            port_tries += 1
            port = random.randrange(8000, 9000)
            logging.debug("Try port: {}".format(port))
            self.server_address = ("localhost", port)

            try:
                self.server_bind()
                bound = True
            except OSError as err:
                if err.errno != errno.EADDRINUSE:
                    raise

                if port_tries >= 10:
                    raise

                # let's try another port
                continue

        self.server_activate()

        # For dynamic bindings
        self.router = {}

        self.thread = threading.Thread(target=self.serve_forever)

    def start(self):
        self.thread.start()

    def stop(self):
        self.shutdown()

        if self.thread:
            self.thread.join()


class MyHttpHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, request, client_address, server, directory=None):
        self.__server = server
        super().__init__(request, client_address, server, directory=directory)

    def log_message(self, fmt, *args):
        # If debug
        # super().log_message(fmt, *args)
        # else:
        pass

    def do_POST(self):
        return self.handle_request("POST")

    def do_PUT(self):
        return self.handle_request("PUT")

    def handle_request(self, method):
        parsed_url = urllib.parse.urlparse(self.path)

        callback = "[{method}]{path}".format(
            method=method,
            path=parsed_url.path,
        )

        if callback not in self.__server.router:
            self.send_response(http.client.NOT_FOUND)
            self.end_headers()
            return

        request = {
            "method": method,
            "path": parsed_url.path,
            "args": {},
        }

        length = int(self.headers["Content-Length"])
        if length > 0:
            request["data"] = self.rfile.read(length)

        contentType = self.headers.get("Content-Type", "")
        if contentType.startswith("application/json"):
            request["json"] = json.loads(request["data"])

        if contentType.startswith("application/x-www-form-urlencoded"):
            request["args"] = urllib.parse.parse_qs(request["data"])

        response = self.__server.router[callback](request)

        self.send_response(response.get("code", 200))

        if "headers" not in response:
            response["headers"] = {}

        if "json" in response and "Content-Type" not in response["headers"]:
            response["headers"]["Content-Type"] = "application/json"

        for k, v in response.get("headers", {}).items():
            self.send_header(k, v)

        self.end_headers()
        if "json" in response:
            self.wfile.write(json.dumps(response["json"]).encode("utf-8"))
        elif "data" in response:
            self.wfile.write(response["data"])

        # TODO - work with encoding instead of hardcoded utf-8
