#
# Copyright (c) 2012 Shotgun Software, Inc
# ----------------------------------------------------
#
"""
Hook to setup the HOUDINI_PATH environment variable.

"""

import os
import platform

import tank
from tank import Hook
from tank import TankError
from tank.platform import constants
from tank.platform.environment import Environment

class BeforeAppLaunch(Hook):
    def execute(self, **kwargs):
        """
        Sets the HOUDINI_PATH environment variable.

        This file should include any site specific path for the houdini path.

        """

        
