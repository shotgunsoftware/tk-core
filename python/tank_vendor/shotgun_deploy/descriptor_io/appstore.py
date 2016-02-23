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
import urllib
import urllib2
import cPickle as pickle

from ..zipfilehelper import unzip_file
from ..descriptor import Descriptor
from ..errors import ShotgunDeployError, ShotgunAppStoreError
from ...shotgun_base import ensure_folder_exists, safe_delete_file

from .. import util
from .. import constants
from .base import IODescriptorBase

# use api json to cover py 2.5
from ... import shotgun_api3
json = shotgun_api3.shotgun.json

log = util.get_shotgun_deploy_logger()

# file where we cache the app store metadata for an item
METADATA_FILE = ".cached_metadata.pickle"

class IODescriptorAppStore(IODescriptorBase):
    """
    Represents a toolkit app store item.

    Short syntax:
        sgtk:app_store:tk-core:v12.3.4
        sgtk:app_store:NAME:VERSION

    Dictionary syntax:
        {type: app_store, name: tk-core, version: v12.3.4}
        {type: app_store, name: NAME, version: VERSION}
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


    def __init__(self, location_dict, sg_connection, bundle_type):
        """
        Constructor

        :param location_dict: Location dictionary describing the bundle
        :param sg_connection: Shotgun connection to associated site
        :param bundle_type: Either Descriptor.APP, CORE, ENGINE or FRAMEWORK
        :return: Descriptor instance
        """
        super(IODescriptorAppStore, self).__init__(location_dict)

        self._validate_locator(
            location_dict,
            required=["type", "name", "version"],
            optional=[]
        )

        self._sg_connection = sg_connection
        self._type = bundle_type
        self._name = location_dict.get("name")
        self._version = location_dict.get("version")
        # cached metadata - loaded on demand
        self.__cached_metadata = None

    def _remove_app_store_metadata(self):
        """
        Clears the app store metadata that is cached on disk.
        This will force a re-fetch from shotgun the next time the metadata is needed.
        Note that while the payload of the app is immutable - e.g. v1.2.3 always stays
        the same, the metadata may change. This typically happens when an item gets deprecated
        and its deprecation status changes.
        """
        if not self.exists_local():
            return

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
        Tries to use a cache if possible.
        """
        if not self.exists_local():
            return {}

        if self.__cached_metadata:
            # got an in-memory cache
            return self.__cached_metadata

        # try to load from cache file
        self.__cached_metadata = None
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

            # try to cache it on disk
            try:
                ensure_folder_exists(os.path.dirname(cache_file))
                fp = open(cache_file, "wt")
                pickle.dump(self.__cached_metadata, fp)
                fp.close()
            except Exception:
                # fail gracefully - this is only a cache!
                pass

        # finally return the data!
        return self.__cached_metadata

    def __download_app_store_metadata(self):
        """
        Fetches metadata about the app from the toolkit app store

        :returns: A dictionary with keys bundle and version, containing
                  Shotgun metadata.
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
            
            version = sg.find_one(
                constants.TANK_CORE_VERSION_ENTITY,
                [["code", "is", self._version]],
                ["description",
                 "sg_detailed_release_notes",
                 "sg_documentation",
                 constants.TANK_CODE_PAYLOAD_FIELD]
            )
            if version is None:
                raise ShotgunDeployError(
                    "The App store does not have a version '%s' of Core!" % self._version
                )
            
        else:
            # engines, apps etc have a 'bundle level entity' in the app store,
            # e.g. something representing the app or engine.
            # then a version entity representing a particular version
            bundle = sg.find_one(
                bundle_entity,
                [["sg_system_name", "is", self._name]],
                ["sg_status_list", "sg_deprecation_message"]
            )

            if bundle is None:
                raise ShotgunDeployError(
                    "The App store does not contain an item named '%s'!" % self._name
                )
    
            # now get the version
            version = sg.find_one(
                version_entity,
                [[link_field, "is", bundle], ["code", "is", self._version]],
                ["description",
                 "sg_detailed_release_notes",
                 "sg_documentation",
                 constants.TANK_CODE_PAYLOAD_FIELD]
            )
            if version is None:
                raise ShotgunDeployError(
                    "The App store does not have a "
                    "version '%s' of item '%s'!" % (self._version, self._name)
                )

        metadata = {"bundle": bundle, "version": version}

        return metadata

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
                    "app_store",
                    self.get_system_name(),
                    self.get_version()
                )
            )
        return paths



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
        Returns information about deprecation.

        :returns: Returns a tuple (is_deprecated, message) to indicate
                  if this item is deprecated.
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

    def get_changelog(self):
        """
        Returns information about the changelog for this item.

        :returns: A tuple (changelog_summary, changelog_url). Values may be None
                  to indicate that no changelog exists.
        """
        summary = None
        url = None
        metadata = self._get_app_store_metadata()
        try:
            summary = metadata.get("version").get("description")
            url = metadata.get("version").get("sg_detailed_release_notes").get("url")
        except Exception:
            pass
        return (summary, url)

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

        # connect to the app store
        (sg, script_user) = self.__create_sg_app_store_connection()

        # get metadata from sg...
        metadata = self._get_app_store_metadata()
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
        log.debug("Downloading attachment %s..." % self._version)
        try:
            bundle_content = sg.download_attachment(attachment_id)
        except Exception, e:
            # retry once
            log.debug("Downloading failed, retrying. Error: %s" % e)
            bundle_content = sg.download_attachment(attachment_id)

        zip_tmp = os.path.join(tempfile.gettempdir(), "%s_tank.zip" % uuid.uuid4().hex)
        fh = open(zip_tmp, "wb")
        fh.write(bundle_content)
        fh.close()

        # unzip core zip file to app target location
        log.debug("Unpacking %s bytes to %s..." % (os.path.getsize(zip_tmp), target))
        unzip_file(zip_tmp, target)

        # remove zip file
        safe_delete_file(zip_tmp)

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
            return self._find_latest_for_pattern(constraint_pattern)
        else:
            return self._find_latest()

    def _find_latest_for_pattern(self, version_pattern):
        """
        Returns an object representing the latest version
        of the sought after object. If no matching item is found, an
        exception is raised.

        :param version_pattern: If this is specified, the query will be constrained
               by the given pattern. Version patterns are on the following forms:

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

        version_numbers = [x.get("code") for x in sg_data]
        version_to_use = self._find_latest_tag_by_pattern(version_numbers, version_pattern)

        # make a location dict
        location_dict = {"type": "app_store", "name": self._name, "version": version_to_use}

        # and return a descriptor instance
        desc = IODescriptorAppStore(location_dict, self._sg_connection, self._type)
        desc.set_cache_roots(self._bundle_cache_root, self._fallback_roots)
        
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
        desc = IODescriptorAppStore(location_dict, self._sg_connection, self._type)
        desc.set_cache_roots(self._bundle_cache_root, self._fallback_roots)
        
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
            try:
                (script_name, script_key) = self.__get_app_store_key_from_shotgun()
            except urllib2.HTTPError, e:
                if e.code == 403:
                    # edge case alert!
                    # this is likely because our session token in shotgun has expired.
                    # The authentication system is based around wrapping the shotgun API,
                    # and requesting authentication if needed. Because the app store
                    # credentials is a separate endpoint and doesn't go via the shotgun
                    # API, we have to explicitly check.
                    #
                    # trigger a refresh of our session token by issuing a shotgun API call
                    self._sg_connection.find_one("HumanUser", [])
                    # and retry
                    (script_name, script_key) = self.__get_app_store_key_from_shotgun()
                else:
                    raise


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
                raise ShotgunAppStoreError(
                    "Could not evaluate the current App Store User! Please contact support."
                )

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


