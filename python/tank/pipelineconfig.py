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
Encapsulates the pipeline configuration and helps navigate and resolve paths
across storages, configurations etc.
"""
import os
import sys
import glob
import cPickle

from tank_vendor import yaml

from .errors import TankError, TankUnreadableFileError
from .deploy import util
from .platform import constants
from .platform.environment import Environment, WritableEnvironment
from .util import shotgun, yaml_cache
from . import hook
from . import pipelineconfig_utils
from . import template_includes

from tank_vendor.shotgun_deploy import Descriptor, create_descriptor
from tank_vendor.shotgun_base import get_shotgun_storage_key

class PipelineConfiguration(object):
    """
    Represents a pipeline configuration in Tank.
    Use the factory methods below to construct this object, do not
    create directly via constructor.
    """

    def __init__(self, pipeline_configuration_path):
        """
        Constructor. Do not call this directly, use the factory methods
        at the bottom of this file.
        
        NOTE ABOUT SYMLINKS!
        
        The pipeline_configuration_path is always populated by the paths
        that were registered in shotgun, regardless of how the symlink setup
        is handled on the OS level.
        """
        self._pc_root = pipeline_configuration_path

        # validate that the current code version matches or is compatible with
        # the code that is locally stored in this config!!!!
        our_associated_api_version = self.get_associated_core_version()
        
        # and get the version of the API currently in memory
        current_api_version = pipelineconfig_utils.get_currently_running_api_version()
        
        if our_associated_api_version is not None and \
           util.is_version_older(current_api_version, our_associated_api_version):
            # currently running API is too old!
            current_api_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            
            # tell the user that their core is too old for this config
            #
            # this can happen if you are running a configuration but you are getting the core
            # API from somewhere else. For example, if you have added a core to your pythonpath
            # and then try to do sgtk_from_path("/path/to/pipeline/config") and that config
            # is using a more recent version of the core. 
            
            raise TankError("You are running Toolkit %s located in '%s'. The configuration you are "
                            "trying to use needs core version %s or higher. To fix this, "
                            "use the tank command (or Toolkit core API) located at '%s' "
                            "which is associated with this configuration." % (current_api_version, 
                                                                              current_api_path, 
                                                                              our_associated_api_version, 
                                                                              self.get_install_location()))            


        self._roots = pipelineconfig_utils.get_roots_metadata(self._pc_root)

        # get the project tank disk name (Project.tank_name),
        # stored in the pipeline config metadata file.
        pipeline_config_metadata = self._get_metadata()
        self._project_name = pipeline_config_metadata.get("project_name")
        self._project_id = pipeline_config_metadata.get("project_id")
        self._pc_id = pipeline_config_metadata.get("pc_id")
        self._pc_name = pipeline_config_metadata.get("pc_name")
        self._published_file_entity_type = pipeline_config_metadata.get("published_file_entity_type", "TankPublishedFile")        
        self._use_shotgun_path_cache = pipeline_config_metadata.get("use_shotgun_path_cache", False)

        # figure out whether to use the global bundle cache or the
        # local pipeline configuration 'install' cache
        if pipeline_config_metadata.get("use_global_bundle_cache"):
            # use global bundle cache
            self._bundle_cache_root_override = None
        else:
            # use cache relative to core install
            self._bundle_cache_root_override = os.path.join(self.get_install_location(), "install")

        if pipeline_config_metadata.get("bundle_cache_fallback_roots"):
            self._bundle_cache_fallback_paths = pipeline_config_metadata.get("bundle_cache_fallback_roots")
        else:
            self._bundle_cache_fallback_paths = []

        # Populate the global yaml_cache if we find a pickled cache
        # on disk.
        # TODO: For immutable configs, move this into bootstrap
        self._populate_yaml_cache()

        # run init hook
        self.execute_core_hook_internal(constants.PIPELINE_CONFIGURATION_INIT_HOOK_NAME, parent=self)

    def __repr__(self):
        return "<Sgtk Configuration %s>" % self._pc_root

    ########################################################################################
    # handling pipeline config metadata
    
    def _get_metadata(self):
        """
        Loads the pipeline config metadata (the pipeline_configuration.yml) file from disk.
        
        :param pipeline_config_path: path to a pipeline configuration root folder
        :returns: deserialized content of the file in the form of a dict.
        """
    
        # now read in the pipeline_configuration.yml file
        cfg_yml = os.path.join(self.get_config_location(), 
                               "core", 
                               "pipeline_configuration.yml")
    
        if not os.path.exists(cfg_yml):
            raise TankError("Configuration metadata file '%s' missing! "
                            "Please contact support." % cfg_yml)
    
        fh = open(cfg_yml, "rt")
        try:
            data = yaml.load(fh)
            if data is None:
                raise Exception("File contains no data!")
        except Exception, e:
            raise TankError("Looks like a config file is corrupt. Please contact "
                            "support! File: '%s' Error: %s" % (cfg_yml, e))
        finally:
            fh.close()
    
        return data
    
    def _update_metadata(self, updates):
        """
        Updates the pipeline configuration on disk with the passed in values.

        :param updates: Dictionary of values to update in the pipeline configuration
        """
        # get current settings
        curr_settings = self._get_metadata()
        
        # apply updates to existing cache
        curr_settings.update(updates)
        
        # write the record to disk
        pipe_config_sg_id_path = os.path.join(self.get_config_location(), 
                                              "core", 
                                              "pipeline_configuration.yml")        
        
        old_umask = os.umask(0)
        try:
            os.chmod(pipe_config_sg_id_path, 0666)
            # and write the new file
            fh = open(pipe_config_sg_id_path, "wt")
            # using safe_dump instead of dump ensures that we
            # don't serialize any non-std yaml content. In particular,
            # this causes issues if a unicode object containing a 7-bit
            # ascii string is passed as part of the data. in this case, 
            # dump will write out a special format which is later on 
            # *loaded in* as a unicode object, even if the content doesn't  
            # need unicode handling. And this causes issues down the line
            # in toolkit code, assuming strings:
            #
            # >>> yaml.dump({"foo": u"bar"})
            # "{foo: !!python/unicode 'bar'}\n"
            # >>> yaml.safe_dump({"foo": u"bar"})
            # '{foo: bar}\n'
            #            
            yaml.safe_dump(curr_settings, fh)
        except Exception, exp:
            raise TankError("Could not write to configuration file '%s'. "
                            "Error reported: %s" % (pipe_config_sg_id_path, exp))
        finally:
            fh.close()
            os.umask(old_umask)            

        self._project_id = curr_settings.get("project").get("id")
        self._pc_id = curr_settings.get("id")
        self._pc_name = curr_settings.get("code")

    def _populate_yaml_cache(self):
        """
        Loads pickled yaml_cache items if they are found and merges them into
        the global YamlCache.
        """
        cache_file = os.path.join(self._pc_root, "yaml_cache.pickle")
        try:
            fh = open(cache_file, 'rb')
        except Exception:
            return

        try:
            cache_items = cPickle.load(fh)
            yaml_cache.g_yaml_cache.merge_cache_items(cache_items)
        except Exception:
            return
        finally:
            fh.close()


    ########################################################################################
    # general access and properties

    def get_path(self):
        """
        Returns the master root for this pipeline configuration
        """
        return self._pc_root

    def get_all_os_paths(self):
        """
        Returns the path to this config for all operating systems,
        as defined in the install_locations file. None, if not defined.
        
        :returns: dictionary with keys linux2, darwin and win32
        """
        return pipelineconfig_utils.resolve_all_os_paths_to_config(self._pc_root)

    def get_name(self):
        """
        Returns the name of this PC.
        """
        return self._pc_name

    def is_auto_path(self):
        """
        Returns true if this config was set up with auto path mode.
        This method will connect to shotgun in order to determine the 
        auto path status.

        January 2016:
        DEPRECATED - DO NOT USE! At some stage this wil be removed.

        :returns: boolean indicating auto path state
        """
        if self.is_unmanaged():
            return False

        sg = shotgun.get_sg_connection()
        data = sg.find_one(constants.PIPELINE_CONFIGURATION_ENTITY,
                           [["id", "is", self.get_shotgun_id()]],
                           ["linux_path", "windows_path", "mac_path"])

        if data is None:
            raise TankError("Cannot find a Pipeline configuration in Shotgun "
                            "that has id %s." % self.get_shotgun_id())

        def _is_empty(d):
            """
            Returns true if value is "" or None, False otherwise
            """
            if d is None or d == "":
                return True
            else:
                return False
        
        if _is_empty(data.get("linux_path")) and \
           _is_empty(data.get("windows_path")) and \
           _is_empty(data.get("mac_path")):
            # all three pipeline config fields are empty.
            # This means that we are running an auto path config
            return True
        
        else:
            return False

    def is_unmanaged(self):
        """
        Returns true if the configuration is unmanaged, e.g. it does not have a
        corresponding path cache in Shotgun.

        :return: boolean indicating if config is unmanaged
        """
        return self.get_shotgun_id() is None

    def is_localized(self):
        """
        Returns true if this pipeline configuration has its own Core
        
        :returns: boolean indicating if config is localized
        """
        return pipelineconfig_utils.is_localized(self._pc_root)

    def get_shotgun_id(self):
        """
        Returns the shotgun id for this PC.
        """
        return self._pc_id

    def get_project_id(self):
        """
        Returns the shotgun id for the project associated with this PC.
        Can return None if the pipeline config represents the site and not a project.
        """
        return self._project_id

    def is_site_configuration(self):
        """
        Returns in the pipeline configuration is for the site configuration.

        :returns: True if this is a site configuration, False otherwise.
        """
        return self.get_project_id() is None

    def get_project_disk_name(self):
        """
        Returns the project name for the project associated with this PC.
        """
        return self._project_name

    def get_published_file_entity_type(self):
        """
        Returns the type of entity being used
        for the 'published file' entity
        """
        return self._published_file_entity_type

    def convert_to_site_config(self):
        """
        Converts the pipeline configuration into the site configuration.
        """
        self._update_metadata({"project_id": None})
        self._project_id = None

    ########################################################################################
    # path cache

    def get_shotgun_path_cache_enabled(self):
        """
        Returns true if the shotgun path cache should be used.
        This should only ever return False for setups created before 0.15.
        All projects created with 0.14+ automatically sets this to true.
        """
        return self._use_shotgun_path_cache
    
    def turn_on_shotgun_path_cache(self):
        """
        Updates the pipeline configuration settings to have the shotgun based (v0.15+)
        path cache functionality enabled.
        
        Note that you need to force a full path sync once this command has been executed. 
        """
        
        if self.get_shotgun_path_cache_enabled():
            raise TankError("Shotgun based path cache already turned on!")
                
        self._update_metadata({"use_shotgun_path_cache": True})
        self._use_shotgun_path_cache = True

        
    ########################################################################################
    # storage roots related
        
    def get_local_storage_roots(self):
        """
        Returns local OS paths to all shotgun local storages used by toolkit. 
        Paths are validated and guaranteed not to be None.
        
        :returns: dictionary of storages, for example {"primary": "/studio", "textures": "/textures"}
        """
        # now pick current os and append project root
        proj_roots = {}
        for r in self._roots:
            root = self._roots[r][get_shotgun_storage_key()]
            
            if root is None:
                raise TankError("Undefined toolkit storage! The local file storage '%s' is not defined for this "
                                "operating system! Please contact toolkit support." % r)
            
            proj_roots[r] = root
            
        return proj_roots
    
    def get_all_platform_data_roots(self):
        """
        Similar to get_data_roots but instead of returning the data roots for a single 
        operating system, the data roots for all operating systems are returned.
        
        The return structure is a nested dictionary structure, for example:

        {
         "primary": {"win32":  "z:\studio\my_project", 
                     "linux2": "/studio/my_project",
                     "darwin": "/studio/my_project"},
                     
         "textures": {"win32":  "z:\studio\my_project", 
                      "linux2": None,
                      "darwin": "/studio/my_project"},
        }
         
        The operating system keys are returned on sys.platform-style notation.
        If a data root has not been defined on a particular platform, None is 
        returned (see example above).
         
        :returns: dictionary of dictionaries. See above.
        """
        
        # note: currently supported platforms are linux2, win32 and darwin, however additional
        # platforms may be added in the future.
        
        proj_roots = {}
        for storage_name in self._roots:
            # create dict entry for each storage
            proj_roots[storage_name] = {}

            for platform in ["win32", "linux2", "darwin"]:
                # for each operating system, append the project root path
                storage_path = self._roots[storage_name][get_shotgun_storage_key(platform)]
                if storage_path:
                    # append project name
                    storage_path = self.__append_project_name_to_root(storage_path, platform)
                # key by operating system
                proj_roots[storage_name][platform] = storage_path
                
        return proj_roots
    
    def get_data_roots(self):
        """
        Returns a dictionary of all the data roots available for this PC,
        keyed by their storage name. Only returns paths for current platform.
        Paths are guaranteed to be not None.

        :returns: A dictionary keyed by storage name, for example
                  {"primary": "/studio/my_project", "textures": "/textures/my_project"}        
        """
        proj_roots = {}
        for storage_name, root_path in self.get_local_storage_roots().iteritems():
            proj_roots[storage_name] = self.__append_project_name_to_root(root_path, sys.platform)
        return proj_roots

    def __append_project_name_to_root(self, root_value, os_name):
        """
        Multi-os method that creates a project root path.
        Note that this method does not use any of the os.path methods,
        since we may for example be evaulating a windows path on linux.
        
        :param root_value: A root path, for example /mnt/projects or c:\foo
        :param os_name: sys.platform name for the path's platform.
          
        :returns: the project disk name properly concatenated onto the root_value
        """
        # get the valid separator for this path
        separators = {"linux2": "/", "win32": "\\", "darwin": "/" }
        separator = separators[os_name] 
        
        # get rid of any slashes at the end
        root_value = root_value.rstrip("/\\")
        # now root value is "/foo/bar", "c:" or "\\hello" 
        
        # concat the full path.
        full_path = root_value + separator + self._project_name
        
        # note that project name may be "foo/bar/baz" even on windows.
        # now get all the separators adjusted.
        full_path = full_path.replace("\\", separator).replace("/", separator)
        
        return full_path
        
    def has_associated_data_roots(self):
        """
        Some configurations do not have a notion of a project storage and therefore
        do not have any storages defined. This flag indicates whether a configuration 
        has any associated data storages. 
        
        :returns: true if the configuration has a primary data root defined, false if not
        """
        return len(self.get_data_roots()) > 0
        
    def get_primary_data_root(self):
        """
        Returns the path to the primary data root for the current platform.
        For configurations where there is no roots defined at all, 
        an exception will be raised.
        
        :returns: str to local path on disk
        """
        if len(self.get_data_roots()) == 0:
            raise TankError("Your current pipeline configuration does not have any project data "
                            "storages defined and therefore does not have a primary project data root!")
         
        return self.get_data_roots().get(constants.PRIMARY_STORAGE_NAME)

    ########################################################################################
    # installation payload (core/apps/engines) disk locations

    def get_associated_core_version(self):
        """
        Returns the version string for the core api associated with this config.
        This method is 'forgiving' and in the case no associated core API can be 
        found for this pipeline configuration, None will be returned rather than 
        an exception raised. 

        :returns: version str e.g. 'v1.2.3', None if no version could be determined. 
        """
        associated_api_root = self.get_install_location()
        return pipelineconfig_utils.get_core_api_version(associated_api_root)

    def get_install_location(self):
        """
        Returns the core api install location associated with this pipeline configuration.

        Tries to resolve it via the explicit link which exists between
        the pipeline config and the its core. If this fails, it uses
        runtime introspection to resolve it.
        
        :returns: path string to the current core API install root location
        """
        core_api_root = pipelineconfig_utils.get_core_path_for_config(self._pc_root)

        if core_api_root is None:
            # lookup failed. fall back onto runtime introspection
            core_api_root = pipelineconfig_utils.get_path_to_current_core()
        
        return core_api_root

    def get_core_python_location(self):
        """
        Returns the python root for this install.
        
        :returns: path string
        """
        return os.path.join(self.get_install_location(), "install", "core", "python")


    ########################################################################################
    # accessing cached code

    def _preprocess_location(self, location_dict):
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
            # several different path parameters are supported by the dev descriptor.
            # scan through all path keys and look for pipeline config token

            # platform specific resolve
            platform_key = get_shotgun_storage_key()
            if platform_key in location_dict:
                location_dict[platform_key] = location_dict[platform_key].replace(
                    constants.PIPELINE_CONFIG_DEV_DESCRIPTOR_TOKEN,
                    self.get_path()
                )

            # local path resolve
            if "path" in location_dict:
                location_dict["path"] = location_dict["path"].replace(
                    constants.PIPELINE_CONFIG_DEV_DESCRIPTOR_TOKEN,
                    self.get_path()
                )

        return location_dict

    def _get_descriptor(self, descriptor_type, location):
        """
        Constructs a descriptor object given a location dictionary.

        :param descriptor_type: Descriptor type (APP, ENGINE, etc)
        :param location:        Location dictionary
        :returns:               Descriptor object
        """
        sg_connection = shotgun.get_sg_connection()
        pp_location = self._preprocess_location(location)

        desc = create_descriptor(
            sg_connection,
            descriptor_type,
            pp_location,
            self._bundle_cache_root_override,
            self._bundle_cache_fallback_paths
        )

        return desc

    def get_app_descriptor(self, location):
        """
        Convenience method that returns a descriptor for an app
        that is associated with this pipeline configuration.
        
        :param location: Location dictionary describing the app source location
        :returns:        Descriptor object
        """
        return self._get_descriptor(Descriptor.APP, location)

    def get_engine_descriptor(self, location):
        """
        Convenience method that returns a descriptor for an engine
        that is associated with this pipeline configuration.
        
        :param location: Location dictionary describing the engine source location
        :returns:        Descriptor object
        """
        return self._get_descriptor(Descriptor.ENGINE, location)

    def get_framework_descriptor(self, location):
        """
        Convenience method that returns a descriptor for a framework
        that is associated with this pipeline configuration.
        
        :param location: Location dictionary describing the framework source location
        :returns:        Descriptor object
        """
        return self._get_descriptor(Descriptor.FRAMEWORK, location)


    ########################################################################################
    # configuration disk locations

    def get_core_hooks_location(self):
        """
        Returns the path to the core hooks location
        
        :returns: path string
        """
        return os.path.join(self._pc_root, "config", "core", "hooks")

    def get_schema_config_location(self):
        """
        Returns the location of the folder schema
        
        :returns: path string
        """
        return os.path.join(self._pc_root, "config", "core", "schema")

    def get_config_location(self):
        """
        Returns the config folder for the project
        
        :returns: path string
        """
        return os.path.join(self._pc_root, "config")

    def get_hooks_location(self):
        """
        Returns the hooks folder for the project
        
        :returns: path string
        """
        return os.path.join(self._pc_root, "config", "hooks")

    def get_shotgun_menu_cache_location(self):
        """
        returns the folder where shotgun menu cache files 
        (used by the browser plugin and java applet) are stored.
        
        :returns: path string
        """
        return os.path.join(self._pc_root, "cache")

    ########################################################################################
    # configuration data access

    def get_environments(self):
        """
        Returns a list with all the environments in this configuration.
        """
        env_root = os.path.join(self._pc_root, "config", "env")
        env_names = []
        for f in glob.glob(os.path.join(env_root, "*.yml")):
            file_name = os.path.basename(f)
            (name, _) = os.path.splitext(file_name)
            env_names.append(name)
        return env_names

    def get_environment(self, env_name, context=None, writable=False):
        """
        Returns an environment object given an environment name.
        You can use the get_environments() method to get a list of
        all the environment names.
        
        :param env_name:    name of the environment to load
        :param context:     context to seed the environment with
        :param writable:    If true, a writable environment object will be 
                            returned, allowing a user to update it.
        :returns:           An environment object
        """        
        env_file = self.get_environment_path(env_name)
        EnvClass = WritableEnvironment if writable else Environment
        env_obj = EnvClass(env_file, self, context)
        return env_obj

    def get_environment_path(self, env_name):
        """
        Returns the path to the environment yaml file for the given
        environment name for this pipeline configuration.

        :param env_name:    The name of the environment.
        :returns:           String path to the environment yaml file.
        """
        return os.path.join(self._pc_root, "config", "env", "%s.yml" % env_name)
    
    def get_templates_config(self):
        """
        Returns the templates configuration as an object
        """
        templates_file = os.path.join(
            self._pc_root,
            "config",
            "core",
            constants.CONTENT_TEMPLATES_FILE,
        )

        try:
            data = yaml_cache.g_yaml_cache.get(templates_file, deepcopy_data=False)
            data = template_includes.process_includes(templates_file, data)
        except TankUnreadableFileError:
            data = dict()

        return data

    ########################################################################################
    # helpers and internal

    def execute_core_hook_internal(self, hook_name, parent, **kwargs):
        """
        Executes an old-style core hook, passing it any keyword arguments supplied.
        
        Typically you don't want to execute this method but instead
        the tk.execute_core_hook method. Only use this one if you for 
        some reason do not have a tk object available.

        :param hook_name: Name of hook to execute.
        :param parent: Parent object to pass down to the hook
        :param **kwargs: Named arguments to pass to the hook
        :returns: Return value of the hook.
        """
        # first look for the hook in the pipeline configuration
        # if it does not exist, fall back onto core API default implementation.
        hook_folder = self.get_core_hooks_location()
        file_name = "%s.py" % hook_name
        hook_path = os.path.join(hook_folder, file_name)
        if not os.path.exists(hook_path):
            # no custom hook detected in the pipeline configuration
            # fall back on the hooks that come with the currently running version
            # of the core API.
            hooks_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "hooks"))
            hook_path = os.path.join(hooks_path, file_name)
        else:
            # some hooks are always custom. ignore those and log the rest.
            if (hasattr(parent, 'log_metric') and
               hook_name not in constants.TANK_LOG_METRICS_CUSTOM_HOOK_BLACKLIST):
                parent.log_metric("custom hook %s" % (hook_name,))

        return hook.execute_hook(hook_path, parent, **kwargs)

    def execute_core_hook_method_internal(self, hook_name, method_name, parent, **kwargs):
        """
        Executes a new style core hook, passing it any keyword arguments supplied.
        
        Typically you don't want to execute this method but instead
        the tk.execute_core_hook method. Only use this one if you for 
        some reason do not have a tk object available.

        :param hook_name: Name of hook to execute.
        :param method_name: Name of hook method to execute
        :param parent: Parent object to pass down to the hook
        :param **kwargs: Named arguments to pass to the hook
        :returns: Return value of the hook.
        """
        # this is a new style hook which supports an inheritance chain
        
        # first add the built-in core hook to the chain
        file_name = "%s.py" % hook_name
        hooks_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "hooks"))
        hook_paths = [os.path.join(hooks_path, file_name)]
        
        # now add a custom hook if that exists.
        hook_folder = self.get_core_hooks_location()        
        hook_path = os.path.join(hook_folder, file_name)
        if os.path.exists(hook_path):
            hook_paths.append(hook_path)
            if hasattr(parent, 'log_metric'):
                parent.log_metric("custom hook %s" % (hook_name,))

        return hook.execute_hook_method(hook_paths, parent, method_name, **kwargs)

