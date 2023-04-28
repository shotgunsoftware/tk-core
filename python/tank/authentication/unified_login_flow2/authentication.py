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

from tank_vendor import six
from tank_vendor.six.moves import http_client, urllib

from .. import errors
from ...util.shotgun import connection

from ... import LogManager

logger = LogManager.get_logger(__name__)


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
        sg_url = urllib.parse.urlparse(sg_url)

        url_handlers.append(
            urllib.request.ProxyHandler(
                {
                    sg_url.scheme: proxy_addr,
                }
            )
        )

    url_opener = urllib.request.build_opener(*url_handlers)

    request = urllib.request.Request(
        urllib.parse.urljoin(sg_url, "/internal_api/app_session_request"),
        # method="POST", # see bellow
        data=urllib.parse.urlencode(
            {
                "appName": product,
                "machineId": platform.node(),
            }
        ).encode(),
    )

    # Hook for Python 2
    request.get_method = lambda: "POST"

    try:
        response = http_request(url_opener, request)
        if response.code != http_client.OK:
            raise errors.AuthenticationError("Request denied", response.json)

        session_id = response.json["sessionRequestId"]
    except KeyError:
        raise errors.AuthenticationError(
            "Proto error - invalid response data - no sessionRequestId key"
        )

    if not session_id:
        raise errors.AuthenticationError("Proto error - token is empty")

    logger.debug("session ID: {session_id}".format(session_id=session_id))
    try:
        ret = browser_open_callback(
            urllib.parse.urljoin(
                sg_url,
                "/app_session_request/{session_id}".format(
                    session_id=session_id,
                ),
            ),
        )
        if not ret:
            raise errors.AuthenticationError("Unable to open local browser")

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
            # method="PUT",
        )

        # Hook for Python 2
        request.get_method = lambda: "PUT"

        t0 = time.time()
        while keep_waiting_callback() and time.time() - t0 < request_timeout:
            response = http_request(url_opener, request)
            if response.code == http_client.NOT_FOUND:
                raise errors.AuthenticationError(
                    "Request has maybe expired or proto error",
                    response.json,
                )

            if "approved" not in response.json or not response.json["approved"]:
                time.sleep(sleep_time)
                continue

            break
    finally:
        # Delete the request (be a nice bot and clean up your own mess)
        try:
            url_opener.open(
                urllib.request.Request(
                    urllib.parse.urljoin(
                        sg_url,
                        "/internal_api/app_session_request/{session_id}".format(
                            session_id=session_id,
                        ),
                    ),
                    # method="DELETE",
                )
            )

            # Hook for Python 2
            request.get_method = lambda: "DELETE"
        except urllib.error.URLError:
            pass

    if "approved" not in response.json:
        raise errors.AuthenticationError("Never approved")
    elif not response.json["approved"]:
        raise errors.AuthenticationError("Rejected")

    logger.debug("Request approved")
    try:
        assert response.json["sessionToken"]
        assert response.json["userLogin"]
    except KeyError:
        raise errors.AuthenticationError("proto error")
    except AssertionError:
        raise errors.AuthenticationError("proto error, empty token")

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
            raise errors.AuthenticationError(
                "Unexpected response from {url}".format(url=exc.url),
                exc,
            )

        response = exc.fp
    except urllib.error.URLError as exc:
        raise errors.AuthenticationError(exc.reason, exc)

    if response.code == http_client.FORBIDDEN:
        logger.error("response: {resp}".format(resp=response.read()))
        raise errors.AuthenticationError(
            "Proto error - invalid response data - not JSON"
        )

    if response.code == http_client.NOT_FOUND:
        logger.error("response: {resp}".format(resp=response.read()))
        raise errors.AuthenticationError("Authentication denied")

    try:
        data = json.load(response)
        assert isinstance(data, dict)
    except json.JSONDecodeError:
        raise errors.AuthenticationError(
            "Proto error - invalid response data - not JSON"
        )

    response.json = data
    return response


def _build_proxy_addr(http_proxy):
    # Expected format: foo:bar@123.456.789.012:3456

    proxy_port = 8080

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


if __name__ == "__main__":
    import argparse
    import sys
    import webbrowser

    parser = argparse.ArgumentParser()
    parser.add_argument("sg_url", help="Provide a ShotGrid URL")
    args = parser.parse_args()

    result = process(
        args.sg_url,
        browser_open_callback=lambda u: webbrowser.open(u),
    )
    if not result:
        print("The web authentication failed. Please try again.")
        sys.exit(1)

    print("The web authentication succeed, now processing.")
    print()
    print(result)
