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
Hook used to resolve publish records in Shotgun into local form on a machine during
a call to :meth:`sgtk.util.resolve_publish_path`.
"""

from sgtk import Hook


class ResolvePublish(Hook):
    def resolve_path(self, sg_publish_data):
        """
        Resolves a Shotgun publish record into a local file on disk.

        If this method returns ``None``, it indicates to Toolkit that the default
        publish resolution logic should be used.

        The default implementation of this hook returns ``None``

        :param dict sg_publish_data: Dictionary containing Shotgun publish data.
            Contains at minimum a code, type, id and a path key.

        :returns: Path to the local file or ``None``.
        :rtype str:
        """
        return None
