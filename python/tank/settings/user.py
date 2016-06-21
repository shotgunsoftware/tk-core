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

from __future__ import with_statement

import os
import ConfigParser
import threading

from .errors import MissingConfigurationFileError
from .. import LogManager

logger = LogManager.get_logger(__name__)

class Singleton(object):
    """
    Thread-safe base class for singletons. Derived classes must implement _init_singleton.
    """

    __lock = threading.Lock()
    def __new__(cls, *args, **kwargs):
        """
        Create the singleton instance if it hasn't been created already. Once instantiated,
        the object will be cached and never be instantiated again for performance
        reasons.
        """

        # Check if the instance has been created before taking the lock for performance
        # reason.
        if not hasattr(cls, "_instance") or cls._instance is None:
            # Take the lock.
            with cls.__lock:
                # Check the instance again, it might have been created between the
                # if and the lock.
                if hasattr(cls, "_instance") and cls._instance:
                    return cls._instance

                # Create and init the instance.
                instance = super(Singleton, cls).__new__(
                    cls,
                    *args,
                    **kwargs
                )
                instance._init_singleton()

                # remember the instance so that no more are created
                cls._instance = instance

        return cls._instance

    @classmethod
    def reset_singleton(cls):
        """
        Resets the internal singleton instance.
        """
        cls._instance = None


class UserSettings(Singleton):
    """
    Handles finding and loading the user settings for Toolkit.
    """

    _LOGIN = "Login"

    @property
    def default_http_proxy(self):
        """
        :returns: The default proxy.
        """
        return self._get_value(self._LOGIN, "http_proxy")

    def is_default_app_store_http_proxy_set(self):
        """
        :returns: ``True`` if ``app_store_http_proxy`` is set, ``False`` otherwise.
        """
        # Passing PROXY_NOT_SET and getting it back means that the proxy wasn't set in the file.
        _PROXY_NOT_SET = "PROXY_NOT_SET"
        proxy = self._get_value(self._LOGIN, "app_store_http_proxy", default=_PROXY_NOT_SET)

        # If proxy wasn't set, then return False, which means Toolkit will use the value from the http_proxy
        # setting for the app store proxy.
        return proxy != _PROXY_NOT_SET

    @property
    def default_app_store_http_proxy(self):
        """
        :returns: The app store specific proxy.
        """
        # If the config parser returned a falsy value, it meant that the app_store_http_proxy
        # setting was present but empty. We'll advertise that fact as None instead.
        return self._get_value(self._LOGIN, "app_store_http_proxy", default=None) or None

    @property
    def default_site(self):
        """
        :returns: The default site.
        """
        return self._get_value(self._LOGIN, "default_site", default=None)

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
        if not self._user_config.has_section(section):
            return default
        elif not self._user_config.has_option(section, key):
            return default
        else:
            return type_cast(self._user_config.get(section, key))

    def _init_singleton(self):
        """
        Singleton initialization.
        """
        path = self._compute_config_location()
        logger.debug("Reading user settings from %s" % path)

        self._user_config = self._load_config(path)

        # Log the default settings
        logger.debug("Default site: %s" % (self.default_site or "<missing>",))
        logger.debug("Default proxy: %s" % (self._get_filtered_proxy(self.default_http_proxy or "<missing>"),))
        proxy = self._get_filtered_proxy(self.default_app_store_http_proxy)
        if self.is_default_app_store_http_proxy_set():
            logger.debug("Default app store proxy: %s" % (proxy or "<empty>",))
        else:
            logger.debug("Default app store proxy: <missing>")
        logger.debug("Default login: %s" % (self.default_login or "<missing>",))

    def _compute_config_location(self):
        """
        Retrieves the location of the ``config.ini`` file. It will look in multiple locations:

            - The ``SGTK_CONFIG_LOCATION`` environment variable,
            - The ``SGTK_DESKTOP_CONFIG_LOCATION`` environment variable.
            - The ``~/Library/Application Support/Shotgun/config.ini`` file
            - The ``~/Library/Caches/Shotgun/desktop/config/config.ini`` file

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

        # Breaks circular dependency...
        from ..util import LocalFileStorageManager

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
        ]

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
