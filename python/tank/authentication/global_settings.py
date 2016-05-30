# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Global settings management.
"""

import os
import ConfigParser

from .errors import MissingConfigurationFileError
from .. import LogManager
from ..util import LocalFileStorageManager

logger = LogManager.get_logger(__name__)


class GlobalSettings(object):
    """
    Handles finding and loading the global settings for Toolkit.
    """

    _LOGIN = "Login"

    def __init__(self, fallback_locations):
        """
        Constructor.

        :param bootstrap: The application bootstrap.
        """
        path = self._compute_config_location(fallback_locations)
        logger.debug("Reading global settings from %s" % path)
        self._global_config = self._load_config(path)
        logger.debug("Default site: %s" % (self.default_site,))
        logger.debug("Default proxy: %s" % (self._get_filtered_proxy(self.default_http_proxy),))
        proxy = self._get_filtered_proxy(self.default_app_store_http_proxy)
        logger.debug("Default app store proxy: %s" % ("<not set>" if proxy is None else proxy,))
        logger.debug("Default login: %s" % (self.default_login,))

    def _get_user_dir_config_location(self, bootstrap):
        """
        :param bootstrap: The application bootstrap.

        :returns: Path to the ``config.ini`` within the user folder.
        """
        return os.path.join(
            bootstrap.get_shotgun_desktop_cache_location(),
            "config",
            "config.ini"
        )

    def _compute_config_location(self, fallback_locations):
        """
        Retrieves the location of the ``config.ini`` file. It will look in multiple locations:

            - The ``SGTK_CONFIG_LOCATION`` environment variable,
            - The ``SGTK_DESKTOP_CONFIG_LOCATION`` environment variable.
            - The ``~/Library/Application Support/Shotgun/config.ini`` file
            - The ``~/Library/Caches/Shotgun/desktop/config/config.ini`` file
            - One of the fallback locations

        :param fallback_locations: List of alternate locations to look for the ``config.ini`` file.

        :returns: The location where to read the configuration file from.
        """
        for var_name in ["SGTK_CONFIG_LOCATION", "SGTK_DESKTOP_CONFIG_LOCATION"]:
            # If environment variable is not set, move to the next one.
            if var_name not in os.environ:
                continue

            # If the path doesn't exist, raise an error.
            path = os.environ[var_name]
            if not os.path.exists(path):
                raise MissingConfigurationFileError(var_name, path)

            # Path is set and exist, we've found it!
            return path

        # This is the default location.
        default_location = os.path.join(
            LocalFileStorageManager.get_global_root(LocalFileStorageManager.PERSISTENT),
            "config.ini"
        )

        # This is the complete list of paths we need to test.
        file_locations = [
            # Default location first
            default_location,
            # This is the location set by users of the Shotgun Desktop in the past.
            os.path.join(
                LocalFileStorageManager.get_global_root(
                    LocalFileStorageManager.CACHE,
                    LocalFileStorageManager.CORE_V17
                ),
                "desktop", "config", "config.ini"
            )
            # Any other locations set by our caller as a fallback.
        ] + fallback_locations

        # Search for the first path that exists and then use it.
        for loc in file_locations:
            if os.path.exists(loc):
                return loc

        # Nothing was found, just use the default location even tough it's empty.
        return default_location

    def _load_config(self, path):
        """
        Loads the configuration at a given location and returns it.

        :param path: Path to the configuration to load.

        :returns: A ConfigParser instance with the contents from the configuration file.
        """
        config = ConfigParser.SafeConfigParser()
        if os.path.exists(path):
            config.read(path)
        return config

    @property
    def default_http_proxy(self):
        """
        :returns: The default proxy.
        """
        return self._get_value(self._LOGIN, "http_proxy")

    @property
    def default_app_store_http_proxy(self):
        """
        :returns: If None, the proxy wasn't set. If an empty string, it has been forced to
        """
        # Passing PROXY_NOT_SET and getting it back means that the proxy wasn't set in the file.
        _PROXY_NOT_SET = "PROXY_NOT_SET"
        proxy = self._get_value(self._LOGIN, "app_store_http_proxy", default=_PROXY_NOT_SET)

        # If proxy wasn't set, then return None, which means Toolkit will use the value from the http_proxy
        # setting for the app store proxy.
        if proxy == _PROXY_NOT_SET:
            return None
        # If the proxy was set to a falsy value, it means it was hardcoded to be None.
        elif not proxy:
            return ""
        else:
            return proxy

    @property
    def default_site(self):
        """
        :returns: The default site.
        """
        return self._get_value(self._LOGIN, "default_site")

    @property
    def default_login(self):
        """
        :returns: The default login.
        """
        return self._get_value(self._LOGIN, "default_login")

    def _get_value(self, section, key, type_cast=str, default=None):
        """
        Retrieves a value from the config.ini file. If the value is not set, returns the default.
        Since all values are strings inside the file, you can optionally cast the data to another type.

        :param section: Section (name between brackets) of the setting.
        :param key: Name of the setting within a section.
        ;param type_cast: Casts the value to the passed in type. Defaults to str.
        :param default: If the value is not found, returns this default value. Defauts to None.

        :returns: The appropriately type casted value if the value is found, default otherwise.
        """
        if not self._global_config.has_section(section):
            return default
        elif not self._global_config.has_option(section, key):
            return default
        else:
            return type_cast(self._global_config.get(section, key))

    def _get_filtered_proxy(self, proxy):
        """
        :param proxy: Proxy server address for which we required credentials filtering.

        :returns: Returns the proxy settings with credentials masked.
        """
        # If there is an address available
        # If there is a username and password in the proxy string. Proxy is None when not set
        # so test that first.
        if proxy and "@" in proxy:
            # Filter out the username and password
            # Given xzy:123@localhost or xyz:12@3@locahost, this will return localhost in both cases
            return "<your credentials have been removed for security reasons>@%s" % proxy.rsplit("@", 1)[-1]
        else:
            return proxy
