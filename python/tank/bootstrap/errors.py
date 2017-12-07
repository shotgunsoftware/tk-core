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

from ..errors import TankError

class TankBootstrapError(TankError):
    """
    Base class for all bootstrap related errors
    """
    pass


class TankBootstrapInvalidPipelineConfigurationError(TankBootstrapError):
    """
    Raised when an invalid pipeline configuration record is detected.
    """
    pass
