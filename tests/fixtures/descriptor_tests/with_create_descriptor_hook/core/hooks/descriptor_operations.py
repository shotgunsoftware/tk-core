# Copyright (c) 2018 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from tank_vendor.shotgun_api3 import Shotgun
from sgtk import get_hook_baseclass
from sgtk.util.shotgun import download_and_unpack_attachment


class DescriptorOperationsHook(get_hook_baseclass()):
    """
    This is an example of a descriptor operations hook. It downloads a bundle
    from the local site if it is found there and from a remote location if
    credentials are found on the pipeline configuration object.

    The descriptor operations hook will be instantiated at least once during
    bootstrap, which means it can retain state between calls.

    The following list of attributes are always available on the hook.

    :attribute shotgun: Connection to the Shotgun site.
    :type shotgun: :class:`shotgun_api3.Shotgun`

    :attribute pipeline_configuration_id: Id of the pipeline configuration we're bootstrapping into.
        If None, the ToolkitManager is bootstrapping into the base configuration.
    :type pipeline_configuration_id: int

    :attribute configuration_descriptor: Configuration the manager is bootstrapping into.
    :type configuration_descriptor: :class:`sgtk.descriptor.ConfigDescriptor`
    """

    def init(self):
        """
        This method is invoked when the hook is instantiated.

        It can be used to cache information so it can be reused for each
        operations.
        """

        # - shotgun: connection to the Shotgun site.
        # - pipeline_configuration_id: If set, this is the id of the pipeline configuration
        #                              that we're bootstrapping into
        # - configuration_descriptor: The descriptor for the configuration we're bootstrapping
        #                             into.

        # Let's pretend someone wants a local cache and a remote cache and they've
        # decided to store the remote credentials on the pipeline configuration
        # object.

        # Grab the external site credentials from the pipeline configuration.
        pc = self.shotgun.find_one(
            "PipelineConfiguration",
            [["id", "is", self.pipeline_configuration_id]],
            ["sg_external_site_credentials"]
        )

        # If we've found something, create a connection to that remote site,
        # but do not connect right away.
        if pc and pc.get("sg_external_site_credentials"):
            self._remote_sg = Shotgun(connect=False, **pc["sg_external_site_credentials"])
        else:
            self._remote_sg = None

    def download_local(self, descriptor):
        """
        This method is invoked during bootstrapping when downloading the core or
        the bundles in the environment from the configuration.

        Your method must download the descriptor's content before the method
        ends of the bootstrap manager will report an error.

        The safest way to download a bundle into the bundle cache is by using the
        :meth:`sgtk.descriptor.Descriptor.external_download` context manager.

        Any exception raised by this code will abort the bootstrap process.

        :param descriptor: The descriptor that will be downloaded.
        :type descriptor: :class:`~sgtk.descriptor.Descriptor`
        """

        # First try to download from the local cache.
        if self._download_from_sg_cache(self.shotgun, descriptor):
            return

        # Then try to download the from remote cache.
        if self._download_from_sg_cache(self._remote_sg, descriptor):
            return

        # Give up, we're going to talk to the source.
        descriptor.download_local()

    def _download_from_sg_cache(self, shotgun, descriptor):
        """
        Downloads a bundle from a Shotgun site.

        :param shotgun: Connection to the site to download from.
        :type shotgun: :class:`shotgun_api3.Shotgun`

        :param descriptor: Descriptor that needs to be downloaded.
        :type descriptor: :class:`~sgtk.descriptor.Descriptor`

        :returns: Returns ``True`` is something was downloaded.
        :rtype: bool
        """

        # Get the uri form the descriptor. We'll have to make sure that descriptor values
        # after the ? are always sorted the same or this will be an issue.
        entity = shotgun.find_one(
            "CustomEntity05",
            [["code", "is", descriptor.get_uri()]], "sg_bundle"
        )
        if not entity:
            return False

        # When calling external_download, the method yields to us
        # a path that needs to be filled with the files. If the
        # with ends normally, the files are copied into the cache.
        # In an exception is raised, the files are deleted and the exception
        # bubbles upward.
        with descriptor.external_download() as external_path:
            download_and_unpack_attachment(shotgun, entity, external_path)

        return True
