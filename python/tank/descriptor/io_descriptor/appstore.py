# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Toolkit App Store Descriptor.
"""

import os
import urllib
import urllib2
import httplib
from tank_vendor.shotgun_api3.lib import httplib2
import cPickle as pickle

from ...util import shotgun, filesystem
from ...util import UnresolvableCoreConfigurationError, ShotgunAttachmentDownloadError
from ...util.user_settings import UserSettings

from ..descriptor import Descriptor
from ..errors import TankAppStoreConnectionError
from ..errors import TankAppStoreError
from ..errors import TankDescriptorError

from ... import LogManager
from .. import constants
from .base import IODescriptorBase

# use api json to cover py 2.5
from tank_vendor import shotgun_api3
json = shotgun_api3.shotgun.json

log = LogManager.get_logger(__name__)


# file where we cache the app store metadata for an item
METADATA_FILE = ".cached_metadata.pickle"


class IODescriptorAppStore(IODescriptorBase):
    """
    Represents a toolkit app store item.

    {type: app_store, name: tk-core, version: v12.3.4}
    {type: app_store, name: NAME, version: VERSION}

    """

    # cache app store connections for performance
    _app_store_connections = {}

    # internal app store mappings
    (APP, FRAMEWORK, ENGINE, CONFIG, CORE) = range(5)

    _APP_STORE_OBJECT = {
        Descriptor.APP: constants.TANK_APP_ENTITY_TYPE,
        Descriptor.FRAMEWORK: constants.TANK_FRAMEWORK_ENTITY_TYPE,
        Descriptor.ENGINE: constants.TANK_ENGINE_ENTITY_TYPE,
        Descriptor.CONFIG: constants.TANK_CONFIG_ENTITY_TYPE,
        Descriptor.CORE: None,
    }

    _APP_STORE_VERSION = {
        Descriptor.APP: constants.TANK_APP_VERSION_ENTITY_TYPE,
        Descriptor.FRAMEWORK: constants.TANK_FRAMEWORK_VERSION_ENTITY_TYPE,
        Descriptor.ENGINE: constants.TANK_ENGINE_VERSION_ENTITY_TYPE,
        Descriptor.CONFIG: constants.TANK_CONFIG_VERSION_ENTITY_TYPE,
        Descriptor.CORE: constants.TANK_CORE_VERSION_ENTITY_TYPE,
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
        Descriptor.CORE: "TankAppStore_CoreApi_Download",
    }

    def __init__(self, descriptor_dict, sg_connection, bundle_type):
        """
        Constructor

        :param descriptor_dict: descriptor dictionary describing the bundle
        :param sg_connection: Shotgun connection to associated site
        :param bundle_type: Either Descriptor.APP, CORE, ENGINE or FRAMEWORK or CONFIG
        :return: Descriptor instance
        """
        super(IODescriptorAppStore, self).__init__(descriptor_dict)

        self._validate_descriptor(
            descriptor_dict,
            required=["type", "name", "version"],
            optional=[]
        )

        self._sg_connection = sg_connection
        self._type = bundle_type
        self._name = descriptor_dict.get("name")
        self._version = descriptor_dict.get("version")
        # cached metadata - loaded on demand
        self.__cached_metadata = None

    def __str__(self):
        """
        Human readable representation
        """
        display_name_lookup = {
            Descriptor.APP: "App",
            Descriptor.FRAMEWORK: "Framework",
            Descriptor.ENGINE: "Engine",
            Descriptor.CONFIG: "Config",
            Descriptor.CORE: "Core",
        }

        # Toolkit App Store App tk-multi-loader2 v1.2.3
        # Toolkit App Store Framework tk-framework-shotgunutils v1.2.3
        # Toolkit App Store Core v1.2.3
        if self._type == Descriptor.CORE:
            return "Toolkit App Store Core %s" % self._version
        else:
            display_name = display_name_lookup[self._type]
            return "Toolkit App Store %s %s %s" % (display_name, self._name, self._version)

    def _get_app_store_metadata(self):
        """
        Returns a metadata dictionary.
        Tries to use a cache if possible.
        """
        if not self.__cached_metadata:

            # make sure we have the app payload
            self.ensure_local()

            # try to load from cache file
            # cache is typically downloaded on app installation but in some legacy cases
            # this is not happening so don't assume file exists
            cache_file = os.path.join(self.get_path(), METADATA_FILE)
            if os.path.exists(cache_file):
                fp = open(cache_file, "rt")
                try:
                    self.__cached_metadata = pickle.load(fp)
                finally:
                    fp.close()
            else:
                log.debug(
                    "%r Could not find cached metadata file %s - "
                    "will proceed with empty app store metadata." % (self, cache_file)
                )
                self.__cached_metadata = {}

        # finally return the data!
        return self.__cached_metadata

    def __refresh_app_store_metadata(self):
        """
        Rebuilds the app store metadata cache
        """
        # make sure we have the app payload
        self.ensure_local()

        # and cache the file
        cache_file = os.path.join(self.get_path(), METADATA_FILE)
        self.__cache_app_store_metadata(cache_file)

    def __cache_app_store_metadata(self, path):
        """
        Fetches metadata about the app from the toolkit app store. Writes it to disk.

        :param path: Path to write the cache file to.
        :returns: A dictionary with keys 'sg_bundle_data' and 'sg_version_data',
                  containing Shotgun metadata.
        """
        # get the appropriate shotgun app store types and fields
        bundle_entity_type = self._APP_STORE_OBJECT[self._type]
        version_entity_type = self._APP_STORE_VERSION[self._type]
        link_field = self._APP_STORE_LINK[self._type]

        # connect to the app store
        (sg, _) = self.__create_sg_app_store_connection()

        if self._type == self.CORE:
            # special handling of core since it doesn't have a high-level
            # 'bundle' entity
            sg_bundle_data = None

            sg_version_data = sg.find_one(
                constants.TANK_CORE_VERSION_ENTITY_TYPE,
                [["code", "is", self._version]],
                ["description",
                 "sg_detailed_release_notes",
                 "sg_documentation",
                 constants.TANK_CODE_PAYLOAD_FIELD]
            )
            if sg_version_data is None:
                raise TankDescriptorError(
                    "The App store does not have a version '%s' of Core!" % self._version
                )
        else:
            # engines, apps etc have a 'bundle level entity' in the app store,
            # e.g. something representing the app or engine.
            # then a version entity representing a particular version
            sg_bundle_data = sg.find_one(
                bundle_entity_type,
                [["sg_system_name", "is", self._name]],
                ["sg_status_list", "sg_deprecation_message"]
            )

            if sg_bundle_data is None:
                raise TankDescriptorError(
                    "The App store does not contain an item named '%s'!" % self._name
                )

            # now get the version
            sg_version_data = sg.find_one(
                version_entity_type,
                [[link_field, "is", sg_bundle_data], ["code", "is", self._version]],
                ["description",
                 "sg_detailed_release_notes",
                 "sg_documentation",
                 constants.TANK_CODE_PAYLOAD_FIELD]
            )
            if sg_version_data is None:
                raise TankDescriptorError(
                    "The App store does not have a "
                    "version '%s' of item '%s'!" % (self._version, self._name)
                )

        metadata = {
            "sg_bundle_data": sg_bundle_data,
            "sg_version_data": sg_version_data
        }

        filesystem.ensure_folder_exists(os.path.dirname(path))
        fp = open(path, "wt")
        try:
            pickle.dump(metadata, fp)
            log.debug("Wrote app store cache file '%s'" % path)
        finally:
            fp.close()

        return metadata

    def _get_bundle_cache_path(self, bundle_cache_root):
        """
        Given a cache root, compute a cache path suitable
        for this descriptor, using the 0.18+ path format.

        :param bundle_cache_root: Bundle cache root path
        :return: Path to bundle cache location
        """
        return os.path.join(
            bundle_cache_root,
            "app_store",
            self.get_system_name(),
            self.get_version()
        )

    def _get_cache_paths(self):
        """
        Get a list of resolved paths, starting with the primary and
        continuing with alternative locations where it may reside.

        Note: This method only computes paths and does not perform any I/O ops.

        :return: List of path strings
        """
        # get default cache paths from base class
        paths = super(IODescriptorAppStore, self)._get_cache_paths()

        # for compatibility with older versions of core, prior to v0.18.x,
        # add the old-style bundle cache path as a fallback. As of v0.18.x,
        # the bundle cache subdirectory names were shortened and otherwise
        # modified to help prevent MAX_PATH issues on windows. This call adds
        # the old path as a fallback for cases where core has been upgraded
        # for an existing project. NOTE: This only works because the bundle
        # cache root didn't change (when use_bundle_cache is set to False).
        # If the bundle cache root changes across core versions, then this will
        # need to be refactored.
        legacy_folder = self._get_legacy_bundle_install_folder(
            "app_store",
            self._bundle_cache_root,
            self._type,
            self.get_system_name(),
            self.get_version()
        )
        if legacy_folder:
            paths.append(legacy_folder)

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
        sg_bundle_data = metadata.get("sg_bundle_data") or {}
        if sg_bundle_data.get("sg_status_list") == "dep":
            msg = sg_bundle_data.get("sg_deprecation_message", "No reason given.")
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
            sg_version_data = metadata.get("sg_version_data") or {}
            summary = sg_version_data.get("description")
            url = sg_version_data.get("sg_detailed_release_notes").get("url")
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
        target = self._get_primary_cache_path()

        # connect to the app store
        (sg, script_user) = self.__create_sg_app_store_connection()

        # fetch metadata from sg...
        metadata_cache_file = os.path.join(target, METADATA_FILE)
        metadata = self.__cache_app_store_metadata(metadata_cache_file)

        # now get the attachment info
        version = metadata.get("sg_version_data")

        # attachment field is on the following form in the case a file has been uploaded:
        #  {'name': 'v1.2.3.zip',
        #  'url': 'https://sg-media-usor-01.s3.amazonaws.com/...',
        #  'content_type': 'application/zip',
        #  'type': 'Attachment',
        #  'id': 139,
        #  'link_type': 'upload'}
        attachment_id = version[constants.TANK_CODE_PAYLOAD_FIELD]["id"]

        # download and unzip
        try:
            shotgun.download_and_unpack_attachment(sg, attachment_id, target)
        except ShotgunAttachmentDownloadError, e:
            raise TankAppStoreError(
                "Failed to download %s. Error: %s" % (self, e)
            )

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

        :returns: IODescriptorAppStore object
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

        # get latest get the filter logic for what to exclude
        if constants.APP_STORE_QA_MODE_ENV_VAR in os.environ:
            latest_filter = [["sg_status_list", "is_not", "bad"]]
        else:
            latest_filter = [["sg_status_list", "is_not", "rev"],
                             ["sg_status_list", "is_not", "bad"]]

        is_deprecated = False
        if self._type != self.CORE:
            # find the main entry
            sg_bundle_data = sg.find_one(
                self._APP_STORE_OBJECT[self._type],
                [["sg_system_name", "is", self._name]],
                ["id", "sg_status_list"]
            )

            if sg_bundle_data is None:
                raise TankDescriptorError("App store does not contain an item named '%s'!" % self._name)

            # check if this has been deprecated in the app store
            # in that case we should ensure that the metadata is refreshed later
            if sg_bundle_data["sg_status_list"] == "dep":
                is_deprecated = True

            # now get all versions
            link_field = self._APP_STORE_LINK[self._type]
            entity_type = self._APP_STORE_VERSION[self._type]
            sg_data = sg.find(
                entity_type,
                [[link_field, "is", sg_bundle_data]] + latest_filter,
                ["code"]
            )
        else:
            # now get all versions
            sg_data = sg.find(
                constants.TANK_CORE_VERSION_ENTITY_TYPE,
                filters=latest_filter,
                fields=["code"]
            )

        if len(sg_data) == 0:
            raise TankDescriptorError("Cannot find any versions for %s in the App store!" % self._name)

        version_numbers = [x.get("code") for x in sg_data]
        version_to_use = self._find_latest_tag_by_pattern(version_numbers, version_pattern)

        # make a descriptor dict
        descriptor_dict = {"type": "app_store", "name": self._name, "version": version_to_use}

        # and return a descriptor instance
        desc = IODescriptorAppStore(descriptor_dict, self._sg_connection, self._type)
        desc.set_cache_roots(self._bundle_cache_root, self._fallback_roots)

        # now if this item has been deprecated, meaning that someone has gone in to the app
        # store and updated the record's deprecation status, we want to make sure we download
        # all this info the next time it is being requested. So we force clear the metadata
        # cache.
        if is_deprecated:
            self.__refresh_app_store_metadata()

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
            latest_filter = [["sg_status_list", "is_not", "bad"]]
        else:
            latest_filter = [["sg_status_list", "is_not", "rev"],
                             ["sg_status_list", "is_not", "bad"]]

        is_deprecated = False

        if self._type != self.CORE:
            # items other than core have a main entity that represents
            # app/engine/etc.

            # find the main entry
            sg_bundle_data = sg.find_one(
                self._APP_STORE_OBJECT[self._type],
                [["sg_system_name", "is", self._name]],
                ["id", "sg_status_list"]
            )

            if sg_bundle_data is None:
                raise TankDescriptorError("App store does not contain an item named '%s'!" % self._name)

            # check if this has been deprecated in the app store
            # in that case we should ensure that the cache is cleared later
            if sg_bundle_data["sg_status_list"] == "dep":
                is_deprecated = True

            # now get the version
            link_field = self._APP_STORE_LINK[self._type]
            entity_type = self._APP_STORE_VERSION[self._type]
            sg_version_data = sg.find_one(
                entity_type,
                filters=[[link_field, "is", sg_bundle_data]] + latest_filter,
                fields=["code"],
                order=[{"field_name": "created_at", "direction": "desc"}]
            )

        else:
            # core API
            sg_version_data = sg.find_one(
                constants.TANK_CORE_VERSION_ENTITY_TYPE,
                filters=latest_filter,
                fields=["code"],
                order=[{"field_name": "created_at", "direction": "desc"}]
            )

        if sg_version_data is None:
            raise TankDescriptorError("Cannot find any versions for %s in the App store!" % self._name)

        version_str = sg_version_data.get("code")
        if version_str is None:
            raise TankDescriptorError("Invalid version number for %s" % sg_version_data)

        # make a descriptor dict
        descriptor_dict = {"type": "app_store",
                           "name": self._name,
                           "version": version_str}

        # and return a descriptor instance
        desc = IODescriptorAppStore(descriptor_dict, self._sg_connection, self._type)
        desc.set_cache_roots(self._bundle_cache_root, self._fallback_roots)

        # now if this item has been deprecated, meaning that someone has gone in to the app
        # store and updated the record's deprecation status, we want to make sure we download
        # all this info the next time it is being requested. So we force clear the metadata
        # cache.
        if is_deprecated:
            self.__refresh_app_store_metadata()

        return desc

    @LogManager.log_timing
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

            log.debug("Connecting to %s..." % constants.SGTK_APP_STORE)
            # Connect to the app store and resolve the script user id we are connecting with.
            # Set the timeout explicitly so we ensure the connection won't hang in cases where
            # a response is not returned in a reasonable amount of time.
            app_store_sg = shotgun_api3.Shotgun(
                constants.SGTK_APP_STORE,
                script_name=script_name,
                api_key=script_key,
                http_proxy=self.__get_app_store_proxy_setting(),
                connect=False
            )
            # set the default timeout for app store connections
            app_store_sg.config.timeout_secs = constants.SGTK_APP_STORE_CONN_TIMEOUT

            # determine the script user running currently
            # get the API script user ID from shotgun
            try:
                script_user = app_store_sg.find_one(
                    "ApiUser",
                    filters=[["firstname", "is", script_name]],
                    fields=["type", "id"]
                )
            # Connection errors can occur for a variety of reasons. For example, there is no
            # internet access or there is a proxy server blocking access to the Toolkit app store.
            except (httplib2.HttpLib2Error, httplib2.socks.HTTPError, httplib.HTTPException), e:
                raise TankAppStoreConnectionError(e)
            # In cases where there is a firewall/proxy blocking access to the app store, sometimes
            # the firewall will drop the connection instead of rejecting it. The API request will
            # timeout which unfortunately results in a generic SSLError with only the message text
            # to give us a clue why the request failed.
            # The exception raised in this case is "ssl.SSLError: The read operation timed out"
            except httplib2.ssl.SSLError, e:
                if "timed" in e.message:
                    raise TankAppStoreConnectionError(
                        "Connection to %s timed out: %s" % (app_store_sg.config.server, e)
                    )
                else:
                    # other type of ssl error
                    raise TankAppStoreError(e)
            except Exception, e:
                raise TankAppStoreError(e)

            if script_user is None:
                raise TankAppStoreError(
                    "Could not evaluate the current App Store User! Please contact support."
                )

            self._app_store_connections[sg_url] = (app_store_sg, script_user)

        return self._app_store_connections[sg_url]

    def __get_app_store_proxy_setting(self):
        """
        Retrieve the app store proxy settings. If the key app_store_http_proxy is not found in the
        ``shotgun.yml`` file, the proxy settings from the client site connection will be used. If the
        key is found, than its value will be used. Note that if the ``app_store_http_proxy`` setting
        is set to ``null`` or an empty string in the configuration file, it means that the app store
        proxy is being forced to ``None`` and therefore won't be inherited from the http proxy setting.

        :returns: The http proxy connection string.
        """
        try:
            config_data = shotgun.get_associated_sg_config_data()
        except UnresolvableCoreConfigurationError:
            # This core is not part of a pipeline configuration, we're probably bootstrapping,
            # so skip the check and simply return the regular proxy settings.
            log.debug("No core configuration was found, using the current connection's proxy setting.")
            return self._sg_connection.config.raw_http_proxy

        if config_data and constants.APP_STORE_HTTP_PROXY in config_data:
            return config_data[constants.APP_STORE_HTTP_PROXY]

        settings = UserSettings()
        if settings.is_app_store_proxy_set():
            return settings.app_store_proxy

        # Use the http proxy from the connection so we don't have to run
        # the connection hook again.
        return self._sg_connection.config.raw_http_proxy

    @LogManager.log_timing
    def __get_app_store_key_from_shotgun(self):
        """
        Given a Shotgun url and script credentials, fetch the app store key
        for this shotgun instance using a special controller method.
        Returns a tuple with (app_store_script_name, app_store_auth_key)

        :returns: tuple of strings with contents (script_name, script_key)
        """
        sg = self._sg_connection

        log.debug("Retrieving app store credentials from %s" % sg.base_url)

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

        log.debug("Retrieved app store credentials for account '%s'." % data["script_name"])

        return data["script_name"], data["script_key"]
