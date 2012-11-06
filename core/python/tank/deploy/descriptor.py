"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Functionality for managing versions of apps.
"""

import os
import shutil

from tank_vendor import yaml

from ..util import shotgun
from ..errors import TankError
from ..platform import constants


class AppDescriptor(object):
    """
    An app descriptor describes a particular version of an app, engine or core component.
    It also knows how to access metadata such as documentation, descriptions etc.

    Several AppDescriptor classes exists, all deriving from this base class, and the
    factory method get_from_location() manufactures the correct descriptor object
    based on a location dict, that is found inside of the environment config.

    Different App Descriptor implementations typically handle different source control
    systems: There may be an app descriptor which knows how to communicate with the
    Tank App store and one which knows how to handle the local file system.
    """

    ###############################################################################################
    # constants and helpers

    # constants describing the type of item we are describing
    APP, ENGINE, FRAMEWORK = range(3)

    def __init__(self, project_root, location_dict):
        self._project_root = project_root
        self._location_dict = location_dict

    def _get_local_location(self, app_type, descriptor_name, name, version):
        """
        Calculate the local location for an item. This is a convenience method
        that can be used by implementing classes if they want to stash the code
        payload in a standardized location in the file system.
        """

        # examples:
        # /studio/tank/install/engines/app_store/tk-nuke/v0.2.3
        # /studio/tank/install/apps/APP_TYPE/NAME/VERSION

        if app_type == AppDescriptor.APP:
            root = constants.get_local_app_location()
        elif app_type == AppDescriptor.ENGINE:
            root = constants.get_local_engine_location()
        elif app_type == AppDescriptor.FRAMEWORK:
            root = constants.get_local_framework_location()
        else:
            raise TankError("Don't know how to figure out the local storage root - unknown type!")
        return os.path.join(root, descriptor_name, name, version)

    def __repr__(self):
        return "Tank Descriptor: %s (%s) %s" % (self.get_short_name(),
                                                self.get_display_name(),
                                                self.get_version())

    def __ensure_sg_field_exists(self, sg, sg_type, sg_field_name, sg_data_type):
        """
        Ensures that a shotgun field exists.
        """

        # sg_my_awesome_field -> My Awesome Field
        if not sg_field_name.startswith("sg_"):
            # invalid field name - exit early
            return
        ui_field_name = " ".join(word.capitalize() for word in sg_field_name[3:].split("_"))

        # ensure that the Entity type is enabled in tank
        try:
            sg.find_one(sg_type, [])
        except:
            raise TankError("The required entity type %s is not enabled in Shotgun!" % sg_type)

        # now check that the field exists
        sg_field_schema = sg.schema_field_read(sg_type)
        if sg_field_name not in sg_field_schema:
            sg.schema_field_create(sg_type, sg_data_type, ui_field_name)

    ###############################################################################################
    # data accessors

    def get_doc_url(self):
        """
        Returns the documentation url for this item. Returns None if the documentation url
        is not defined.
        """
        return None

    def get_display_name(self):
        """
        Returns the display name for this item. Returns "Undefined" if not defined.
        """
        meta = self.get_metadata()
        display_name = meta.get("display_name")
        return display_name or self._get_default_display_name()

    def _get_default_display_name(self):
        """
        Used if display_name not set in configuration.
        """
        return "Undefined"

    def get_description(self):
        """
        Returns a short description for the app.
        """
        return "No description available"

    def get_short_name(self):
        """
        Returns a short name, suitable for use in configuration files
        and for folders on disk
        """
        raise NotImplementedError

    def get_changelog(self):
        """
        Returns information about the changelog for this item.
        Returns a tuple: (changelog_summary, changelog_url). Values may be None
        to indicate that no changelog exists.
        """
        return (None, None)

    def get_version_constraints(self):
        """
        Returns a dictionary with version constraints. The absence of a key
        indicates that there is no defined constraint. The following keys can be
        returned: min_sg, min_core, min_engine
        """
        # default implementation has no constraints
        return {}

    def get_version(self):
        """
        Returns the version number string for this item.
        """
        raise NotImplementedError

    def get_location(self):
        """
        Returns the location dict associated with this descriptor
        """
        raise NotImplementedError

    def get_path(self):
        """
        returns the path to the folder where this item resides
        """
        raise NotImplementedError

    ###############################################################################################
    # methods

    def exists_local(self):
        """
        Returns true if this item exists in a local repo
        """
        raise NotImplementedError

    def download_local(self):
        """
        Retrieves this version to local repo.
        """
        raise NotImplementedError

    def find_latest_version(self):
        """
        Returns a descriptor object that represents the latest version
        """
        raise NotImplementedError

    def get_metadata(self):
        """
        Returns the info.yml metadata associated with this description.
        Note that this call involves deep introspection; in order to
        access the metadata we normally need to have the code content
        local, so this method may trigger a remote code fetch if necessary.
        """
        # local import due to cyclic deps
        from ..platform.environment import Environment

        # make sure payload exists locally
        if not self.exists_local():
            self.download_local()
        # get the metadata
        bundle_root = self.get_path()

        file_path = os.path.join(bundle_root, constants.BUNDLE_METADATA_FILE)

        if not os.path.exists(file_path):
            raise TankError("Tank metadata file '%s' missing." % file_path)

        try:
            file_data = open(file_path)
            try:
                metadata = yaml.load(file_data)
            finally:
                file_data.close()
        except Exception, exp:
            raise TankError("Cannot load metadata file '%s'. Error: %s" % (file_path, exp))

        # validate the bundle
        if not "configuration" in metadata:
            raise TankError("Missing configuration section in %s!" % file_path)
        elif metadata["configuration"] is None:
            metadata["configuration"] = {}

        return metadata

    def ensure_shotgun_fields_exist(self, project_root):
        """
        Ensures that any shotgun fields a particular descriptor requires
        exists in shotgun. In the metadata (info.yml) for an app or an engine,
        it is possible to define a section for this:

        # the Shotgun fields that this app needs in order to operate correctly
        requires_shotgun_fields:
            Version:
                - { "system_name": "sg_movie_type", "type": "text" }

        This method will retrieve the metadata and ensure that any required
        fields exists.
        """
        # first fetch metadata
        meta = self.get_metadata()
        # get a sg handle
        sg = shotgun.create_sg_connection(project_root)
        # get fields def
        sg_fields_def = meta.get("requires_shotgun_fields")
        if sg_fields_def:  # can be defined as None from yml file
            for sg_entity_type in sg_fields_def:
                for field in sg_fields_def.get(sg_entity_type, []):
                    # attempt to create field!
                    sg_data_type = field["type"]
                    sg_field_name = field["system_name"]
                    self.__ensure_sg_field_exists(sg, sg_entity_type, sg_field_name, sg_data_type)

    def install_hook(self, logger, default_hook_name):
        """
        Installs a hook given the default name. If a hook with the same name already exists it will prepend the app/engine shortname.

        :param Logger logger: a logger for output.
        :param str default_hook_name: default hook filename as define in the app/engine info.yml
        :returns str: the final hook filename
        """
        install_path = self.get_path()
        hook_file = os.path.join(install_path, "hooks", "%s.py" % default_hook_name)
        project_hook_location = constants.get_hooks_folder(self._project_root)
        if not os.path.exists(hook_file):
            raise TankError("Hook file %s could not be found." % hook_file)

        project_hook_file = os.path.join(project_hook_location, "%s.py" % default_hook_name)
        hook_name = default_hook_name
        if os.path.exists(project_hook_file):
            hook_name = "%s_%s" % (self.get_short_name().replace("-", "_"), default_hook_name)
            project_hook_file = os.path.join(project_hook_location, "%s.py" % hook_name)

        try:
            shutil.copy(hook_file, project_hook_file)
            logger.info("Installed Hook: %s", project_hook_file)
        except (IOError, OSError), ex:
            raise TankError("Could not copy hook.\nError: %s" % (ex))
        return hook_name

################################################################################################
# factory method for app descriptors

def get_from_location(app_or_engine, project_root, location_dict):
    """
    Factory method.

    :param app_or_engine: Either AppDescriptor.APP AppDescriptor.ENGINE or FRAMEWORK
    :param project_root: The project root
    :param location_dict: A tank location dict
    :returns: an AppDescriptor object
    """
    from .app_store_descriptor import TankAppStoreDescriptor
    from .dev_descriptor import TankDevDescriptor
    from .github_dev_descriptor import TankGitHubDevDescriptor
    from .github_descriptor import TankGitHubDescriptor
    from .git_descriptor import TankGitDescriptor

    # temporary implementation. Todo: more error checks!

    # tank app store format - apps/engines
    # location: {"type": "app_store", "name": "tk-nukepublish", "version": "v0.5.0"}
    if location_dict.get("type") == "app_store":
        return TankAppStoreDescriptor(project_root, location_dict, app_or_engine)

    # git repo
    # location: {"type": "git", "path": "/path/to/repo.git", "version": "v0.2.1"}
    elif location_dict.get("type") == "git":
        return TankGitDescriptor(project_root, location_dict, app_or_engine)

    # github public repo
    # location: {"type": "github", "vendor": "shotgunsoftware", "repo": "tk-nuke", "version": "v0.2.1"}
    elif location_dict.get("type") == "github":
        return TankGitHubDescriptor(project_root, location_dict, app_or_engine)

    # local dev format
    # location: {"type": "dev", "path": "/path/to/app"}
    # or
    # location: {"type": "dev", "windows_path": "c:\\path\\to\\app", "linux_path": "/path/to/app", "mac_path": "/path/to/app"}
    elif location_dict.get("type") == "dev":
        return TankDevDescriptor(project_root, location_dict)

    # github dev - track head of repo
    # location: {"type": "github_dev", "vendor": "shotgunsoftware", "repo": "tk-nuke"}
    elif location_dict.get("type") == "github_dev":
        return TankGitHubDevDescriptor(project_root, location_dict, app_or_engine)

    else:
        raise TankError("Invalid location dict '%s'" % location_dict)

