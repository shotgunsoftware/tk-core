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
import sgtk
from tank import Hook

log = sgtk.LogManager.get_logger(__name__)


class DefaultStorageRoot(Hook):
    def execute(self, storage_roots, project_id=None, metadata=None):
        """
        Custom implementation sets default root to project-specific storage root name stored
        in a custom project field on Flow Production Tracking site called "Storage Root Name"
        """
        if not project_id:
            return

        # query project-specific storage root's name
        sg_data = self.parent.shotgun.find_one(
            "Project",
            [["id", "is", project_id]],
            ["sg_storage_root_name"],
        )

        # check if custom field was set and filled
        if not sg_data or not sg_data.get("sg_storage_root_name"):
            log.debug("Using global storage root.")
            return

        project_storage_name = sg_data["sg_storage_root_name"]

        # check if local storage exists on PTR site
        local_storage = self.parent.shotgun.find(
            "LocalStorage", [["code", "is", project_storage_name]]
        )
        if not local_storage:
            log.debug(
                "The local file storage %s for project %d is not defined for this operating system."
                % (project_storage_name, project_id)
            )
            return
        # Modify the folder creation metadata, this make sure to register the new storage root
        # path on disk as FilesystemLocation entities in PTR.
        if metadata:
            metadata.update({"root_name": project_storage_name})

        # project-specific storage available, set as default
        storage_roots._default_storage_name = project_storage_name
        log.debug(
            "Project-specific storage root set to default: %s" % project_storage_name
        )
