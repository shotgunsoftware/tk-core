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
All custom exceptions that the tank platform module emits are defined here.
"""

from ..errors import TankError

class TankContextChangeNotSupportedError(TankError):
    """
    Exception that indicates that a requested context change is not allowed
    based on a check of the current engine and all of its active apps.
    """
    pass

class TankEngineInitError(TankError):
    """
    Exception that indicates that an engine could not start up.
    """
    pass

class TankEngineEventError(TankError):
    """
    Exception that is raised when there is a problem during engine event emission.
    """
    pass

