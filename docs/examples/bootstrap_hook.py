# Copyright (c) 2018 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

# This file is included in the sphinx documentation as an example. Keep this in mind
# when editing it.

# Everything after this line will be part of the documentation. #documentationStart
from sgtk import get_hook_baseclass
from sgtk.util.shotgun import download_and_unpack_attachment


# By using sgtk.get_hook_baseclass instead of deriving from sgtk.Hook, we'll be
# getting the default hook's init method for free.
class Bootstrap(get_hook_baseclass()):
    """
    This hook allows to download certain bundles from Shotgun instead of
    official source for the bundle.
    """
    def can_cache_bundle(self, descriptor):
        """
        Returns true if the descriptor has been cached in Shotgun.

        :param descriptor: Descriptor of the bundle that needs to be cached.
        :type descriptor: :class:`~sgtk.descriptor.Descriptor`

        :returns: ``True`` if the bundle is cached in Shotgun, ``False`` otherwise.
        """
        return bool(
            descriptor.get_dict()["type"] in ["app_store", "git"] and
            self._get_bundle_attachment(descriptor)
        )

    def _get_bundle_attachment(self, descriptor):
        """
        Retrieves the attachment associated to this descriptor in Shotgun.

        :param descriptor: Descriptor of the bundle that needs to be cached.
        :type descriptor: :class:`~sgtk.descriptor.Descriptor`

        :returns: The attachment entity dict.
        :rtype: dict
        """
        # This method gets invoked twice by the bootstrap hook, but will only be
        # invoked if the bundle is missing from disk so it is not worth putting a
        # caching system in place for the method.

        # We're using the descriptor uri, i.e.
        # sgtk:descriptor:app_store?name=tk-core&version=v0.18.150,
        # as the code for the entity. If an entry is found and there is an
        # attachment, the bundle can be downloaded from Shotgun.
        #
        # You could write a script that introspects a configuration,
        # extracts all bundles that need to be cached into Shotgun and pushes
        # them to Shotgun. Part of this workflow can be automated with the
        # ``developer/populate_bundle_cache.py`` script, which will download
        # locally every single bundle for a given config.
        entity = self.shotgun.find_one(
            "CustomNonProjectEntity01",
            [["sg_descriptor", "is", descriptor.get_uri()]], ["sg_content"]
        )
        if entity:
            return entity["sg_content"]
        else:
            return None

    def populate_bundle_cache_entry(self, destination, descriptor, **kwargs):
        """
        This method will retrieve the bundle from the Shotgun site and unpack it
        in the destination folder.

        :param destination: Folder where the bundle needs to be written. Note
            that this is not the final destination folder inside the bundle
            cache.

        :param descriptor: Descriptor of the bundle that needs to be cached.
        :type descriptor: :class:`~sgtk.descriptor.Descriptor`
        """
        attachment = self._get_bundle_attachment(descriptor)
        download_and_unpack_attachment(self.shotgun, attachment, destination)
        self.logger.info(
            "Bundle %s was downloaded from %s.",
            descriptor.get_uri(), self.shotgun.base_url
        )
# Everything after this line will not be part of the documentation. #documentationEnd
