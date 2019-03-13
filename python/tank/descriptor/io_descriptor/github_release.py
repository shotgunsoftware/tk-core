# Copyright (c) 2016 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.
from ...util.shotgun import download

import json
import os
import urllib2

from .downloadable import IODescriptorDownloadable
from ..errors import TankError, TankDescriptorError
from ... import LogManager

log = LogManager.get_logger(__name__)


class IODescriptorGithubRelease(IODescriptorDownloadable):
    """
    Represents a shotgun entity to which apps have been attached.
    This can be an attachment field on any entity. Typically it will be
    a pipeline configuration. In that configuration, the descriptor represents
    a 'cloud based configuration'. It could also be a custom entity or non-project
    entity in the case you want to store a descriptor (app, engine or config)
    that can be easily accessed from any project.

    There are two ways of addressing an entity.

    {
     type: shotgun,
     entity_type: CustomEntity01,   # entity type
     name: tk-foo,                  # name of the record in shotgun (i.e. 'code' field)
     project_id: 123,               # optional project id. If omitted, name is assumed to be unique.
     field: sg_config,              # attachment field where payload can be found
     version: 456                   # attachment id of particular attachment
    }

    or

    {
     type: shotgun,
     entity_type: CustomEntity01,   # entity type
     id: 123,                       # id of the record in shotgun (i.e. 'id' field)
     field: sg_config,              # attachment field where payload can be found
     version: 456                   # attachment id of particular attachment
    }

    This can for example be used for attaching items to a pipeline configuration.
    Create an attachment field named sg_config, upload a zip file, and use the following
    descriptor:

    {type: shotgun, entity_type: PipelineConfiguration,
     name: primary, project_id: 123, field: sg_config, version: 1341}

    When a new zip file is uploaded, the attachment id (e.g. version) changes, resulting in
    a new descriptor.

    The latest version is defined as the current record available in Shotgun.
    """

    def __init__(self, descriptor_dict, sg_connection):
        """
        Constructor

        :param descriptor_dict: descriptor dictionary describing the bundle
        :param sg_connection: Shotgun connection to associated site
        :return: Descriptor instance
        """
        super(IODescriptorGithubRelease, self).__init__(descriptor_dict)
        self._validate_descriptor(
            descriptor_dict,
            required=["type", "organization", "repository", "version"],
            optional=[]
        )
        # @todo: validation, check for illegal chars, etc perhaps
        self._sg_connection = sg_connection
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
            "github",
            self._organization,
            self.get_system_name(),
            self.get_version()
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
        # @todo: should we use Github API to get the zipball URL in case this URL changes in
        # the future?  would mean an additional transaction (to get URL) but would mean
        # only API changes would cause this to stop working.
        url = "https://github.com/{organization}/{system_name}/archive/{version}.zip"
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

    def _get_github_release_versions(self, latest_only=False):
        url = "https://api.github.com/repos/{organization}/{system_name}/releases"
        url = url.format(organization=self._organization, system_name=self.get_system_name())
        if latest_only:
            url += "/latest"
        
        try:
            response = urllib2.urlopen(url)
            # @todo this will only load a max of 30 releases -- if more releases exist
            # a ?page=2 url will be included in the "link" field in the response
            # headers.  We can continue to get more as needed when applying a constraint
            # pattern, working under the assumption that release ordering chronologically
            # and numerically will be identical.
            response_data = json.load(response)
        except urllib2.URLError as e:
            raise TankDescriptorError("Unable to contact Github API: %s" % e)
        except urllib2.HTTPError as e:
            if e.code == 404:
                # Github API gives a 404 when no releases have been published
                return []
            else:
                raise TankDescriptorError("Error communicatingh with Github API: %s" % e)
        # zipballs are stored under the tag name, not the release name,
        # so that's the "version" name we want
        if latest_only:
            return [response_data["tag_name"]]
        return [release["tag_name"] for release in response_data]

    def get_latest_version(self, constraint_pattern=None):
        """
        Returns a descriptor object that represents the latest version.

        .. note:: The concept of constraint patterns doesn't apply to
                  shotgun attachment ids and any data passed via the
                  constraint_pattern argument will be ignored by this
                  method implementation.

        :param constraint_pattern: This parameter is unused and remains here to be compatible
            with the expected signature for this method.

        :returns: IODescriptorShotgunEntity object
        """
        if constraint_pattern:
            versions = self._get_github_release_versions()
            version = self._find_latest_tag_by_pattern(versions, constraint_pattern)
        else:
            version = self._get_github_release_versions(latest_only=True)
        if version is None or version == self.get_version():
            # there is no latest release, or the latest release is this one, so return this descriptor.
            return self
        # otherwise generate a descriptor for the version we found
        descriptor_dict = {
            "organization": self._organization,
            "repository": self.get_system_name(),
            "version": version,
        }
        return IODescriptorGithubRelease(descriptor_dict, self._sg_connection)

    def get_latest_cached_version(self, constraint_pattern=None):
        """
        Returns a descriptor object that represents the latest version
        that is locally available in the bundle cache search path.

        .. note:: The concept of constraint patterns doesn't apply to
                  shotgun attachment ids and any data passed via the
                  constraint_pattern argument will be ignored by this
                  method implementation.

        :param constraint_pattern: This parameter is unused and remains here to be compatible
            with the expected signature for this method.

        :returns: instance deriving from IODescriptorBase or None if not found
        """
        if constraint_pattern:
            log.warning("%s does not support version constraint patterns." % self)

        # not possible to determine what 'latest' means in this case
        # so check if the current descriptor exists on disk and in this
        # case return it
        if self.get_path():
            return self
        else:
            # no cached version exists
            return None
        

    def has_remote_access(self):
        """
        Probes if the current descriptor is able to handle
        remote requests. If this method returns, true, operations
        such as :meth:`download_local` and :meth:`get_latest_version`
        can be expected to succeed.

        :return: True if a remote is accessible, false if not.
        """
        # check if we can connect to Shotgun
        can_connect = True
        try:
            log.debug("%r: Probing if a connection to Github can be established..." % self)
            pass
            # @todo: check GH connection
            log.debug("...connection established!")
        except Exception as e:
            log.debug("...could not establish connection: %s" % e)
            can_connect = False
        return can_connect
