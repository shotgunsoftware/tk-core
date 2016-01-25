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
import errno


def ensure_folder_exists(path, permissions=0777):
    """
    Helper method - creates a folder if it doesn't already exists.

    :param path: path to create
    :param permissions: Permissions to use when folder is created
    """
    if not os.path.exists(path):
        old_umask = os.umask(0)
        try:
            os.makedirs(path, permissions)
        except OSError, e:
            # Race conditions are perfectly possible on some network storage setups
            # so make sure that we ignore any file already exists errors, as they
            # are not really errors!
            if e.errno != errno.EEXIST:
                # re-raise
                raise
        finally:
            os.umask(old_umask)
