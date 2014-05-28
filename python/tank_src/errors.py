# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
All custom exceptions that Tank emits are defined here.

"""


class TankError(Exception):
    """
    Exception that indicates an error has occurred.
    """
    pass

class TankEngineInitError(TankError):
    """
    Exception that indicates that an engine could not start up 
    """
    pass