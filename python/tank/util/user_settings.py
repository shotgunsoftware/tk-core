# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
User settings management.
"""

import os
import ConfigParser

from .local_file_storage import LocalFileStorageManager
from .errors import EnvironmentVariableFileLookupError
from .. import LogManager
from .singleton import Singleton


logger = LogManager.get_logger(__name__)


class UserSettings(Singleton):
    """
    Handles finding and loading the user settings for Toolkit.
    """

    _LOGIN = "Login"

    def _init_singleton(self):
        """
        Singleton initialization.
        """
        path = self._compute_config_location()
        logger.debug("Reading user settings from %s" % path)

        self._user_config = self._load_config(path)

        # Log the default settings
        logger.debug("Default site: %s" % (self.default_site or "<missing>",))
        logger.debug("Default login: %s" % (self.default_login or "<missing>",))
        logger.debug("Shotgun proxy: %s" % (self._get_filtered_proxy(self.shotgun_proxy or "<missing>"),))
        proxy = self._get_filtered_proxy(self.app_store_proxy)
        if self.is_app_store_proxy_set():
            logger.debug("App Store proxy: %s" % (proxy or "<empty>",))
        else:
            logger.debug("App Store proxy: <missing>")

    @property
    def shotgun_proxy(self):
        """
        :returns: The default proxy.
        """
        return self._get_value("http_proxy")

    def is_app_store_proxy_set(self):
        """
        :returns: ``True`` if ``app_store_http_proxy`` is set, ``False`` otherwise.
        """
        return self._is_setting_found("app_store_http_proxy")

    @property
    def app_store_proxy(self):
        """
        :returns: The app store specific proxy. If ``None``, it means the setting is absent from the
            file or set to an empty value. Use `is_app_store_proxy_set` to disambiguate.
        """
        # If the config parser returned a falsy value, it meant that the app_store_http_proxy
        # setting was present but empty. We'll advertise that fact as None instead.
        return self._get_value("app_store_http_proxy") or None

    @property
    def default_site(self):
        """
        :returns: The default site.
        """
        return self._get_value("default_site")

    @property
    def default_login(self):
        """
        :returns: The default login.
        """
        return self._get_value("default_login")

    def _get_value(self, key):
        """
        Retrieves a value from the ``config.ini`` file. If the value is not set, returns the default.
        Since all values are strings inside the file, you can optionally cast the data to another type.

        :param key: Name of the setting within the Login section.

        :returns: The appropriately type casted value if the value is found, default otherwise.
        """
        if not self._is_setting_found(key):
            return None
        else:
            # Read the value, remove any extra whitespace.
            value = os.path.expandvars(self._user_config.get(self._LOGIN, key))
            return value.strip()

    def _is_setting_found(self, key):
        """
        Checks if the setting is in the file.

        :param key: Name of the setting within the Login section.

        :returns: True if found, False otherwise.
        """
        if not self._user_config.has_section(self._LOGIN):
            return False
        elif not self._user_config.has_option(self._LOGIN, key):
            return False
        return True

    def _evaluate_env_var(self, var_name):
        """
        Evaluates an environment variable.

        :param var_name: Variable to evaluate.

        :returns: Value if set, None otherwise.

        :raises EnvironmentVariableFileLookupError: Raised if the variable is set, but the file doesn't
                                                    exist.
        """
        if var_name not in os.environ:
            return None

        # If the path doesn't exist, raise an error.
        raw_path = os.environ[var_name]
        path = os.path.expanduser(raw_path)
        path = os.path.expandvars(path)
        if not os.path.exists(path):
            raise EnvironmentVariableFileLookupError(var_name, raw_path)

        # Path is set and exist, we've found it!
        return path

    def _compute_config_location(self):
        """
        Retrieves the location of the ``config.ini`` file. It will look in multiple locations:

            - The ``SGTK_CONFIG_LOCATION`` environment variable.
            - The ``SGTK_DESKTOP_CONFIG_LOCATION`` environment variable.
            - The Shotgun folder.
            - The Shotgun Desktop folder.

        :returns: The location where to read the configuration file from.
        """

        # This is the default location.
        default_location = os.path.join(
            LocalFileStorageManager.get_global_root(LocalFileStorageManager.PREFERENCES),
            "toolkit.ini"
        )

        # This is the complete list of paths we need to test.
        file_locations = [
            self._evaluate_env_var("SGTK_PREFERENCES_LOCATION"),
            self._evaluate_env_var("SGTK_DESKTOP_CONFIG_LOCATION"),
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
        ]

        # Search for the first path that exists and then use it.
        for loc in file_locations:
            if loc and os.path.exists(loc):
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
