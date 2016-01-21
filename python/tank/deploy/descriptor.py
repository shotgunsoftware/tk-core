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
Functionality for managing versions of apps.
"""

import os
import sys
import copy
import sys

from tank_vendor import yaml

from .. import hook
from ..util import shotgun, yaml_cache
from ..errors import TankError, TankFileDoesNotExistError
from ..platform import constants


class AppDescriptor(object):
    """
    An app descriptor describes a particular version of an app, engine or core component.
    It also knows how to access metadata such as documentation, descriptions etc.

    Several AppDescriptor classes exists, all deriving from this base class, and the
    factory method descriptor_factory() manufactures the correct descriptor object
    based on a location dict, that is found inside of the environment config.

    Different App Descriptor implementations typically handle different source control
    systems: There may be an app descriptor which knows how to communicate with the
    Tank App store and one which knows how to handle the local file system.
    """

    ###############################################################################################
    # constants and helpers

    # constants describing the type of item we are describing
    APP, ENGINE, FRAMEWORK, CORE = range(4)

    def __init__(self, bundle_install_path, location_dict):
        self._bundle_install_path = bundle_install_path
        self._location_dict = location_dict
        self.__manifest_data = None

    def __repr__(self):
        class_name = self.__class__.__name__
        return "<%s %s %s>" % (class_name, self.get_system_name(), self.get_version())

    def __str__(self):
        """
        Used for pretty printing
        """
        return "%s %s" % (self.get_system_name(), self.get_version())

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
            root = os.path.join(self._bundle_install_path, "apps")
        elif app_type == AppDescriptor.ENGINE:
            root = os.path.join(self._bundle_install_path, "engines")
        elif app_type == AppDescriptor.FRAMEWORK:
            root = os.path.join(self._bundle_install_path, "frameworks")
        elif app_type == AppDescriptor.CORE:
            root = os.path.join(self._bundle_install_path, "cores")
        else:
            raise TankError("Don't know how to figure out the local storage root - unknown type!")
        return os.path.join(root, descriptor_name, name, version)

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

    def _get_metadata(self):
        """
        Returns the info.yml metadata associated with this descriptor.
        Note that this call involves deep introspection; in order to
        access the metadata we normally need to have the code content
        local, so this method may trigger a remote code fetch if necessary.
        """
        if self.__manifest_data is None:
            # make sure payload exists locally
            if not self.exists_local():
                self.download_local()
                
            # get the metadata
            bundle_root = self.get_path()
            file_path = os.path.join(bundle_root, constants.BUNDLE_METADATA_FILE)

            try:
                metadata = yaml_cache.g_yaml_cache.get(file_path, deepcopy_data=False)
            except TankFileDoesNotExistError:
                raise
            except Exception, exp:
                raise TankError("Cannot load metadata file '%s'. Error: %s" % (file_path, exp))

            # cache it
            self.__manifest_data = metadata
        return self.__manifest_data


    ###############################################################################################
    # data accessors

    def get_location(self):
        """
        Returns the location dict associated with this descriptor
        """
        return self._location_dict

    def get_display_name(self):
        """
        Returns the display name for this item.
        If no display name has been defined, the system name will be returned.
        """
        meta = self._get_metadata()
        display_name = meta.get("display_name")
        if display_name is None:
            display_name = self.get_system_name()
        return display_name

    def get_description(self):
        """
        Returns a short description for the app.
        """
        meta = self._get_metadata()
        desc = meta.get("description")
        if desc is None:
            desc = "No description available." 
        return desc

    def get_icon_256(self):
        """
        Returns the path to a 256px square png icon file for this app
        """
        app_icon = os.path.join(self.get_path(), "icon_256.png")
        if os.path.exists(app_icon):
            return app_icon
        else:
            # return default
            default_icon = os.path.abspath(os.path.join( os.path.dirname(__file__), 
                                                         "..", "platform", "qt",
                                                         "default_app_icon_256.png"))
            return default_icon

    def get_support_url(self):
        """
        Returns a url that points to a support web page where you can get help
        if you are stuck with this item.
        """
        meta = self._get_metadata()
        support_url = meta.get("support_url")
        if support_url is None:
            support_url = "https://support.shotgunsoftware.com" 
        return support_url

    def get_doc_url(self):
        """
        Returns the documentation url for this item. Returns None if the documentation url
        is not defined. This is sometimes subclassed, where a descriptor (like the tank app
        store) and support for automatic, built in documentation management. If not, the 
        default implementation will search the manifest for a doc url location.
        """
        meta = self._get_metadata()
        doc_url = meta.get("documentation_url")
        # note - doc_url can be none which is fine.
        return doc_url


    def get_version_constraints(self):
        """
        Returns a dictionary with version constraints. The absence of a key
        indicates that there is no defined constraint. The following keys can be
        returned: min_sg, min_core, min_engine and min_desktop
        """
        constraints = {}

        meta = self._get_metadata()
        
        if meta.get("requires_shotgun_version") is not None:
            constraints["min_sg"] = meta.get("requires_shotgun_version")
        
        if meta.get("requires_core_version") is not None:
            constraints["min_core"] = meta.get("requires_core_version")

        if meta.get("requires_engine_version") is not None:
            constraints["min_engine"] = meta.get("requires_engine_version")

        if meta.get("requires_desktop_version") is not None:
            constraints["min_desktop"] = meta.get("requires_desktop_version")

        return constraints

    def get_supported_engines(self):
        """
        Returns the engines supported for this app. May return None,
        meaning that anything goes.
        
        return: None                   (all engines are fine!)
        return: ["tk-maya", "tk-nuke"] (works with maya and nuke)
        """
        md  = self._get_metadata()
        return md.get("supported_engines")
        
    def get_required_context(self):
        """
        Returns the required context, if there is one defined for a bundle.
        This is a list of strings, something along the lines of 
        ["user", "task", "step"] for an app that requires a context with 
        user task and step defined.
        
        Always returns a list, with an empty list meaning no items required.
        """
        md  = self._get_metadata()
        rc = md.get("required_context")
        if rc is None:
            rc = []
        return rc
    
    def get_supported_platforms(self):
        """
        Returns the platforms supported. Possible values
        are windows, linux and mac. 
        
        Always returns a list, returns an empty list if there is 
        no constraint in place. 
        
        example: ["windows", "linux"]
        example: []
        """
        md  = self._get_metadata()
        sp = md.get("supported_platforms")
        if sp is None:
            sp = []
        return sp
        
    def get_configuration_schema(self):
        """
        Returns the manifest configuration schema for this bundle.
        Always returns a dictionary.
        """
        md  = self._get_metadata()
        cfg = md.get("configuration")
        # always return a dict
        if cfg is None:
            cfg = {}
        return cfg
         
    def get_required_frameworks(self):
        """
        returns the list of required frameworks for this item.
        Always returns a list for example
        
        [{'version': 'v0.1.0', 'name': 'tk-framework-widget'}]
        
        Each item contains a name and a version key.
        """
        md  = self._get_metadata()
        frameworks = md.get("frameworks")
        # always return a list
        if frameworks is None:
            frameworks = []
        return frameworks

    def get_deprecation_status(self):
        """
        Returns (is_deprecated (bool), message (str)) to indicate if this item is deprecated.
        """
        # only some descriptors handle this. Default is to not support deprecation, e.g.
        # always return that things are active.
        return (False, "")

    def is_shared_framework(self):
        """
        Returns a boolean indicating whether the bundle is a shared framework.

        Shared frameworks only have a single instance per instance name in the
        current environment.
        """
        md  = self._get_metadata()
        shared = md.get("shared")
        # always return a bool
        if shared is None:
            # frameworks are now shared by default unless you opt out.
            shared = True
        return shared

    ###############################################################################################
    # stuff typically implemented by deriving classes
    
    def get_system_name(self):
        """
        Returns a short name, suitable for use in configuration files
        and for folders on disk
        """
        raise NotImplementedError
    
    def get_version(self):
        """
        Returns the version number string for this item.
        """
        raise NotImplementedError    
    
    def get_path(self):
        """
        returns the path to the folder where this item resides
        """
        raise NotImplementedError
        
    def get_changelog(self):
        """
        Returns information about the changelog for this item.
        Returns a tuple: (changelog_summary, changelog_url). Values may be None
        to indicate that no changelog exists.
        """
        return (None, None)
    
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
        raise NotImplementedError

    ###############################################################################################
    # helper methods

    def ensure_shotgun_fields_exist(self):
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
        meta = self._get_metadata()
        # get fields def
        sg_fields_def = meta.get("requires_shotgun_fields")
        if sg_fields_def:  # can be defined as None from yml file
            # get a sg handle
            sg = shotgun.get_sg_connection()
            
            for sg_entity_type in sg_fields_def:
                for field in sg_fields_def.get(sg_entity_type, []):
                    # attempt to create field!
                    sg_data_type = field["type"]
                    sg_field_name = field["system_name"]
                    self.__ensure_sg_field_exists(sg, sg_entity_type, sg_field_name, sg_data_type)

    def run_post_install(self, tk):
        """
        If a post install hook exists in a descriptor, execute it. In the
        hooks directory for an app or engine, if a 'post_install.py' hook
        exists, the hook will be executed upon each installation.
        
        :param tk: Tk API instance associated with this item
        """
        
        post_install_hook_path = os.path.join(self.get_path(), "hooks",
                                              "post_install.py")
        try:
            hook.execute_hook(post_install_hook_path, 
                              parent=None,
                              pipeline_configuration=tk.pipeline_configuration.get_path(),
                              path=self.get_path())
        except TankFileDoesNotExistError:
            pass
        except Exception, e:
            raise TankError("Could not run post-install hook for %s. "
                            "Error reported: %s" % (self, e))


class VersionedSingletonDescriptor(AppDescriptor):
    """
    Singleton base class for the versioned app descriptor classes.

    Each descriptor object is a singleton based on its install root path,
    name, and version number.
    """
    _instances = dict()

    def __new__(cls, bundle_install_path, location_dict, *args, **kwargs):
        """
        Executed prior to all __init__s. Handles singleton caching of descriptors.

        Since all our normal descriptors are immutable - they represent a specific,
        readonly and cached version of an app, engine or framework on disk, we can
        also cache their wrapper objects.

        All descriptor types deriving from this caching class need to have a
        required name and version key as part of their location dict. These
        keys are used by the class to uniquely identify objects.

        :param bundle_install_path: Location on disk where items are cached
        :param location_dict: Location dictionary describing the bundle
        :return: Descriptor instance
        """

        # We will cache based on the bundle install path, name of the
        # app/engine/framework, and version number.
        instance_cache = cls._instances
        name = location_dict.get("name")
        version = location_dict.get("version")

        if name is None or version is None:
            raise TankError("Cannot process location '%s'. Name and version keys required." % location_dict)

        # Instantiate and cache if we need to, otherwise just return what we
        # already have stored away.
        if (bundle_install_path not in instance_cache or
            name not in instance_cache[bundle_install_path] or
            version not in instance_cache[bundle_install_path][name]):
            # If the bundle install path isn't in the cache, then we are
            # starting fresh. Otherwise, check to see if the app (by name)
            # is cached, and if not initialize its specific cache. After
            # that we instantiate and store by version.
            if bundle_install_path not in instance_cache:
                instance_cache[bundle_install_path] = dict()
            if name not in instance_cache[bundle_install_path]:
                instance_cache[bundle_install_path][name] = dict()
            instance_cache[bundle_install_path][name][version] = super(VersionedSingletonDescriptor, cls).__new__(
                cls,
                bundle_install_path,
                location_dict,
                *args, **kwargs
            )

        return instance_cache[bundle_install_path][name][version]


################################################################################################
# factory method for app descriptors

def preprocess_location(location_dict, pipeline_config):
    """
    Preprocess location dict to resolve config-specific constants and directives.
    
    This is only relevant if the locator system is used in conjunction with 
    a toolkit configuration. For example, the keyword {PIPELINE_CONFIG} is
    only meaningful if used in the context of a configuration.
    
    Location dictionaries defined and used outside of the scope of a 
    pipeline configuration do not support such keywords (since no 
    pipeline configuration exists at that point). 
    
    :param location_dict: Location dict to operate on
    :param pipeline_config: Pipeline Config object
    :returns: location dict with any directives resolved.
    """

    if location_dict.get("type") == "dev":
        
        # platform specific location support
        platform_key = {"linux2": "linux_path", "darwin": "mac_path", "win32": "windows_path"}[sys.platform]
        if platform_key in location_dict:
            location_dict[platform_key] = location_dict[platform_key].replace("{PIPELINE_CONFIG}", pipeline_config.get_path())

        if "path" in location_dict:
            location_dict["path"] = location_dict["path"].replace("{PIPELINE_CONFIG}", pipeline_config.get_path())

    return location_dict


def descriptor_factory(descriptor_type, app_cache_root, location_dict):
    """
    Factory method.

    :param descriptor_type: Either AppDescriptor.APP, CORE, ENGINE or FRAMEWORK
    :param app_cache_root: Root path to where downloaded apps are cached
    :param location_dict: A std location dictionary
    :returns: Descriptor object
    """
    return get_from_location_and_paths(descriptor_type, None, app_cache_root, location_dict)

################################################################################################
# legacy methods - do not use.

def get_from_location(app_or_engine, pipeline_config, location_dict):
    """
    Factory method.
    
    LEGACY - Use pipelineconfiguration.get_app|engine|framework_descriptor() 
             instead.

    :param app_or_engine: Either AppDescriptor.APP ENGINE CORE or FRAMEWORK
    :param pipeline_config: Pipeline Configuration Object
    :param location_dict: A tank location dict
    :returns: an AppDescriptor object
    """
    return get_from_location_and_paths(
        app_or_engine,
        None,
        pipeline_config._get_bundles_location(), #TODO - fix this
        location_dict
    )

def get_from_location_and_paths(app_or_engine, pc_path, bundle_install_path, location_dict):
    """
    Factory method.
    
    LEGACY - Use descriptor_factory() instead.

    :param app_or_engine: Either AppDescriptor.APP ENGINE CORE or FRAMEWORK
    :param pc_path: Path to the root of the pipeline configuration. 
                    Legacy parameter and no longer used. This value will be ignored.
    :param bundle_install_path: Path to the root of the apps, frameworks and engines bundles.
    :param location_dict: A tank location dict
    :returns: an AppDescriptor object
    """

    from .app_store_descriptor import TankAppStoreDescriptor
    from .dev_descriptor import TankDevDescriptor
    from .git_descriptor import TankGitDescriptor
    from .manual_descriptor import TankManualDescriptor

    # tank app store format
    # location: {"type": "app_store", "name": "tk-nukepublish", "version": "v0.5.0"}
    if location_dict.get("type") == "app_store":
        return TankAppStoreDescriptor(bundle_install_path, location_dict, app_or_engine)

    # manual format
    # location: {"type": "manual", "name": "tk-nukepublish", "version": "v0.5.0"}
    elif location_dict.get("type") == "manual":
        return TankManualDescriptor(bundle_install_path, location_dict, app_or_engine)

    # git repo
    # location: {"type": "git", "path": "/path/to/repo.git", "version": "v0.2.1"}
    elif location_dict.get("type") == "git":
        return TankGitDescriptor(bundle_install_path, location_dict, app_or_engine)

    # local dev format
    # location: {"type": "dev", "path": "/path/to/app"}
    # or
    # location: {"type": "dev", "windows_path": "c:\\path\\to\\app", "linux_path": "/path/to/app", "mac_path": "/path/to/app"}
    elif location_dict.get("type") == "dev":
        return TankDevDescriptor(bundle_install_path, location_dict)

    else:
        raise TankError("%s: Invalid location dict '%s'" % (app_or_engine, location_dict))
