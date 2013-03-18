"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Encapsulates the pipeline configuration and helps navigate and resolve paths
across storages, configurations etc.
"""
import os
import sys
import glob

from tank_vendor import yaml

from .errors import TankError

from .platform.environment import Environment

CACHE_DB_FILENAME = "path_cache.db"
CONTENT_TEMPLATES_FILE = "templates.yml"
ROOTS_FILE = "roots.yml"
CONFIG_BACK_MAPPING_FILE = "tank_configs.yml"

def from_path(path):
    """
    Factory method that constructs a PC object from a path:
    - data paths are being traversed and resolved
    - if the path is a direct path to a PC root that's fine too
    """
    return PipelineConfiguration(path)
    
    
    
def get_core_api_version_based_on_current_code():
    """
    Returns the version number string for the core API, based on the code that is currently
    executing.
    """
    # read this from info.yml
    info_yml_path = os.path.abspath(os.path.join( os.path.dirname(__file__), "..", "..", "info.yml"))
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


class StorageConfigurationMapping(object):
    """
    Handles operation on the mapping from a data root to a pipeline config
    """
    
    def __init__(self, data_root):
        self._root = data_root
        self._config_file = os.path.join(self._root, "tank", "config", CONFIG_BACK_MAPPING_FILE)
        
    def add_pipeline_configuration(self, mac_path, win_path, linux_path):
        """
        Add pipeline configuration mapping to a storage
        """
        if os.path.exists(self._config_file):
            # we have a config already - so read it in
        info_fh = open(info_yml_path, "r")
        try:
            data = yaml.load(info_fh)
        finally:
            info_fh.close()
        data = str(data.get("version", "unknown"))
            
            
        
    
    def get_pipeline_configs(self, path):
        """
        Returns a list of current os paths to pipeline configs, given an arbitrary path.
        Returns empty list if no matches are found.
        """
    

    

class PipelineConfiguration(object):
    """
    Represents a pipeline configuration in Tank.
    Use the factory methods above to construct this object, do not 
    create directly via constructor.
    """
    
    def __init__(self, pipeline_configuration_path):
        """
        Constructor.
        """
        self._pc_root = pipeline_configuration_path
        
        # validate that the current code version matches or is compatible with
        # the code that is locally stored in this config!!!!
        
                
    def __repr__(self):
        return "<Tank Configuration %s>" % self._pc_root
                
    ########################################################################################
    # data roots access
        
    def get_path(self):
        """
        Returns the master root for this pc
        """
        return self._pc_root
        
    def get_data_roots(self):
        """
        Returns a dictionary of all the data roots available for this PC,
        keyed by their storage name.
        """
    
    def get_primary_data_root(self):
        """
        Returns the path to the primary data root on the current platform
        """
            
            
    def get_path_cache_location(self):
        return os.path.join(self.primary_data_root, "tank", "cache", CACHE_DB_FILENAME)
            
            
            
    def get_project_id(self):
        """
        Returns the shotgun project id that is associated with this config
        """
            
            
    ########################################################################################
    # apps and engines
                        
    def get_install_root(self):
        """
        returns the install root for apps, engines, core
        """
        return os.path.join(self._pc_root, "install")
            
    def get_apps_location(self):
        """
        Returns the location where apps are stored
        """
        return os.path.join(self._pc_root, "install", "apps")
            
    def get_engines_location(self):
        """
        Returns the location where apps are stored
        """
        return os.path.join(self._pc_root, "install", "engines")
            
    def get_frameworks_location(self):
        """
        Returns the location where apps are stored
        """
        return os.path.join(self._pc_root, "install", "frameworks")
            
        
    ########################################################################################
    # configuration
        
    def get_templates_location(self):
        """
        Returns the path to the template config
        """
        return os.path.join(self._pc_root, "config", "core", CONTENT_TEMPLATES_FILE)
    
    def get_core_hooks_location(self):
        pass
    
    
    def get_schema_config_location(self):
        """
        returns the location of the schema
        """
        return os.path.join(self._pc_root, "config", "core", "schema")

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
            (name, ext) = os.path.splitext(file_name)
            env_names.append(name)
        return env_names
    
    def get_environment(self, env_name):
        """
        Returns an environment object given an environment name.
        You can use the get_environments() method to get a list of 
        all the environment names.
        """
        env_file = os.path.join(self._pc_root, "config", "env", "%s.yml" % env_name)    
        if not os.path.exists(env_file):     
            raise TankError("Cannot load environment '%s': Environment configuration "
                            "file '%s' does not exist!" % (env_name, env_file))
        
        return Environment(env_file, self)
        
    
    
    
    
    







#######################



#
#
#
#def get_project_roots(pipeline_configuration_path):
#    """
#    Returns a mapping of project root names to root paths based on roots file.
#    
#    :param project_root: Path to primary project root.
#    :returns: Dictionary of project root names to project root paths
#    """
#    
#    # TODO - FIX
#    
#    roots = {}
#    roots_data = _read_roots_file(pipeline_configuration_path)
#
#    platform_name = _determine_platform()
#    project_name = os.path.basename(project_root)
#    
#    for root_name, platform_paths in roots_data.items():
#        # Use platform appropriate root path
#        platform_path = platform_paths[platform_name]
#        roots[root_name] = os.path.join(platform_path, project_name)
#
#    # Use argument to check/set primary root
#    if roots.get("primary", project_root) != project_root:
#        err_msg = ("Primary root defined in roots.yml file does not match that passed as argument" + 
#                  " (likely from Tank local storage): \n%s\n%s" % (roots["primary"], project_root))
#        raise TankError(err_msg)
#    roots["primary"] = project_root
#    
#    return roots
#
#def platform_paths_for_root(root_name, pipeline_configuration_path):
#    """
#    Returns root paths for all platform for specified root.
#
#    :param root_name: Name of root whose paths are to be returned.
#    :param project_root: Path of primary project root.
#    """
#    project_name = os.path.basename(project_root)
#    roots_data = _read_roots_file(pipeline_configuration_path)
#    root_data = roots_data.get(root_name)
#    if root_data is None:
#        root_data = {}
#    
#    # Add project directory to the root path for all platforms defined
#    # in the roots file
#    for platform in root_data:
#        platform_root_path = root_data.get(platform)
#        if platform_root_path is None:
#            # skip it!
#            continue
#
#        root_data[platform] = os.path.join(platform_root_path, project_name)
#    return root_data
#
#
#def _read_roots_file(pipeline_configuration_path):
#    root_file_path = constants.get_roots_file_location(pipeline_configuration_path)
#    if os.path.exists(root_file_path):
#        root_file = open(root_file_path, "r")
#        try:
#            roots_data = yaml.load(root_file)
#        finally:
#            root_file.close()
#    else: 
#        roots_data = {}
#    return roots_data
#
#def get_primary_root(input_path):
#    """
#    Returns path to the primary project root.
#
#    :param input_path: A path in the project.
#
#    :returns: Path to primary project root
#    :raises: TankError if input_path is not part of a tank project tree.
#    """
#    # find tank config directory
#    cur_path = input_path
#    while True:
#        config_path = os.path.join(cur_path, "tank", "config")
#        # need to test for something in project vs studio config
#        if os.path.exists(config_path):
#            break
#        parent_path = os.path.dirname(cur_path)
#        if parent_path == cur_path:
#            # Topped out without finding config
#            raise TankError("Path is not part of a Tank project: %s" % input_path)
#        cur_path = parent_path
#
#    primary_roots_file = os.path.join(config_path, "primary_project.yml")
#    if os.path.exists(primary_roots_file):
#        # Get path from file
#        open_file = open(primary_roots_file, "r")
#        try:
#            primary_paths = yaml.load(open_file)
#        finally:
#            open_file.close()
#        platform_name = _determine_platform()
#        return primary_paths.get(platform_name)
#    else:
#        schema_path = os.path.join(config_path, "core", "schema")
#        # primary root file missing, check if it's project or studio path
#        if os.path.exists(schema_path):
#            return cur_path
#        raise TankError("Path is not part of a Tank project: %s" % input_path)
#
#            
#def _determine_platform():
#    system = sys.platform.lower()
#
#    if system == 'darwin':
#        platform_name = "mac_path"
#    elif system.startswith('linux'):
#        platform_name = 'linux_path'
#    elif system == 'win32':
#        platform_name = 'windows_path'
#    else:
#        raise TankError("Unable to determine operating system.")
#    return platform_name
