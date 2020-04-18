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
Hook that gets executed every time an engine has been fully initialized.
"""

from tank import Hook


class EngineInit(Hook):
    def execute(self, engine, **kwargs):
        """
        Executed when a Toolkit engine has been fully initialized.

        At this point, all apps and frameworks have been loaded,
        and the engine is fully operational.

        The default implementation does nothing.

        :param engine: Engine that has been initialized.
        :type engine: :class:`~sgtk.platform.Engine`
        """
        pass
