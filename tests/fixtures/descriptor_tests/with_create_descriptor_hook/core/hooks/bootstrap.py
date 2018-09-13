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

    def can_cache_bundle(self, descriptor):
        # Returns true if the descriptor has been cached in Shotgun.
        return True if self._get_bundle_attachment(descriptor) else False

    def _get_bundle_attachment(self, descriptor):
        # Finds the bundle in Shotgun, if available.
        # This method gets invoked twice by the bootstrap hook, but will only be
        # invoked if the bundle is missing from disk so its not worth putting a
        # caching system in place for the method.
        entity = self.shotgun.find_one(
            "CustomNonProjectEntity01",
            [["code", "is", descriptor.get_uri()]], ["sg_uploaded_bundle"]
        )
        if entity:
            return entity["sg_uploaded_bundle"]
        else:
            return None

    def populate_bundle_cache_entry(self, destination, descriptor, **kwargs):
        """
        Populates an entry from the bundle cache.

        This method will be invoked for every bundle for which the method ``can_cache_bundle``
        returned ``True``.

        :param destination: Folder where the bundle needs to be written. Note that this is not
            the final destination folder inside the bundle cache.

        :param descriptor: Descriptor of the bundle that needs to be cached.
        :type descriptor: :class:`~sgtk.descriptor.Descriptor`
        """
        attachment = self._get_bundle_attachment(descriptor)
        download_and_unpack_attachment(self.shotgun, attachment, destination)
        self.logger.info("Bundle %s was downloaded from %s." % (descriptor.get_uri(), self.shotgun.base_url))
