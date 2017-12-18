# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
All custom exceptions that this package emits are defined here.
"""

from ...errors import TankError


class BundleCacheUsageError(TankError):

    def __init__(self, filepath, message=None):
        super(BundleCacheUsageError, self).__init__(message)
        self._filepath = filepath


class BundleCacheUsageFileDeletionError(BundleCacheUsageError):

    def __init__(self, filepath, message=None):
        super(BundleCacheUsageFileDeletionError, self).__init__(filepath, message)


class BundleCacheUsageTimeoutError(BundleCacheUsageError):

    def __init__(self, method_name):
        super(BundleCacheUsageTimeoutError, self).__init__(method_name)
