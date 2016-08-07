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

from .base import IODescriptorBase
from ...util import filesystem, shotgun
from ...util.errors import ShotgunAttachmentDownloadError
from ..errors import TankDescriptorError
from ... import LogManager

log = LogManager.get_logger(__name__)

class IODescriptorShotgunEntity(IODescriptorBase):
    """
    Represents a shotgun entity to which apps have been attached.
    This can be an attachment field on any entity. Typically it will be
    a pipeline configuration. In that configuration, the descriptor represents
    a 'cloud based configuration'. It could also be a custom entity or non-project
    entity in the case you want to store a descriptor (app, engine or config)
    that can be easily accessed from any project.

    {
     type: shotgun,
     entity_type: CustomEntity01,   # entity type
     name: tk-foo,                  # name of the record in shotgun (e.g. 'code' field)
     project_id: 123,               # optional project id. If omitted, name is assumed to be unique.
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
        super(IODescriptorShotgunEntity, self).__init__(descriptor_dict)

        self._validate_descriptor(
            descriptor_dict,
            required=["type", "entity_type", "name", "version", "field"],
            optional=["project_id"]
        )

        self._sg_connection = sg_connection
        self._entity_type = descriptor_dict.get("entity_type")
        self._name = descriptor_dict.get("name")
        self._version = descriptor_dict.get("version")
        self._field = descriptor_dict.get("field")

        self._project_link = None
        if "project_id" in descriptor_dict:
            self._project_link = {"type": "Project", "id": descriptor_dict["project_id"]}

        self._project_id = descriptor_dict.get("project_id")

    def _get_bundle_cache_path(self, bundle_cache_root):
        """
        Given a cache root, compute a cache path suitable
        for this descriptor, using the 0.18+ path format.

        :param bundle_cache_root: Bundle cache root path
        :return: Path to bundle cache location
        """
        return os.path.join(
            bundle_cache_root,
            "sg_upload",
            self.get_version()
        )

    def get_system_name(self):
        """
        Returns a short name, suitable for use in configuration files
        and for folders on disk, e.g. 'tk-maya'
        """
        if self._project_id:
            name = "p%s_%s" % (self._project_id, self._name)
        else:
            name = self._name
        return filesystem.create_valid_filename(name)

    def get_version(self):
        """
        Returns the version number string for this item.
        In this case, this is the linked shotgun attachment id.
        """
        return "v%s" % self._version

    def download_local(self):
        """
        Retrieves this version to local repo.
        Will exit early if app already exists local.
        """
        if self.exists_local():
            # nothing to do!
            return

        # cache into the primary location
        target = self._get_primary_cache_path()

        try:
            shotgun.download_and_unpack_attachment(self._sg_connection, self._version, target)
        except ShotgunAttachmentDownloadError, e:
            raise TankDescriptorError(
                "Failed to download %s from %s. Error: %s" % (self, self._sg_connection.base_url, e)
            )


    def get_latest_version(self, constraint_pattern=None):
        """
        Returns a descriptor object that represents the latest version.

        .. note:: The concept of constraint patterns doesn't apply to
                  shotgun attachment ids and any data passed via the
                  constraint_pattern argument will be ignored by this
                  method implementation.

        :param constraint_pattern: If this is specified, the query will be constrained
               by the given pattern. Version patterns are on the following forms:

                - v0.1.2, v0.12.3.2, v0.1.3beta - a specific version
                - v0.12.x - get the highest v0.12 version
                - v1.x.x - get the highest v1 version

        :returns: IODescriptorShotgunEntity object
        """
        if constraint_pattern:
            log.warning("%s does not support version constraint patterns." % self)

        log.debug("Finding latest version of %s..." % self)

        # in the case of a pipeline configuration, simply fetch the current pipeline configuration attachment
        # and build a descriptor based on that
        spec_name_fields = {
            "Project": "name",
            "Task": "content",
            "HumanUser": "name"
        }
        name_field = spec_name_fields.get(self._entity_type, "code")

        filters = [[name_field, "is", self._name]]

        if self._project_link:
            filters.append(["project", "is", self._project_link])

        data = self._sg_connection.find_one(self._entity_type, filters, [self._field])

        # attachment field is on the following form in the case a file has been
        # uploaded:
        #  {'name': 'v1.2.3.zip',
        #  'url': 'https://sg-media-usor-01.s3.amazonaws.com/...',
        #  'content_type': 'application/zip',
        #  'type': 'Attachment',
        #  'id': 139,
        #  'link_type': 'upload'}

        if data is None:
            raise TankDescriptorError(
                "Cannot find a pipeline configuration named '%s'!" % self._name
            )

        if data[self._field].get("link_type") != "upload":
            raise TankDescriptorError(
                "Latest version of %s is not an uploaded file: %s" % (self, data)
            )

        attachment_id = data[self._field]["id"]

        # make a descriptor dict
        descriptor_dict = {
            "type": "shotgun",
            "entity_type": self._entity_type,
            "field": self._field,
            "name": self._name,
            "version": attachment_id
        }

        if self._project_link:
            descriptor_dict[self._project_id] = self._project_id

        # and return a descriptor instance
        desc = IODescriptorShotgunEntity(descriptor_dict, self._sg_connection)
        desc.set_cache_roots(self._bundle_cache_root, self._fallback_roots)

        log.debug("Latest version resolved to %s" % desc)
        return desc

