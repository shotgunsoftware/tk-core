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

import cPickle as pickle

from ..zipfilehelper import unzip_file
from .base import IODescriptorBase

from .. import constants

from ..errors import ShotgunDeployError
from ...shotgun_base import ensure_folder_exists


from .. import util

# use api json to cover py 2.5
from ... import shotgun_api3
json = shotgun_api3.shotgun.json

log = util.get_shotgun_deploy_logger()

METADATA_FILE = ".cached_metadata.pickle"


class IODescriptorShotgunEntity(IODescriptorBase):
    """
    Represents a shotgun entity to which apps have been attached.

    {type: shotgun, entity_type: CustomEntity01, name: tk-foo, version: v0.1.2}
    """

    def __init__(self, bundle_cache_root, location_dict, sg_connection):
        """
        Constructor

        :param bundle_cache_root: Location on disk where items are cached
        :param location_dict: Location dictionary describing the bundle
        :param sg_connection: Shotgun connection to associated site
        :return: Descriptor instance
        """
        super(IODescriptorShotgunEntity, self).__init__(bundle_cache_root, location_dict)

        self._sg_connection = sg_connection
        self._entity_type = location_dict.get("entity_type")
        self._name = location_dict.get("name")
        self._version = location_dict.get("version")
        # cached metadata - loaded on demand
        self.__cached_metadata = None

    def _get_app_store_metadata(self):
        """
        Returns a metadata dictionary for this particular location.
        The manner in which this is being retrieved depends on the state of the descriptor.

        - First it will see if it has already been loaded into this class instance. In that
          case it will make a copy of the dict and return that.
        - Secondly it will look for a local cache file. This is normally present if the
          app/engine is installed locally.
        - Failing this, it will connect to shotgun and download it from the app store.
        """

        if self.__cached_metadata is None:
            # no locally loaded. Try to load from disk
            cache_file = os.path.join(self.get_path(), METADATA_FILE)
            if os.path.exists(cache_file):
                # try to load
                try:
                    fp = open(cache_file, "rt")
                    self.__cached_metadata = pickle.load(fp)
                    fp.close()
                except Exception:
                    pass

        if self.__cached_metadata is None:
            # load from disk failed. Get from shotgun
            self.__cached_metadata = self.__download_app_store_metadata()

        # finally return the data!
        return self.__cached_metadata

    def __download_app_store_metadata(self):
        """
        Fetches metadata about the app from the tank app store
        returns a dictionary with a bundle key and a version key.
        """
        data = self._sg_connection.find_one(
            self._entity_type,
            [["code", "is", self._name],
             [constants.ENTITY_DESCRIPTOR_VERSION_FIELD , "is", self._version]],
            ["description", constants.ENTITY_DESCRIPTOR_PAYLOAD_FIELD]
        )

        if data is None:
            raise ShotgunDeployError("%s not found in %s" % (self._location_dict, self._sg_connection.base_url))

        if data[constants.ENTITY_DESCRIPTOR_PAYLOAD_FIELD] is None:
            raise ShotgunDeployError("Cannot find zip contents for %s" % self._location_dict)

        # cache it on disk
        folder = self.get_path()

        try:
            ensure_folder_exists(folder)
            fp = open(os.path.join(folder, METADATA_FILE), "wt")
            pickle.dump(data, fp)
            fp.close()
        except Exception:
            # fail gracefully - this is only a cache!
            pass

        return data


    ###############################################################################################
    # data accessors

    def get_system_name(self):
        """
        Returns a short name, suitable for use in configuration files
        and for folders on disk
        """
        return self._name

    def get_version(self):
        """
        Returns the version number string for this item
        """
        return self._version

    def get_path(self):
        """
        returns the path to the folder where this item resides
        """
        return self._get_local_location("sg", self.get_system_name(), self.get_version())

    def get_changelog(self):
        """
        Returns information about the changelog for this item.
        Returns a tuple: (changelog_summary, changelog_url). Values may be None
        to indicate that no changelog exists.
        """
        summary = None
        metadata = self._get_app_store_metadata()
        try:
            summary = metadata.get("description")
        except:
            pass
        return (summary, None)

    def download_local(self):
        """
        Retrieves this version to local repo.
        Will exit early if app already exists local.
        """
        if self.exists_local():
            # nothing to do!
            return

        target = self.get_path()
        ensure_folder_exists(target)

        # get metadata from sg...
        metadata = self._get_app_store_metadata()

        # attachment field is on the following form in the case a file has been uploaded:
        #  {'name': 'v1.2.3.zip',
        #  'url': 'https://sg-media-usor-01.s3.amazonaws.com/...',
        #  'content_type': 'application/zip',
        #  'type': 'Attachment',
        #  'id': 139,
        #  'link_type': 'upload'}
        attachment_id = metadata[constants.ENTITY_DESCRIPTOR_PAYLOAD_FIELD]["id"]

        # and now for the download.
        # @todo: progress feedback here - when the SG api supports it!
        # sometimes people report that this download fails (because of flaky connections etc)
        # engines can often be 30-50MiB - as a quick fix, just retry the download once
        # if it fails.
        try:
            bundle_content = self._sg_connection.download_attachment(attachment_id)
        except:
            # retry once
            bundle_content = self._sg_connection.download_attachment(attachment_id)

        zip_tmp = os.path.join(tempfile.gettempdir(), "%s_tank.zip" % uuid.uuid4().hex)
        fh = open(zip_tmp, "wb")
        fh.write(bundle_content)
        fh.close()

        # unzip core zip file to app target location
        unzip_file(zip_tmp, target)


    #############################################################################
    # searching for other versions

    def get_latest_version(self, constraint_pattern=None):
        """
        Returns a descriptor object that represents the latest version.
        
        This method is useful if you know the name of an app (after browsing in the
        app store for example) and want to get a formal "handle" to it.
        
        :param constraint_pattern: If this is specified, the query will be constrained
               by the given pattern. Version patterns are on the following forms:
        
                - v0.1.2, v0.12.3.2, v0.1.3beta - a specific version
                - v0.12.x - get the highest v0.12 version
                - v1.x.x - get the highest v1 version

        :returns: descriptor object
        """
        if constraint_pattern:
            return self._find_latest_for_pattern(constraint_pattern)
        else:
            return self._find_latest()

    def _find_latest_for_pattern(self, name, version_pattern):
        """
        Returns an IODescriptorAppStore object representing the latest version
        of the sought after object. If no matching item is found, an
        exception is raised.

        the version_pattern parameter can be on the following forms:
        
        - v0.1.2, v0.12.3.2, v0.1.3beta - a specific version
        - v0.12.x - get the highest v0.12 version
        - v1.x.x - get the highest v1 version 

        :returns: IODescriptorAppStore instance
        """
        sg_data = self._sg_connection.find(
            self._entity_type,
            [["code", "is", self._name]],
            [constants.ENTITY_DESCRIPTOR_VERSION_FIELD]
        )

        if len(sg_data) == 0:
            raise ShotgunDeployError(
                "Cannot find any versions for %s in %s!" % (self._name, self._sg_connection.base_url)
            )

        version_numbers = [x.get(constants.ENTITY_DESCRIPTOR_VERSION_FIELD) for x in sg_data]
        version_to_use = self._find_latest_tag_by_pattern(version_numbers, version_pattern)

        # make a location dict
        location_dict = {"type": "shotgun",
                         "entity_type": self._entity_type,
                         "name": self._name,
                         "version": version_to_use}

        # and return a descriptor instance
        desc = IODescriptorShotgunEntity(self._bundle_cache_root, location_dict, self._sg_connection)

        return desc

    def _find_latest(self):
        """
        Returns an IODescriptorAppStore object representing the latest version
        of the sought after object. If no matching item is found, an
        exception is raised.

        :returns: IODescriptorAppStore instance
        """
        sg_version_data = self._sg_connection.find_one(
            self._entity_type,
            [["code", "is", self._name]],
            [constants.ENTITY_DESCRIPTOR_VERSION_FIELD]
        )

        if sg_version_data is None:
            raise ShotgunDeployError(
                "Cannot find any versions for %s in %s!" % (self._name, self._sg_connection.base_url)
            )

        version_str = sg_version_data.get(constants.ENTITY_DESCRIPTOR_VERSION_FIELD)
        if version_str is None:
            raise ShotgunDeployError("Invalid version number for %s" % sg_version_data)

        # make a location dict
        location_dict = {"type": "shotgun",
                         "entity_type": self._entity_type,
                         "name": self._name, 
                         "version": version_str}

        # and return a descriptor instance
        desc = IODescriptorShotgunEntity(self._bundle_cache_root, location_dict, self._sg_connection)
        
        return desc

