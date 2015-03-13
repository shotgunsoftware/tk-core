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

from tank_vendor import yaml

from .errors import TankError
from .deploy import util
from .platform import constants
from .platform.environment import Environment
from .util import shotgun
from . import hook
from . import pipelineconfig_utils
from . import template_includes

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

        # get the project tank disk name (Project.tank_name), stored in the PC metadata file.
        data = pipelineconfig_utils.get_metadata(self._pc_root)
        if data.get("project_name") is None:
            raise TankError("Project name not defined in config metadata for config %s! "
                            "Please contact support." % self._pc_root)
        self._project_name = data.get("project_name")

        # cache fields lazily populated on getter access
        self._clear_cached_settings()
        
        self.execute_core_hook_internal(constants.PIPELINE_CONFIGURATION_INIT_HOOK_NAME, parent=self)

    def __repr__(self):
        return "<Sgtk Configuration %s>" % self._pc_root

    def _clear_cached_settings(self):
        """
        Force the pc object to reread its settings from disk.
        Call this if you have made changes to config files and 
        want these to be picked up. The next time settings are needed,
        these will be automatically re-read from disk.
        """
        self._project_id = None
        self._pc_id = None
        self._pc_name = None
        self._published_file_entity_type = None
        self._cache_folder = None
        self._path_cache_path = None
        self._use_shotgun_path_cache = None

    def _load_metadata_from_sg(self):
        """
        Caches PC metadata from shotgun.
        """
        sg = shotgun.get_sg_connection()
        platform_lookup = {"linux2": "linux_path", "win32": "windows_path", "darwin": "mac_path" }
        sg_path_field = platform_lookup[sys.platform]
        data = sg.find_one(constants.PIPELINE_CONFIGURATION_ENTITY,
                           [[sg_path_field, "is", self._pc_root]],
                           ["id", "project", "code"])
        if data is None:
            raise TankError("Cannot find a Pipeline configuration in Shotgun that has its %s "
                            "set to '%s'!" % (sg_path_field, self._pc_root))

        self._project_id = data.get("project").get("id")
        self._pc_id = data.get("id")
        self._pc_name = data.get("code")
    
    
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
        May connect to Shotgun to retrieve this.
        """
        if self._pc_name is None:
            # try to get it from the cache file
            data = pipelineconfig_utils.get_metadata(self._pc_root)
            self._pc_name = data.get("pc_name")


            if self._pc_name is None:
                # not in metadata file on disk. Fall back on SG lookup
                self._load_metadata_from_sg()

        return self._pc_name

    def is_auto_path(self):
        """
        Returns true if this config was set up with auto path mode.
        This method will connect to shotgun in order to determine the auto path status.
        
        :returns: boolean indicating auto path state
        """
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
            # all three PC fields are empty. This means that we are running an auto path config
            return True
        
        else:
            return False
        
    def is_localized(self):
        """
        Returns true if this pipeline configuration has its own Core
        
        :returns: boolean indicating if config is localized
        """
        return pipelineconfig_utils.is_localized(self._pc_root)

    def get_shotgun_id(self):
        """
        Returns the shotgun id for this PC. 
        May connect to Shotgun to retrieve this.
        """
        if self._pc_id is None:
            # try to get it from the cache file
            data = pipelineconfig_utils.get_metadata(self._pc_root)
            self._pc_id = data.get("pc_id")

            if self._pc_id is None:
                # not in metadata file on disk. Fall back on SG lookup
                self._load_metadata_from_sg()

        return self._pc_id

    def get_project_id(self):
        """
        Returns the shotgun id for the project associated with this PC. 
        May connect to Shotgun to retrieve this.
        """
        if self._project_id is None:
            # try to get it from the cache file
            data = pipelineconfig_utils.get_metadata(self._pc_root)
            self._project_id = data.get("project_id")

            if self._project_id is None:
                # not in metadata file on disk. Fall back on SG lookup
                self._load_metadata_from_sg()

        return self._project_id

    def get_project_disk_name(self):
        """
        Returns the project name for the project associated with this PC.
        """
        return self._project_name

    def set_project_disk_name(self, project_disk_name):
        """
        Sets the internal project_name.  This is temporary and only available
        while this instance is in memory.  Will not affect the metadata on
        disk nor in Shotgun.
        """
        self._project_name = project_disk_name

    def get_published_file_entity_type(self):
        """
        Returns the type of entity being used
        for the 'published file' entity
        """
        if self._published_file_entity_type is None:
            # try to get it from the cache file
            data = pipelineconfig_utils.get_metadata(self._pc_root)
            self._published_file_entity_type = data.get("published_file_entity_type")

            if self._published_file_entity_type is None:
                # fall back to legacy type:
                self._published_file_entity_type = "TankPublishedFile"

        return self._published_file_entity_type

    ########################################################################################
    # path cache

    def get_shotgun_path_cache_enabled(self):
        """
        Returns true if the shotgun path cache should be used.
        This should only ever return False for setups created before 0.15.
        All projects created with 0.14+ automatically sets this to true.
        """
        if self._use_shotgun_path_cache is None:
            # try to get it from the cache file
            data = pipelineconfig_utils.get_metadata(self._pc_root)
            self._use_shotgun_path_cache = data.get("use_shotgun_path_cache")

            if self._use_shotgun_path_cache is None:
                # if not defined assume it is off
                self._use_shotgun_path_cache = False

        return self._use_shotgun_path_cache

    def turn_on_shotgun_path_cache(self):
        """
        Updates the pipeline configuration settings to have the shotgun based (v0.15+)
        path cache functionality enabled.
        
        Note that you need to force a full path sync once this command has been executed. 
        """
        
        if self.get_shotgun_path_cache_enabled():
            raise TankError("Shotgun based path cache already turned on!")
                
        # get current settings
        curr_settings = pipelineconfig_utils.get_metadata(self._pc_root)
        
        # add path cache setting
        curr_settings["use_shotgun_path_cache"] = True
        
        # write the record to disk
        pipe_config_sg_id_path = os.path.join(self._pc_root, "config", "core", "pipeline_configuration.yml")        
        
        old_umask = os.umask(0)
        try:
            os.chmod(pipe_config_sg_id_path, 0666)
            # and write the new file
            fh = open(pipe_config_sg_id_path, "wt")
            yaml.dump(curr_settings, fh)
        except Exception, exp:
            raise TankError("Could not write to pipeline configuration settings file %s. "
                            "Error reported: %s" % (pipe_config_sg_id_path, exp))
        finally:
            fh.close()
            os.umask(old_umask)             
            
        # update settings in memory
        self._clear_cached_settings()      
        
    ########################################################################################
    # storage roots related
        
    def get_local_storage_roots(self):
        """
        Returns local OS paths to all shotgun local storages used by toolkit. 
        Paths are validated and guaranteed not to be None.
        
        :returns: dictionary of storages, for example {"primary": "/studio", "textures": "/textures"}
        """
        
        platform_lookup = {"linux2": "linux_path", "win32": "windows_path", "darwin": "mac_path" }

        # now pick current os and append project root
        proj_roots = {}
        for r in self._roots:
            root = self._roots[r][ platform_lookup[sys.platform] ]
            
            if root is None:
                raise TankError("Undefined toolkit storage! The local file storage '%s' is not defined for this "
                                "operating system! Please contact toolkit support." % r)
            
            proj_roots[r] = root
            
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

        Tries to resolve it via the explicit link which exists between the pc and the its core.
        If this fails, it uses runtime introspection to resolve it.
        
        :returns: path string to the current core API install root location
        """
        core_api_root = pipelineconfig_utils.get_core_path_for_config(self._pc_root)

        if core_api_root is None:
            # lookup failed. fall back onto runtime introspection
            core_api_root = pipelineconfig_utils.get_path_to_current_core()
        
        return core_api_root
            
    def get_apps_location(self):
        """
        Returns the location where apps are stored
        """
        return os.path.join(self.get_install_location(), "install", "apps")

    def get_engines_location(self):
        """
        Returns the location where apps are stored
        """
        return os.path.join(self.get_install_location(), "install", "engines")

    def get_frameworks_location(self):
        """
        Returns the location where apps are stored
        """
        return os.path.join(self.get_install_location(), "install", "frameworks")

    def get_core_python_location(self):
        """
        returns the python root for this install.
        """
        return os.path.join(self.get_install_location(), "install", "core", "python")

    ########################################################################################
    # configuration disk locations

    def get_core_hooks_location(self):
        """
        Returns the path to the core hooks location
        """
        return os.path.join(self._pc_root, "config", "core", "hooks")

    def get_schema_config_location(self):
        """
        returns the location of the schema
        """
        return os.path.join(self._pc_root, "config", "core", "schema")

    def get_config_location(self):
        """
        returns the config folder for the project
        """
        return os.path.join(self._pc_root, "config")

    def get_hooks_location(self):
        """
        returns the hooks folder for the project
        """
        return os.path.join(self._pc_root, "config", "hooks")

    def get_shotgun_menu_cache_location(self):
        """
        returns the folder where shotgun menu cache files 
        (used by the browser plugin and java applet) are stored.
        
        NOTE! Because of hard coded values inside the Shotgun java applet,
        this location cannot be customized.
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

    def get_environment(self, env_name, context=None):
        """
        Returns an environment object given an environment name.
        You can use the get_environments() method to get a list of
        all the environment names.
        
        :returns: An environment object
        """        
        env_file = os.path.join(self._pc_root, "config", "env", "%s.yml" % env_name)
        if not os.path.exists(env_file):
            raise TankError("Cannot load environment '%s': Environment configuration "
                            "file '%s' does not exist!" % (env_name, env_file))
        env_obj = Environment(env_file, self, context)
        
        return env_obj

    def get_templates_config(self):
        """
        Returns the templates configuration as an object
        """
        templates_file = os.path.join(self._pc_root, "config", "core", constants.CONTENT_TEMPLATES_FILE)

        if os.path.exists(templates_file):
            config_file = open(templates_file, "r")
            try:
                data = yaml.load(config_file) or {}
            finally:
                config_file.close()
        else:
            data = {}

        # and process include files
        data = template_includes.process_includes(templates_file, data)

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
            
        return hook.execute_hook_method(hook_paths, parent, method_name, **kwargs)

