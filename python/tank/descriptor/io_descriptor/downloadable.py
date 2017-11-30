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
import uuid

from .base import IODescriptorBase
from ..errors import TankDescriptorError, TankError
from ...util import filesystem

from ... import LogManager
log = LogManager.get_logger(__name__)


class IODescriptorDownloadable(IODescriptorBase):
    """
    Base class for descriptors that can be downloaded locally to a path on disk.

    In order to create a Descriptor associated with data that can
    be downloaded locally to disk, it is necessary to derive from this class.
    By default, the AppStore, Git and Shotgun entity descriptors can be downloaded
    to disk and hence are of type :class: `IODescriptorDownloadable`.

    Descriptor data can be downloaded by invoking the :meth: `download_local` on instances
    of such derived classes. These classes are also expected to implement the
    :meth: `_download_local` and optionally, the :meth: `_post_download`.

    A general implementation of such a Descriptor class will be of the form:

    eg. class MyNewDownloadableDescriptor(IODescriptorDownloadable):
            def _download_local(self, destination_path):
                # .. code to download data to destination_path

            def _post_download(self, download_path):
                # .. code that will be executed post download.
    """
    def download_local(self):
        """
        Downloads the data represented by the descriptor into the primary bundle
        cache path.

        It does so in a two step process. First, by downloading it to
        a temporary bundle cache path (typically in a 'tmp/<uuid>' directory
        in the bundle cache path), then, by moving the data to the primary bundle
        cache path for that descriptor. This helps to guard against multiple
        processes attempting to download the same descriptor simultaneously.
        """

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
                log.error("Failed to create parent directory %s: %s" % (os.path.dirname(target), e))
                raise TankDescriptorError("Failed to create parent directory %s: %s" % (os.path.dirname(target), e))

        try:
            # attempt to download the descriptor to the temporary path.
            log.debug("Downloading %s to the temporary download path %s." % (self, temporary_path))
            self._download_local(temporary_path)
        except Exception as e:
            # something went wrong during the download, remove the temporary files.
            log.error("Failed to download into path %s: %s. Attempting to remove it."
                      % (temporary_path, e))
            filesystem.safe_delete_folder(temporary_path)
            raise TankDescriptorError("Failed to download into path %s: %s" % (temporary_path, e))

        log.debug("Attempting to move descriptor %s from temporary path %s to target path %s." % (
            self, temporary_path, target)
        )
        try:
            # atomically rename the directory temporary_path to the target.
            os.rename(temporary_path, target)
            log.debug("Successfully moved the downloaded descriptor to target path: %s." % target)
        except Exception as e:
            # if the target path does not already exist, something else might have gone wrong.
            if not os.path.exists(target):
                log.error("Failed to move descriptor from the temporary path %s " % temporary_path +
                          " to the bundle cache %s: %s" % (target, e))
                raise TankError("Failed to move descriptor from the temporary path %s " % temporary_path +
                                " to the bundle cache %s: %s" % (target, e))
        else:
            self._post_download(target)
        finally:
            if os.path.exists(temporary_path):
                log.debug("Removing temporary path: %s" % temporary_path)
                filesystem.safe_delete_folder(temporary_path)

    def _get_temporary_cache_path(self):
        """
        Returns a temporary download cache path for this descriptor.
        """
        return os.path.join(self._bundle_cache_root, "tmp", uuid.uuid4().hex)

    def _download_local(self, destination_path):
        """
        Downloads the data identified by the descriptor to the destination_path.

        :param destination_path: The path on disk to which the descriptor is to
        be downloaded.

        eg. If the `destination_path` is
        /shared/bundle_cache/tmp/2f601ff3d85c43aa97d5811a308d99b3 for a git
        tag descriptor, this method is expected to download data directly to
        into the destination path. Thus the .git folder of the descriptor will have
        a path of /shared/bundle_cache/tmp/2f601ff3d85c43aa97d5811a308d99b3/.git
        """
        raise NotImplementedError

    def _post_download(self, download_path):
        """
        Method executed after a descriptor has been downloaded successfully.

        :param download_path: The path on disk to which the descriptor has been
        downloaded.
        """
        pass
