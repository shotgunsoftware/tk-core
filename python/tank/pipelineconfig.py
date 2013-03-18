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
from .deploy import util
from .platform import constants
from .platform.environment import Environment


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
        our_version = self.__get_core_version()
        if our_version is not None:
            # we have an API installed locally
            current_api = get_core_api_version_based_on_current_code()
        
            if util.is_version_older(current_api, our_version):
                # currently running API is too old!
                current_api_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
                raise TankError("You are currently running a Tank API located in '%s'. "
                                "The current Configuration '%s' has separately installed "
                                "version of the API (%s) which is more recent than the currently "
                                "running version (%s). In order to use this pipeline configuration, "
                                "add %s to your PYTHONPATH and try again." % (current_api_path, 
                                                                              self.get_path(), 
                                                                              our_version, 
                                                                              current_api, 
                                                                              self.get_python_location()))
        
        
        
        
                
    def __repr__(self):
        return "<Tank Configuration %s>" % self._pc_root
                
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
                data = str(data.get("version", "unknown"))
            except:
                data = "unknown"
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
        
    def get_data_roots(self):
        """
        Returns a dictionary of all the data roots available for this PC,
        keyed by their storage name.
        """
        roots_yml = os.path.join(self._pc_root, "install", "core", constants.ROOTS_FILE)
        if not os.path.exists(roots_yml):
            raise TankError("Cannot find roots.yml file %s! Please contact support." % roots_yml)
            
        fh = open(roots_yml, "rt")
        try:
            data = yaml.load(fh)
        except Exception, e:
            raise TankError("Looks like the roots file is corrupt. Please contact "
                            "support! File: '%s' Error: %s" % (roots_yml, e))
        finally:
            fh.close()
        
        return data
    
    def get_primary_data_root(self):
        """
        Returns the path to the primary data root on the current platform
        """
        data = self.get_data_roots()
        
        if constants.PRIMARY_STORAGE_NAME not in data:
            raise TankError("Could not find a primary storage in roots file for %s!" % self)
        primary = data.get(constants.PRIMARY_STORAGE_NAME)
        if sys.platform not in primary:
            raise TankError("Roots file for %s is missing an entry for %s." % (self, sys.platform))
        
        return primary[sys.platform]
            
            
    def get_path_cache_location(self):
        """
        Returns the path to the path cache file.
        """
        return os.path.join(self.primary_data_root, "tank", "cache", constants.CACHE_DB_FILENAME)
            
            
    ########################################################################################
    # apps and engines
                        
    def get_install_root(self):
        """
        returns the install root for apps, engines, core
        """
        return os.path.join(self._pc_root, "install")
            
    def get_python_location(self):
        """
        returns the python root for this install.
        """
        return os.path.join(self._pc_root, "install", "core", "python")

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
        return os.path.join(self._pc_root, "config", "core", constants.CONTENT_TEMPLATES_FILE)
    
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
        
    
    


class StorageConfigurationMapping(object):
    """
    Handles operation on the mapping from a data root to a pipeline config
    """
    
    def __init__(self, data_root):
        self._root = data_root
        self._config_file = os.path.join(self._root, "tank", "config", constants.CONFIG_BACK_MAPPING_FILE)
        
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
    
    




def from_path(path):
    """
    Factory method that constructs a PC object from a path:
    - data paths are being traversed and resolved
    - if the path is a direct path to a PC root that's fine too
    """
    
    # first see if this path is a pipeline configuration
    
    # if not, walk up until a tank folder is found, 
    
    # todo: support user based work spaces
    
    
    
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



