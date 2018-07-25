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


class BootstrapHook(get_hook_baseclass()):
    """
    This is an example of a descriptor operations hook. It downloads a bundle
    from the local site if it is found there and from a remote location if
    credentials are found on the pipeline configuration object.
    """

    def init(self, shotgun, pipeline_configuration, configuration_descriptor):
        super(BootstrapHook, self).init(shotgun, pipeline_configuration, configuration_descriptor)

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

    def download_bundle(self, descriptor):
        # First try to download from the local cache.
        if self._download_from_sg_cache(self.shotgun, descriptor):
            return

        # Then try to download the from remote cache.
        if self._remote_sg and self._download_from_sg_cache(self._remote_sg, descriptor):
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
            "CustomNonProjectEntity01",
            [["code", "is", descriptor.get_uri()]], ["sg_uploaded_bundle"]
        )
        if not entity:
            return False

        # When calling external_download, the method yields to us
        # a path that needs to be filled with the files. If the
        # with ends normally, the files are copied into the cache.
        # In an exception is raised, the files are deleted and the exception
        # bubbles upward.
        with descriptor.external_download() as external_path:
            download_and_unpack_attachment(shotgun, entity["sg_uploaded_bundle"], external_path)

        return True
