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


class BootstrapHook(get_hook_baseclass()):
    """
    The bootstrap hook can be added to a configuration's core hooks folder
    (``core/hooks``) in order to override some of the functionality of
    the ToolkitManager's bootstrapping process.

    The hook will be instantiated only after a configuration has been selected
    by the ``ToolkitManager``. Therefore, this hook will not be invoked to download
    a configuration. However, the Toolkit Core, applications, frameworks and
    engines will be downloaded through the hook.
    """

    def init(self, shotgun, pipeline_configuration_id, configuration_descriptor, **kwargs):
        """
        This method is invoked when the hook is instantiated.

        It can be used to cache information so it can be reused, for example a
        shotgun connection to external site.

        The ``kwargs`` is there for forward compatibility with future versions of Toolkit.

        :param shotgun: Connection to the Shotgun site.
        :type shotgun: :class:`shotgun_api3.Shotgun`

        :param pipeline_configuration_id: Id of the pipeline configuration we're bootstrapping into.
            If None, the ToolkitManager is bootstrapping into the base configuration.
        :type pipeline_configuration_id: int

        :param configuration_descriptor: Configuration the manager is bootstrapping into.
        :type configuration_descriptor: :class:`sgtk.descriptor.ConfigDescriptor`
        """
        self.shotgun = shotgun
        self.pipeline_configuration_id = pipeline_configuration_id
        self.configuration_descriptor = configuration_descriptor

    def can_cache_bundle(self, descriptor):
        """
        Indicates if a bundle can be cached by the ``populate_bundle_cache_entry`` method.

        This method is invoked when the bootstrap manager wants to a bundle used by a configuration.

        :param descriptor: Descriptor of the bundle that needs to be cached.
        :type descriptor: :class:`~sgtk.descriptor.Descriptor`

        :returns: ``True`` if the bundle cache be cached, ``False`` if not.
        :rtype: bool
        """
        return False

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
        raise NotImplementedError("BootstrapHook.populate_bundle_cache_entry is not implemented.")

# The following is an example of how you can use this hook to download
# applications that are uploaded to a custom entity in Shotgun. Copy this
# file into your core/hooks folder and

# class BootstrapHook(get_hook_baseclass()):
#     """
#     This is an example of a descriptor operations hook. It downloads a bundle
#     from the local site if it is found.
#     """
#
#     def can_cache_bundle(self, descriptor):
#         # Returns true if the descriptor has been cached in Shotgun.
#         return True if self._get_bundle_attachment(descriptor) else False
#
#     def _get_bundle_attachment(self, descriptor):
#         # Finds the bundle in Shotgun, if available.
#         # This method gets invoked twice by the bootstrap hook, but will only be
#         # invoked if the bundle is missing from disk so its not worth putting a
#         # caching system in place for the method.
#         entity = self.shotgun.find_one(
#             "CustomNonProjectEntity01",
#             [["code", "is", descriptor.get_uri()]], ["sg_uploaded_bundle"]
#         )
#         if not entity:
#             return None
#         else:
#             return entity["sg_uploaded_bundle"]
#
#     def populate_bundle_cache_entry(self, destination, descriptor, **kwargs):
#         """
#         Populates an entry from the bundle cache.
#
#         This method will be invoked for every bundle for which the method ``can_cache_bundle``
#         returned ``True``.
#
#         :param destination: Folder where the bundle needs to be written. Note that this is not
#             the final destination folder inside the bundle cache.
#
#         :param descriptor: Descriptor of the bundle that needs to be cached.
#         :type descriptor: :class:`~sgtk.descriptor.Descriptor`
#         """
#         attachment = self._get_bundle_attachment(descriptor)
#         download_and_unpack_attachment(self.shotgun, attachment, destination)
#         self.logger.info("Bundle %s was downloaded from %s." % (descriptor.get_uri(), self.shotgun.base_url))
