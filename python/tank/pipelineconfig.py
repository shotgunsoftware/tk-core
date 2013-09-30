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
from .util import login
from . import hook
from . import template_includes

class PipelineConfiguration(object):
    """
    Represents a pipeline configuration in Tank.
    Use the factory methods above to construct this object, do not
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
        our_version = self.__get_core_version()
        if our_version is not None:
            # we have an API installed locally
            current_api = get_core_api_version_based_on_current_code()

            if util.is_version_older(current_api, our_version):
                # currently running API is too old!
                current_api_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
                raise TankError("You are currently running an Sgtk API located in '%s'. "
                                "The current Configuration '%s' has separately installed "
                                "version of the API (%s) which is more recent than the currently "
                                "running version (%s). In order to use this pipeline configuration, "
                                "add %s to your PYTHONPATH and try again." % (current_api_path,
                                                                              self.get_path(),
                                                                              our_version,
                                                                              current_api,
                                                                              self.get_python_location()))


        self._roots = get_pc_roots_metadata(self._pc_root)

        # get the project tank disk name (Project.tank_name), stored in the PC metadata file.
        data = get_pc_disk_metadata(self._pc_root)
        if data.get("project_name") is None:
            raise TankError("Project name not defined in config metadata for config %s! "
                            "Please contact support." % self._pc_root)
        self._project_name = data.get("project_name")

        # cache fields lazily populated on getter access
        self._project_id = None
        self._pc_id = None
        self._pc_name = None
        self._published_file_entity_type = None
        self.execute_hook(constants.PIPELINE_CONFIGURATION_INIT_HOOK_NAME, parent=self)


    def __repr__(self):
        return "<Sgtk Configuration %s>" % self._pc_root

    ########################################################################################
    # helpers

    def __get_core_version(self):
        """
        Returns the version string for the core api associated with this config,
        none if it does not exist.
        """
        info_yml_path = os.path.join(self._pc_root, "install", "core", "info.yml")

        if os.path.exists(info_yml_path):
            try:
                info_fh = open(info_yml_path, "r")
                try:
                    data = yaml.load(info_fh)
                finally:
                    info_fh.close()
                data = data.get("version")
            except:
                data = None
        else:
            data = None

        return data


    ########################################################################################
    # data roots access

    def get_path(self):
        """
        Returns the master root for this pipeline configuration
        """
        return self._pc_root

    def _load_metadata_from_sg(self):
        """
        Caches PC metadata from shotgun.
        """
        sg = shotgun.create_sg_connection()
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


    def get_name(self):
        """
        Returns the name of this PC.
        May connect to Shotgun to retrieve this.
        """
        if self._pc_name is None:
            # try to get it from the cache file
            data = get_pc_disk_metadata(self._pc_root)
            self._pc_name = data.get("pc_name")


            if self._pc_name is None:
                # not in metadata file on disk. Fall back on SG lookup
                self._load_metadata_from_sg()

        return self._pc_name

    def get_shotgun_id(self):
        """
        Returns the shotgun id for this PC. 
        May connect to Shotgun to retrieve this.
        """
        if self._pc_id is None:
            # try to get it from the cache file
            data = get_pc_disk_metadata(self._pc_root)
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
            data = get_pc_disk_metadata(self._pc_root)
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
            data = get_pc_disk_metadata(self._pc_root)
            self._published_file_entity_type = data.get("published_file_entity_type")

            if self._published_file_entity_type is None:
                # fall back to legacy type:
                self._published_file_entity_type = "TankPublishedFile"

        return self._published_file_entity_type

    def get_local_storage_roots(self):
        """
        Returns local OS paths to all shotgun local storages used by toolkit. 
        """
        
        platform_lookup = {"linux2": "linux_path", "win32": "windows_path", "darwin": "mac_path" }

        # now pick current os and append project root
        proj_roots = {}
        for r in self._roots:
            proj_roots[r] = self._roots[r][ platform_lookup[sys.platform] ]
        return proj_roots
        

    def get_data_roots(self):
        """
        Returns a dictionary of all the data roots available for this PC,
        keyed by their storage name. Only returns paths for current platform.

        Returns for example:

        {"primary": "/studio/my_project", "textures": "/textures/my_project"}

        """
        platform_lookup = {"linux2": "linux_path", "win32": "windows_path", "darwin": "mac_path" }

        # now pick current os and append project root
        proj_roots = {}
        for r in self._roots:
            current_os_root = self._roots[r][ platform_lookup[sys.platform] ]
            if current_os_root is None:
                proj_roots[r] = None
            else:
                proj_roots[r] = self.__append_project_name_to_root(current_os_root, sys.platform)

        return proj_roots

    def get_all_data_roots(self):
        """
        Returns a dictionary containing dictionaries of all the data roots
        available for this PC, keyed by their storage name and {os}_path

        Returns for example:

        {
          "primary": {
                        "linux_path":"/studio/my_project",
                        "mac_path":"/studio/my_project",
                        "windows_path":"P:/studio/my_project"
          "textures": {
                        "linux_path":"/textures/my_project",
                        "mac_path":"/textures/my_project",
                        "windows_path":"P:/textures/my_project"
                      }
        }

        """
        
        # mapping from an entity dict 
        platform_lookup = {"linux_path": "linux2", 
                           "windows_path": "win32", 
                           "mac_path": "darwin" }

        # now pick current os and append project root
        proj_roots = {}
        for r in self._roots:
            proj_roots[r] = {}
            for p in self._roots[r]:
                current_root = self._roots[r][p]
                if current_root is None:
                    proj_roots[r][p] = None
                else:
                    os_name = platform_lookup[p]
                    proj_roots[r][p] = self.__append_project_name_to_root(current_root, os_name)

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
        
    def get_primary_data_root(self):
        """
        Returns the path to the primary data root for the current platform
        """
        return self.get_data_roots().get(constants.PRIMARY_STORAGE_NAME)


    def get_path_cache_location(self):
        """
        Returns the path to the path cache file.
        """
        return os.path.join(self.get_primary_data_root(), "tank", "cache", constants.CACHE_DB_FILENAME)


    ########################################################################################
    # apps and engines

    def get_python_location(self):
        """
        returns the python root for this install.
        """
        return os.path.join(self.get_install_root(), "core", "python")

    def get_install_root(self):
        """
        Returns the install location, the location where tank caches engines and apps.
        This location is local to the install, so if you run localized core, it will
        be in your PC, if you run studio location core, it will be a shared cache.

        If you are a developer and are symlinking the core, this may not work.
        In that case set an environment env TANK_INSTALL_LOCATION and point
        that at the install location.
        """

        # locate the studio install root as a location local to this file
        install_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

        if not os.path.exists(install_path):
            if "TANK_INSTALL_LOCATION" in os.environ:
                install_path = os.environ["TANK_INSTALL_LOCATION"]
            else:
                raise TankError("Cannot resolve the install location from the location of the Sgtk Code! "
                                "This can happen if you try to move or symlink the Sgtk API. "
                                "Please contact support.")
        return install_path


    def get_apps_location(self):
        """
        Returns the location where apps are stored
        """
        return os.path.join(self.get_install_root(), "apps")

    def get_engines_location(self):
        """
        Returns the location where apps are stored
        """
        return os.path.join(self.get_install_root(), "engines")

    def get_frameworks_location(self):
        """
        Returns the location where apps are stored
        """
        return os.path.join(self.get_install_root(), "frameworks")

    ########################################################################################
    # cache

    def get_cache_location(self):
        """
        Returns the pipeline config -centric cache location
        """
        return os.path.join(self._pc_root, "cache")


    ########################################################################################
    # configuration

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
        """
        env_file = os.path.join(self._pc_root, "config", "env", "%s.yml" % env_name)
        if not os.path.exists(env_file):
            raise TankError("Cannot load environment '%s': Environment configuration "
                            "file '%s' does not exist!" % (env_name, env_file))

        return Environment(env_file, self, context)

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

    def execute_hook(self, hook_name, parent, **kwargs):
        """
        Executes a core level hook, passing it any keyword arguments supplied.

        Note! This is part of the private Sgtk API and should not be called from ouside
        the core API.

        :param hook_name: Name of hook to execute.
        :returns: Return value of the hook.
        """
        # first look for the hook in the pipeline configuration
        # if it does not exist, fall back onto core API default implementation.
        hook_folder = self.get_core_hooks_location()
        file_name = "%s.py" % hook_name
        hook_path = os.path.join(hook_folder, file_name)
        if not os.path.exists(hook_path):
            # construct install hooks path if no project(override) hook
            hooks_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "hooks"))
            hook_path = os.path.join(hooks_path, file_name)

        return hook.execute_hook(hook_path, parent, **kwargs)


class StorageConfigurationMapping(object):
    """
    Handles operation on the mapping from a data root to a pipeline config
    """

    def __init__(self, data_root):
        self._root = data_root
        self._config_file = os.path.join(self._root, "tank", "config", constants.CONFIG_BACK_MAPPING_FILE)

    def clear_mappings(self):
        """
        Removes any content from the storage mappings file
        """
        # open the file without append to overwrite any previous content
        try:
            fh = open(self._config_file, "wt")
            fh.write("# this file is automatically created by the shotgun pipeline toolkit\n")
            fh.write("# please do not edit by hand\n\n")
            fh.close()
        except Exception, exp:
            raise TankError("Could not write to roots file %s. "
                            "Error reported: %s" % (self._config_file, exp))
        
    def add_pipeline_configuration(self, mac_path, win_path, linux_path):
        """
        Add pipeline configuration mapping to a storage
        """
        data = []

        if os.path.exists(self._config_file):
            # we have a config already - so read it in
            fh = open(self._config_file, "rt")
            try:
                data = yaml.load(fh)
                # if clear_mappings was run, data is None
                if data is None:
                    data = []
            except Exception, e:
                raise TankError("Looks like the config lookup file is corrupt. Please contact "
                                "support! File: '%s' Error: %s" % (self._config_file, e))
            finally:
                fh.close()

        # now add our new mapping to this data structure
        new_item = {"darwin": mac_path, "win32": win_path, "linux2": linux_path}
        if new_item not in data:
            data.append(new_item)

        # and write the file
        try:
            fh = open(self._config_file, "wt")
            yaml.dump(data, fh)
            fh.close()
        except Exception, exp:
            raise TankError("Could not write to roots file %s. "
                            "Error reported: %s" % (self._config_file, exp))


    def get_pipeline_configs(self):
        """
        Returns a list of current os paths to pipeline configs
        """
        data = []

        if os.path.exists(self._config_file):
            # we have a config already - so read it in
            fh = open(self._config_file, "rt")
            try:
                data = yaml.load(fh)
            except Exception, e:
                raise TankError("Looks like the config lookup file %s is corrupt. Please contact "
                                "support! File: '%s' Error: %s" % (self._config_file, e))
            finally:
                fh.close()

        current_os_paths = [ x.get(sys.platform) for x in data ]
        return current_os_paths


def from_entity(entity_type, entity_id):
    """
    Factory method that constructs a PC given a shotgun object
    """

    platform_lookup = {"linux2": "linux_path", "win32": "windows_path", "darwin": "mac_path" }

    sg = shotgun.create_sg_connection()

    e = sg.find_one(entity_type, [["id", "is", entity_id]], ["project", "name"])

    if e is None:
        raise TankError("Cannot resolve a pipeline configuration object from %s %s - this object "
                        "does not exist in Shotgun!" % (entity_type, entity_id))

    if entity_type == "Project":
        proj = {"type": "Project", "id": entity_id, "name": e.get("name")}

    else:
        if e.get("project") is None:
            raise TankError("Cannot resolve a pipeline configuration object from %s %s - this object "
                            "is not linked to a project!" % (entity_type, entity_id))
        proj = e.get("project")

    pipe_configs = sg.find(constants.PIPELINE_CONFIGURATION_ENTITY,
                           [["project", "is", proj]],
                           ["windows_path", "mac_path", "linux_path", "code"])

    if len(pipe_configs) == 0:
        raise TankError("Cannot resolve a pipeline configuration object from %s with id %s - looks "
                        "like its associated Shotgun Project '%s' has not yet been set up with "
                        "the Shotgun Pipeline Toolkit!" % (entity_type, entity_id, proj.get("name")))

    #############################################################################################
    # ok now we have all the PCs in Shotgun for this project.
    # apply the following logic:
    #
    # if this method was called from a generic tank command, just find the primary PC 
    # and use that.
    #
    # if this was called from a specific tank command, use that. 

    if "TANK_CURRENT_PC" not in os.environ:
        # we are running the generic tank command, the code that we are running
        # is not connected to any particular PC.
        # in this case, find the primary pipeline config and use that
        primary_pc = None
        for pc in pipe_configs:
            if pc.get("code") == constants.PRIMARY_PIPELINE_CONFIG_NAME:
                primary_pc = pc
                break
        if primary_pc is None:
            raise TankError("The Shotgun Project '%s' does not have a default Pipeline "
                            "Configuration! This is required by the Sgtk. It needs to be named '%s'. "
                            "Please double check by opening to the Pipeline configuration Page in "
                            "Shotgun for the given project." % (proj.get("name"), constants.PRIMARY_PIPELINE_CONFIG_NAME))

        # check that there is a path for our platform
        current_os_path = primary_pc.get(platform_lookup[sys.platform])
        if current_os_path is None:
            raise TankError("The Shotgun Project '%s' has a Primary pipeline configuration but "
                            "it has not been configured to work with the current "
                            "operating system." % proj.get("name"))

        # ok there is a path - now check that the path exists!
        if not os.path.exists(current_os_path):
            raise TankError("The Shotgun Project '%s' has a Primary pipeline configuration registered "
                            "to be located in '%s', however this path does cannot be "
                            "found!" % (proj.get("name"), current_os_path))

        # looks good, we got a primary pipeline config that exists
        return PipelineConfiguration(current_os_path)




    else:
        # we are running the tank command from a specific PC.
        # in this case we need to check that the entity actually belongs to the project
        curr_pc_path = os.environ["TANK_CURRENT_PC"]

        # do a bit of cleanup - windows paths can end with a space
        if curr_pc_path.endswith(" "):
            curr_pc_path = curr_pc_path[:-1]
        # windows tends to end with a backslash
        if curr_pc_path.endswith("\\"):
            curr_pc_path = curr_pc_path[:-1]

        # the path stored in the TANK_CURRENT_PC env var may be a symlink etc.
        # now we need to find which PC entity this corresponds to in Shotgun.
        # Once found, we can double check that the current Entity is actually
        # associated with the project that the PC is associated with.
        pc_registered_path = get_pc_registered_location(curr_pc_path)

        if pc_registered_path is None:
            raise TankError("Error starting from the configuration located in '%s' - "
                            "it looks like this pipeline configuration and tank command "
                            "has not been configured for the current operating system." % curr_pc_path)

        # now that we have the proper pc path, we can find which PC entity this is
        found_matching_path = False
        for sg_pc in pipe_configs:
            if sg_pc.get(platform_lookup[sys.platform]) == pc_registered_path:
                found_matching_path = True
                break

        if not found_matching_path:
            raise TankError("Error launching for %s with id %s (Belonging to the project '%s') "
                            "from the configuration located in '%s'. This config is not "
                            "associated with that project. For a list of which tank commands can be "
                            "used with this project, go to the Pipeline Configurations page in "
                            "Shotgun for the project." % (entity_type, entity_id, proj.get("name"), pc_registered_path))
        # ok we got a pipeline config matching the tank command from which we launched.
        # because we found the PC in the list of PCs for this project, we know that it must be valid!
        return PipelineConfiguration(pc_registered_path)




def from_path(path):
    """
    Factory method that constructs a PC object from a path:
    - data paths are being traversed and resolved
    - if the path is a direct path to a PC root that's fine too
    """

    if not isinstance(path, basestring):
        raise TankError("Cannot create a Configuration from path '%s' - "
                        "path must be a string!" % path)

    path = os.path.abspath(path)

    # make sure folder exists on disk
    if not os.path.exists(path):
        # there are cases when a PC is being created from a _file_ which does not yet
        # exist on disk. To try to be reasonable with this case, try this check on the
        # parent folder of the path as a last resort.
        parent_path = os.path.dirname(path)
        if os.path.exists(parent_path):
            path = parent_path
        else:
            raise TankError("Cannot create a Configuration from path '%s' - the path does "
                            "not exist on disk!" % path)


    ########################################################################################
    # first see if this path is a pipeline configuration

    pc_config = os.path.join(path, "config", "core", "pipeline_configuration.yml")
    if os.path.exists(pc_config):
        # done deal!

        # resolve the "real" location that is stored in Shotgun and 
        # cached in the file system
        pc_registered_path = get_pc_registered_location(path)

        if pc_registered_path is None:
            raise TankError("Error starting from the configuration located in '%s' - "
                            "it looks like this pipeline configuration and tank command "
                            "has not been configured for the current operating system." % path)

        return PipelineConfiguration(pc_registered_path)


    ########################################################################################
    # assume it is a data path.
    # walk up the file system until a tank folder is found, then find tank config directory

    cur_path = path
    config_path = None
    while True:
        config_path = os.path.join(cur_path, "tank", "config", constants.CONFIG_BACK_MAPPING_FILE)
        # need to test for something in project vs studio config
        if os.path.exists(config_path):
            break
        parent_path = os.path.dirname(cur_path)
        if parent_path == cur_path:
            # Topped out without finding config
            raise TankError("Cannot create a Configuration from path '%s' - this path does "
                            "not belong to an Sgtk Project!" % path)
        cur_path = parent_path

    # all right - now read the config and get all the registered pipeline configs.
    try:
        fh = open(config_path, "r")
        try:
            data = yaml.load(fh)
        finally:
            fh.close()
    except Exception, e:
        raise TankError("Looks like a config file is corrupt. Please contact "
                        "support! File: '%s' Error: %s" % (config_path, e))

    # get all the registered pcs for the current platform
    current_os_pcs = [ x.get(sys.platform) for x in data if x is not None]

    # Now if we are running a studio tank command, find the Primary PC and use that
    # if we are using a specific tank command, try to use that PC

    if "TANK_CURRENT_PC" not in os.environ:
        # we are running a studio level tank command - not associated with 
        # a particular PC. Out of the list of PCs associated with this location, 
        # find the Primary PC and use that.

        # try to figure out what the primary storage is by looking for a metadata 
        # file in each PC. 
        for pc_path in current_os_pcs:
            data = None
            try:
                data = get_pc_disk_metadata(pc_path)
            except TankError:
                # didn't find so just skip this pc
                continue
            pc_name = data.get("pc_name")
            if pc_name == constants.PRIMARY_PIPELINE_CONFIG_NAME:
                return PipelineConfiguration(pc_path)

        # no luck - this may be because some projects don't have this 
        # metadata cached. Now try by looking in Shotgun instead.

        # in the list of paths found in the inverse lookup table on disk, find the primary.
        sg = shotgun.create_sg_connection()
        platform_lookup = {"linux2": "linux_path", "win32": "windows_path", "darwin": "mac_path" }
        filters = [ platform_lookup[sys.platform], "in"]
        filters.extend(current_os_pcs)
        primary_pc = sg.find_one(constants.PIPELINE_CONFIGURATION_ENTITY,
                                 [filters, ["code", "is", constants.PRIMARY_PIPELINE_CONFIG_NAME]],
                                 ["windows_path", "mac_path", "linux_path", "project"])

        if primary_pc is None:
            raise TankError("Cannot find a Primary Pipeline Configuration for path '%s'. "
                            "The following Pipeline configuration are associated with the "
                            "path, but none of them is marked as Primary: %s" % (path, current_os_pcs))

        # check that there is a path for our platform
        current_os_path = primary_pc.get(platform_lookup[sys.platform])
        if current_os_path is None:
            raise TankError("The Shotgun Project '%s' has a Primary pipeline configuration but "
                            "it has not been configured to work with the current "
                            "operating system." % primary_pc.get("project").get("name"))

        # ok there is a path - now check that the path exists!
        if not os.path.exists(current_os_path):
            raise TankError("The Shotgun Project '%s' has a Primary pipeline configuration registered "
                            "to be located in '%s', however this path does cannot be "
                            "found!" % (primary_pc.get("project"), current_os_path))

        # looks good, we got a primary pipeline config that exists
        return PipelineConfiguration(current_os_path)

    else:
        # we are running a tank command coming from a particular PC!
        # make sure that this PC is actually associated with this project
        # and then use it.
        curr_pc_path = os.environ["TANK_CURRENT_PC"]

        # do a bit of cleanup - windows paths can end with a space
        if curr_pc_path.endswith(" "):
            curr_pc_path = curr_pc_path[:-1]
        # windows tends to end with a backslash
        if curr_pc_path.endswith("\\"):
            curr_pc_path = curr_pc_path[:-1]

        # the path stored in the TANK_CURRENT_PC env var may be a symlink etc.
        # now we need to find which PC entity this corresponds to in Shotgun.        
        pc_registered_path = get_pc_registered_location(curr_pc_path)

        if pc_registered_path is None:
            raise TankError("Error starting from the configuration located in '%s' - "
                            "it looks like this pipeline configuration and tank command "
                            "has not been configured for the current operating system." % curr_pc_path)

        # now if this tank command is associated with the path, the registered path should be in 
        # in the list of paths found in the tank data backlink file
        if pc_registered_path not in current_os_pcs:
            raise TankError("You are trying to start using the configuration and tank command "
                            "located in '%s'. The path '%s' you are trying to load is not "
                            "associated with that configuration. The path you are trying to load "
                            "is associated with the following configurations: %s. "
                            "Please use the tank command or Sgtk API in any of those "
                            "locations in order to continue. This error can occur if you "
                            "have moved a Configuration on disk without correctly updating "
                            "it. It can also occur if you are trying to use a tank command "
                            "associated with Project A to try to operate on a Shot or Asset that "
                            "that belongs to a project B." % (curr_pc_path, path, current_os_pcs))

        # okay so this PC is valid!
        return PipelineConfiguration(pc_registered_path)








################################################################################################
# method for loading configuration data. 

def get_core_api_version_for_pc(pc_root):
    """
    Returns the version number string for the core API, based on a given path
    """
    # read this from info.yml
    info_yml_path = os.path.join(pc_root, "install", "core", "info.yml")
    try:
        info_fh = open(info_yml_path, "r")
        try:
            data = yaml.load(info_fh)
        finally:
            info_fh.close()
        data = str(data.get("version", "unknown"))
    except:
        data = "unknown"

    return data

def get_core_api_version_based_on_current_code():
    """
    Returns the version number string for the core API, based on the code that is currently
    executing.
    """
    # read this from info.yml
    info_yml_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "info.yml"))
    try:
        info_fh = open(info_yml_path, "r")
        try:
            data = yaml.load(info_fh)
        finally:
            info_fh.close()
        data = str(data.get("version", "unknown"))
    except:
        data = "unknown"

    return data


def get_pc_registered_location(pipeline_config_root_path):
    """
    Loads the location metadata file from install_location.yml
    This contains a reflection of the paths given in the pc entity.

    Returns the path that has been registered for this pipeline configuration 
    for the current OS.
    This is the path that has been defined in shotgun. It is also the path that is being
    used in the inverse pointer files that exist in each storage.
    
    This is useful when drive letter mappings or symlinks are being used - in these
    cases get_path() may not return the same value as get_registered_location_path().
    
    This may return None if no path has been registered for the current os.
    """
    # now read in the pipeline_configuration.yml file
    cfg_yml = os.path.join(pipeline_config_root_path, "config", "core", "install_location.yml")

    if not os.path.exists(cfg_yml):
        raise TankError("Location metadata file '%s' missing! Please contact support." % cfg_yml)

    fh = open(cfg_yml, "rt")
    try:
        data = yaml.load(fh)
    except Exception, e:
        raise TankError("Looks like a config file is corrupt. Please contact "
                        "support! File: '%s' Error: %s" % (cfg_yml, e))
    finally:
        fh.close()

    if sys.platform == "linux2":
        return data.get("Linux")
    elif sys.platform == "win32":
        return data.get("Windows")
    elif sys.platform == "darwin":
        return data.get("Darwin")
    else:
        raise TankError("Unsupported platform '%s'" % sys.platform)


def get_pc_disk_metadata(pipeline_config_root_path):
    """
    Loads the config metadata file from disk.    
    """

    # now read in the pipeline_configuration.yml file
    cfg_yml = os.path.join(pipeline_config_root_path, "config", "core", "pipeline_configuration.yml")

    if not os.path.exists(cfg_yml):
        raise TankError("Configuration metadata file '%s' missing! Please contact support." % cfg_yml)

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



def get_pc_roots_metadata(pipeline_config_root_path):
    """
    Loads and validates the roots metadata file.
    """
    # now read in the roots.yml file
    # this will contain something like
    # {'primary': {'mac_path': '/studio', 'windows_path': None, 'linux_path': '/studio'}}
    roots_yml = os.path.join(pipeline_config_root_path, "config", "core", "roots.yml")

    if not os.path.exists(roots_yml):
        raise TankError("Roots metadata file '%s' missing! Please contact support." % roots_yml)

    fh = open(roots_yml, "rt")
    try:
        data = yaml.load(fh)
    except Exception, e:
        raise TankError("Looks like the roots file is corrupt. Please contact "
                        "support! File: '%s' Error: %s" % (roots_yml, e))
    finally:
        fh.close()

    # sanity check that there is a primary root
    if constants.PRIMARY_STORAGE_NAME not in data:
        raise TankError("Could not find a primary storage in roots file "
                        "for configuration %s!" % pipeline_config_root_path)





    # make sure that all paths are correctly ended without a path separator
    #
    # Examples of paths in the metadata file and how they should be processed:
    #
    # 1. /foo/bar      - unchanged
    # 2. /foo/bar/     - /foo/bar
    # 3. z:/foo/       - z:\foo
    # 4. z:/           - z:\
    # 5. z:\           - z:\
    # 6. \\foo\bar\    - \\foo\bar
    

    def _convert_helper(path, separator):
        # ensures slashes are correct.
        
        # first, get rid of any slashes at the end
        # path value will be "/foo/bar", "c:" or "\\hello"
        path = path.rstrip("/\\")
        
        # add slash for drive letters: c: --> c:/
        if len(path) == 2 and path.endswith(":"):
            path += "/"
        
        # and convert to the right separators
        return path.replace("\\", separator).replace("/", separator)
        

    # now use our helper function to process the paths    
    for s in data:
        if data[s]["mac_path"]:
            data[s]["mac_path"] = _convert_helper(data[s]["mac_path"], "/")
        if data[s]["linux_path"]:
            data[s]["linux_path"] = _convert_helper(data[s]["linux_path"], "/")
        if data[s]["windows_path"]:
            data[s]["windows_path"] = _convert_helper(data[s]["windows_path"], "\\")

    return data
