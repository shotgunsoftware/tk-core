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
    Exception that indicates that an engine could not start up.
    """
    pass

class TankErrorProjectIsSetup(TankError):
    """
    Exception that indicates that a project already has a toolkit name but no pipeline configuration.
    """

    def __init__(self):
        """
        Include error message
        """
        super(TankErrorProjectIsSetup, self).__init__("You are trying to set up a project which has already been set up. "
                                                      "If you want to do this, make sure to set the force parameter.")

class TankAuthenticationError(TankError):
    """
    Exception that indicates an error has occurred.
    """
    pass


class TankAuthenticationDisabled(TankError):
    """
    Exception that indicates that interactive authentication has been disabled.
    """
    def __init__(self):
        TankError.__init__(self, "Authentication has been disabled.")

