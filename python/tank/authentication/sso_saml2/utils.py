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
SSO/SAML2 Utility functions.
"""

# pylint: disable=unused-import

import time

from tank_vendor import shotgun_api3

from .core.utils import (  # noqa
    get_logger,
    set_logger_parent,
    get_saml_claims_expiration,
    get_session_expiration,
    _decode_cookies,
    _get_shotgun_user_id,
    _sanitize_http_proxy,
)


# Cache the servers infos for 30 seconds.
INFOS_CACHE_TIMEOUT = 30
# This is a global state variable. It is used to cache information about the Shotgun servers we
# are interacting with. This is purely to avoid making multiple calls to the servers which would
# yield back the same information. (That info is relatively constant on a given server)
# Should this variable be cleared when doing a Python Core swap, it is not an issue.
# The side effect would be an additional call to the Shotgun site.
INFOS_CACHE = {}


def _get_site_infos(url, http_proxy=None):
    """
    Get and cache the desired site infos.

    We want this method to fail as quickly as possible if there are any
    issues. Failure is not considered critical, thus known exceptions are
    silently ignored. At the moment this method is only used to make the
    GUI show/hide some of the input fields.

    :param url:            Url of the site to query.
    :param http_proxy:     HTTP proxy to use, if any.

    :returns:   A dictionary with the site infos.
    """
    infos = {}
    try:
        # Temporary shotgun instance, used only for the purpose of checking
        # the site infos.
        #
        # The constructor of Shotgun requires either a username/login or
        # key/scriptname pair or a session_token. The token is only used in
        # calls which need to be authenticated. The 'info' call does not
        # require authentication.
        http_proxy = _sanitize_http_proxy(http_proxy).netloc
        if http_proxy:
            get_logger().debug(
                "Using HTTP proxy to connect to the Shotgun server: %s", http_proxy
            )
        # Checks if the information is in the cache, is missing or out of date.
        if url not in INFOS_CACHE or (
            (time.time() - INFOS_CACHE[url][0]) > INFOS_CACHE_TIMEOUT
        ):
            get_logger().info("Infos for site '%s' not in cache or expired", url)
            sg = shotgun_api3.Shotgun(
                url, session_token="dummy", connect=False, http_proxy=http_proxy
            )
            # Remove delay between attempts at getting the site info.  Since
            # this is called in situations where blocking during multiple
            # attempts can make UIs less responsive, we'll avoid sleeping.
            # This change was introduced after delayed retries were added in
            # python-api v3.0.41
            sg.config.rpc_attempt_interval = 0
            infos = sg.info()
            INFOS_CACHE[url] = (time.time(), infos)
        else:
            get_logger().info("Infos for site '%s' found in cache", url)
            infos = INFOS_CACHE[url][1]
    # pylint: disable=broad-except
    except Exception as exc:
        # Silently ignore exceptions
        get_logger().debug("Unable to connect with %s, got exception '%s'", url, exc)

    return infos


def _get_user_authentication_method(url, http_proxy=None):
    """
    Get the user authentication method for site.

    :param url:            Url of the site to query.
    :param http_proxy:     HTTP proxy to use, if any.

    :returns:   A string, such as 'default', 'ldap', 'saml' or 'oxygen', indicating the mode used.
                None is returned when the information is unavailable or we could not reach the site.
    """
    infos = _get_site_infos(url, http_proxy)
    user_authentication_method = None
    if "user_authentication_method" in infos:
        get_logger().debug(
            "User authentication method for %s: %s",
            url,
            infos["user_authentication_method"],
        )
        user_authentication_method = infos["user_authentication_method"]
    return user_authentication_method


# pylint: disable=invalid-name
def is_unified_login_flow_enabled_on_site(url, http_proxy=None):
    """
    Check to see if the web site uses the unified login flow.

    This setting appeared in the Shotgun 7.X serie, being rarely enabled.
    It became enabled by default starting at Shotgun 8.0

    :param url:            Url of the site to query.
    :param http_proxy:     HTTP proxy to use, if any.

    :returns:   A boolean indicating if the unified login flow is enabled or not.
    """
    infos = _get_site_infos(url, http_proxy)
    if "unified_login_flow_enabled" in infos:
        get_logger().debug(
            "unified_login_flow_enabled for %s: %s",
            url,
            infos["unified_login_flow_enabled"],
        )
        return infos["unified_login_flow_enabled"]
    return False


def is_sso_enabled_on_site(url, http_proxy=None):
    """
    Check to see if the web site uses sso.

    :param url:            Url of the site to query.
    :param http_proxy:     HTTP proxy to use, if any.

    :returns:   A boolean indicating if SSO has been enabled or not.
    """
    return _get_user_authentication_method(url, http_proxy) == "saml2"


# pylint: disable=invalid-name
def is_autodesk_identity_enabled_on_site(url, http_proxy=None):
    """
    Check to see if the web site uses Autodesk Identity.

    :param url:            Url of the site to query.
    :param http_proxy:     HTTP proxy to use, if any.

    :returns:   A boolean indicating if Autodesk Identity has been enabled or not.
    """
    return _get_user_authentication_method(url, http_proxy) == "oxygen"


def has_unified_login_flow_info_in_cookies(encoded_cookies):
    """
    Indicate if the Unified Login Flow is being used from the Shotgun cookies.

    :param encoded_cookies: An encoded string representing the cookie jar.

    :returns: True if there are ULF infos in the cookies.
    """
    return get_session_expiration(encoded_cookies) is not None


def has_sso_info_in_cookies(encoded_cookies):
    """
    Indicate if SSO is being used from the Shotgun cookies.

    :param encoded_cookies: An encoded string representing the cookie jar.

    :returns: True if there are SSO-related infos in the cookies.
    """
    return get_saml_claims_expiration(encoded_cookies) is not None
