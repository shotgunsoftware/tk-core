# Copyright (c) 2023 Autodesk.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Hook that gets executed during Toolkit initialization.
This hook makes it possible to modify the default storage root.
"""
import os

import sgtk
from tank import Hook

log = sgtk.LogManager.get_logger(__name__)


class DefaultStorageRoot(Hook):
    def execute(self, storage_roots, project_id=None):
        """
        Custom implementation sets default root to project-specific storage root stored
        in an environment variable called "[project_id]_STORAGE_ROOT"
        """
        # query project-specific storage root's name
        project_storage_name = os.getenv("STORAGE_ROOT_%d" % project_id)
        # if project-specific storage available, set as default
        if project_storage_name:
            storage_roots._default_storage_name = project_storage_name
            log.debug(
                "Project-specific storage root set to default: %s"
                % project_storage_name
            )
