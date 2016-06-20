# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Methods to access settings in shotgun.yml
"""

import os
from . import constants
from ..errors import TankError
from .. import hook


class CoreSettings(object):
    """
    Allows to retrieve the values from the current core's shotgun.yml

    The shotgun.yml may look like:

        host: str
        api_script: str
        api_key: str
        http_proxy: str
        app_store_http_proxy: str

        or

        <User>:
            host: str
            api_script: str
            api_key: str
            http_proxy: str
            app_store_http_proxy: str

        <User>:
            host: str
            api_script: str
            api_key: str
            http_proxy: str
            app_store_http_proxy: str

    The optional user param refers to the <User> in the shotgun.yml.
    If a user is not found the old style is attempted.

    :param user: Optional user to pass when a multi-user config is being read.
    """

    @classmethod
    def get_location(cls):
        """
        Returns the core's shotgun.yml path for this install.

        :returns: full path to to shotgun.yml config file
        """
        from ..pipelineconfig_utils import get_api_core_config_location
        core_cfg = get_api_core_config_location()
        path = os.path.join(core_cfg, "shotgun.yml")
        return path

    def __init__(self, user=None):
        """
        Parses the shotgun.yml file.
        """
        cfg = CoreSettings.get_location()
        if user is None:
            self._data = self._get_sg_config_data(cfg)
        else:
            self._data = self.__get_sg_config_data_with_script_user(cfg, user)

    @property
    def host(self):
        """
        :returns: The host.
        """
        return self._data["host"]

    def is_script_user_configured(self):
        """
        :returns: True if api_key and api_script are set, False otherwise.
        """
        return True if self.api_script and self.api_key else False

    @property
    def api_script(self):
        """
        :returns: The api script.
        """
        return self._data.get("api_script")

    @property
    def api_key(self):
        """
        :returns: The api script's key.
        """
        return self._data.get("api_key")

    @property
    def http_proxy(self):
        """
        :returns: The http proxy used to connect to Shotgun.
        """
        return self._data.get("http_proxy")

    def is_app_store_http_proxy_set(self):
        """
        :returns: ``True`` if ``app_store_http_proxy`` is set, ``False`` otheriwe.
        """
        return "app_store_http_proxy" in self._data

    @property
    def app_store_http_proxy(self):
        """
        :returns: The app store specific proxy. If None, the proxy wasn't set. If an empty string, app
            store access is forced to not use a proxy.
        """
        return self._data.get("app_store_http_proxy")

    def __get_sg_config_data_with_script_user(self, shotgun_cfg_path, user="default"):
        """
        Returns the Shotgun configuration yml parameters given a config file, just like
        _get_sg_config_data, but the script user is expected to be present or an exception will be
        thrown.

        :param shotgun_cfg_path: path to config file
        :param user: Optional user to pass when a multi-user config is being read

        :raises TankError: Raised if the script user is not configured.

        :returns: dictionary with mandatory keys host, api_script, api_key and optionally http_proxy
        """
        config_data = self._get_sg_config_data(shotgun_cfg_path, user)
        # If the user is configured, we're happy.
        if config_data.get("api_script") and config_data.get("api_key"):
            return config_data
        else:
            raise TankError("Missing required script user in config '%s'" % shotgun_cfg_path)

    def _get_sg_config_data(self, shotgun_cfg_path, user="default"):
        """
        Returns the shotgun configuration yml parameters given a config file.

        :param shotgun_cfg_path: path to config file
        :param user: Optional user to pass when a multi-user config is being read

        :returns: dictionary with key host and optional keys api_script, api_key and http_proxy
        """
        # load the config file
        try:
            # FIXME: yaml_cache shouldn't be in util, it's much lower level since it doesn't
            # build on top of anything else.

            # Avoid circular dep.
            from ..util import yaml_cache
            file_data = yaml_cache.g_yaml_cache.get(shotgun_cfg_path, deepcopy_data=False)
        except Exception, error:
            raise TankError("Cannot load config file '%s'. Error: %s" % (shotgun_cfg_path, error))

        return self._parse_config_data(file_data, user, shotgun_cfg_path)

    def _parse_config_data(self, file_data, user, shotgun_cfg_path):
        """
        Parses configuration data and overrides it with the studio level hook's result if available.
        :param file_data: Dictionary with all the values from the configuration data.
        :param user: Picks the configuration for a specific user in the configuration data.
        :param shotgun_cfg_path: Path the configuration was loaded from.
        :raises: TankError if there are missing fields in the configuration. The accepted configurations are:
                - host
                - host, api_script, api_key
                In both cases, http_proxy is optional.
        :returns: A dictionary holding the configuration data.
        """
        if user in file_data:
            # new config format!
            # we have explicit users defined!
            config_data = file_data[user]
        else:
            # old format - not grouped by user
            config_data = file_data

        from ..pipelineconfig_utils import get_api_core_config_location

        # now check if there is a studio level override hook which want to refine these settings
        sg_hook_path = os.path.join(get_api_core_config_location(), constants.STUDIO_HOOK_SG_CONNECTION_SETTINGS)

        if os.path.exists(sg_hook_path):
            # custom hook is available!
            config_data = hook.execute_hook(sg_hook_path,
                                            parent=None,
                                            config_data=config_data,
                                            user=user,
                                            cfg_path=shotgun_cfg_path)

        def _raise_missing_key(key):
            raise TankError(
                "Missing required field '%s' in config '%s' for script user authentication." % (key, shotgun_cfg_path)
            )

        if not config_data.get("host"):
            _raise_missing_key("host")

        # The script authentication credentials need to be complete in order to work. They can be completely
        # omitted or fully specified, but not halfway configured.
        if config_data.get("api_script") and not config_data.get("api_key"):
            _raise_missing_key("api_key")
        if not config_data.get("api_script") and config_data.get("api_key"):
            _raise_missing_key("api_script")

        return config_data
