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


class DefaultsManager(sg_auth.DefaultsManager):

    def get_host(self):
        from . import shotgun
        return shotgun.get_associated_sg_base_url()

    def get_http_proxy(self):
        from . import shotgun
        return shotgun.get_associated_sg_config_data().get("http_proxy")

    def get_user(self):
        from . import shotgun
        data = shotgun.get_associated_sg_config_data()
        if "api_script" in data:
            return sg_auth.user.ScriptUser(**data)
        return None
