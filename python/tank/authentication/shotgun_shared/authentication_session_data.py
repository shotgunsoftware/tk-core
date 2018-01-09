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
Authentication Session abstraction.
"""


class AuthenticationSessionData(object):
    """
    Holds session information.

    A session object holds information coming from both the toolkit current session
    and from the QWebView used to login/renew session from our SSO enabled site.

    Attributes:
        cookies:            A string of the base64 encoded json string of raw
                            cookies.
        crsf_value:         A string for the crsf value.
        csrf_key:           A string for the crsf key.
        error:              A string which describe the error encountered.
        host:               A string for the hostname.
        product:            A string for the product (used at login).
        session_expitation: An int in seconds for the UTC time of expiration.
        session_id:         A string for the session id.
        user_id:            A string for the user id.
    """

    def __init__(self, settings={}):
        """
        Constructor.

        Args:
            settings (dict):    Dictionary of element to add to the settings.
                                Non-used key/value pairs will be discarded
                                silently.
        """
        self._cookies = None
        self._csrf_key = None
        self._csrf_value = None
        self._error = None
        self._host = None
        self._product = None
        self._session_expiration = None
        self._session_id = None
        self._user_id = None
        self.merge_settings(settings)

    def __repr__(self):
        """
        Returns a string reprensentation of the session.

        :returns: A string containing all of the session data.
        """
        params = {}
        for key, value in vars(self).iteritems():
            if value is not None:
                params[key] = value

        return "<Session %s>" % params

    def merge_settings(self, settings):
        """
        Merge new settings with existing ones.

        Args:
            settings (dict):    Dictionary of element to merge to the settings.
                                Non-used key/value pairs will be discarded
                                silently.
        """
        for key, value in settings.iteritems():
            _key = "_%s" % key
            if _key in vars(self):
                setattr(self, _key, value)

    @property
    def cookies(self):
        """String R/W property."""
        return str(self._cookies or "")

    @cookies.setter
    def cookies(self, value):
        self._cookies = value

    @property
    def csrf_key(self):
        """
        String R/W property.

        This is the key name of the CRSF token, which will include a unique ID.
        The ID corresponds to the Shogun user ID.
        """
        return str(self._csrf_key or "")

    @csrf_key.setter
    def csrf_key(self, value):
        self._csrf_key = value

    @property
    def csrf_value(self):
        """
        String R/W property.

        This is the value of the Cross-Site Request Forgery token.
        """
        return str(self._csrf_value or "")

    @csrf_value.setter
    def csrf_value(self, value):
        self._csrf_value = value

    @property
    def error(self):
        """String R/W property."""
        return str(self._error or "")

    @error.setter
    def error(self, value):
        self._error = value

    @property
    def host(self):
        """String R/W property."""
        return str(self._host or "")

    @host.setter
    def host(self, value):
        self._host = value

    @property
    def product(self):
        """String R/W property."""
        return str(self._product or "undefined")

    @product.setter
    def product(self, value):
        self._product = value

    @property
    def session_expiration(self):
        """Int R/W property."""
        return int(self._session_expiration or 0)

    @session_expiration.setter
    def session_expiration(self, value):
        self._session_expiration = int(value)

    @property
    def session_id(self):
        """String R/W property."""
        return str(self._session_id or "")

    @session_id.setter
    def session_id(self, value):
        self._session_id = value

    @property
    def user_id(self):
        """String R/W property."""
        return str(self._user_id or "")

    @user_id.setter
    def user_id(self, value):
        self._user_id = value
