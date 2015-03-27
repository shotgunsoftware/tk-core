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
All custom exceptions that this module emits are defined here.
"""


class AuthenticationModuleError(Exception):
    """
    Base class for all exceptions coming out from this module.
    """
    pass


class AuthenticationError(AuthenticationModuleError):
    """
    Exception that indicates an authentication error has occurred.
    """
    pass


class AuthenticationDisabled(AuthenticationModuleError):
    """
    Exception that indicates that interactive authentication has been disabled.
    """
    def __init__(self):
        Exception.__init__(self, "Authentication has been disabled.")
