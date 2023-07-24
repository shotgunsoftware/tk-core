# Copyright (c) 2018 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Custom hook to modify default storage root.
"""
import sgtk
from tank import Hook

log = sgtk.LogManager.get_logger(__name__)


class ModifyDefaultStorageRoot(Hook):
    def execute(self, storage_roots, project_id=None):
        """
        Custom implementation sets default root to project-specific storage root if available.
        """
        # query project-specific storage root's name
        project_storage_name = self.parent.shotgun.find_one(
            "Project",
            [["id", "is", project_id]],
            ["sg_storage_root_name"],
        )

        # if project-specific storage available, set as default
        if project_storage_name and project_storage_name.get("sg_storage_root_name"):
            storage_roots._default_storage_name = project_storage_name[
                "sg_storage_root_name"
            ]
            log.debug(
                "Project-specific storage root set to default: %s"
                % project_storage_name["sg_storage_root_name"]
            )
