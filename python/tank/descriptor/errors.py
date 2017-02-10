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


class TankDescriptorError(TankError):
    """
    Base class for all descriptor related errors.
    """
    pass


class TankAppStoreError(TankDescriptorError):
    """
    Errors relating to the Toolkit App Store app store.
    """
    pass


class TankAppStoreConnectionError(TankAppStoreError):
    """
    Errors indicating an error connecting to the Toolkit App Store.
    """
    pass


class InvalidAppStoreCredentialsError(TankAppStoreConnectionError):
    """
    Error indicating no credentials for the Toolkit App Store were found in Shotgun.
    """


class CheckVersionConstraintsError(TankDescriptorError):
    """
    Error throw when one or more version constraints checks failed.
    """

    def __init__(self, reasons):
        """
        :param list(str) reasons: List of reasons why the check failed.
        """
        self._reasons = reasons

    def __str__(self):
        """
        Concatenates all the reasons with a space between each.
        """
        return " ".join(self._reasons)

    @property
    def reasons(self):
        """
        List of strings explaining why the constraints check failed.
        """
        return self._reasons
