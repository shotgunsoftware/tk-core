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

import os
import hashlib
import json
import fnmatch
import datetime

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

    def get_cache_contents_hash(self, pc_descriptor):
        hashsum = hashlib.md5()

        sg = sgtk.platform.current_engine().shotgun
        sw_entities = sg.find(
            "Software",
            [],
            fields=sg.schema_field_read("Software").keys(),
        )

        hashsum.update(
            json.dumps(
                sw_entities,
                sort_keys=True,
                default=self.__json_default,
            ),
        )

        if pc_descriptor.is_immutable() == False:
            yml_files = dict()

            for root, dir_names, file_names in os.walk(pc_descriptor.get_path()):
                for file_name in fnmatch.filter(file_names, "*.yml"):
                    full_path = os.path.join(root, file_name)
                    yml_files[full_path] = os.path.getmtime(full_path)

            hashsum.update(json.dumps(yml_files, sort_keys=True))

        return hashsum.hexdigest()

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

    def __json_default(self, item):
        """
        Fallback logic for serealization of items that are not natively supported by the
        json library.

        :param item: The item to be serialized.

        :returns: A serialized equivalent of the given item.
        """
        if isinstance(item, datetime.datetime):
            return item.isoformat()
        raise TypeError("Item cannot be serialized: %s" % item)


