# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import sys


class DefaultsManager(object):
    """
    This class allows the ShotgunAuthenticator to get some default values when
    authenticating a user.
    """

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
        interactive authentication.

        When the host is fixed, this has to return a value.

        :returns: A string containing the default host name. Default implementation returns None.
        """
        return None

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
        if sys.platform == "win32":
            # http://stackoverflow.com/questions/117014/how-to-retrieve-name-of-current-windows-user-ad-or-local-using-python
            return os.environ.get("USERNAME", None)
        else:
            try:
                import pwd
                pwd_entry = pwd.getpwuid(os.geteuid())
                return pwd_entry[0]
            except:
                return None

    def get_user(self):
        """
        Override to provide a default user's dictionary of credentials.

        :returns: Default implementation returns None.
        """
        return None
