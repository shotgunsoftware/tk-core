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
    This class allows the ShotgunAuthenticator to get some values when authenticating.
    """

    def get_host(self):
        """
        Override to provide a default host.
        :returns: Default implementation returns None.
        """
        return None

    def get_http_proxy(self):
        """
        Override to provide a default http proxy.
        :returns: Default implementation returns None.
        """

    def get_login(self):
        """
        Override to provide a default login when asking for credentials
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
        Override to provide a default user.
        :returns: Default implementation returns None.
        """
        return None

    def get_password(self, host, login):
        """
        Override to retrieve the password got a given user/login pair.
        :returns: Default implementation returns None.
        """
        return None

    def save_password(self, host, login, password):
        """
        Override to store the password for a given user/login pair. Default implementation does nothing.
        """
        pass

    def clear_password(self, host, login):
        """
        Override to clear the password for a given user/login pair. Default implementation does nothing.
        """
        pass


