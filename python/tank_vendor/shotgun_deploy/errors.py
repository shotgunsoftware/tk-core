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
All custom exceptions that this module emits are defined here.
"""

from ..shotgun_base import ShotgunBaseError

class ShotgunDeployError(ShotgunBaseError):
    """
    Base class for all deploy related errors
    """
    pass

class ShotgunAppStoreError(ShotgunDeployError):
    """
    Errors relating to the shotgun app store
    """
    pass

class ShotgunAppStoreConnectionError(ShotgunAppStoreError):
    """
    Errors indicating an error connecting to the Toolkit App Store
    """
    pass
