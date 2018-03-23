# Copyright (c) 2017 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.
from sgtk import Hook


class PublishResolver(Hook):
    """
    Hook used to resolve publish records in Shotgun into
    local form on a machine.
    """

    def resolve_path(self, sg_publish_data):
        """
        Resolves a Shotgun publish record into a local file on disk.
        If the method returns None, the default implementation will be used.

        For more information, see
        http://developer.shotgunsoftware.com/tk-core/utils.html#sgtk.util.resolve_publish_path

        :param sg_publish_data: Dictionary containing Shotgun publish data.
            Contains at minimum a code, type, id and a path key.

        :returns: Local Path or None to indicate no resolve.
        """
        return None


