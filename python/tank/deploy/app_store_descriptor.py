"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Tank App Store Connectivity.
"""

import os
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


TANK_APP_ENTITY         = "CustomNonProjectEntity02"
TANK_APP_VERSION_ENTITY = "CustomNonProjectEntity05"
TANK_ENGINE_ENTITY      = "CustomNonProjectEntity03"
TANK_ENGINE_VERSION_ENTITY = "CustomNonProjectEntity04"
TANK_FRAMEWORK_ENTITY      = "CustomNonProjectEntity13"
TANK_FRAMEWORK_VERSION_ENTITY = "CustomNonProjectEntity09"

TANK_CODE_PAYLOAD_FIELD = "sg_payload"
TANK_APP_STORE_DUMMY_PROJECT = {"type": "Project", "id": 64}

METADATA_FILE = ".metadata.json"

class TankAppStoreDescriptor(AppDescriptor):
    """
    Represents an app store item.

    Note: Construction of instances of this class can happen in two ways:

    - via the factory method in descriptor.get_from_location()
    - via the class method TankAppStoreDescriptor.find_item()

    """

    def __init__(self, project_root, location_dict, bundle_type):
        super(TankAppStoreDescriptor, self).__init__(project_root, location_dict)

        self._type = bundle_type
        self._tk = Tank(project_root)
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

        # connect to the app store
        (sg, script_user) = shotgun.create_sg_app_store_connection_proj_root(self._project_root)

        if self._type == AppDescriptor.APP:

            # first find the app entity
            bundle = sg.find_one(TANK_APP_ENTITY,
                                 [["sg_system_name", "is", self._name]],
                                 ["description", "code"])
            if bundle is None:
                raise TankError("App store does not contain an app named '%s'!" % self._name)

            # now get the version
            version = sg.find_one(TANK_APP_VERSION_ENTITY,
                                  [["sg_tank_app", "is", bundle], ["code", "is", self._version]],
                                  ["description",
                                   TANK_CODE_PAYLOAD_FIELD,
                                   "sg_min_shotgun_version",
                                   "sg_min_core_version",
                                   "sg_min_engine_version",
                                   "sg_detailed_release_notes",
                                   "sg_documentation",
                                   ])
            if version is None:
                raise TankError("App store does not have a version "
                                "'%s' of app '%s'!" % (self._version, self._name))

        elif self._type == AppDescriptor.FRAMEWORK:

            # first find the engine entity
            bundle = sg.find_one(TANK_FRAMEWORK_ENTITY,
                                 [["sg_system_name", "is", self._name]],
                                 ["description", "code"])
            if bundle is None:
                raise TankError("App store does not contain a framework named '%s'!" % self._name)

            # now get the version
            version = sg.find_one(TANK_FRAMEWORK_VERSION_ENTITY,
                                  [["sg_tank_framework", "is", bundle], ["code", "is", self._version]],
                                  ["description",
                                   TANK_CODE_PAYLOAD_FIELD,
                                   "sg_detailed_release_notes",
                                   "sg_documentation",
                                   ])
            if version is None:
                raise TankError("App store does not have a version "
                                "'%s' of framework '%s'!" % (self._version, self._name))

        elif self._type == AppDescriptor.ENGINE:

            # first find the engine entity
            bundle = sg.find_one(TANK_ENGINE_ENTITY,
                                 [["sg_system_name", "is", self._name]],
                                 ["description", "code"])
            if bundle is None:
                raise TankError("App store does not contain an engine named '%s'!" % self._name)

            # now get the version
            version = sg.find_one(TANK_ENGINE_VERSION_ENTITY,
                                  [["sg_tank_engine", "is", bundle], ["code", "is", self._version]],
                                  ["description",
                                   TANK_CODE_PAYLOAD_FIELD,
                                   "sg_min_shotgun_version",
                                   "sg_min_core_version",
                                   "sg_detailed_release_notes",
                                   "sg_documentation",
                                   ])
            if version is None:
                raise TankError("App store does not have a version "
                                "'%s' of engine '%s'!" % (self._version, self._name))

        else:
            raise TankError("Illegal type value!")

        return {"bundle": bundle, "version": version}

    def __cache_app_store_metadata(self, metadata):
        """
        Caches app store metadata to disk.
        """
        # write it to file for later access

        folder = self.get_path()

        try:
            if not os.path.exists(folder):
                self._tk.execute_hook(constants.CREATE_FOLDERS_CORE_HOOK_NAME, path=folder, sg_entity=None)
            fp = open(os.path.join(folder, METADATA_FILE), "wt")
            json.dump(metadata, fp)
            fp.close()
        except:
            # fail gracefully - this is only a cache!
            pass

    ###############################################################################################
    # class methods

    @classmethod
    def find_item(cls, project_root, bundle_type, name, version=None):
        """
        Returns an TankAppStoreDescriptor object representing the latest version
        of the sought after object. If no matching item is found, an
        exception is raised.

        This method is useful if you know the name of an app (after browsing in the
        app store for example) and want to get a formal "handle" to it.

        If version is None, the latest version is returned.

        :returns: TankAppStoreDescriptor instance
        """

        # connect to the app store
        (sg, script_user) = shotgun.create_sg_app_store_connection_proj_root(project_root)

        if version is None:
            # get latest
            # get the filter logic for what to exclude
            if constants.APP_STORE_QA_MODE_ENV_VAR in os.environ:
                latest_filter = [["sg_status_list", "is_not", "bad" ]]
            else:
                latest_filter = [["sg_status_list", "is_not", "rev" ],
                                 ["sg_status_list", "is_not", "bad" ]]
        
        else:
            # specific version
            latest_filter = [["code", "is", version]]
        
        # set up some lookup tables so we look in the right table in sg
        main_entity_map = { AppDescriptor.APP: TANK_APP_ENTITY,
                            AppDescriptor.FRAMEWORK: TANK_FRAMEWORK_ENTITY,
                            AppDescriptor.ENGINE: TANK_ENGINE_ENTITY }

        version_entity_map = { AppDescriptor.APP: TANK_APP_VERSION_ENTITY,
                               AppDescriptor.FRAMEWORK: TANK_FRAMEWORK_VERSION_ENTITY,
                               AppDescriptor.ENGINE: TANK_ENGINE_VERSION_ENTITY }

        link_field_map = { AppDescriptor.APP: "sg_tank_app",
                           AppDescriptor.FRAMEWORK: "sg_tank_framework",
                           AppDescriptor.ENGINE: "sg_tank_engine" }

        # find the main entry
        bundle = sg.find_one(main_entity_map[bundle_type], [["sg_system_name", "is", name]], ["id"])
        if bundle is None:
            raise TankError("App store does not contain an item named '%s'!" % name)

        # now get the version
        link_field = link_field_map[bundle_type]
        entity_type = version_entity_map[bundle_type]
        sg_version_data = sg.find_one(entity_type,
                                      filters = [[link_field, "is", bundle]] + latest_filter,
                                      fields = ["code"],
                                      order=[{"field_name": "created_at", "direction": "desc"}])
        if sg_version_data is None:
            if version is None:
                raise TankError("Cannot find any versions for %s in the Tank store!" % name)
            else:
                raise TankError("Cannot find %s %s in the Tank store!" % (name, version))



        version_str = sg_version_data.get("code")
        if version_str is None:
            raise TankError("Invalid version number for %s" % sg_version_data)

        # make a location dict
        location_dict = {"type": "app_store", "name": name, "version": version_str}

        # and return a descriptor instance
        return TankAppStoreDescriptor(project_root, location_dict, bundle_type)


    ###############################################################################################
    # data accessors

    def get_display_name(self):
        """
        Returns the display name for this item. The display name represents
        a brief name of the app, such as "Nuke Publish".
        """
        # overriden from base class. uses name in info.yml if possible.
        info_yml_display_name = AppDescriptor.get_display_name(self)
        
        if info_yml_display_name != self.get_system_name():
            # there is a display name defined in info.yml! 
            return info_yml_display_name
        
        # no display name found in info.yml - get it from the app store...
        metadata = self._get_app_store_metadata()
        display_name = "Unknown"
        try:
            display_name = metadata.get("bundle").get("code")
        except:
            pass
        return display_name

    def get_description(self):
        """
        Returns a short description for the app.
        """
        # overriden from base class. uses name in info.yml if possible.
        info_yml_description = AppDescriptor.get_description(self)
        
        if info_yml_description != "No description available":
            # there is a display name defined in info.yml! 
            return info_yml_description
        
        # no desc found in info.yml - get it from the app store...
        metadata = self._get_app_store_metadata()
        desc = "No description available"
        try:
            desc = metadata.get("bundle").get("description")
        except:
            pass
        return desc


    def get_version_constraints(self):
        """
        Returns a dictionary with version constraints. The absence of a key
        indicates that there is no defined constraint. Keys include:
        * min_sg
        * min_core
        * min_engine
        """
        constraints = AppDescriptor.get_version_constraints(self)
        if len(constraints) > 0:
            # found constraints in info.yml
            # use these
            return constraints 
        
        # no constraints in info.yml. Check with app store
        metadata = self._get_app_store_metadata()
        constraints = {}
        version = metadata.get("version")

        if version:
            min_sg_version = version.get("sg_min_shotgun_version")
            if min_sg_version:
                constraints["min_sg"] = min_sg_version

            min_core_version = version.get("sg_min_core_version")
            if min_core_version:
                # this is an entity link, so grab the name field
                constraints["min_core"] = min_core_version.get("name")

            min_engine_version = version.get("sg_min_engine_version")
            if min_engine_version:
                # this is an entity link, so grab the name field
                constraints["min_engine"] = min_engine_version.get("name")

        return constraints


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
            self._tk.execute_hook(constants.CREATE_FOLDERS_CORE_HOOK_NAME, path=target, sg_entity=None)

        # connect to the app store
        (sg, script_user) = shotgun.create_sg_app_store_connection_proj_root(self._project_root)
        local_sg = shotgun.create_sg_connection(self._project_root)

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
            attachment_id = int(version[TANK_CODE_PAYLOAD_FIELD]["url"].split("/")[-1])
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
            data["project"] = TANK_APP_STORE_DUMMY_PROJECT
            data["attribute_name"] = TANK_CODE_PAYLOAD_FIELD
            sg.create("EventLogEntry", data)

        elif self._type == AppDescriptor.FRAMEWORK:
            data = {}
            data["description"] = "%s: Framework %s %s was downloaded" % (local_sg.base_url, self._name, self._version)
            data["event_type"] = "TankAppStore_Framework_Download"
            data["entity"] = version
            data["user"] = script_user
            data["project"] = TANK_APP_STORE_DUMMY_PROJECT
            data["attribute_name"] = TANK_CODE_PAYLOAD_FIELD
            sg.create("EventLogEntry", data)

        elif self._type == AppDescriptor.ENGINE:
            data = {}
            data["description"] = "%s: Engine %s %s was downloaded" % (local_sg.base_url, self._name, self._version)
            data["event_type"] = "TankAppStore_Engine_Download"
            data["entity"] = version
            data["user"] = script_user
            data["project"] = TANK_APP_STORE_DUMMY_PROJECT
            data["attribute_name"] = TANK_CODE_PAYLOAD_FIELD
            sg.create("EventLogEntry", data)

        else:
            raise TankError("Invalid bundle type")

    def find_latest_version(self):
        """
        Returns a descriptor object that represents the latest version
        """
        latest_version = self.find_item(self._project_root, self._type, self._name)
        return latest_version


