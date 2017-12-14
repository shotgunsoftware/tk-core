# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Pick environment hook.
"""

from tank import Hook


class PickEnvironment(Hook):
    """
    Picks the environment based on the context.
    """

    def execute(self, context):
        """
        Always picks the test environment unless step is not set, in which case
        it picks the entity environment.
        """
        if context.step:
            return "test"
        else:
            return "entity"
