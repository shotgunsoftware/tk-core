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
        Executes right after constructing a pipeline configuration during
        Toolkit initialization.

        You can find example implementations in the
        `tests/core_tests/test_default_storage_root_hook <https://github.com/shotgunsoftware/tk-core/tree/master/tests/core_tests/test_default_storage_root_hook>`_
        folder which allow you to switch between storages if you have a
        different storage root per project.

        The default implementation does nothing.

        :param ``StorageRoots`` storage_roots: The storage roots for the project.
        :param int project_id: id of the project toolkit is being initialized in
        :param dict metadata: Contents of the Project configuration file.
        """
        pass
