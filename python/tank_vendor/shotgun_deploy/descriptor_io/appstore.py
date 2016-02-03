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
import re
import copy
import uuid
import tempfile

import cPickle as pickle

from ..zipfilehelper import unzip_file
from .base import IODescriptorBase

# use api json to cover py 2.5
from ... import shotgun_api3
json = shotgun_api3.shotgun.json

from .. import constants

from ..descriptor import Descriptor

from ..errors import ShotgunDeployError, ShotgunAppStoreError
from ...shotgun_base import ensure_folder_exists

import urllib
import urllib2


METADATA_FILE = ".cached_metadata.pickle"


class IODescriptorAppStore(IODescriptorBase):
    """
    Represents an app store item.
    """

    # cache app store connections for performance
    _app_store_connections = {}

    # internal app store mappings
    (APP, FRAMEWORK, ENGINE, CONFIG, CORE) = range(5)

    _APP_STORE_OBJECT = {
        Descriptor.APP: constants.TANK_APP_ENTITY,
        Descriptor.FRAMEWORK: constants.TANK_FRAMEWORK_ENTITY,
        Descriptor.ENGINE: constants.TANK_ENGINE_ENTITY,
        Descriptor.CONFIG: constants.TANK_CONFIG_ENTITY,
        Descriptor.CORE: None,
    }

    _APP_STORE_VERSION = {
        Descriptor.APP: constants.TANK_APP_VERSION_ENTITY,
        Descriptor.FRAMEWORK: constants.TANK_FRAMEWORK_VERSION_ENTITY,
        Descriptor.ENGINE: constants.TANK_ENGINE_VERSION_ENTITY,
        Descriptor.CONFIG: constants.TANK_CONFIG_VERSION_ENTITY,
        Descriptor.CORE: constants.TANK_CORE_VERSION_ENTITY,
    }

    _APP_STORE_LINK = {
        Descriptor.APP: "sg_tank_app",
        Descriptor.FRAMEWORK: "sg_tank_framework",
        Descriptor.ENGINE: "sg_tank_engine",
        Descriptor.CONFIG: "sg_tank_config",
        Descriptor.CORE: None,
    }

    _DOWNLOAD_STATS_EVENT_TYPE = {
        Descriptor.APP: "TankAppStore_App_Download",
        Descriptor.FRAMEWORK: "TankAppStore_Framework_Download",
        Descriptor.ENGINE: "TankAppStore_Engine_Download",
        Descriptor.CONFIG: "TankAppStore_Config_Download",
        Descriptor.CORE: "TankAppStore_Core_Download",
    }


    def __init__(self, bundle_install_path, location_dict, sg_connection, bundle_type):
        """
        Constructor

        :param bundle_install_path: Location on disk where items are cached
        :param location_dict: Location dictionary describing the bundle
        :param sg_connection: Shotgun connection to associated site
        :param bundle_type: Either Descriptor.APP, CORE, ENGINE or FRAMEWORK
        :return: Descriptor instance
        """
        super(IODescriptorAppStore, self).__init__(bundle_install_path, location_dict)

        self._sg_connection = sg_connection
        self._type = bundle_type
        self._name = location_dict.get("name")
        self._version = location_dict.get("version")
        # cached metadata - loaded on demand
        self.__cached_metadata = None

    def _remove_app_store_metadata(self):
        """
        Clears the app store metadata that is cached on disk.
        This will force a re-fetch from shotgun the next time the metadata is needed
        """
        cache_file = os.path.join(self.get_path(), METADATA_FILE)
        if os.path.exists(cache_file):
            try:
                os.remove(cache_file)
            except:
                # fail gracefully - this is only a cache
                pass
    
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
        return copy.deepcopy(self.__cached_metadata)

    def __download_app_store_metadata(self):
        """
        Fetches metadata about the app from the tank app store
        returns a dictionary with a bundle key and a version key.
        """

        # get the appropriate shotgun app store types and fields
        bundle_entity = self._APP_STORE_OBJECT[self._type]
        version_entity = self._APP_STORE_VERSION[self._type]
        link_field = self._APP_STORE_LINK[self._type]

        # connect to the app store
        (sg, _) = self.__create_sg_app_store_connection()

        if self._type == self.CORE:
            # special handling of core since it doesn't have a high-level
            # 'bundle' entity
            
            bundle = None
            
            version = sg.find_one(constants.TANK_CORE_VERSION_ENTITY,
                                  [["code", "is", self._version]],
                                  ["description", 
                                   "sg_detailed_release_notes", 
                                   "sg_documentation",
                                   constants.TANK_CODE_PAYLOAD_FIELD])
            if version is None:
                raise ShotgunDeployError(
                    "The App store does not have a version '%s' of Core!" % self._version
                )
            
            
        else:
        
            # first find the bundle level entity
            bundle = sg.find_one(
                    bundle_entity,
                    [["sg_system_name", "is", self._name]],
                    ["sg_status_list", "sg_deprecation_message"]
            )

            if bundle is None:
                raise ShotgunDeployError("The App store does not contain an item named '%s'!" % self._name)
    
            # now get the version
            version = sg.find_one(version_entity,
                                  [[link_field, "is", bundle], ["code", "is", self._version]],
                                  ["description", 
                                   "sg_detailed_release_notes", 
                                   "sg_documentation",
                                   constants.TANK_CODE_PAYLOAD_FIELD])
            if version is None:
                raise ShotgunDeployError(
                    "The App store does not have a version '%s' of item '%s'!" % (self._version, self._name)
                )

        return {"bundle": bundle, "version": version}

    def __cache_app_store_metadata(self, metadata):
        """
        Caches app store metadata to disk.
        """
        # write it to file for later access

        folder = self.get_path()

        try:
            ensure_folder_exists(folder)
            fp = open(os.path.join(folder, METADATA_FILE), "wt")
            pickle.dump(metadata, fp)
            fp.close()
        except Exception:
            # fail gracefully - this is only a cache!
            pass

    ###############################################################################################
    # data accessors

    def get_system_name(self):
        """
        Returns a short name, suitable for use in configuration files
        and for folders on disk
        """
        return self._name

    def get_deprecation_status(self):
        """
        Returns (is_deprecated (bool), message (str)) to indicate if this item is deprecated.
        """
        metadata = self._get_app_store_metadata()
        if metadata.get("bundle").get("sg_status_list") == "dep":
            msg = metadata.get("bundle").get("sg_deprecation_message", "No reason given.")
            return (True, msg)
        else:
            return (False, "")        

    def get_version(self):
        """
        Returns the version number string for this item
        """
        return self._version

    def get_path(self):
        """
        returns the path to the folder where this item resides
        """
        return self._get_local_location("app_store", self._name, self._version)

    def get_changelog(self):
        """
        Returns information about the changelog for this item.
        Returns a tuple: (changelog_summary, changelog_url). Values may be None
        to indicate that no changelog exists.
        """
        summary = None
        url = None
        metadata = self._get_app_store_metadata()
        try:
            summary = metadata.get("version").get("description")
            url = metadata.get("version").get("sg_detailed_release_notes").get("url")
        except:
            pass
        return (summary, url)

    def exists_local(self):
        """
        Returns true if this item exists in a local repo
        """
        # we determine local existance based on the info.yml
        info_yml_path = os.path.join(self.get_path(), constants.BUNDLE_METADATA_FILE)
        return os.path.exists(info_yml_path)

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

        # connect to the app store
        (sg, script_user) = self.__create_sg_app_store_connection()

        # get metadata from sg...
        metadata = self.__download_app_store_metadata()
        self.__cache_app_store_metadata(metadata)
        version = metadata.get("version")

        # attachment field is on the following form in the case a file has been uploaded:
        #  {'name': 'v1.2.3.zip',
        #  'url': 'https://sg-media-usor-01.s3.amazonaws.com/...',
        #  'content_type': 'application/zip',
        #  'type': 'Attachment',
        #  'id': 139,
        #  'link_type': 'upload'}
        attachment_id = version[constants.TANK_CODE_PAYLOAD_FIELD]["id"]

        # and now for the download.
        # @todo: progress feedback here - when the SG api supports it!
        # sometimes people report that this download fails (because of flaky connections etc)
        # engines can often be 30-50MiB - as a quick fix, just retry the download once
        # if it fails.
        try:
            bundle_content = sg.download_attachment(attachment_id)
        except:
            # retry once
            bundle_content = sg.download_attachment(attachment_id)

        zip_tmp = os.path.join(tempfile.gettempdir(), "%s_tank.zip" % uuid.uuid4().hex)
        fh = open(zip_tmp, "wb")
        fh.write(bundle_content)
        fh.close()

        # unzip core zip file to app target location
        unzip_file(zip_tmp, target)

        # write a stats record to the tank app store
        data = {}
        data["description"] = "%s: %s %s was downloaded" % (self._sg_connection.base_url, self._name, self._version)
        data["event_type"] = self._DOWNLOAD_STATS_EVENT_TYPE[self._type]
        data["entity"] = version
        data["user"] = script_user
        data["project"] = constants.TANK_APP_STORE_DUMMY_PROJECT
        data["attribute_name"] = constants.TANK_CODE_PAYLOAD_FIELD
        sg.create("EventLogEntry", data)

    #############################################################################
    # searching for other versions

    def find_latest_version(self, constraint_pattern=None):
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

        # connect to the app store
        (sg, _) = self.__create_sg_app_store_connection()

        # set up some lookup tables so we look in the right table in sg

        # find the main entry
        bundle = sg.find_one(self._APP_STORE_OBJECT[self._type],
                             [["sg_system_name", "is", self._name]], 
                             ["id", "sg_status_list"])
        if bundle is None:
            raise ShotgunDeployError("App store does not contain an item named '%s'!" % self._name)

        # check if this has been deprecated in the app store
        # in that case we should ensure that the cache is cleared later
        is_deprecated = False
        if bundle["sg_status_list"] == "dep":
            is_deprecated = True

        # now get all versions
        
        # get latest get the filter logic for what to exclude
        if constants.APP_STORE_QA_MODE_ENV_VAR in os.environ:
            latest_filter = [["sg_status_list", "is_not", "bad" ]]
        else:
            latest_filter = [["sg_status_list", "is_not", "rev" ],
                             ["sg_status_list", "is_not", "bad" ]]        
        
        link_field = self._APP_STORE_LINK[self._type]
        entity_type = self._APP_STORE_VERSION[self._type]
        sg_data = sg.find(entity_type, [[link_field, "is", bundle]] + latest_filter, ["code"])

        if len(sg_data) == 0:
            raise ShotgunDeployError("Cannot find any versions for %s in the App store!" % self._name)

        # now put all version number strings which match the form
        # vX.Y.Z into a nested dictionary where it is keyed by major,
        # then minor then increment.
        #
        # For example, the following versions:
        # v1.2.1, v1.2.2, v1.2.3, v1.4.3, v1.4.2, v1.4.1
        # 
        # Would generate the following:
        # { "1": { "2": [1,2,3], "4": [3,2,1] } }
        #  
        
        version_numbers = [x.get("code") for x in sg_data]
        versions = {}
        
        for version_num in version_numbers:

            try:
                (major_str, minor_str, increment_str) = version_num[1:].split(".")
                (major, minor, increment) = (int(major_str), int(minor_str), int(increment_str))
            except:
                # this version number was not on the form vX.Y.Z where X Y and Z are ints. skip.
                continue
            
            if major not in versions:
                versions[major] = {}
            if minor not in versions[major]:
                versions[major][minor] = []
            if increment not in versions[major][minor]:
                versions[major][minor].append(increment)


        # now handle the different version strings
        version_to_use = None
        if "x" not in version_pattern:
            # we are looking for a specific version
            if version_pattern not in version_numbers:
                raise ShotgunDeployError("Could not find requested version '%s' "
                                "of '%s' in the App store!" % (version_pattern, self._name))
            else:
                # the requested version exists in the app store!
                version_to_use = version_pattern 
        
        elif re.match("v[0-9]+\.x\.x", version_pattern):
            # we have a v123.x.x pattern
            (major_str, _, _) = version_pattern[1:].split(".")
            major = int(major_str)
            
            if major not in versions:
                raise ShotgunDeployError("%s does not have a version matching the pattern '%s'. "
                                "Available versions are: %s" % (self._name, version_pattern, ", ".join(version_numbers)))
            # now find the max version
            max_minor = max(versions[major].keys())            
            max_increment = max(versions[major][max_minor])
            version_to_use = "v%s.%s.%s" % (major, max_minor, max_increment)

        elif re.match("v[0-9]+\.[0-9]+\.x", version_pattern):
            # we have a v123.345.x pattern
            (major_str, minor_str, _) = version_pattern[1:].split(".")
            major = int(major_str)
            minor = int(minor_str)

            # make sure the constraints are fulfilled
            if (major not in versions) or (minor not in versions[major]):
                raise ShotgunDeployError("%s does not have a version matching the pattern '%s'. "
                                "Available versions are: %s" % (self._name, version_pattern, ", ".join(version_numbers)))
            
            # now find the max increment
            max_increment = max(versions[major][minor])
            version_to_use = "v%s.%s.%s" % (major, minor, max_increment)
        
        else:
            raise ShotgunDeployError("Cannot parse version expression '%s'!" % version_pattern)

        # make a location dict
        location_dict = {"type": "app_store", "name": self._name, "version": version_to_use}

        # and return a descriptor instance
        desc = IODescriptorAppStore(self._bundle_install_path, location_dict, self._sg_connection, self._type)
        
        # now if this item has been deprecated, meaning that someone has gone in to the app
        # store and updated the record's deprecation status, we want to make sure we download
        # all this info the next time it is being requested. So we force clear the metadata
        # cache.
        if is_deprecated:
            desc._remove_app_store_metadata()
        
        return desc

    def _find_latest(self):
        """
        Returns an IODescriptorAppStore object representing the latest version
        of the sought after object. If no matching item is found, an
        exception is raised.

        :returns: IODescriptorAppStore instance
        """

        # connect to the app store
        (sg, _) = self.__create_sg_app_store_connection()

        # get latest
        # get the filter logic for what to exclude
        if constants.APP_STORE_QA_MODE_ENV_VAR in os.environ:
            latest_filter = [["sg_status_list", "is_not", "bad" ]]
        else:
            latest_filter = [["sg_status_list", "is_not", "rev" ],
                             ["sg_status_list", "is_not", "bad" ]]

        is_deprecated = False
        
        if self._type != self.CORE:
            # items other than core have a main entity that represents
            # app/engine/etc.
            
            # find the main entry
            bundle = sg.find_one(self._APP_STORE_OBJECT[self._type],
                                 [["sg_system_name", "is", self._name]], 
                                 ["id", "sg_status_list"])
            if bundle is None:
                raise ShotgunDeployError("App store does not contain an item named '%s'!" % self._name)
    
            # check if this has been deprecated in the app store
            # in that case we should ensure that the cache is cleared later    
            if bundle["sg_status_list"] == "dep":
                is_deprecated = True

            # now get the version
            link_field = self._APP_STORE_LINK[self._type]
            entity_type = self._APP_STORE_VERSION[self._type]
            sg_version_data = sg.find_one(entity_type,
                                          filters = [[link_field, "is", bundle]] + latest_filter,
                                          fields = ["code"],
                                          order=[{"field_name": "created_at", "direction": "desc"}])
            
        else:
            # core API
            sg_version_data = sg.find_one(constants.TANK_CORE_VERSION_ENTITY,
                                          filters = latest_filter,
                                          fields = ["code"],
                                          order=[{"field_name": "created_at", "direction": "desc"}])
        
        if sg_version_data is None:
            raise ShotgunDeployError("Cannot find any versions for %s in the App store!" % self._name)

        version_str = sg_version_data.get("code")
        if version_str is None:
            raise ShotgunDeployError("Invalid version number for %s" % sg_version_data)

        # make a location dict
        location_dict = {"type": "app_store", 
                         "name": self._name, 
                         "version": version_str}

        # and return a descriptor instance
        desc = IODescriptorAppStore(self._bundle_install_path, location_dict, self._sg_connection, self._type)
        
        # now if this item has been deprecated, meaning that someone has gone in to the app
        # store and updated the record's deprecation status, we want to make sure we download
        # all this info the next time it is being requested. So we force clear the metadata
        # cache.
        if is_deprecated:
            desc._remove_app_store_metadata()
        
        return desc

    def __create_sg_app_store_connection(self):
        """
        Creates a shotgun connection that can be used to access the Toolkit app store.

        :returns: (sg, dict) where the first item is the shotgun api instance and the second
                  is an sg entity dictionary (keys type/id) corresponding to to the user used
                  to connect to the app store.
        """
        # maintain a cache for performance
        # cache is keyed by client shotgun site
        # this assumes that there is a strict
        # 1:1 relationship between app store accounts
        # and shotgun sites.
        sg_url = self._sg_connection.base_url

        if sg_url not in self._app_store_connections:

            # Connect to associated Shotgun site and retrieve the credentials to use to
            # connect to the app store site
            (script_name, script_key) = self.__get_app_store_key_from_shotgun()

            # connect to the app store and resolve the script user id we are connecting with
            app_store_sg = shotgun_api3.Shotgun(
                constants.SGTK_APP_STORE,
                script_name=script_name,
                api_key=script_key,
                http_proxy=self._sg_connection.config.raw_http_proxy
            )

            # determine the script user running currently
            # get the API script user ID from shotgun
            script_user = app_store_sg .find_one(
                "ApiUser",
                [["firstname", "is", script_name]],
                fields=["type", "id"]
            )

            if script_user is None:
                raise ShotgunAppStoreError("Could not evaluate the current App Store User! Please contact support.")

            self._app_store_connections[sg_url] = (app_store_sg, script_user)

        return self._app_store_connections[sg_url]


    def __get_app_store_key_from_shotgun(self):
        """
        Given a Shotgun url and script credentials, fetch the app store key
        for this shotgun instance using a special controller method.
        Returns a tuple with (app_store_script_name, app_store_auth_key)

        :returns: tuple of strings with contents (script_name, script_key)
        """
        sg = self._sg_connection

        # handle proxy setup by pulling the proxy details from the main shotgun connection
        if sg.config.proxy_handler:
            opener = urllib2.build_opener(sg.config.proxy_handler)
            urllib2.install_opener(opener)

        # now connect to our site and use a special url to retrieve the app store script key
        session_token = sg.get_session_token()
        post_data = {"session_token": session_token}
        response = urllib2.urlopen("%s/api3/sgtk_install_script" % sg.base_url, urllib.urlencode(post_data))
        html = response.read()
        data = json.loads(html)

        return data["script_name"], data["script_key"]


