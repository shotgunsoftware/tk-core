# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.


class BundleCacheUsageException(Exception):

    def __init__(self, filepath, message=None):
        super(BundleCacheUsageException, self).__init__(message)
        self._filepath = filepath


class BundleCacheUsageFileDeletionException(BundleCacheUsageException):

    def __init__(self, filepath, message=None):
        super(BundleCacheUsageFileDeletionException, self).__init__(filepath, message)


class BundleCacheUsageTimeoutException(Exception):

    def __init__(self, method_name):
        super(BundleCacheUsageTimeoutException, self).__init__(method_name)
