# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from tank_vendor.shotgun_authentication.authentication_manager import AuthenticationManager
from . import shotgun


# FIXME: Quick hack to easily disable logging in this module while keeping the
# code compatible. We have to disable it by default because Maya will print all out
# debug strings.
if False:
    import logging
    # Configure logging
    logger = logging.getLogger("sgtk.core_authentication_manager")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler())
else:
    class logger:
        @staticmethod
        def debug(*args, **kwargs):
            pass

        @staticmethod
        def info(*args, **kwargs):
            pass

        @staticmethod
        def warning(*args, **kwargs):
            pass

        @staticmethod
        def error(*args, **kwargs):
            pass

        @staticmethod
        def exception(*args, **kwargs):
            pass


class CoreAuthenticationManager(AuthenticationManager):

    @staticmethod
    def is_script_user_authenticated(connection_information):
        """
        Indicates if we are authenticating with a script user for a given configuration.
        :param connection_information: Information used to connect to Shotgun.
        :returns: True is "api script" and "api_key" are present, False otherwise.
        """
        return connection_information.get("api_script") and connection_information.get("api_key")

    def __init__(self):
        """
        Creates a CoreAuthenticationManager instance.
        """
        self.__core_config_data = None

    def get_host(self):
        """
        Returns the current host.
        :returns: A string with the hostname.
        """
        return self._core_config_data.get("host") or super(CoreAuthenticationManager, self).get_host()

    def get_http_proxy(self):
        """
        Returns the optional http_proxy.
        :returns: A string with the hostname of the proxy. Can be None.
        """
        return self._core_config_data.get("http_proxy") or super(CoreAuthenticationManager, self).get_http_proxy()

    def get_credentials(self):
        """
        Retrieves the credentials for the current user.
        :returns: A dictionary holding the credentials that were found. Can either contains keys:
                  - api_script and api_key
                  - login, session_token
                  - an empty dictionary.
                  The dictionary will be empty if no credentials were found.
        """
        script_user_credentials = self._get_script_user_credentials()
        if script_user_credentials:
            return script_user_credentials

        return super(CoreAuthenticationManager, self).get_credentials()

    def _get_script_user_credentials(self):
        """
        Returns the script user credentials
        """
        if CoreAuthenticationManager.is_script_user_authenticated(self._core_config_data):
            return {
                "api_key": self._core_config_data.get("api_key"),
                "api_script": self._core_config_data.get("api_script")
            }
        else:
            return {}

    def _is_authenticated(self, connection_information):
        """
        Tests if we are authenticated as script user. If we are not, tests if we are authenticated as a
        human user.
        :param connection_information: Information used to connect to Shotgun.
        :returns: True is we are authenticated, False otherwise.
        """
        if CoreAuthenticationManager.is_script_user_authenticated(connection_information):
            logger.debug("Is script user authenticated.")
            return True
        else:
            return super(CoreAuthenticationManager, self)._is_authenticated(connection_information)

    @property
    def _core_config_data(self):
        """
        _config_core_data is lazy loaded. This is the accessor.
        """
        if not self.__core_config_data:
            self.__core_config_data = shotgun.get_associated_sg_config_data()
            logger.debug("Reading configuration data from disk: %s", self.__core_config_data)
        return self.__core_config_data
