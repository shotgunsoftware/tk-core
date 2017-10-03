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
import shutil

from .base import IODescriptorBase
from ..errors import TankDescriptorError, TankError
from ...util import filesystem

from ... import LogManager
log = LogManager.get_logger(__name__)


class IODescriptorDownloadable(IODescriptorBase):
    """
    Base class for descriptors that can be downloaded locally to a path on disk.
    """
    def download_local(self):

        # Return if the descriptor exists locally.
        if self.exists_local():
            return

        # cache into a temporary location
        temporary_path = self._get_temporary_cache_path()

        # move into primary location
        target = self._get_primary_cache_path()

        # ensure that the parent directory of the target is present.
        # make sure we guard against multiple processes attempting to create it simultaneously.
        try:
            filesystem.ensure_folder_exists(os.path.dirname(target))
        except Exception as e:
            if not os.path.exists(os.path.dirname(target)):
                raise TankDescriptorError("Failed to create parent directory %s: %s" % (os.path.dirname(target), e))

        try:
            # attempt to download the descriptor to the temporary path.
            self._download_local(temporary_path)
        except Exception as e:
            # something went wrong during the download, remove the temporary files.
            shutil.rmtree(temporary_path)
            raise TankDescriptorError("Failed to download into path %s: %s" % (temporary_path, e))

        success = False
        try:
            # atomically rename the directory temporary_path to the target.
            os.rename(temporary_path, target)
            success = True
            log.debug("Successfully downloaded the descriptor to %s." % target)
        except Exception as e:
            # if the target path does not already exist, it something else might have gone wrong.
            if not os.path.exists(target):
                raise TankError("Failed to move descriptor from the temporary path %s to " +
                                "the bundle cache %s: %s" % (temporary_path, target, e))
        finally:
            if os.path.exists(temporary_path):
                shutil.rmtree(temporary_path)

        if success:
            self._post_download(temporary_path)

    def _download_local(self, destination_path):
        """
        Downloads the data identified by the descriptor to the destination_path.
        :param destination_path:
        """
        raise NotImplementedError

    def _post_download(self, download_path=None):
        """
        Method executed after a descriptor has been downloaded successfully.
        :param download_path: The path on disk to which the descriptor is download.
        """
        pass
