# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
from .. import shotgun_base
from . import util

def get_bundle_cache_root():
    """
    Returns the cache location for the default bundle cache.
    Ensures that this folder exists.

    :returns: path on disk
    """
    bundle_cache_root = os.path.join(shotgun_base.get_cache_root(), "bundle_cache")
    shotgun_base.ensure_folder_exists(bundle_cache_root)
    return bundle_cache_root


