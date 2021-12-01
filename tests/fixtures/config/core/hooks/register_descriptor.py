# Copyright (c) 2020 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
This hook is used override some of the functionality of the :class:`~sgtk.bootstrap.ToolkitManager`.

It will be instantiated only after a configuration has been selected by the :class:`~sgtk.bootstrap.ToolkitManager`.
Therefore, this hook will not be invoked to download a configuration. However, the Toolkit Core,
applications, frameworks and engines can be downloaded through the hook.
"""
import os

from sgtk import get_hook_baseclass
from sgtk.descriptor.io_descriptor.downloadable import IODescriptorDownloadable
from sgtk.descriptor.errors import TankError, TankDescriptorError
from sgtk.util.shotgun import download


class IODescriptorBitbucketRelease(IODescriptorDownloadable):
    def __init__(self, descriptor_dict, sg_connection, bundle_type):
        """
        Constructor

        :param descriptor_dict: descriptor dictionary describing the bundle
        :param sg_connection: Shotgun connection to associated site.
        :param bundle_type: Either AppDescriptor.APP, CORE, ENGINE or FRAMEWORK.
        :return: Descriptor instance
        """
        super(IODescriptorBitbucketRelease, self).__init__(
            descriptor_dict, sg_connection, bundle_type
        )
        self._validate_descriptor(
            descriptor_dict,
            required=["type", "organization", "repository", "version"],
            optional=[],
        )
        self._sg_connection = sg_connection
        self._bundle_type = bundle_type
        self._organization = descriptor_dict["organization"]
        self._repository = descriptor_dict["repository"]
        self._version = descriptor_dict["version"]

    def _get_bundle_cache_path(self, bundle_cache_root):
        """
        Given a cache root, compute a cache path suitable
        for this descriptor, using the 0.18+ path format.

        :param bundle_cache_root: Bundle cache root path
        :return: Path to bundle cache location
        """
        return os.path.join(
            bundle_cache_root,
            "bitbucket",
            self._organization,
            self.get_system_name(),
            self.get_version(),
        )

    def get_system_name(self):
        """
        Returns a short name, suitable for use in configuration files
        and for folders on disk, e.g. 'tk-maya'
        """
        return self._repository

    def get_version(self):
        """
        Returns the version number string for this item.
        In this case, this is the linked shotgun attachment id.
        """
        return self._version

    def _download_local(self, destination_path):
        """
        Retrieves this version to local repo.
        Will exit early if app already exists local.

        :param destination_path: The directory path to which the shotgun entity is to be
        downloaded to.
        """
        url = "https://bitbucket.org/{organization}/{system_name}/get/{version}.zip"
        url = url.format(
            organization=self._organization,
            system_name=self.get_system_name(),
            version=self.get_version(),
        )

        try:
            download.download_and_unpack_url(
                self._sg_connection, url, destination_path, auto_detect_bundle=True
            )
        except TankError as e:
            raise TankDescriptorError(
                "Failed to download %s from %s. Error: %s" % (self, url, e)
            )


class MyCustomRegisterDescriptorsHook(get_hook_baseclass()):
    def register_io_descriptors(self):
        # To register the default IODescriptor classes
        super(MyCustomRegisterDescriptorsHook, self).register_io_descriptors()
        self.io_descriptor_base.register_descriptor_factory(
            "bitbucket_release", IODescriptorBitbucketRelease
        )
