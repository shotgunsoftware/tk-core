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

from .core.utils import (  # noqa
    get_logger,
    set_logger_parent,
    get_saml_claims_expiration,
    _decode_cookies,
    _get_shotgun_user_id,
    _sanitize_http_proxy,
)


def is_sso_enabled_on_site(shotgun_module, url, http_proxy=None):
    """
    Check to see if the web site uses sso.

    We want this method to fail as quickly as possible if there are any
    issues. Failure is not considered critical, thus known exceptions are
    silently ignored. At the moment this method is only used to make the
    GUI show/hide some of the input fields.

    :param shotgun_module: Instance of the Shotgun API3 module.
    :param url:            Url of the site to query.
    :param http_proxy:     HTTP proxy to use, if any.

    :returns:   A boolean indicating if SSO has been enabled or not.
    """
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
            get_logger().debug("Using HTTP proxy to connect to the Shotgun server: %s" % http_proxy)
        info = shotgun_module.Shotgun(url, session_token="dummy", connect=False, http_proxy=http_proxy).info()
        get_logger().debug("User authentication method for %s: %s" % (url, info["user_authentication_method"]))
        if "user_authentication_method" in info:
            return info["user_authentication_method"] == "saml2"
    except Exception as e:
        # Silently ignore exceptions
        get_logger().debug("Unable to connect with %s, got exception '%s' assuming SSO is not enabled" % (url, e))

    return False


def has_sso_info_in_cookies(encoded_cookies):
    """
    Indicate if SSO is being used from the Shotgun cookies.

    :param encoded_cookies: An encoded string representing the cookie jar.

    :returns: True if there are SSO-related infos in the cookies.
    """
    cookies = _decode_cookies(encoded_cookies)
    return _get_shotgun_user_id(cookies) is not None
