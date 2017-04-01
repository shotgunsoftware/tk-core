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
        pc_uri = pc_descriptor.get_uri()
        return "%s@%s" % (pc_uri, entity_type)

    def get_cache_contents_hash(self, entity_type, pc_descriptor):
        return ""
