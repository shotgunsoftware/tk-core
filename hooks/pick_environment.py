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
Hook which chooses an environment file to use based on the current context.
This file is almost always overridden by a configuration.
"""

from tank import Hook


class PickEnvironment(Hook):
    def execute(self, context, **kwargs):
        """
        Executed when Toolkit needs to pick an environment file.

        The default implementation will return ``shot`` or ``asset`` based
        on the type of the entity in :attr:`sgtk.Context.entity`. If the type
        does not match ``Shot`` or ``Asset``, ``None`` will be returned.

        :params context: The context for which an environment will be picked.
        :type context: :class:`~sgtk.Context`

        :returns: Name of the environment to use or ``None`` is there was no match.
        :rtype: str
        """
        # Must have an entity
        if context.entity is None:
            return None

        if context.entity["type"] == "Shot":
            return "shot"
        elif context.entity["type"] == "Asset":
            return "asset"

        return None
