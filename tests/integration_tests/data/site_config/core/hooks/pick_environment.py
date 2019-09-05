# Copyright (c) 2018 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from sgtk import Hook


class PickEnvironment(Hook):
    """
    The pick environment hook gets called when Toolkit tries to
    determine which configuration to use. Based on the context
    provided by Toolkit, the name of the environment file to be
    used should be returned by the execute method below.
    """

    def execute(self, context, **kwargs):
        return "project"
