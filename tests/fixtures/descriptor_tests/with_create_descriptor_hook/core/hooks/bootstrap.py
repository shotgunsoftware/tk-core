# Copyright (c) 2018 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from sgtk import get_hook_baseclass
from sgtk.util.shotgun import download_and_unpack_attachment


class BootstrapHook(get_hook_baseclass()):
    """
    This is an example of a descriptor operations hook. It downloads a bundle
    from the local site if it is found.
    """
    def download_bundle(self, descriptor):
        """
        Downloads a bundle from a Shotgun site.

        :param descriptor: Descriptor that needs to be downloaded.
        :type descriptor: :class:`~sgtk.descriptor.Descriptor`
        """

        # Get the uri form the descriptor.
        entity = self.shotgun.find_one(
            "CustomNonProjectEntity01",
            [["code", "is", descriptor.get_uri()]], ["sg_uploaded_bundle"]
        )
        if not entity:
            self.logger.info("Bundle %s was not found in the site cache for %s." % (
                descriptor.get_uri(), self.shotgun.base_url)
            )
            return descriptor.download_local()

        # When calling _open_write_location, the method yields to us
        # a path that needs to be filled with the files. If the
        # with ends normally, the files are copied into the cache.
        # In an exception is raised, the files are deleted and the exception
        # bubbles upward.
        with self._open_write_location(descriptor) as write_location:
            download_and_unpack_attachment(self.shotgun, entity["sg_uploaded_bundle"], write_location)

        self.logger.info("Bundle %s was downloaded from %s." % (descriptor.get_uri(), self.shotgun.base_url))
        return True
