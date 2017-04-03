# Copyright (c) 2017 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Hook which chooses an environment file to use based on the current context.
This file is almost always overridden by a standard config.

"""

import sgtk

class BrowserIntegration(sgtk.Hook):
    def get_cache_lookup_hash(self, entity_type, pc_descriptor):
        """
        Computes a unique key for a row in a cache database for the given
        pipeline configuration descriptor and entity type.

        :param str entity_type: The entity type.
        :param pc_descriptor: A descriptor object for the pipeline configuration.

        :returns: The computed lookup hash.
        :rtype: str
        """
        return "%s@%s" % (pc_descriptor.get_uri(), entity_type)

    def get_cache_contents_hash(self, entity_type, pc_descriptor):
        return ""

    def supported_entity_types(self):
        """
        Returns a whitelist of entity types that are supported.

        :rtype: list
        """
        return [
            "Asset",
            "Project",
            "PublishedFile",
            "Sequence",
            "Shot",
            "Task",
            "Version",
        ]
