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
All custom exceptions relative to the bundle cache usage functionality.
"""

from ...errors import TankError


class BundleCacheUsageError(TankError):
    """
    Exception that indicates a general error relating to the bundle cache usage functionality.
    """


class BundleCacheUsageFileDeletionError(BundleCacheUsageError):
    """
    Exception that indicates an error deleting a file or bundle in the context
    of the bundle cache usage functionality.
    """


class BundleCacheUsageTimeoutError(BundleCacheUsageError):
    """
    Exception that indicates that an operation timeout in the context
    of the bundle cache usage functionality.
    """


class BundleCacheUsageInvalidBundleCacheRootError(BundleCacheUsageError):
    """
    Exception that indicates that the specified bundle cache root folder is invalid.
    """