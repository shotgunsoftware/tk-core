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
Provides shorthand versions of all public methods on the CoreAuthenticationManager. Useful
when mocking for unit test without having to worry to mock the most derived class.
"""

# Import everthing from other authentication module for easy access
from tank_vendor.shotgun_authentication.authentication import *

from .core_authentication_manager import CoreAuthenticationManager


def is_script_user_authenticated(connection_information):
    """
    Indicates if we are authenticating with a script user for a given configuration.
    :param connection_information: Information used to connect to Shotgun.
    :returns: True is "api script" and "api_key" are present, False otherwise.
    """
    return CoreAuthenticationManager.is_script_user_authenticated(connection_information)
