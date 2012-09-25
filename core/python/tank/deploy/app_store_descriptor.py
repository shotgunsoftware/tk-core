"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Tank App Store Connectivity.
"""

import os
import copy
import json
import uuid
import zipfile
import tempfile

from ..api import Tank
from ..util import shotgun
from ..errors import TankError
from ..platform import constants
from .descriptor import AppDescriptor


TANK_APP_ENTITY         = "CustomNonProjectEntity02"
TANK_APP_VERSION_ENTITY = "CustomNonProjectEntity05"
TANK_ENGINE_ENTITY      = "CustomNonProjectEntity03"
TANK_ENGINE_VERSION_ENTITY = "CustomNonProjectEntity04"
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

    def __repr__(self):
        if self._type == AppDescriptor.APP:
            return "Tank App Store App %s, %s" % (self._name, self._version)
        elif self._type == AppDescriptor.ENGINE:
            return "Tank App Store Engine %s, %s" % (self._name, self._version)
        else:
            return "Tank App Store <Unknown> %s, %s" % (self._name, self._version)

    def _get_metadata(self):
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
                self._tk.execute_hook(constants.CREATE_FOLDERS_CORE_HOOK_NAME, path=folder)
            fp = open(os.path.join(folder, METADATA_FILE), "wt")
            json.dump(metadata, fp)
            fp.close()
        except:
            # fail gracefully - this is only a cache!
            pass

    ###############################################################################################
    # class methods

    @classmethod
    def find_item(cls, project_root, bundle_type, name):
        """
        Returns an TankAppStoreDescriptor object representing the latest version
        of the sought after object. If no matching item is found, an
        exception is raised.

        This method is useful if you know the name of an app (after browsing in the
        app store for example) and want to get a formal "handle" to it.

        :returns: TankAppStoreDescriptor instance
        """

        # connect to the app store
        (sg, script_user) = shotgun.create_sg_app_store_connection_proj_root(project_root)

        # get the filter logic for what to exclude
        if constants.APP_STORE_QA_MODE_ENV_VAR in os.environ:
            latest_filter = [["sg_status_list", "is_not", "bad" ]]
        else:
            latest_filter = [["sg_status_list", "is_not", "rev" ],
                             ["sg_status_list", "is_not", "bad" ]]
        

        if bundle_type == AppDescriptor.APP:

            # first find the app entity
            bundle = sg.find_one(TANK_APP_ENTITY, [["sg_system_name", "is", name]], ["id"])
            if bundle is None:
                raise TankError("App store does not contain an app named '%s'!" % name)

            # now get the version
            version = sg.find_one(TANK_APP_VERSION_ENTITY,
                                  filters = [["sg_tank_app", "is", bundle]] + latest_filter,
                                  fields = ["code"],
                                  order=[{"field_name": "created_at", "direction": "desc"}])
            if version is None:
                raise TankError("Cannot find any versions for the app '%s'!" % name)

        elif bundle_type == AppDescriptor.ENGINE:

            # first find the engine entity
            bundle = sg.find_one(TANK_ENGINE_ENTITY, [["sg_system_name", "is", name]], ["id"])
            if bundle is None:
                raise TankError("App store does not contain an engine named '%s'!" % name)

            # now get the version
            version = sg.find_one(TANK_ENGINE_VERSION_ENTITY,
                                  filters = [["sg_tank_engine", "is", bundle]] + latest_filter,
                                  fields = ["code"],
                                  order=[{"field_name": "created_at", "direction": "desc"}])
            if version is None:
                raise TankError("Cannot find any versions for the engine '%s'!" % name)

        else:
            raise TankError("Illegal type value!")

        version_str = version.get("code")
        if version_str is None:
            raise TankError("Invalid version number for %s" % version)

        # make a location dict
        location_dict = {"type": "app_store", "name": name, "version": version_str}

        # and return a descriptor instance
        return TankAppStoreDescriptor(project_root, location_dict, bundle_type)

    @classmethod
    def find_engine_for_app(cls, project_root, app_name):
        """
        Returns an TankAppStoreDescriptor object representing the latest version
        of an engine, given an app descriptor. The app store keeps track of
        app/engine relationships

        :returns: TankAppStoreDescriptor instance
        """

        # connect to the app store
        (sg, script_user) = shotgun.create_sg_app_store_connection_proj_root(project_root)

        # get the filter logic for what to exclude
        if constants.APP_STORE_QA_MODE_ENV_VAR in os.environ:
            latest_filter = [["sg_status_list", "is_not", "bad" ]]
        else:
            latest_filter = [["sg_status_list", "is_not", "rev" ],
                             ["sg_status_list", "is_not", "bad" ]]

        # first find the app entity
        bundle = sg.find_one(TANK_APP_ENTITY, [["sg_system_name", "is", app_name]], ["sg_tank_engine"])
        if bundle is None:
            raise TankError("App store does not contain an app named '%s'!" % app_name)

        engine_id = bundle.get("sg_tank_engine", {}).get("id")
        if engine_id is None:
            raise TankError("App does not have an engine associated in Tank App Store!")

        # now find the engine entity
        bundle = sg.find_one(TANK_ENGINE_ENTITY, [["id", "is", engine_id]], ["sg_system_name", "id"])

        # engine name
        name = bundle["sg_system_name"]

        # now get the version
        version = sg.find_one(TANK_ENGINE_VERSION_ENTITY,
                              filters = [["sg_tank_engine", "is", bundle]] + latest_filter,
                              fields = ["code"],
                              order=[{"field_name": "created_at", "direction": "desc"}])
        if version is None:
            raise TankError("Cannot find any versions for the engine '%s'!" % name)

        version_str = version.get("code")
        if version_str is None:
            raise TankError("Invalid version number for %s" % version)

        # make a location dict
        location_dict = {"type": "app_store", "name": name, "version": version_str}

        # and return a descriptor instance
        return TankAppStoreDescriptor(project_root, location_dict, AppDescriptor.ENGINE)

    ###############################################################################################
    # data accessors

    def get_doc_url(self):
        """
        Returns the documentation url for this item. May return None.
        """
        metadata = self._get_metadata()
        url = None
        try:
            url = metadata.get("version").get("sg_documentation").get("url")
        except:
            pass
        return url

    def _get_default_display_name(self):
        """
        Returns the display name for this item. The display name represents
        a brief name of the app, such as "Nuke Publish".
        """
        metadata = self._get_metadata()
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
        metadata = self._get_metadata()
        desc = "No description found"
        try:
            desc = metadata.get("bundle").get("description")
        except:
            pass
        return desc

    def get_short_name(self):
        """
        Returns a short name, suitable for use in configuration files
        and for folders on disk
        """
        return self._name

    def get_changelog(self):
        """
        Returns information about the changelog for this item.
        Returns a tuple: (changelog_summary, changelog_url). Values may be None
        to indicate that no changelog exists.
        """
        summary = None
        url = None
        metadata = self._get_metadata()
        try:
            summary = metadata.get("version").get("description")
            url = metadata.get("version").get("sg_detailed_release_notes").get("url")
        except:
            pass
        return (summary, url)

    def get_version_constraints(self):
        """
        Returns a dictionary with version constraints. The absence of a key
        indicates that there is no defined constraint. Keys include:
        * min_sg
        * min_core
        * min_engine
        """
        metadata = self._get_metadata()
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

    def get_version(self):
        """
        Returns the version number string for this item
        """
        return self._version

    def get_location(self):
        """
        Returns the location for this descriptor
        """
        return self._location_dict

    def get_path(self):
        """
        returns the path to the folder where this item resides
        """
        return self._get_local_location(self._type, "app_store", self._name, self._version)

    ###############################################################################################
    # methods

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
            self._tk.execute_hook(constants.CREATE_FOLDERS_CORE_HOOK_NAME, path=target)

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
        bundle_content = sg.download_attachment(attachment_id)

        zip_tmp = os.path.join(tempfile.gettempdir(), "%s_tank.zip" % uuid.uuid4().hex)
        fh = open(zip_tmp, "wb")
        fh.write(bundle_content)
        fh.close()

        # unzip core zip file to app target location
        z = zipfile.ZipFile(zip_tmp, "r")
        z.extractall(target)

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


