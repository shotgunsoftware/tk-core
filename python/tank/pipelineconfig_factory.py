# Copyright (c) 2014 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import sys
import urlparse
import collections
import cPickle as pickle

from .errors import TankError
from .platform import constants 
from .util import shotgun
from . import pipelineconfig_utils
from .pipelineconfig import PipelineConfiguration



def from_entity(entity_type, entity_id):
    """
    Factory method that constructs a pipeline configuration given a Shotgun Entity.
    
    Note! Because this is a factory method which is part of the initialization of
    Toolkit, at the point of execution, very little state has been established.
    Because the pipeline configuration and project is not know at this point,
    conventional configuration data and hooks cannot be accessed. 
    
    :param entity_type: Shotgun Entity type
    :param entity_id: Shotgun id
    :returns: Pipeline Configuration object
    """
    try:
        pc = _from_entity(entity_type, entity_id, force_reread_shotgun_cache=False)
    except TankError:
        # lookup failed! This may be because there are missing items
        # in the cache. For failures, try again, but this time
        # force re-read the cache (e.g connect to shotgun)
        # if the previous failure was due to a missing item
        # in the cache, 
        pc = _from_entity(entity_type, entity_id, force_reread_shotgun_cache=True)
    
    return pc


def _from_entity(entity_type, entity_id, force_reread_shotgun_cache):
    """
    Factory method that constructs a pipeline configuration given a Shotgun Entity.
    This method contains the implementation payload.
    
    :param entity_type: Shotgun Entity type
    :param entity_id: Shotgun id
    :param force_reread_shotgun_cache: Should the cache be force re-populated?
    :returns: Pipeline Configuration object
    """

    # first see if we can resolve a project id from this entity
    project_id = __get_project_id(entity_type, entity_id, force_reread_shotgun_cache)
    
    # now given the project id, find the pipeline configurations
    if project_id is None:
        raise TankError("Cannot find a valid %s with id %s in Shotgun! "
                        "Please ensure that the object exists "
                        "and that it has been linked up to a Toolkit "
                        "enabled project." % (entity_type, entity_id))

    # now find the pipeline configurations that are matching this project
    data = _get_pipeline_configs(force_reread_shotgun_cache)
    associated_sg_pipeline_configs = _get_pipeline_configs_for_project(project_id, data)
    
    if len(associated_sg_pipeline_configs) == 0:
        raise TankError("Cannot resolve a pipeline configuration for %s %s - Toolkit is not "
                        "enabled for that Shotgun project." % (entity_type, entity_id)) 

    # extract path data from the pipeline configuration shotgun data
    (local_pc_paths, primary_pc_paths) = _get_pipeline_configuration_paths(associated_sg_pipeline_configs)
        
    # figure out if we are running a tank command / api from a local pc or from a studio level install
    config_context_path  = _get_configuration_context()

    if config_context_path:
        # we are running the tank command or API from a configuration
        
        if config_context_path not in local_pc_paths:
            # the tank command / api proxy which this session was launched for is *not*
            # associated with the given entity type and entity id!
            raise TankError("The pipeline configuration in '%s' is is associated with a different "
                            "project from %s %s. To see which pipeline configurations are available " 
                            "for a project, open the pipeline configurations page "
                            "in Shotgun." % (config_context_path, entity_type, entity_id))                        
            
        # ok we got a pipeline config matching the tank command from which we launched.
        # because we found the PC in the list of PCs for this project, we know that it must be valid!
        return PipelineConfiguration(config_context_path)

    else:
        # we are running the tank command or API proxy from the studio location, e.g.
        # a core which is located outside a pipeline configuration.
        
        # in this case, find the primary pipeline config and use that
        if len(primary_pc_paths) == 0:
            raise TankError("The Project associated with %s %s does not have a primary Pipeline "
                            "Configuration! This is required by Toolkit. It needs to be named '%s'. "
                            "Please double check by opening to the Pipeline configuration Page in "
                            "Shotgun for the project." % (entity_type, entity_id, 
                                                          constants.PRIMARY_PIPELINE_CONFIG_NAME))

        if len(primary_pc_paths) > 1:
            # for an entity lookup, there should be no ambiguity - an entity belongs to a project
            # and a project has got a distinct set of pipeline configs, exactly one of which
            # is the primary.
            raise TankError("More than one primary pipeline configuration is associated "
                            "with the entity %s %s: %s - Please contact support at "
                            "toolkitsupport@shotgunsoftware.com." % (entity_type, entity_id, primary_pc_paths))            

        # looks good, we got a primary pipeline config that exists
        return PipelineConfiguration(primary_pc_paths[0])



def from_path(path):
    """
    Factory method that constructs a pipeline configuration given a path on disk.
    
    Note! Because this is a factory method which is part of the initialization of
    Toolkit, at the point of execution, very little state has been established.
    Because the pipeline configuration and project is not know at this point,
    conventional configuration data and hooks cannot be accessed. 
    
    :param path: Path to a pipeline configuration or associated project folder
    :returns: Pipeline Configuration object
    """

    try:
        pc = _from_path(path, force_reread_shotgun_cache=False)
    except TankError:
        # lookup failed! This may be because there are missing items
        # in the cache. For failures, try again, but this time
        # force re-read the cache (e.g connect to shotgun)
        # if the previous failure was due to a missing item
        # in the cache, 
        pc = _from_path(path, force_reread_shotgun_cache=True)
    
    return pc


def _from_path(path, force_reread_shotgun_cache):
    """
    Internal method that constructs a pipeline configuration given a path on disk.
    
    :param path: Path to a pipeline configuration or associated project folder
    :param force_reread_shotgun_cache: Should the cache be force re-populated?
    :returns: Pipeline Configuration object
    """

    if not isinstance(path, basestring):
        raise TankError("Cannot create a configuration from path '%s' - path must be a string!" % path)

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
            raise TankError("Cannot create a configuration from path '%s' - the path does "
                            "not exist on disk!" % path)

    # first see if someone is passing the path to an actual pipeline configuration    
    if pipelineconfig_utils.is_pipeline_config(path):
        # resolve the "real" location that is stored in Shotgun and 
        # cached in the file system
        pc_registered_path = pipelineconfig_utils.get_config_install_location(path)

        if pc_registered_path is None:
            raise TankError("Error starting from the configuration located in '%s' - "
                            "it looks like this pipeline configuration and tank command "
                            "has not been configured for the current operating system." % path)
        return PipelineConfiguration(pc_registered_path)

    # now get storage data, use cache unless force flag is set 
    sg_data = _get_pipeline_configs(force_reread_shotgun_cache)
        
    # now given ALL pipeline configs for ALL projects and their associated projects
    # and project root paths (in sg_data), figure out which pipeline configurations
    # are matching the given path.
    associated_sg_pipeline_configs = _get_pipeline_configs_for_path(path, sg_data)

    if len(associated_sg_pipeline_configs) == 0:
        # no matches! The path is unknown or invalid.
        raise TankError("The path '%s' does not seem to belong to any known Toolkit project!" % path)

    # extract current os path data from the pipeline configuration shotgun data
    (local_pc_paths, primary_pc_paths) = _get_pipeline_configuration_paths(associated_sg_pipeline_configs)

    # figure out if we are running a tank command / api from a local pc or from a studio level install
    config_context_path  = _get_configuration_context()

    if config_context_path:
        # we are running the tank command or API proxy from a configuration
        
        # now if this tank command is associated with the path, the registered path should be in 
        # in the list of paths found in the tank data backlink file
        if config_context_path not in local_pc_paths:
            raise TankError("You are trying to start Toolkit using the pipeline configuration "
                            "located in '%s'. The path '%s' you are trying to load is not "
                            "associated with that configuration. Instead, it is "
                            "associated with the following pipeline configurations: %s. "
                            "Please use the tank command or Toolkit API in any of those "
                            "locations in order to continue. This error can occur if you "
                            "have moved a configuration manually rather than using "
                            "the 'tank move_configuration command'. It can also occur if you " 
                            "are trying to use a tank command associated with Project A "
                            "to try to operate on a Shot or Asset that belongs to a "
                            "project B." % (config_context_path, path, local_pc_paths))

        # okay so this PC is valid!
        return PipelineConfiguration(config_context_path)
        
    else:
        # we are running a studio level tank command.
        # find the primary pipeline configuration in the list of matching configurations.        
        if len(primary_pc_paths) == 0:
            raise TankError("Cannot find a primary pipeline configuration for path '%s'. "
                            "The following pipeline configurations are associated with the "
                            "path, but none of them is marked as Primary: %s" % (path, local_pc_paths))

        if len(primary_pc_paths) > 1:
            raise TankError("The path '%s' is associated with more than one primary pipeline "
                            "configuration. This can happen if there is ambiguity in your project setup, where "
                            "projects store their data in an overlapping fashion. For example, if a project is "
                            "named the same as a local storage root. In this case, try creating "
                            "your API instance (or tank command) directly from the pipeline configuration rather "
                            "than via the studio level API. This will explicitly call out which project you are "
                            "intending to use in conjunction with he path. The pipeline configuration paths "
                            "associated with this path are: %s" % (path, primary_pc_paths))
        
        # looks good, we got a primary pipeline config that exists
        return PipelineConfiguration(primary_pc_paths[0])

    


#################################################################################################################
# utilities

def _get_configuration_context():
    """
    Returns a path if the API was invoked via a configuration context, otherwise None.
    
    If this session was involved (tank command or python API) from a studio level API,
    e.g. with no connection to any config, None is returned.
    
    In the case the session was started via a python proxy API or tank command
    connected to a configuration, the path to that configuration root is returned.
    The path returned is normalized and should reflect the exact value stored in the 
    pipeline configuration entry in shotgun.
    
    :returns: path or None 
    """
    # default for studio level tank command/API
    val = None

    if "TANK_CURRENT_PC" in os.environ:
        # config level tank command/API
        curr_pc_path = os.environ["TANK_CURRENT_PC"]

        # the path stored in the TANK_CURRENT_PC env var may be a symlink etc.
        # now we need to find which PC entity this corresponds to in Shotgun.
        # Once found, we can double check that the current Entity is actually
        # associated with the project that the PC is associated with.
        val = pipelineconfig_utils.get_config_install_location(curr_pc_path)
        
    return val


def _get_pipeline_configuration_paths(sg_pipeline_configs):
    """
    Given a list of Shotgun Pipeline configuration entity data, return a list
    of pipeline configuration paths for the current platform. Also returns
    the local os path to any primary pipeline configurations if such are found.
    
    :param sg_pipeline_configs: SG pipeline configuration data. List of dicts.
    :returns: (all_paths, primary_paths) - tuple with two lists of path strings 
    """
    # get list of local path to pipeline configurations that we have
    platform_lookup = {"linux2": "linux_path", "win32": "windows_path", "darwin": "mac_path" }
    local_pc_paths = []
    primary_pc_paths = []
    for pc in sg_pipeline_configs:
        curr_os_path = pc.get(platform_lookup[sys.platform])
        local_pc_paths.append(curr_os_path)
        if pc.get("code") == constants.PRIMARY_PIPELINE_CONFIG_NAME:
            primary_pc_paths.append(curr_os_path)
    
    return (local_pc_paths, primary_pc_paths)


def _get_pipeline_configs_for_path(path, data):
    """
    Given a path on disk and a cache data structure, return a list of
    associated pipeline configurations.

    Based on the Shotgun cache data, generates a list of project root locations.
    These are then compared (case insensitively) against the given path and 
    if it is determined that the input path belongs to any of these project
    roots, the list of pipeline configuration objects for that root is returned.
    
    the return data structure is a list of dicts, each dict containing the 
    following fields:
    
        - id
        - code 
        - windows_path 
        - linux_path 
        - mac_path 
        - project 
        - project.Project.tank_name    

    
    Edge case notes:
    
    Normally, this command returns all the pipeline configurations that
    are associated with a single project only. 
    
    However, there are edge cases where it may return pipeline configurations 
    for *multiple* projects.
      
    in the case there are overlapping storage roots, or where a project is named 
    the same name as a storage root, this may lead to a scenario where a path on 
    disk could potentially belong to *two* projects. In this case, this method will
    return the pipeline configurations for both projects.
    
    For example, imagine the following setup:
    
    Storages: f:\ and f:\foo
    Project names: foo and bar
    
    (Note that the project name 'foo' is named the same as the storage F:\foo)
    
    This means we have the following project roots:
    (1) f:\foo      (storage f:\, project foo)
    (2) f:\bar      (storage f:\, project bar)
    (3) f:\foo\foo  (storage f:\foo, project foo)
    (4) f:\foo\bar  (storage f:\foo, project bar)
    
    If we have a path f:\foo\bar\hello_world.ma, this could either belong to 
    project 'bar' (matching 4) or project 'foo' (matching 1).
    
    In this case, the pipeline configurations for both foo and bar
    are returned.
        
    :param path: Path to look for
    :param data: Cache data chunk, obtained using _get_pipeline_configs()
    :returns: list of pipeline configurations matching the path, [] if no match.
    """
    platform_lookup = {"linux2": "linux_path", "win32": "windows_path", "darwin": "mac_path" }
    
    # step 1 - extract all storages for the current os
    storages = []
    for s in data["local_storages"]:
        storage_path = s[ platform_lookup[sys.platform] ]
        if storage_path: 
            storages.append(storage_path)
    
    # step 2 - build a dict of storage project paths and associate with project id
    project_paths = collections.defaultdict(list)
    for pc in data["pipeline_configurations"]:

        for s in storages:
            # all pipeline configurations are associated
            # with a project which has a tank_name set
            project_name = pc["project.Project.tank_name"]
            
            # for multi level projects, there may be slashes, e.g
            # project_name is "parent/child"
            # ensure this is translated to "parent\child" on windows
            project_name = project_name.replace("/", os.path.sep)
            
            # now, another windows edge case we need to ensure is covered
            # if a windows storage is defined as 'x:', then 
            # os.path.join('x:', 'folder') will return 'x:folder'
            # and not 'x:\folder as we would expect
            # so ensure that any path on this form is extended:
            # 'x:' --> 'x:\'
            if len(s) == 2 and s.endswith(":"):
                s = "%s%s" % (s, os.path.sep)
            
            # and concatenate it with the storage
            project_path = os.path.join(s, project_name)
            # associate this path with the pipeline configuration
            project_paths[project_path].append(pc)
    
    # step 3 - look at the path we passed in - see if any of the computed
    # project folders are determined to be a parent path
    all_matching_pcs = []
    
    for project_path in project_paths:
        
        # (like the SG API, this logic is case preserving, not case insensitive)
        path_lower = path.lower()
        proj_path_lower = project_path.lower()
        # check if the path matches. Either
        # direct match: path: /mnt/proj_x == project path: /mnt/proj_x
        # child path: path: /mnt/proj_x/foo/bar starts with /mnt/proj_x/
        
        if path_lower == proj_path_lower or path_lower.startswith("%s%s" % (proj_path_lower, os.path.sep)):
            # found a match!
            associated_pcs = project_paths[project_path] 
            all_matching_pcs.extend(associated_pcs)

    return all_matching_pcs
    

def _get_pipeline_configs_for_project(project_id, data):
    """
    Given a project id, return a list of associated pipeline configurations.
    
    Based on the Shotgun cache data, generates a list of project root locations.
    These are then compared (case insensitively) against the given path and 
    if it is determined that the input path belongs to any of these project
    roots, the list of pipeline configuration objects for that root is returned.
    
    the return data structure is a list of dicts, each dict containing the 
    following fields:
    
        - id
        - code 
        - windows_path 
        - linux_path 
        - mac_path 
        - project 
        - project.Project.tank_name    
        
    :param project_id: Project id to look for
    :param data: Cache data chunk, obtained using _get_pipeline_configs()
    :returns: list of pipeline configurations matching the path, [] if no match.
    """
    matching_pipeline_configs = []
    
    for pc in data["pipeline_configurations"]:
        
        # note the null check - in the future, the site configs will
        # have null values for project.
        if pc["project"] and pc["project"]["id"] == project_id:
            matching_pipeline_configs.append(pc)  
    
    return matching_pipeline_configs
    


#################################################################################################################
# methods relating to maintaining a small cache to speed up initialization

def __get_project_id(entity_type, entity_id, force=False):
    """
    Connects to Shotgun and retrieves the project id for an entity.
    
    Uses a cache if possible.
    
    :param entity_type: Shotgun Entity type
    :param entity_id: Shotgun entity id
    :param force: Force read values from Shotgun
    :returns: project id (int) or None if not found
    """
    if entity_type == "Project":
        # don't need the cache for this one :)
        return entity_id
    
    CACHE_KEY = "%s_%s" % (entity_type, entity_id)
    
    if force == False:
        # try to load cache first
        # if that doesn't work, fall back on shotgun
        cache = _load_lookup_cache()
        if cache and cache.get(CACHE_KEY):
            # cache hit!
            return cache.get(CACHE_KEY)
         
    # ok, so either we are force recomputing the cache or the cache wasn't there
    sg = shotgun.get_sg_connection()
    
    # get all local storages for this site
    entity_data = sg.find_one(entity_type, [["id", "is", entity_id]], ["project"]) 
    
    project_id = None
    if entity_data and entity_data["project"]:
        # we have a project id! - cache this data
        project_id = entity_data["project"]["id"] 
        _add_to_lookup_cache(CACHE_KEY, project_id)
    
    return project_id
    

def _get_pipeline_configs(force=False):
    """
    Connects to Shotgun and retrieves information about all projects 
    and all pipeline configurations in Shotgun. Adds this to the disk cache.
    If a cache already exists, this is used instead of talking to Shotgun.
    
    To force a re-cache, set the force flag to True.
     
    Returns a complex data structure with the following fields
    
    local_storages:
        - id
        - code 
        - windows_path
        - mac_path
        - linux_path
    
    pipeline_configurations:
        - id
        - code 
        - windows_path 
        - linux_path 
        - mac_path 
        - project 
        - project.Project.tank_name    
    
    :param force: set this to true to force a cache refresh
    :returns: dictionary with keys local_storages and pipeline_configurations.
    """
    
    CACHE_KEY = "paths"
    
    if force == False:
        # try to load cache first
        # if that doesn't work, fall back on shotgun
        cache = _load_lookup_cache()
        if cache and cache.get(CACHE_KEY):
            # cache hit!
            return cache.get(CACHE_KEY)
         
    # ok, so either we are force recomputing the cache or the cache wasn't there
    sg = shotgun.get_sg_connection()
    
    # get all local storages for this site
    local_storages = sg.find("LocalStorage", 
                             [], 
                             ["id", "code", "windows_path", "mac_path", "linux_path"])
    
    # get all pipeline configurations (and their associated projects) for this site
    pipeline_configs = sg.find("PipelineConfiguration", 
                               [["project.Project.tank_name", "is_not", None]], 
                               ["id", 
                                "code", 
                                "windows_path", 
                                "linux_path", 
                                "mac_path", 
                                "project", 
                                "project.Project.tank_name"])

    # cache this data
    data = {"local_storages": local_storages, "pipeline_configurations": pipeline_configs}
    _add_to_lookup_cache(CACHE_KEY, data)
    
    return data

def _load_lookup_cache():
    """
    Load lookup cache file from disk.
    
    :returns: cache cache, as constructed by the _add_to_lookup_cache method
    """
    cache_file = _get_cache_location()
    cache_data = {}
    
    if os.path.exists(cache_file):
        # try to load the cache, fail gracefully if this fails for whatever reason
        try:
            fh = open(cache_file, "rb")
            try:
                cache_data = pickle.load(fh)
            finally:
                fh.close()
        except:
            # failed to load cache from file. Continue silently. 
            pass 
        
    return cache_data
        
def _add_to_lookup_cache(key, data):
    """
    Add a key to the lookup cache. This method will silently
    fail if the cache cannot be operated on.
    
    :param key: Dictionary key for the cache
    :param data: Data to associate with the dictionary key
    """
    
    # first load the content
    cache_data = _load_lookup_cache()
    # update
    cache_data[key] = data
    # and write out the cache
    cache_file = _get_cache_location()
    
    old_umask = os.umask(0)
    try:
        
        # try to create the cache folder with as open permissions as possible
        cache_dir = os.path.dirname(cache_file)
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir, 0777)
        
        # write cache file
        fh = open(cache_file, "wb")
        try:
            cache_data = pickle.dump(cache_data, fh)
        finally:
            fh.close()
        # and ensure the cache file has got open permissions
        os.chmod(cache_file, 0666)
    
    except:
        # silently continue in case exceptions are raised
        pass
    
    finally:
        os.umask(old_umask)
    
def _get_cache_location():    
    """
    Get the location of the initializtion lookup cache.
    Just computes the path, no I/O.
    
    :returns: A path on disk to the cache file
    """

    # optimized version of creating an sg instance and then calling sg.base_url
    # this is to avoid connecting to shotgun if possible.
    sg_base_url = shotgun.get_associated_sg_base_url()

    # the default implementation will place things in the following locations:
    # macosx: ~/Library/Caches/Shotgun/SITE_NAME/toolkit_init.cache
    # windows: $APPDATA/Shotgun/SITE_NAME/toolkit_init.cache
    # linux: ~/.shotgun/SITE_NAME/toolkit_init.cache
    
    # first establish the root location
    if sys.platform == "darwin":
        root = os.path.expanduser("~/Library/Caches/Shotgun")
    elif sys.platform == "win32":
        root = os.path.join(os.environ["APPDATA"], "Shotgun")
    elif sys.platform.startswith("linux"):
        root = os.path.expanduser("~/.shotgun")

    # get site only; https://www.foo.com:8080 -> www.foo.com
    base_url = urlparse.urlparse(sg_base_url)[1].split(":")[0]
    
    # now structure things by site, project id, and pipeline config id
    return os.path.join(root, base_url, constants.SITE_INIT_CACHE_FILE_NAME)    

