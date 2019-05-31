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
This file is almost always overridden by a standard config.

"""

from tank import Hook


class PickEnvironment(Hook):

    def execute(self, context, **kwargs):
        # Test project has a single environment file, project.yml
        return "project"
