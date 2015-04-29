# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from . import session_cache


class DefaultsManager(object):
    """
    This class allows the ShotgunAuthenticator to get some default values when
    authenticating a user. Having a default host and user allows having a single
    sign-on mechanism for all Toolkit applications.
    """

    def __init__(self):
        """
        Constructor.

        Reads the default host and login from disk.
        """
        self._host = session_cache.get_current_host()
        if self._host:
            self._login = session_cache.get_current_user(self.get_host())
        else:
            self._login = None

    def is_host_fixed(self):
        """
        When doing an interactive login, this indicates if the user can choose
        the host to connect to.

        :returns: True is the host can't be edited, False otherwise,
        """
        return False

    def get_host(self):
        """
        The default host is used as a useful starting point when doing
        interactive authentication. When the host is not fixed, the return
        value of get_host is what is used to implement single sign-on between
        all Toolkit desktop applications (at the moment, tank and Shotgun
        Desktop).

        When the host is fixed, this has to return a value.

        :returns: A string containing the default host name.
        """
        return self._host

    def set_host(self, host):
        """
        Sets the defaults host. If host is fixed, the default host is not
        updated.

        :param host: The new default host.
        """
        # Host is fixed, don't update the default host.
        if self.is_host_fixed():
            return
        self._host = host
        session_cache.set_current_host(host)

    def get_http_proxy(self):
        """
        Provides the http proxy associated to the default host.

        :returns: String containing the default http proxy. Default implementation returns None.
        """
        return None

    def get_login(self):
        """
        The default login is provided as a useful starting point when doing
        interactive authentication.

        :returns: Default implementation returns the current os user login name.
        """
        return self._login

    def get_user_credentials(self):
        """
        Returns the credentials for the currently logged in user across all
        Toolkit applications. This is a combination of the default host and
        default login.

        :returns: A dictionary with keys login and session_token or None.
        """
        if self.get_host() and self.get_login():
            return session_cache.get_session_data(self.get_host(), self.get_login())
        else:
            return None

    def set_login(self, login):
        """
        Saves to disk the last user logged in.
        """
        self._login = login
        session_cache.set_current_user(self.get_host(), login)
