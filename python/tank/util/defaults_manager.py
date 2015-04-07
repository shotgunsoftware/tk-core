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
    This defaults manager implementation taps into core's shotgun.yml to provide
    a default host, proxy and user.
    """

    def is_host_fixed(self):
        """
        When prompting for a user for a core, the host is always fixed to whatever
        is in shotgun.yml.
        :returns: True
        """
        return True

    def get_host(self):
        """
        Returns the host found in shotgun.yml
        :returns: The host value from shotgun.yml
        """
        from . import shotgun
        return shotgun.get_associated_sg_base_url()

    def get_http_proxy(self):
        """
        Returns the optional http proxy from shotgun.yml.
        :returns: The http_proxy value from shotgun.yml, None if not set or if set to null.
        """
        from . import shotgun
        return shotgun.get_associated_sg_config_data().get("http_proxy")

    def get_user(self):
        """
        Returns the script user configured in shotgun.yml, if configured.
        :returns: A ScriptUser instance, None if api_script and api_key were not configured.
        """
        from . import shotgun
        data = shotgun.get_associated_sg_config_data()
        if data.get("api_script") and data.get("api_key"):
            return data
        return None
