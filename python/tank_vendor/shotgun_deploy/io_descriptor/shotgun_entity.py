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
import tempfile

from .base import IODescriptorBase
from .. import util
from ..zipfilehelper import unzip_file
from ..errors import ShotgunDeployError
from ...shotgun_base import ensure_folder_exists, safe_delete_file

log = util.get_shotgun_deploy_logger()


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

    Url format:

        sgtk:shotgun:PipelineConfiguration:sg_config:primary:p123:v456 (with project id)
        sgtk:shotgun:PipelineConfiguration:sg_config:primary::v456     (without project id)

    """

    def __init__(self, location_dict, sg_connection):
        """
        Constructor

        :param location_dict: Location dictionary describing the bundle
        :param sg_connection: Shotgun connection to associated site
        :return: Descriptor instance
        """
        super(IODescriptorShotgunEntity, self).__init__(location_dict)

        self._validate_locator(
            location_dict,
            required=["type", "entity_type", "name", "version", "field"],
            optional=["project_id"]
        )

        self._sg_connection = sg_connection
        self._entity_type = location_dict.get("entity_type")
        self._name = location_dict.get("name")
        self._version = location_dict.get("version")
        self._field = location_dict.get("field")

        self._project_link = None
        if "project_id" in location_dict:
            self._project_link = {"type": "Project", "id": location_dict["project_id"]}

        self._project_id = location_dict.get("project_id")


    def _get_cache_paths(self):
        """
        Get a list of resolved paths, starting with the primary and
        continuing with alternative locations where it may reside.

        :return: List of path strings
        """
        paths = []

        for root in [self._bundle_cache_root] + self._fallback_roots:
            paths.append(
                os.path.join(
                    root,
                    "sg_upload",
                    self.get_version()
                )
            )
        return paths


    @classmethod
    def dict_from_uri(cls, uri):
        """
        Given a location uri, return a location dict

        :param uri: Location uri string
        :return: Location dictionary
        """
        # sgtk:shotgun:PipelineConfiguration:sg_config:primary:p123:v456 # with project id
        # sgtk:shotgun:PipelineConfiguration:sg_config:primary::v456     # without project id
        #
        # sgtk:shotgun:EntityType:sg_field_name:shotgun_entity_name:pproject_id:vversion_id

        # explode into dictionary
        location_dict = cls._explode_uri(
            uri,
            "shotgun",
            ["entity_type", "field", "name", "project_id", "version"]
        )

        # validate it
        cls._validate_locator(
            location_dict,
            required=["type", "entity_type", "name", "version", "field"],
            optional=["project_id"]
        )

        # version and project_id in the uri needs casting to int and
        # have their prefix stripped

        location_dict["version"] = int(location_dict["version"][1:])

        if "project_id" in location_dict:
            location_dict["project_id"] = int(location_dict["project_id"][1:])

        return location_dict

    @classmethod
    def uri_from_dict(cls, location_dict):
        """
        Given a location dictionary, return a location uri

        :param location_dict: Location dictionary
        :return: Location uri string
        """
        # sgtk:shotgun:PipelineConfiguration:sg_config:primary:p123:v456 # with project id
        # sgtk:shotgun:PipelineConfiguration:sg_config:primary::v456     # without project id
        #
        # sgtk:shotgun:EntityType:sg_field_name:shotgun_entity_name:pproject_id:vversion_id

        cls._validate_locator(
            location_dict,
            required=["type", "entity_type", "name", "version", "field"],
            optional=["project_id"]
        )

        uri = [
            "shotgun",
            location_dict["entity_type"],
            location_dict["field"],
            location_dict["name"],
            "p%s" % (location_dict.get("project_id") or ""),
            "v%s" % location_dict["version"]
        ]

        return cls._make_uri_from_chunks(uri)

    def get_system_name(self):
        """
        Returns a short name, suitable for use in configuration files
        and for folders on disk, e.g. 'tk-maya'
        """
        if self._project_id:
            name = "p%s_%s" % (self._project_id, self._name)
        else:
            name = self._name
        return util.create_valid_filename(name)

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
        target = self._get_cache_paths()[0]
        ensure_folder_exists(target)

        # and now for the download.
        # @todo: progress feedback here - when the SG api supports it!
        # sometimes people report that this download fails (because of flaky connections etc)
        log.debug("Downloading attachment %s..." % self._version)
        try:
            bundle_content = self._sg_connection.download_attachment(self._version)
        except Exception, e:
            # retry once
            log.debug("Downloading failed, retrying. Error: %s" % e)
            bundle_content = self._sg_connection.download_attachment(self._version)

        zip_tmp = os.path.join(tempfile.gettempdir(), "%s_tank.zip" % uuid.uuid4().hex)
        fh = open(zip_tmp, "wb")
        fh.write(bundle_content)
        fh.close()

        # unzip core zip file to app target location
        log.debug("Unpacking %s bytes to %s..." % (os.path.getsize(zip_tmp), target))
        unzip_file(zip_tmp, target)

        # clear temp file
        safe_delete_file(zip_tmp)


    def get_latest_version(self, constraint_pattern=None):
        """
        Returns a descriptor object that represents the latest version.

        :param constraint_pattern: If this is specified, the query will be constrained
               by the given pattern. Version patterns are on the following forms:

                - v0.1.2, v0.12.3.2, v0.1.3beta - a specific version
                - v0.12.x - get the highest v0.12 version
                - v1.x.x - get the highest v1 version

        :returns: descriptor object
        """
        if constraint_pattern:
            raise ShotgunDeployError(
                "%s does not support version constraint patterns." % self
            )

        log.debug("Finding latest version of %s..." % self)

        # in the case of a pipeline configuration, simply fetch the current pipeline configuration attachment
        # and build a descriptor based on that

        filters = [["code", "is", self._name]]
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
            raise ShotgunDeployError(
                "Cannot find a pipeline configuration named '%s'!" % self._name
            )

        if data[self._field].get("link_type") != "upload":
            raise ShotgunDeployError(
                "Latest version of %s is not an uploaded file: %s" % (self, data)
            )

        attachment_id = data[self._field]["id"]

        # make a location dict
        location_dict = {
            "type": "shotgun",
            "entity_type": self._entity_type,
            "field": self._field,
            "name": self._name,
            "version": attachment_id
        }

        if self._project_link:
            location_dict[self._project_id] = self._project_id

        # and return a descriptor instance
        desc = IODescriptorShotgunEntity(location_dict, self._sg_connection)
        desc.set_cache_roots(self._bundle_cache_root, self._fallback_roots)

        log.debug("Latest version resolved to %s" % desc)
        return desc
