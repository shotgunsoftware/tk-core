# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Tank App Store Connectivity.
"""

import os
import re
import copy
import uuid
import tempfile

# use api json to cover py 2.5
# todo - replace with proper external library  
from tank_vendor import shotgun_api3  
json = shotgun_api3.shotgun.json

from ..api import Tank
from ..util import shotgun
from ..errors import TankError
from ..platform import constants
from .descriptor import AppDescriptor
from .zipfilehelper import unzip_file

METADATA_FILE = ".metadata.json"

class TankAppStoreDescriptor(AppDescriptor):
    """
    Represents an app store item.

    Note: Construction of instances of this class can happen in two ways:

    - via the factory method in descriptor.get_from_location()
    - via the class method TankAppStoreDescriptor.find_latest_item()

    """

    def __init__(self, pc_path, bundle_install_path, location_dict, bundle_type):
        super(TankAppStoreDescriptor, self).__init__(pc_path, bundle_install_path, location_dict)

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
                    self.__cached_metadata = json.load(fp)
                    fp.close()
                except:
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
        
        # find the right shotgun entity types
        if self._type == AppDescriptor.APP:
            bundle_entity = constants.TANK_APP_ENTITY
            version_entity = constants.TANK_APP_VERSION_ENTITY
            link_field = "sg_tank_app"

        elif self._type == AppDescriptor.FRAMEWORK:
            bundle_entity = constants.TANK_FRAMEWORK_ENTITY
            version_entity = constants.TANK_FRAMEWORK_VERSION_ENTITY
            link_field = "sg_tank_framework"

        elif self._type == AppDescriptor.ENGINE:
            bundle_entity = constants.TANK_ENGINE_ENTITY
            version_entity = constants.TANK_ENGINE_VERSION_ENTITY
            link_field = "sg_tank_engine"

        else:
            raise TankError("Illegal type value!")

        # connect to the app store
        (sg, script_user) = shotgun.create_sg_app_store_connection()

        # first find the bundle level entity
        bundle = sg.find_one(bundle_entity, [["sg_system_name", "is", self._name]], ["sg_status_list", "sg_deprecation_message"])
        if bundle is None:
            raise TankError("The App store does not contain an item named '%s'!" % self._name)

        # now get the version
        version = sg.find_one(version_entity,
                              [[link_field, "is", bundle], ["code", "is", self._version]],
                              ["description", 
                               "sg_detailed_release_notes", 
                               "sg_documentation",
                               constants.TANK_CODE_PAYLOAD_FIELD])
        if version is None:
            raise TankError("The App store does not have a version "
                            "'%s' of item '%s'!" % (self._version, self._name))

        return {"bundle": bundle, "version": version}

    def __cache_app_store_metadata(self, metadata):
        """
        Caches app store metadata to disk.
        """
        # write it to file for later access

        folder = self.get_path()

        try:
            if not os.path.exists(folder):
                old_umask = os.umask(0)
                os.makedirs(folder, 0777)
                os.umask(old_umask)                
            fp = open(os.path.join(folder, METADATA_FILE), "wt")
            json.dump(metadata, fp)
            fp.close()
        except:
            # fail gracefully - this is only a cache!
            pass

    ###############################################################################################
    # class methods

    @classmethod
    def _find_latest_for_pattern(cls, pc_path, bundle_install_path, bundle_type, name, version_pattern):
        """
        Returns an TankAppStoreDescriptor object representing the latest version
        of the sought after object. If no matching item is found, an
        exception is raised.

        This method is useful if you know the name of an app (after browsing in the
        app store for example) and want to get a formal "handle" to it.

        the version_pattern parameter can be on the following forms:
        
        - v0.1.2, v0.12.3.2, v0.1.3beta - a specific version
        - v0.12.x - get the highest v0.12 version
        - v1.x.x - get the highest v1 version 

        :returns: TankAppStoreDescriptor instance
        """

        # connect to the app store
        (sg, script_user) = shotgun.create_sg_app_store_connection()

        # set up some lookup tables so we look in the right table in sg
        main_entity_map = { AppDescriptor.APP: constants.TANK_APP_ENTITY,
                            AppDescriptor.FRAMEWORK: constants.TANK_FRAMEWORK_ENTITY,
                            AppDescriptor.ENGINE: constants.TANK_ENGINE_ENTITY }

        version_entity_map = { AppDescriptor.APP: constants.TANK_APP_VERSION_ENTITY,
                               AppDescriptor.FRAMEWORK: constants.TANK_FRAMEWORK_VERSION_ENTITY,
                               AppDescriptor.ENGINE: constants.TANK_ENGINE_VERSION_ENTITY }

        link_field_map = { AppDescriptor.APP: "sg_tank_app",
                           AppDescriptor.FRAMEWORK: "sg_tank_framework",
                           AppDescriptor.ENGINE: "sg_tank_engine" }

        # find the main entry
        bundle = sg.find_one(main_entity_map[bundle_type], 
                             [["sg_system_name", "is", name]], 
                             ["id", "sg_status_list"])
        if bundle is None:
            raise TankError("App store does not contain an item named '%s'!" % name)

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
        
        link_field = link_field_map[bundle_type]
        entity_type = version_entity_map[bundle_type]
        sg_data = sg.find(entity_type, [[link_field, "is", bundle]] + latest_filter, ["code"])

        if len(sg_data) == 0:
            raise TankError("Cannot find any versions for %s in the App store!" % name)

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
                raise TankError("Could not find requested version '%s' "
                                "of '%s' in the App store!" % (version_pattern, name))
            else:
                # the requested version exists in the app store!
                version_to_use = version_pattern 
        
        elif re.match("v[0-9]+\.x\.x", version_pattern):
            # we have a v123.x.x pattern
            (major_str, _, _) = version_pattern[1:].split(".")
            major = int(major_str)
            
            if major not in versions:
                raise TankError("%s does not have a version matching the pattern '%s'. "
                                "Available versions are: %s" % (name, version_pattern, ", ".join(version_numbers)))
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
                raise TankError("%s does not have a version matching the pattern '%s'. "
                                "Available versions are: %s" % (name, version_pattern, ", ".join(version_numbers)))
            
            # now find the max increment
            max_increment = max(versions[major][minor])
            version_to_use = "v%s.%s.%s" % (major, minor, max_increment)
        
        else:
            raise TankError("Cannot parse version expression '%s'!" % version_pattern)

        # make a location dict
        location_dict = {"type": "app_store", "name": name, "version": version_to_use}

        # and return a descriptor instance
        desc = TankAppStoreDescriptor(pc_path, bundle_install_path, location_dict, bundle_type)
        
        # now if this item has been deprecated, meaning that someone has gone in to the app
        # store and updated the record's deprecation status, we want to make sure we download
        # all this info the next time it is being requested. So we force clear the metadata
        # cache.
        if is_deprecated:
            desc._remove_app_store_metadata()
        
        return desc

    
    
    @classmethod
    def _find_latest(cls, pc_path, bundle_install_path, bundle_type, name):
        """
        Returns an TankAppStoreDescriptor object representing the latest version
        of the sought after object. If no matching item is found, an
        exception is raised.

        This method is useful if you know the name of an app (after browsing in the
        app store for example) and want to get a formal "handle" to it.

        :returns: TankAppStoreDescriptor instance
        """

        # connect to the app store
        (sg, script_user) = shotgun.create_sg_app_store_connection()

        # get latest
        # get the filter logic for what to exclude
        if constants.APP_STORE_QA_MODE_ENV_VAR in os.environ:
            latest_filter = [["sg_status_list", "is_not", "bad" ]]
        else:
            latest_filter = [["sg_status_list", "is_not", "rev" ],
                             ["sg_status_list", "is_not", "bad" ]]
        
        # set up some lookup tables so we look in the right table in sg
        main_entity_map = { AppDescriptor.APP: constants.TANK_APP_ENTITY,
                            AppDescriptor.FRAMEWORK: constants.TANK_FRAMEWORK_ENTITY,
                            AppDescriptor.ENGINE: constants.TANK_ENGINE_ENTITY }

        version_entity_map = { AppDescriptor.APP: constants.TANK_APP_VERSION_ENTITY,
                               AppDescriptor.FRAMEWORK: constants.TANK_FRAMEWORK_VERSION_ENTITY,
                               AppDescriptor.ENGINE: constants.TANK_ENGINE_VERSION_ENTITY }

        link_field_map = { AppDescriptor.APP: "sg_tank_app",
                           AppDescriptor.FRAMEWORK: "sg_tank_framework",
                           AppDescriptor.ENGINE: "sg_tank_engine" }

        # find the main entry
        bundle = sg.find_one(main_entity_map[bundle_type], 
                             [["sg_system_name", "is", name]], 
                             ["id", "sg_status_list"])
        if bundle is None:
            raise TankError("App store does not contain an item named '%s'!" % name)

        # check if this has been deprecated in the app store
        # in that case we should ensure that the cache is cleared later
        is_deprecated = False
        if bundle["sg_status_list"] == "dep":
            is_deprecated = True

        # now get the version
        link_field = link_field_map[bundle_type]
        entity_type = version_entity_map[bundle_type]
        sg_version_data = sg.find_one(entity_type,
                                      filters = [[link_field, "is", bundle]] + latest_filter,
                                      fields = ["code"],
                                      order=[{"field_name": "created_at", "direction": "desc"}])
        if sg_version_data is None:
            raise TankError("Cannot find any versions for %s in the App store!" % name)



        version_str = sg_version_data.get("code")
        if version_str is None:
            raise TankError("Invalid version number for %s" % sg_version_data)

        # make a location dict
        location_dict = {"type": "app_store", "name": name, "version": version_str}

        # and return a descriptor instance
        desc = TankAppStoreDescriptor(pc_path, bundle_install_path, location_dict, bundle_type)
        
        # now if this item has been deprecated, meaning that someone has gone in to the app
        # store and updated the record's deprecation status, we want to make sure we download
        # all this info the next time it is being requested. So we force clear the metadata
        # cache.
        if is_deprecated:
            desc._remove_app_store_metadata()
        
        return desc

    @classmethod
    def find_latest_item(cls, pc_path, bundle_install_path, bundle_type, name, constraint_pattern=None):
        """
        Returns an TankAppStoreDescriptor object representing the latest version
        of the sought after object. If no matching item is found, an
        exception is raised. A constraint pattern can be specified if you want to search
        a subset of the version space available.

        This pattern can be on the following forms:

        - v0.1.2, v0.12.3.2, v0.1.3beta - a specific version
        - v0.12.x - get the highest v0.12 version
        - v1.x.x - get the highest v1 version

        This method is useful if you know the name of an app (after browsing in the
        app store for example) and want to get a formal "handle" to it.

        :returns: TankAppStoreDescriptor instance
        """
        return cls._find_latest_item_internal(
            pc_path, bundle_install_path, bundle_type, name, constraint_pattern
        )

    @classmethod
    def _find_latest_item_internal(cls, pc_path, bundle_install_path, bundle_type, name, constraint_pattern=None):
        """
        Actual implementation of find_latest_item. For parameter and return value information,
        see find_latest_item for more details.
        """
        if constraint_pattern:
            return cls._find_latest_for_pattern(pc_path, bundle_install_path, bundle_type, name, constraint_pattern)
        else:
            return cls._find_latest(pc_path, bundle_install_path, bundle_type, name)


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
        return self._get_local_location(self._type, "app_store", self._name, self._version)

    def get_doc_url(self):
        """
        Returns the documentation url for this item. May return None.
        """
        metadata = self._get_app_store_metadata()
        url = None
        try:
            url = metadata.get("version").get("sg_documentation").get("url")
        except:
            pass
        return url

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

        if not os.path.exists(target):
            old_umask = os.umask(0)
            os.makedirs(target, 0777)
            os.umask(old_umask)

        # connect to the app store
        (sg, script_user) = shotgun.create_sg_app_store_connection()
        local_sg = shotgun.get_sg_connection()

        # get metadata from sg...
        metadata = self.__download_app_store_metadata()
        self.__cache_app_store_metadata(metadata)
        version = metadata.get("version")

        # now have to get the attachment id from the data we obtained. This is a bit hacky.
        # data example for the payload field, as returned by the query above:
        # {'url': 'http://tank.shotgunstudio.com/file_serve/attachment/21', 'name': 'tank_core.zip',
        #  'content_type': 'application/zip', 'link_type': 'upload'}
        #
        # grab the attachment id off the url field and pass that to the download_attachment()
        # method below.
        try:
            attachment_id = int(version[constants.TANK_CODE_PAYLOAD_FIELD]["url"].split("/")[-1])
        except:
            raise TankError("Could not extract attachment id from data %s" % version)

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

        # write a record to the tank app store
        if self._type == AppDescriptor.APP:
            data = {}
            data["description"] = "%s: App %s %s was downloaded" % (local_sg.base_url, self._name, self._version)
            data["event_type"] = "TankAppStore_App_Download"
            data["entity"] = version
            data["user"] = script_user
            data["project"] = constants.TANK_APP_STORE_DUMMY_PROJECT
            data["attribute_name"] = constants.TANK_CODE_PAYLOAD_FIELD
            sg.create("EventLogEntry", data)

        elif self._type == AppDescriptor.FRAMEWORK:
            data = {}
            data["description"] = "%s: Framework %s %s was downloaded" % (local_sg.base_url, self._name, self._version)
            data["event_type"] = "TankAppStore_Framework_Download"
            data["entity"] = version
            data["user"] = script_user
            data["project"] = constants.TANK_APP_STORE_DUMMY_PROJECT
            data["attribute_name"] = constants.TANK_CODE_PAYLOAD_FIELD
            sg.create("EventLogEntry", data)

        elif self._type == AppDescriptor.ENGINE:
            data = {}
            data["description"] = "%s: Engine %s %s was downloaded" % (local_sg.base_url, self._name, self._version)
            data["event_type"] = "TankAppStore_Engine_Download"
            data["entity"] = version
            data["user"] = script_user
            data["project"] = constants.TANK_APP_STORE_DUMMY_PROJECT
            data["attribute_name"] = constants.TANK_CODE_PAYLOAD_FIELD
            sg.create("EventLogEntry", data)

        else:
            raise TankError("Invalid bundle type")

    def find_latest_version(self, constraint_pattern=None):
        """
        Returns a descriptor object that represents the latest version.
        
        :param constraint_pattern: If this is specified, the query will be constrained
        by the given pattern. Version patterns are on the following forms:
        
            - v1.2.3 (means the descriptor returned will inevitably be same as self)
            - v1.2.x 
            - v1.x.x

        :returns: descriptor object
        """
        return self._find_latest_item_internal(self._pipeline_config_path, self._bundle_install_path, self._type, self._name, constraint_pattern)
        
        


