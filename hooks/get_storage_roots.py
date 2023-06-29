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
Default hook to get local storage root.
"""
import sgtk
from tank import Hook

log = sgtk.LogManager.get_logger(__name__)


class GetStorageRoots(Hook):
    def execute(self, sg_connection, local_storage_fields, project_id=None):
        """
        Default implementation retrieves the site-based local storage.
        """
        sg_storages = sg_connection.find("LocalStorage", [], local_storage_fields)
        log.debug("Query returned %s global site storages." % (len(sg_storages)))

        return sg_storages
