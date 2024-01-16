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

from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import (
    mock,
    ShotgunTestBase,
)

from tank.authentication import (
    app_session_launcher,
)

from tank_vendor.six.moves import urllib

import errno
import http.client
import http.server
import json
import logging
import os
import random
import sys
import threading


class AppSessionLauncherTests(ShotgunTestBase):
    def test_process_parameters(self):
        with self.assertRaises(AssertionError):
            app_session_launcher.process(
                "https://test.shotgunstudio.com",
                None,  # browser_open_callback
            )

        with self.assertRaises(AssertionError):
            app_session_launcher.process(
                "https://test.shotgunstudio.com",
                "Test",  # browser_open_callback
            )

        with self.assertRaises(AssertionError):
            app_session_launcher.process(
                "https://test.shotgunstudio.com",
                lambda: True,  # browser_open_callback
                keep_waiting_callback=None,
            )

    def test_build_proxy_addr(self):
        self.assertEqual(
            app_session_launcher._build_proxy_addr("10.20.30.40"),
            "http://10.20.30.40:8080",
        )

        with self.assertRaises(ValueError):
            app_session_launcher._build_proxy_addr("10.20.30.40:string")

        self.assertEqual(
            app_session_launcher._build_proxy_addr("10.20.30.40:3128"),
            "http://10.20.30.40:3128",
        )

        self.assertEqual(
            app_session_launcher._build_proxy_addr("u:p@10.20.30.40"),
            "http://u:p@10.20.30.40:8080",
        )

    @mock.patch.dict(os.environ)
    def test_get_product_name(self):
        # Validate the default product name
        self.assertEqual(
            app_session_launcher.get_product_name(),
            app_session_launcher.PRODUCT_DEFAULT,
        )

        # Validate the FLAME product name
        os.environ["SHOTGUN_FLAME_CONFIGPATH"] = "/flame"
        os.environ["SHOTGUN_FLAME_VERSION"] = "1.2.3"
        self.assertEqual(
            app_session_launcher.get_product_name(),
            "Flame 1.2.3",
        )

        # Validate Flow Production Tracking Toolkit
        with mock.patch.object(
            sys,
            "argv",
            [os.path.join("Applications", "ShotGun.exe")],
        ):
            self.assertEqual(
                app_session_launcher.get_product_name(),
                app_session_launcher.PRODUCT_DESKTOP,
            )

        # Validate Engine host info
        class MyEngine:
            host_info = {
                "name": "desktop",
                "version": "3.2.1",
            }

        with mock.patch(
            "tank.platform.current_engine", MyEngine,
        ):
            self.assertEqual(
                app_session_launcher.get_product_name(),
                "Flow Production Tracking Toolkit 3.2.1",
            )

        # Validate the TK_AUTH_PRODUCT environment variable
        os.environ["TK_AUTH_PRODUCT"] = "software_8b1a7bd"
        self.assertEqual(
            app_session_launcher.get_product_name(),
            "software_8b1a7bd",
        )


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
        # Register the proper HTTP server API responses
        self.httpd.router["[POST]/internal_api/app_session_request"] = lambda request: {
            "json": {
                "sessionRequestId": "a1b2c3",
                "url": "https://1.2.3.4/click_me/a1b2c3",
            }
        }
        self.httpd.router[
            "[PUT]/internal_api/app_session_request/a1b2c3"
        ] = lambda request: {
            "json": {
                "approved": True,
                "sessionToken": "to123",
                "userLogin": "john",
            },
        }

        def url_opener(url):
            os.environ["test_f444c4820c16e8"] = url
            return True

        self.assertEqual(
            app_session_launcher.process(
                self.api_url,
                url_opener,  # browser_open_callback
                http_proxy="{fqdn}:{port}".format(  # For code coverage
                    fqdn=self.httpd.server_address[0],
                    port=self.httpd.server_address[1],
                ),
            ),
            (self.api_url, "john", "to123", None),
        )

        self.assertEqual(
            os.environ["test_f444c4820c16e8"],
            "https://1.2.3.4/click_me/a1b2c3",
        )

    @mock.patch("time.sleep")
    def test_not_reachable(self, *mocks):
        # Shutdown the HTTP server
        self.httpd.stop()
        self.httpd.server_close()  # To unbind the port

        with self.assertRaises(app_session_launcher.AuthenticationError) as cm:
            app_session_launcher.process(
                self.api_url,
                lambda url: True,  # browser_open_callback
            )

        self.assertIsInstance(
            cm.exception.parent_exception.reason, ConnectionRefusedError
        )
        self.assertEqual(cm.exception.parent_exception.reason.errno, errno.ECONNREFUSED)

    @mock.patch("time.sleep")
    def test_fault_tolerance(self, *mocks):
        def api_post_handler(request):
            try_num = int(os.environ.get("API_POST_RUN_NUM", "0")) + 1
            os.environ["API_POST_RUN_NUM"] = str(try_num)

            if try_num == 1:
                return {"code": http.client.INTERNAL_SERVER_ERROR}
            elif try_num == 2:
                raise NotImplementedError("Server, please crash!")
            elif try_num == 3:
                return {"code": http.client.BAD_GATEWAY}

            return {
                "json": {
                    "sessionRequestId": "a1b2c3",
                    "url": "https://1.2.3.4/click_me/a1b2c3",
                },
            }

        def api_put_handler(request):
            try_num = int(os.environ.get("API_PUT_RUN_NUM", "0")) + 1
            os.environ["API_PUT_RUN_NUM"] = str(try_num)

            if try_num == 1:
                return {"code": http.client.INTERNAL_SERVER_ERROR}
            elif try_num == 2:
                raise NotImplementedError("Server, please crash!")
            elif try_num == 3:
                return {"code": http.client.BAD_GATEWAY}
            elif try_num == 4:
                return {"json": {}}
            elif try_num == 5:
                return {"code": http.client.BAD_GATEWAY}
            elif try_num == 6:
                return {"code": http.client.GATEWAY_TIMEOUT}
            elif try_num == 7:
                return {"code": http.client.SERVICE_UNAVAILABLE}

            return {
                "json": {
                    "approved": True,
                    "sessionToken": "to123",
                    "userLogin": "john",
                },
            }

        self.httpd.router["[POST]/internal_api/app_session_request"] = api_post_handler
        self.httpd.router[
            "[PUT]/internal_api/app_session_request/a1b2c3"
        ] = api_put_handler

        self.assertEqual(
            app_session_launcher.process(
                self.api_url,
                lambda url: True,  # browser_open_callback
            ),
            (self.api_url, "john", "to123", None),
        )

    @mock.patch("time.sleep")
    def test_post_request(self, *mocks):
        # First test with an empty HTTP server
        with self.assertRaises(app_session_launcher.AuthenticationError) as cm:
            app_session_launcher.process(
                self.api_url,
                lambda url: True,  # browser_open_callback
            )

        self.assertEqual(
            repr(cm.exception.parent_exception), "<HTTPError 404: 'Not Found'>"
        )

        # Then, make the server return a 500
        self.httpd.router["[POST]/internal_api/app_session_request"] = lambda request: {
            "code": 500
        }
        with self.assertRaises(app_session_launcher.AuthenticationError) as cm:
            app_session_launcher.process(
                self.api_url,
                lambda url: True,  # browser_open_callback
            )

        self.assertEqual(
            repr(cm.exception.parent_exception),
            "<HTTPError 500: 'Internal Server Error'>",
        )

        # Now, make the server crash
        def api_handler1(request):
            raise AttributeError("test")

        self.httpd.router["[POST]/internal_api/app_session_request"] = api_handler1
        with self.assertRaises(app_session_launcher.AuthenticationError) as cm:
            app_session_launcher.process(
                self.api_url,
                lambda url: True,  # browser_open_callback
            )

        self.assertIsInstance(
            cm.exception.parent_exception,
            http.client.RemoteDisconnected,
        )
        self.assertEqual(
            cm.exception.parent_exception.args[0],
            "Remote end closed connection without response",
        )

        # Unsupported method
        self.httpd.router["[POST]/internal_api/app_session_request"] = lambda request: {
            "code": 501
        }
        with self.assertRaises(app_session_launcher.AuthenticationError) as cm:
            app_session_launcher.process(
                self.api_url,
                lambda url: True,  # browser_open_callback
            )

        self.assertEqual(
            repr(cm.exception.parent_exception), "<HTTPError 501: 'Not Implemented'>"
        )

        # 200 but no json
        self.httpd.router[
            "[POST]/internal_api/app_session_request"
        ] = lambda request: {}
        with self.assertRaises(app_session_launcher.AuthenticationError) as cm:
            app_session_launcher.process(
                self.api_url,
                lambda url: True,  # browser_open_callback
            )

        self.assertEqual(
            cm.exception.args[0],
            "Unexpected response from the Flow Production Tracking site",
        )

        # 200 with valid empty json
        self.httpd.router["[POST]/internal_api/app_session_request"] = lambda request: {
            "json": {}
        }
        with self.assertRaises(app_session_launcher.AuthenticationError) as cm:
            app_session_launcher.process(
                self.api_url,
                lambda url: True,  # browser_open_callback
            )

        self.assertEqual(
            cm.exception.args[0],
            "Unexpected response from the Flow Production Tracking site",
        )

        # 400 with error in json
        self.httpd.router["[POST]/internal_api/app_session_request"] = lambda request: {
            "code": 400,
            "json": {"message": "missing parameters"},
        }
        with self.assertRaises(app_session_launcher.AuthenticationError) as cm:
            app_session_launcher.process(
                self.api_url,
                lambda url: True,  # browser_open_callback
            )

        self.assertEqual(
            cm.exception.args[0], "Unable to create an authentication request"
        )

        # Send a 200 with JSON content type but not valid JSON
        self.httpd.router["[POST]/internal_api/app_session_request"] = lambda request: {
            "data": b"test1",
            "headers": {"Content-Type": "application/json"},
        }

        with self.assertRaises(app_session_launcher.AuthenticationError) as cm:
            app_session_launcher.process(
                self.api_url,
                lambda url: True,  # browser_open_callback
            )

        self.assertEqual(
            cm.exception.args[0],
            "Unable to decode JSON content",
        )

        # Send a 200 with JSON but not a dict
        self.httpd.router["[POST]/internal_api/app_session_request"] = lambda request: {
            "json": True
        }

        with self.assertRaises(app_session_launcher.AuthenticationError) as cm:
            app_session_launcher.process(
                self.api_url,
                lambda url: True,  # browser_open_callback
            )

        self.assertEqual(
            cm.exception.args[0],
            "Unexpected response from the Flow Production Tracking site",
        )

        # Send a 200 with sessionRequestId but not url field
        self.httpd.router["[POST]/internal_api/app_session_request"] = lambda request: {
            "json": {
                "sessionRequestId": "a1b2c3",
            }
        }

        with self.assertRaises(app_session_launcher.AuthenticationError) as cm:
            app_session_launcher.process(
                self.api_url,
                lambda url: True,  # browser_open_callback
            )

        self.assertEqual(
            cm.exception.args[0],
            "Unexpected response from the Flow Production Tracking site",
        )

        # Finaly, send a 200 with a sessionRequestId
        self.httpd.router["[POST]/internal_api/app_session_request"] = lambda request: {
            "json": {
                "sessionRequestId": "a1b2c3",
                "url": "https://1.2.3.4/click_me",
            }
        }

        # Expect a 404 on the PUT request
        with self.assertRaises(app_session_launcher.AuthenticationError) as cm:
            app_session_launcher.process(
                self.api_url,
                lambda url: True,  # browser_open_callback
            )

        self.assertEqual(
            repr(cm.exception.parent_exception), "<HTTPError 404: 'Not Found'>"
        )

    def test_browser_error(self):
        # Install a proper POST request handler
        self.httpd.router["[POST]/internal_api/app_session_request"] = lambda request: {
            "json": {
                "sessionRequestId": "a1b2c3",
                "url": "https://1.2.3.4/click_me",
            }
        }

        with self.assertRaises(app_session_launcher.AuthenticationError) as cm:
            app_session_launcher.process(
                self.api_url,
                lambda url: False,  # browser_open_callback
            )

        self.assertEqual(
            cm.exception.args[0],
            "Unable to open local browser",
        )

    @mock.patch.dict(os.environ)
    def test_param_product(self):
        def api_handler1(request):
            os.environ["test_96272fea51"] = request["args"][b"appName"][0].decode()
            return {
                "json": {
                    "sessionRequestId": "a1b2c3",
                    "url": "https://1.2.3.4/click_me",
                },
            }

        # Install a proper POST request handler
        self.httpd.router["[POST]/internal_api/app_session_request"] = api_handler1

        with self.assertRaises(app_session_launcher.AuthenticationError) as cm:
            app_session_launcher.process(
                self.api_url,
                lambda url: True,  # browser_open_callback
                product="app_2a37c59",
                keep_waiting_callback=lambda: False,
            )

        self.assertEqual(cm.exception.args[0], "The request has never been approved")

        self.assertEqual(
            os.environ["test_96272fea51"],
            "app_2a37c59",
        )

    @mock.patch("time.sleep")
    def test_put_request(self, *mocks):
        # Install a proper POST request handler
        self.httpd.router["[POST]/internal_api/app_session_request"] = lambda request: {
            "json": {
                "sessionRequestId": "a1b2c3",
                "url": "https://1.2.3.4/click_me/a1b2c3",
            }
        }

        def url_opener(url):
            os.environ["test_8979b275121ac8"] = url
            return True

        # Now, make the server crash on the PUT request
        def api_handler1(request):
            raise AttributeError("test")

        self.httpd.router[
            "[PUT]/internal_api/app_session_request/a1b2c3"
        ] = api_handler1
        with self.assertRaises(app_session_launcher.AuthenticationError) as cm:
            app_session_launcher.process(
                self.api_url,
                url_opener,  # browser_open_callback
            )

        self.assertIsInstance(
            cm.exception.parent_exception,
            http.client.RemoteDisconnected,
        )
        self.assertEqual(
            cm.exception.parent_exception.args[0],
            "Remote end closed connection without response",
        )

        # Proove the PUT request was called
        self.assertEqual(
            os.environ["test_8979b275121ac8"],
            "https://1.2.3.4/click_me/a1b2c3",
        )

        # Unsupported method
        self.httpd.router[
            "[PUT]/internal_api/app_session_request/a1b2c3"
        ] = lambda request: {"json": {"approved": False}}
        with self.assertRaises(app_session_launcher.AuthenticationError) as cm:
            app_session_launcher.process(
                self.api_url,
                lambda url: True,  # browser_open_callback
                keep_waiting_callback=lambda: False,  # Avoid 5 minute timeout
            )

        self.assertEqual(cm.exception.args[0], "The request has never been approved")

        self.httpd.router[
            "[PUT]/internal_api/app_session_request/a1b2c3"
        ] = lambda request: {"json": {}}

        with self.assertRaises(app_session_launcher.AuthenticationError) as cm:
            app_session_launcher.process(
                self.api_url,
                lambda url: True,  # browser_open_callback
                keep_waiting_callback=lambda: False,  # Avoid 5 minute timeout
            )

        self.assertEqual(cm.exception.args[0], "The request has never been approved")


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
