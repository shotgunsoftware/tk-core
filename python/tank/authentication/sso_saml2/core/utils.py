# Copyright (c) 2017 Autodesk.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.
"""
SSO/SAML2 Core utility functions.
"""

import base64
import logging
import urllib
import urlparse
from Cookie import SimpleCookie


from .errors import (
    SsoSaml2MultiSessionNotSupportedError,
)


def get_logger():
    """
    Obtain the logger for this module.

    :returns: The logger instance for this module.
    """
    return logging.getLogger(__name__)


def set_logger_parent(logger_parent):
    """
    Set the logger parent to this module's logger.

    Some client code may want to re-parent this module's logger in order to
    influence the output.

    :param logger_parent: New logger parent.
    """
    logger = get_logger()
    logger.parent = logger_parent


def _decode_cookies(encoded_cookies):
    """
    Extract the cookies from a base64 encoded string.

    :param encoded_cookies: An encoded string representing the cookie jar.

    :returns: A SimpleCookie containing all the cookies.
    """
    cookies = SimpleCookie()
    if encoded_cookies:
        try:
            decoded_cookies = base64.b64decode(encoded_cookies)
            cookies.load(decoded_cookies)
        except TypeError as e:
            get_logger().error("Unable to decode the cookies: %s" % e.message)
    return cookies


def _encode_cookies(cookies):
    """
    Extract the cookies from a base64 encoded string.

    :param cookies: A Cookie.SimpleCookie instance representing the cookie jar.

    :returns: An encoded string representing the cookie jar.
    """
    encoded_cookies = base64.b64encode(cookies.output())
    return encoded_cookies


def _get_shotgun_user_id(cookies):
    """
    Returns the id of the user in the shotgun instance, based on the cookies.

    :param cookies: A Cookie.SimpleCookie instance representing the cookie jar.

    :returns: A string user id value, or None.
    """
    user_id = None
    user_domain = None
    for cookie in cookies:
        # Shotgun appends the unique numerical ID of the user to the cookie name:
        # ex: shotgun_sso_session_userid_u78
        if cookie.startswith("shotgun_sso_session_userid_u"):
            if user_id is not None:
                # Should we find multiple cookies with the same prefix, it means
                # that we are using cookies from a multi-session environment. We
                # have no way to identify the proper user id in the lot.
                message = "The cookies for this user seem to come from two different shotgun sites: '%s' and '%s'"
                raise SsoSaml2MultiSessionNotSupportedError(message % (user_domain, cookies[cookie]['domain']))
            user_id = cookie[28:]
            user_domain = cookies[cookie]['domain']
    return user_id


def _get_cookie_from_prefix(encoded_cookies, cookie_prefix):
    """
    Returns a cookie value based on a prefix to which we will append the user id.

    :param encoded_cookies: An encoded string representing the cookie jar.
    :param cookie_prefix:   The prefix of the cookie name.

    :returns: A string of the cookie value, or None.
    """
    value = None
    cookies = _decode_cookies(encoded_cookies)
    key = "%s%s" % (cookie_prefix, _get_shotgun_user_id(cookies))
    if key in cookies:
        value = cookies[key].value
    return value


def _sanitize_http_proxy(http_proxy):
    """
    Returns a parsed url (a la urlparse).

    We want to support both the proxy notation expected by
    Shotgun:                      username:password@hostname:port (a.k.a. netloc)
    Qt's QtNetwork.QNetworkProxy: scheme://username:password@hostname:port (a.k.a. scheme://netloc)

    :param http_proxy: URL of the proxy. If the URL does not start with a scheme,
                       'http://' will be automatically appended before being parsed.

    :returns: A 6-tuple of the different URL components. See urlparse.urlparse.
    """
    http_proxy = http_proxy or ""
    http_proxy = http_proxy.lower().strip()

    if http_proxy and not (http_proxy.startswith("http://") or http_proxy.startswith("https://")):
        get_logger().debug("Assuming the proxy to be HTTP")
        alt_http_proxy = "http://%s" % http_proxy
        parsed_url = urlparse.urlparse(alt_http_proxy)
        # We want to ensure that the resulting URL is valid.
        if parsed_url.netloc:
            http_proxy = alt_http_proxy

    return urlparse.urlparse(http_proxy)


def get_saml_claims_expiration(encoded_cookies):
    """
    Obtain the expiration time of the saml claims from the Shotgun cookies.

    :param encoded_cookies: An encoded string representing the cookie jar.

    :returns: An int with the time in seconds since January 1st 1970 UTC, or None
    """
    # Shotgun appends the unique numerical ID of the user to the cookie name:
    # ex: shotgun_sso_session_expiration_u78
    saml_claims_expiration = _get_cookie_from_prefix(encoded_cookies, "shotgun_sso_session_expiration_u")
    if saml_claims_expiration is not None:
        saml_claims_expiration = int(saml_claims_expiration)
    return saml_claims_expiration


def get_saml_user_name(encoded_cookies):
    """
    Obtain the saml user name from the Shotgun cookies.

    :param encoded_cookies: An encoded string representing the cookie jar.

    :returns: A string with the user name, or None
    """
    # Shotgun appends the unique numerical ID of the user to the cookie name:
    # ex: shotgun_sso_session_userid_u78
    user_name = _get_cookie_from_prefix(encoded_cookies, "shotgun_sso_session_userid_u")
    if user_name is not None:
        user_name = urllib.unquote(user_name)
    return user_name


def get_session_id(encoded_cookies):
    """
    Obtain the session id from the Shotgun cookies.

    :param encoded_cookies: An encoded string representing the cookie jar.

    :returns: A string with the session id, or None
    """
    session_id = None
    cookies = _decode_cookies(encoded_cookies)
    key = "_session_id"
    if key in cookies:
        session_id = cookies[key].value
    return session_id


def get_csrf_token(encoded_cookies):
    """
    Obtain the csrf token from the Shotgun cookies.

    :param encoded_cookies: An encoded string representing the cookie jar.

    :returns: A string with the csrf token, or None
    """
    # Shotgun appends the unique numerical ID of the user to the cookie name:
    # ex: csrf_token_u78
    return _get_cookie_from_prefix(encoded_cookies, "csrf_token_u")


def get_csrf_key(encoded_cookies):
    """
    Obtain the csrf token name from the Shotgun cookies.

    :param encoded_cookies: An encoded string representing the cookie jar.

    :returns: A string with the csrf token name
    """
    cookies = _decode_cookies(encoded_cookies)
    # Shotgun appends the unique numerical ID of the user to the cookie name:
    # ex: csrf_token_u78
    return "csrf_token_u%s" % _get_shotgun_user_id(cookies)
