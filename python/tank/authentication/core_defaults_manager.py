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
Provides defaults for authentication based on a core's configuration. Namely, it
will provide a default host and an optional http proxy. If a script user has
been configured with the core, its credentials will also be provided.
"""

import os

from .defaults_manager import DefaultsManager
from .. import util
from ..pipelineconfig_utils import get_sgtk_module_path
from ..log import LogManager

logger = LogManager.get_logger(__name__)


class CoreDefaultsManager(DefaultsManager):
    """
    This defaults manager implementation taps into the core's configuration
    (shotgun.yml) to provide a default host, proxy and user.

    :param bool mask_script_user: Prevents the get_user_credentials method from
        returning the script user credentials if the are available.
    :param str core_install_folder: Root of the core's installation folder. This
        is generally the same as the root of the pipeline configuration, but can
        also be an external studio-wide core. If the core is not specified,
        the location of the ``shotgun.yml`` will be calculated relative to the
        location of the currently imported copy of Toolkit, which is incompatible
        with a descriptor-based configuration and can only be used with configurations
        instantiated with :meth:`sgtk.sgtk_from_path`.

        Otherwise, the ``CoreDefaultsManager`` will rely on the global state of
        Toolkit, which will be deprecated in the future.
    """

    def __init__(self, mask_script_user=False, core_install_folder=None):
        """
        Constructor
        """
        if core_install_folder:
            logger.debug(
                "CoreDefaultsManager will look for shotgun.yml under '%s'", core_install_folder
            )
            self._core_install_folder = core_install_folder
        # This is a hack to avoid breaking the Shotgun Desktop.
        elif "TANK_CURRENT_PC" in os.environ:
            logger.debug(
                "CoreDefaultsManager did not receive a core install folder on creation and will "
                "fall back on TANK_CURRENT_PC set to '%s' to find shotgun.yml.",
                os.environ["TANK_CURRENT_PC"]
            )
            self._core_install_folder = os.environ["TANK_CURRENT_PC"]
        else:
            logger.debug(
                "CoreDefaultsManager will locate shotgun.yml relative to the Toolkit library "
                "at '%s'.", get_sgtk_module_path()
            )
            self._core_install_folder = None

        self._mask_script_user = mask_script_user
        super(CoreDefaultsManager, self).__init__()

    def is_host_fixed(self):
        """
        Returns if the host is fixed. Note that the defaults manager for a core
        is always fixed, since a core works with the one and only host specified
        in the configuration.
        :returns: True
        """
        return True

    def get_host(self):
        """
        Returns the host found in the core configuration.
        :returns: The host value from the configuration
        """
        return self._get_shotgun_yaml_data().get("host")

    def get_http_proxy(self):
        """
        Returns an optional proxy string to be used when connecting to Shotgun.
        For detailed information about what proxy settings are supported, see
        https://github.com/shotgunsoftware/python-api/wiki/Reference%3A-Methods#shotgun

        :returns: String with proxy definition suitable for the Shotgun API or
                  None if not necessary.
        """
        sg_config_data = self._get_shotgun_yaml_data()
        # If http_proxy is not set, fallback on the base class. Note that http_proxy
        # can be set to an empty value, which we want to use in that case.
        if "http_proxy" not in sg_config_data:
            return super(CoreDefaultsManager, self).get_http_proxy()
        else:
            return sg_config_data["http_proxy"]

    def get_user_credentials(self):
        """
        Returns the script user's credentials configured for this core, if
        available.

        :returns: A dictionary either with keys login and session_token in the case
                  of a normal Shotgun User, keys api_script and api_key in the case of a Script
                  User or None in case no credentials could be established.
        """
        if not self._mask_script_user:
            data = self._get_shotgun_yaml_data()
            if data.get("api_script") and data.get("api_key"):
                return {
                    "api_script": data["api_script"],
                    "api_key": data["api_key"]
                }
        return super(CoreDefaultsManager, self).get_user_credentials()

    def _get_shotgun_yaml_data(self):
        """
        Returns the data from the shotgun.yml file.

        :returns: Dictionary of the data.
        """
        return util.shotgun.get_associated_sg_config_data(self._core_install_folder)


# For backwards compatibility.
util.CoreDefaultsManager = CoreDefaultsManager
