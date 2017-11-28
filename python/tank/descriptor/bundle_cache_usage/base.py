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
Methods relating to the Path cache, a central repository where metadata about
all Tank items in the file system are kept.

"""
from .. import LogManager

log = LogManager.get_logger(__name__)
DEBUG = False


class BundleCacheUsageWriterBase(object):
    pass


class BundleCacheUsageAPI(object):

    def log_usage(self, bundle_path):
        pass

    def delete_expired_bundles(self):
        pass
