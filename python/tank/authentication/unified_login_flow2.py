# Copyright (c) 2023 Autodesk.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import json
import os
import platform
import time

import tank
from tank_vendor import six
from tank_vendor.six.moves import http_client, urllib

from . import errors
from ..util.shotgun import connection

from .. import LogManager

logger = LogManager.get_logger(__name__)

class AuthenticationError(errors.AuthenticationError):
    def __init__(self, msg, ulf2_errno=None, payload=None, parent_exception=None):
        errors.AuthenticationError.__init__(self, msg)
        self.ulf2_errno = ulf2_errno
        self.payload = payload
        self.parent_exception = parent_exception


def process(
    sg_url,
    http_proxy=None,
    product=None,
    browser_open_callback=None,
    keep_waiting_callback=lambda: True,
):
    sg_url = connection.sanitize_url(sg_url)

    if not product and "TK_AUTH_PRODUCT" in os.environ:
        product = os.environ["TK_AUTH_PRODUCT"]

    assert product
    assert callable(browser_open_callback)
    assert callable(keep_waiting_callback)

    url_handlers = [urllib.request.HTTPHandler]
    if http_proxy:
        proxy_addr = _build_proxy_addr(http_proxy)
        sg_url_parsed = urllib.parse.urlparse(sg_url)

        url_handlers.append(
            urllib.request.ProxyHandler(
                {
                    sg_url_parsed.scheme: proxy_addr,
                }
            )
        )

    url_opener = urllib.request.build_opener(*url_handlers)

    user_agent = build_user_agent().encode(errors="ignore")

    request = urllib.request.Request(
        urllib.parse.urljoin(sg_url, "/internal_api/app_session_request"),
        # method="POST", # see bellow
        data=urllib.parse.urlencode(
            {
                "appName": product,
                "machineId": platform.node(),
            }
        ).encode(),
        headers={
            "User-Agent": user_agent,
        },
    )

    # Hook for Python 2
    request.get_method = lambda: "POST"

    response = http_request(url_opener, request)
    if response.code != http_client.OK:
        raise AuthenticationError("Request denied", payload=response.json)

    session_id = response.json.get("sessionRequestId")
    if not session_id:
        raise AuthenticationError("Proto error - token is empty")

    logger.debug("session ID: {session_id}".format(session_id=session_id))

    browser_url = response.json.get("url")
    if not browser_url:
        # Retro compatibility with ShotGrid versions <v8.53.0.1993
        browser_url = urllib.parse.urljoin(
            sg_url,
            "/app_session_request/{session_id}".format(
                session_id=session_id,
            ),
        )

    ret = browser_open_callback(browser_url)
    if not ret:
        raise AuthenticationError("Unable to open local browser")

    logger.debug("awaiting browser login...")

    sleep_time = 2
    request_timeout = 180  # 5 minutes
    request = urllib.request.Request(
        urllib.parse.urljoin(
            sg_url,
            "/internal_api/app_session_request/{session_id}".format(
                session_id=session_id,
            ),
        ),
        # method="PUT", # see bellow
        headers={
            "User-Agent": user_agent,
        },
    )

    # Hook for Python 2
    request.get_method = lambda: "PUT"

    t0 = time.time()
    while keep_waiting_callback() and time.time() - t0 < request_timeout:
        response = http_request(url_opener, request)
        if response.code == http_client.NOT_FOUND:
            raise AuthenticationError(
                "Request has maybe expired or proto error",
                payload=response.json,
            )

        if response.json.get("approved", None) is None:
            time.sleep(sleep_time)
            continue

        break

    approved = response.json.get("approved", None)
    if approved is None:
        raise AuthenticationError("Never approved")
    elif not approved:
        raise AuthenticationError("Rejected")

    logger.debug("Request approved")
    try:
        assert response.json["sessionToken"]
        assert response.json["userLogin"]
    except KeyError:
        raise AuthenticationError("proto error")
    except AssertionError:
        raise AuthenticationError("proto error, empty token")

    logger.debug("Session token: {sessionToken}".format(**response.json))

    return (
        sg_url,
        response.json["userLogin"],
        response.json["sessionToken"],
        None,  # Extra metadata - useless here
    )


def _get_content_type(headers):
    if six.PY2:
        value = headers.get("content-type", "text/plain")
        return value.split(";", 1)[0].lower()
    else:
        return headers.get_content_type()


def http_request(opener, req):
    try:
        response = opener.open(req)
        assert _get_content_type(response.headers) == "application/json"
    except urllib.error.HTTPError as exc:
        if _get_content_type(exc.headers) != "application/json":
            raise AuthenticationError(
                "Unexpected response from {url}".format(url=exc.url),
                parent_exception=exc,
            )

        response = exc.fp
    except urllib.error.URLError as exc:
        raise AuthenticationError(exc.reason, parent_exception=exc)
    except AssertionError:
        raise AuthenticationError("No json")

    if response.code == http_client.FORBIDDEN:
        logger.error("response: {resp}".format(resp=response.read()))
        raise AuthenticationError(
            "Proto error - invalid response data - not JSON"
        )

    if response.code == http_client.NOT_FOUND:
        logger.error("response: {resp}".format(resp=response.read()))
        raise AuthenticationError("Authentication denied")

    try:
        data = json.load(response)
        assert isinstance(data, dict)
    except (json.JSONDecodeError, AssertionError):
        raise AuthenticationError(
            "Proto error - invalid response data - not JSON"
        )

    response.json = data
    return response


def _build_proxy_addr(http_proxy):
    # Expected format: foo:bar@123.456.789.012:3456

    proxy_port = 8080

    proxy_user = None
    proxy_pass = None

    # check if we're using authentication. Start from the end since
    # there might be @ in the user's password.
    p = http_proxy.rsplit("@", 1)
    if len(p) > 1:
        proxy_user, proxy_pass = p[0].split(":", 1)
        proxy_server = p[1]
    else:
        proxy_server = http_proxy

    proxy_netloc_list = proxy_server.split(":", 1)
    proxy_server = proxy_netloc_list[0]
    if len(proxy_netloc_list) > 1:
        try:
            proxy_port = int(proxy_netloc_list[1])
        except ValueError:
            raise ValueError(
                'Invalid http_proxy address "{http_proxy}".'
                'Valid format is "123.456.789.012" or "123.456.789.012:3456".'
                "If no port is specified, a default of {proxy_port} will be "
                "used.".format(
                    http_proxy=http_proxy,
                    proxy_port=proxy_port,
                )
            )

    # now populate proxy_handler
    if proxy_user and proxy_pass:
        auth_string = "{proxy_user}:{proxy_pass}@".format(
            proxy_pass=proxy_pass,
            proxy_user=proxy_user,
        )
    else:
        auth_string = ""

    return "http://{auth_string}{proxy_server}:{proxy_port}".format(
        auth_string=auth_string,
        proxy_port=proxy_port,
        proxy_server=proxy_server,
    )


def build_user_agent():
    return "tk-core/{tank_ver} {py_impl}/{py_ver} ({platform})".format(
        platform=platform.platform(),
        py_impl=platform.python_implementation(),
        py_ver=platform.python_version(),
        tank_ver=tank.__version__,
    )


if __name__ == "__main__":
    import argparse
    import sys
    import webbrowser

    parser = argparse.ArgumentParser()
    parser.add_argument("sg_url", help="Provide a ShotGrid URL")
    args = parser.parse_args()

    result = process(
        args.sg_url,
        product="Test Script",
        browser_open_callback=lambda u: webbrowser.open(u),
    )
    if not result:
        print("The web authentication failed. Please try again.")
        sys.exit(1)

    print("The web authentication succeed, now processing.")
    print()
    print(result)
