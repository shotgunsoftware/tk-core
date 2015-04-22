# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from tank_vendor import shotgun_authentication as sg_auth


class CoreDefaultsManager(sg_auth.DefaultsManager):
    """
    This defaults manager implementation taps into the core's configuration to
    provide a default host, proxy and user.
    """

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
        from . import shotgun
        return shotgun.get_associated_sg_config_data().get("host")

    def get_http_proxy(self):
        """
        Returns an optional proxy string to be used when connecting to Shotgun.
        For detailed information about what proxy settings are supported, see
        https://github.com/shotgunsoftware/python-api/wiki/Reference%3A-Methods#shotgun

        :returns: String with proxy definition suitable for the Shotgun API or
                  None if not necessary.
        """
        from . import shotgun
        return shotgun.get_associated_sg_config_data().get("http_proxy")

    def get_user_credentials(self):
        """
        Returns the script user's credentials configured for this core, if
        available.
        :returns: A dictionary with keys api_script and api_key.
        """
        from . import shotgun
        data = shotgun.get_associated_sg_config_data()
        if data.get("api_script") and data.get("api_key"):
            return data
        return None
