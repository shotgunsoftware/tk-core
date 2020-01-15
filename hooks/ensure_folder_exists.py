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
This hook is called when an engine, app or framework's
:class:`~sgtk.platform.Application.ensure_folder_exists` method is called.
"""

from sgtk.util import filesystem
from sgtk import Hook


class EnsureFolderExists(Hook):
    def execute(self, path, bundle_obj, **kwargs):
        """
        Creates folders on disk.

        Toolkit bundles call this method when they want to ensure that
        a leaf-level folder structure exists on disk. In the case where customization
        is required, the hook is passed the bundle that issued the original request.
        This should allow for some sophisticated introspection inside the hook.

        The default implementation creates these folders with read/write
        permissions for everyone.

        :param str path: path to create
        :param bundle_object: Object requesting the creation. This is a legacy
                              parameter and we recommend using self.parent instead.
        :type bundle_object: :class:`~sgtk.platform.Engine`, :class:`~sgtk.platform.Framework`
            or :class:`~sgtk.platform.Application`
        """
        filesystem.ensure_folder_exists(path, permissions=0o777)
