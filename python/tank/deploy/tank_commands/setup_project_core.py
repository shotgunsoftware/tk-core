# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import sys
import os
import shutil

from ...platform import constants
from ...errors import TankError
from ... import pipelineconfig


from tank_vendor import yaml
    
def emit_project_setup_summary(log, setup_params):
    """
    Emit project summary to the given logger
    
    :param log: python logger object
    :param setup_params: Parameters object which holds gathered project settings
    """

    log.info("")
    log.info("")
    log.info("Project Creation Summary:")
    log.info("-------------------------")
    log.info("")
    log.info("You are about to set up the Shotgun Pipeline Toolkit "
             "for Project %s - %s " % (setup_params.get_project_id(), 
                                       setup_params.get_project_name()))
    log.info("The following items will be created:")
    log.info("")
    log.info("* A Shotgun Pipeline configuration will be created:" )
    log.info("  - on Macosx:  %s" % setup_params.get_config_disk_location("darwin"))
    log.info("  - on Linux:   %s" % setup_params.get_config_disk_location("linux2"))
    log.info("  - on Windows: %s" % setup_params.get_config_disk_location("win32"))
    log.info("")
    log.info("* The Pipeline configuration will use the following Core API:")
    log.info("  - on Macosx:  %s" % setup_params.get_associated_core_path("darwin"))
    log.info("  - on Linux:   %s" % setup_params.get_associated_core_path("linux2"))
    log.info("  - on Windows: %s" % setup_params.get_associated_core_path("win32"))
    log.info("")

    for storage_name in setup_params.get_required_storages():

        log.info("* Toolkit will connect to the project folder in Storage '%s':" % storage_name )
        
        mac_path = setup_params.get_project_path(storage_name, "darwin")
        win_path = setup_params.get_project_path(storage_name, "darwin")
        linux_path = setup_params.get_project_path(storage_name, "darwin")        
        
        log.info("  - on Linux:   '%s'" % linux_path if linux_path else "  - on Linux:   No path defined")
        log.info("  - on Windows: '%s'" % win_path if win_path else "  - on Windows: No path defined")
        log.info("  - on Mac:     '%s'" % mac_path if mac_path else "  - on Mac:     No path defined")
        
    log.info("")
    log.info("")
    
    
    
def validate_project_setup(log, setup_params):
    """
    Pre-flight sanity check to be executed before actually carrying out the project setup.
    This will check to ensure permissions are correct, disk locations are correct etc.
    
    :param log: python logger object
    :param setup_params: Parameters object which holds gathered project settings
    """    
    
    # get the location of the configuration
    config_path_current_os = setup_params.get_config_disk_location(sys.platform) 
    
    # validate the local storages
    for storage_name in setup_params.get_required_storages():
        
        # get the project path for this storage
        # note! at this point, the storage root has been checked and exists on disk.
        project_path_local_os = setup_params.get_project_path(storage_name, sys.platform)
                        
        # make sure that the storage location is not the same folder
        # as the pipeline config location. That will confuse tank.
        if config_path_current_os == project_path_local_os:
            raise TankError("Your configuration location '%s' has been set to the same "
                            "as one of the storage locations. This is not supported!" % config_path_current_os)
        
        if not os.path.exists(project_path_local_os):
            raise TankError("The Project path %s for storage %s does not exist on disk! "
                            "Please create it and try again!" % (project_path_local_os, storage_name))
    
        tank_folder = os.path.join(project_path_local_os, "tank")
        if os.path.exists(tank_folder):
            # tank folder exists - make sure it is writable
            if not os.access(tank_folder, os.W_OK|os.R_OK|os.X_OK):
                raise TankError("The permissions setting for '%s' is too strict. The current user "
                                "cannot create files or folders in this location." % tank_folder)
        else:
            # no tank folder has been created in this storage
            # make sure we can create it
            if not os.access(project_path_local_os, os.W_OK|os.R_OK|os.X_OK):
                raise TankError("The permissions setting for '%s' is too strict. The current user "
                                "cannot create a tank folder in this location." % project_path_local_os)
            
    # validate that the config location is not taken
    if os.path.exists(config_path_current_os):
        # pc location already exists - make sure it doesn't already contain an install
        if os.path.exists(os.path.join(config_path_current_os, "install")) or \
           os.path.exists(os.path.join(config_path_current_os, "config")):
            raise TankError("Looks like the location '%s' already contains a "
                            "configuration!" % config_path_current_os)
        # also make sure it has right permissions
        if not os.access(config_path_current_os, os.W_OK|os.R_OK|os.X_OK):
            raise TankError("The permissions setting for '%s' is too strict. The current user "
                            "cannot create files or folders in this location." % config_path_current_os)
        
    else:
        # path does not exist! 
        # make sure parent path exists and is writable
        # find an existing parent path
        parent_os_pc_location = None
        curr_path = config_path_current_os
        while curr_path != os.path.dirname(curr_path):
            
            # get parent folder
            curr_path = os.path.dirname(curr_path)
            if os.path.exists(curr_path):
                parent_os_pc_location = curr_path 
                break
    
        if parent_os_pc_location is None:
            raise TankError("The folder '%s' does not exist! Please create "
                            "it before proceeding!" % config_path_current_os)
                
        # and make sure we can create a folder in it
        if not os.access(parent_os_pc_location, os.W_OK|os.R_OK|os.X_OK):
            raise TankError("Cannot create a project configuration in location '%s'! "
                            "The permissions setting for the closest parent folder that "
                            "can be detected, '%s', is too strict. The current user "
                            "cannot create folders in this location. Please create the "
                            "project configuration folder by hand and then re-run the project "
                            "setup." % (config_path_current_os, parent_os_pc_location))
    
    
    
    
def run_project_setup(log, sg, sg_app_store, sg_app_store_script_user, force, template_config_obj, setup_params):
    """
    Execute the actual project setup.
    No validation is happening at this point - ensure that you have executed _validate_project_setup()
    before calling this method! 

    :param log: python logger object
    :param sg: shotgun api connection to the associated site
    :param sg_app_store: toolkit app store sg connection
    :param sg_app_store_script_user: The script user used to connect to the app store, as a shotgun link-dict
    :param force: boolean indicating that the setup should be forced, e.g. makes it possible to set up
                  a project which has already got a toolkit setup registered.
    :param template_config_obj: object representing the configuration to use as part of the setup.
    :param setup_params: Parameters object which holds gathered project settings
    """
    old_umask = os.umask(0)
    try:
        return _project_setup_internal(log, 
                                       sg, 
                                       sg_app_store, 
                                       sg_app_store_script_user, 
                                       force, 
                                       setup_params)
    finally:
        os.umask(old_umask)
   
    
def _project_setup_internal(log, sg, sg_app_store, sg_app_store_script_user, force, setup_params):
    """
    Execute the actual project setup.
    No validation is happening at this point - ensure that you have executed _validate_project_setup()
    before calling this method! 

    :param log: python logger object
    :param sg: shotgun api connection to the associated site
    :param sg_app_store: toolkit app store sg connection
    :param sg_app_store_script_user: The script user used to connect to the app store, as a shotgun link-dict
    :param force: boolean indicating that the setup should be forced, e.g. makes it possible to set up
                  a project which has already got a toolkit setup registered.
    :param setup_params: Parameters object which holds gathered project settings
    """
    
    log.info("")
    log.info("Starting project setup.")
    
    # get the location of the configuration
    config_location_curr_os = setup_params.get_config_disk_location(sys.platform)
    config_location_mac = setup_params.get_config_disk_location("darwin")
    config_location_linux = setup_params.get_config_disk_location("linux2")
    config_location_win = setup_params.get_config_disk_location("win32")
    
    # project id
    project_id = setup_params.get_project_id()
    
    # if we have the force flag enabled, remove any pipeline configurations
    if force:
        pcs = sg.find("PipelineConfiguration", 
                      [["project", "is", {"id": project_id, "type": "Project"} ]],
                      ["code"])
        for x in pcs:
            log.warning("Force mode: Deleting old pipeline configuration %s..." % x["code"])
            sg.delete("PipelineConfiguration", x["id"])
            
    # first do disk structure setup, this is most likely to fail.
    log.info("Installing configuration into '%s'..." % config_location_curr_os )
    if not os.path.exists(config_location_curr_os):
        # note that we have already validated that creation is possible
        os.makedirs(config_location_curr_os, 0775)
    
    # create pipeline config base folder structure            
    _make_folder(log, os.path.join(config_location_curr_os, "cache"), 0777)    
    _make_folder(log, os.path.join(config_location_curr_os, "config"), 0775)
    _make_folder(log, os.path.join(config_location_curr_os, "install"), 0775)
    _make_folder(log, os.path.join(config_location_curr_os, "install", "core"), 0777)
    _make_folder(log, os.path.join(config_location_curr_os, "install", "core", "python"), 0777)
    _make_folder(log, os.path.join(config_location_curr_os, "install", "core", "setup"), 0777)
    _make_folder(log, os.path.join(config_location_curr_os, "install", "core.backup"), 0777)
    _make_folder(log, os.path.join(config_location_curr_os, "install", "core.backup", "activation_13"), 0777, True)
    _make_folder(log, os.path.join(config_location_curr_os, "install", "engines"), 0777, True)
    _make_folder(log, os.path.join(config_location_curr_os, "install", "apps"), 0777, True)
    _make_folder(log, os.path.join(config_location_curr_os, "install", "frameworks"), 0777, True)
    
    # copy the configuration into place
    tc = setup_params.get_template_configuration()
    tc.create_configuration(os.path.join(config_location_curr_os, "config"))
    
    # copy the tank binaries to the top of the config
    log.debug("Copying Toolkit binaries...")
    core_api_root = os.path.abspath(os.path.join( os.path.dirname(__file__), "..", "..", "..", ".."))
    root_binaries_folder = os.path.join(core_api_root, "setup", "root_binaries")
    for file_name in os.listdir(root_binaries_folder):
        src_file = os.path.join(root_binaries_folder, file_name)
        tgt_file = os.path.join(config_location_curr_os, file_name)
        shutil.copy(src_file, tgt_file)
        os.chmod(tgt_file, 0775)
    
    # copy the python stubs
    log.debug("Copying python stubs...")
    tank_proxy = os.path.join(core_api_root, "setup", "tank_api_proxy")
    _copy_folder(log, tank_proxy, os.path.join(config_location_curr_os, "install", "core", "python"))
        
    # specify the parent files in install/core/core_PLATFORM.cfg
    log.debug("Creating core redirection config files...")
    
    core_path = os.path.join(config_location_curr_os, "install", "core", "core_Darwin.cfg")
    core_location = setup_params.get_associated_core_path("darwin")
    fh = open(core_path, "wt")
    fh.write(core_location if core_location else "undefined")
    fh.close()
    
    core_path = os.path.join(config_location_curr_os, "install", "core", "core_Linux.cfg")
    core_location = setup_params.get_associated_core_path("linux2")
    fh = open(core_path, "wt")
    fh.write(core_location if core_location else "undefined")
    fh.close()

    core_path = os.path.join(config_location_curr_os, "install", "core", "core_Windows.cfg")
    core_location = setup_params.get_associated_core_path("win32")
    fh = open(core_path, "wt")
    fh.write(core_location if core_location else "undefined")
    fh.close()
    
    # write a file location file for our new setup
    sg_code_location = os.path.join(config_location_curr_os, "config", "core", "install_location.yml")
    
    # if we are basing our setup on an existing project setup, make sure we can write to the file.
    if os.path.exists(sg_code_location):
        os.chmod(sg_code_location, 0666)

    fh = open(sg_code_location, "wt")
    fh.write("# Shotgun Pipeline Toolkit configuration file\n")
    fh.write("# This file was automatically created by setup_project\n")
    fh.write("# This file reflects the paths in the primary pipeline\n")
    fh.write("# configuration defined for this project.\n")
    fh.write("\n")
    fh.write("Windows: '%s'\n" % config_location_win)
    fh.write("Darwin: '%s'\n" % config_location_mac)    
    fh.write("Linux: '%s'\n" % config_location_linux)                    
    fh.write("\n")
    fh.write("# End of file.\n")
    fh.close()
        
    # update the roots.yml file in the config to match our settings
    # resuffle list of associated local storages to be a dict keyed by storage name
    # and with keys mac_path/windows_path/linux_path

    log.debug("Writing roots.yml...")
    roots_path = os.path.join(config_location_curr_os, "config", "core", "roots.yml")
    
    roots_data = {}
    for storage_name in setup_params.get_required_storages():
    
        roots_data[storage_name] = {"windows_path": setup_params.get_project_path(storage_name, "win32"),
                                    "linux_path": setup_params.get_project_path(storage_name, "linux2"),
                                    "mac_path": setup_params.get_project_path(storage_name, "darwin")}
    
    try:
        fh = open(roots_path, "wt")
        yaml.dump(roots_data, fh)
        fh.close()
    except Exception, exp:
        raise TankError("Could not write to roots file %s. "
                        "Error reported: %s" % (roots_path, exp))
    
    # now ensure there is a tank folder in every storage
    for storage_name in setup_params.get_required_storages():
        
        log.info("Setting up %s storage..." % storage_name )
        
        # get the project path for this storage
        current_os_path = setup_params.get_project_path(storage_name, sys.platform)
        log.debug("Project path: %s" % current_os_path )
        
        tank_path = os.path.join(current_os_path, "tank")
        if not os.path.exists(tank_path):
            _make_folder(log, tank_path, 0777)
        
        cache_path = os.path.join(tank_path, "cache")
        if not os.path.exists(cache_path):
            _make_folder(log, cache_path, 0777)

        config_path = os.path.join(tank_path, "config")
        if not os.path.exists(config_path):
            _make_folder(log, config_path, 0777)
        
        if storage_name == constants.PRIMARY_STORAGE_NAME:
            # primary storage - make sure there is a path cache file
            # this is to secure the ownership of this file
            cache_file = os.path.join(cache_path, "path_cache.db")
            if not os.path.exists(cache_file):
                log.debug("Touching path cache %s" % cache_file)
                fh = open(cache_file, "wb")
                fh.close()
                os.chmod(cache_file, 0666)
                
        # create file for configuration backlinks
        log.debug("Setting up storage -> PC mapping...")
        scm = pipelineconfig.StorageConfigurationMapping(current_os_path)
        
        # make sure there is no existing backlinks associated with the config
        #
        # this can be the case if the config setup is using a pre-0.13 setup
        # where the project tank folder and the install folder is the same,
        # and the project was based on another project and thefore when the 
        # files were copied across, the back mappings file also got accidentally
        # copied.
        #
        # it can also happen when doing a force re-install of a project.
        scm.clear_mappings()
        
        # and add our configuration
        scm.add_pipeline_configuration(config_location_mac, config_location_win, config_location_linux)    
    
    # creating project.tank_name record
    log.info("Registering project in Shotgun...")
    project_name = setup_params.get_project_name()
    log.debug("Shotgun: Setting Project.tank_name to %s" % project_name)
    sg.update("Project", project_id, {"tank_name": project_name})
    
    # create pipeline configuration record
    log.info("Creating Pipeline Configuration in Shotgun...")
    data = {"project": {"type": "Project", "id": project_id },
            "linux_path": config_location_linux,
            "windows_path": config_location_win,
            "mac_path": config_location_mac,
            "code": constants.PRIMARY_PIPELINE_CONFIG_NAME}
    pc_entity = sg.create(constants.PIPELINE_CONFIGURATION_ENTITY, data)
    log.debug("Created data: %s" % pc_entity)
    
    # write the record to disk
    pipe_config_sg_id_path = os.path.join(config_location_curr_os, "config", "core", "pipeline_configuration.yml")
    log.debug("Writing to pc cache file %s" % pipe_config_sg_id_path)
    
    # determine the entity type to use for Published Files:
    pf_entity_type = _get_published_file_entity_type(log, sg)
    
    data = {}
    data["project_name"] = project_name
    data["pc_id"] = pc_entity["id"]
    data["project_id"] = project_id
    data["pc_name"] = constants.PRIMARY_PIPELINE_CONFIG_NAME 
    data["published_file_entity_type"] = pf_entity_type
    
    try:
        fh = open(pipe_config_sg_id_path, "wt")
        yaml.dump(data, fh)
        fh.close()
    except Exception, exp:
        raise TankError("Could not write to pipeline configuration cache file %s. "
                        "Error reported: %s" % (pipe_config_sg_id_path, exp))
    
    if sg_app_store:
        # we have an app store connection
        # write a custom event to the shotgun event log
        log.debug("Writing app store stats...")
        data = {}
        data["description"] = "%s: An Toolkit Project was created" % sg.base_url
        data["event_type"] = "TankAppStore_Project_Created"
        data["user"] = sg_app_store_script_user
        data["project"] = constants.TANK_APP_STORE_DUMMY_PROJECT
        sg_app_store.create("EventLogEntry", data)
    
    
    ##########################################################################################
    # install apps
    
    # We now have a fully functional tank setup! Time to start it up...
    pc = pipelineconfig.from_path(config_location_curr_os)
    
    # each entry in the config template contains instructions about which version of the app
    # to use.
    
    for env_name in pc.get_environments():
        env_obj = pc.get_environment(env_name)
        log.info("Installing apps for environment %s..." % env_obj)
        _install_environment(env_obj, log)

    ##########################################################################################
    # post processing of the install
    
    # run after project create script if it exists
    after_script_path = os.path.join(config_location_curr_os, "config", "after_project_create.py")
    if os.path.exists(after_script_path):
        log.info("Found a post-install script %s" % after_script_path)
        log.info("Executing post-install commands...")
        sys.path.insert(0, os.path.dirname(after_script_path))
        try:
            import after_project_create
            after_project_create.create(sg=sg, project_id=project_id, log=log)
        except Exception, e:
            if ("API read() invalid/missing string entity" in e.__str__()
                and "\"type\"=>\"TankType\"" in e.__str__()):
                # Handle a specific case where an old version of the 
                # after_project_create script set up TankType entities which
                # are now disabled following the migration to the 
                # new PublishedFileType entity
                log.info("")
                log.warning("The post install script failed to complete.  This is most likely because it "
                            "is from an old configuration that is attempting to create 'TankType' entities "
                            "which are now disabled in Shotgun.")
            else:
                log.info("")
                log.error("The post install script failed to complete: %s" % e)
        else:
            log.info("Post install phase complete!")            
        finally:
            sys.path.pop(0)

    log.info("")
    log.info("Your Toolkit Project has been fully set up.")
    log.info("")

    # show the readme file if it exists
    readme_file = os.path.join(config_location_curr_os, "config", "README")
    if os.path.exists(readme_file):
        log.info("")
        log.info("README file for template:")
        fh = open(readme_file)
        for line in fh:
            print line.strip()
        fh.close()
    
    log.info("")
    log.info("We recommend that you now run 'tank updates' to get the latest")
    log.info("versions of all apps and engines for this project.")
    log.info("")
    log.info("For more Apps, Support, Documentation and the Toolkit Community, go to")
    log.info("https://toolkit.shotgunsoftware.com")
    log.info("")        

    
    

########################################################################################
# helper methods
       

def _make_folder(log, folder, permissions, create_placeholder_file = False):
    """
    Create folder helper method
    
    :param log: std log handle
    :param folder: path to folder
    :param permissions: chmod int (e.g. 0777)
    :param create_placeholder_file: if true, a file named placeholder will be created. 
                                    this is to make the config more compatible with file 
                                    based SCMs such as perforce and git, where empty folders
                                    are not handled by the system
    """
    log.debug("Creating folder %s.." % folder)
    os.mkdir(folder, permissions)
    if create_placeholder_file:
        ph_path = os.path.join(folder, "placeholder")
        fh = open(ph_path, "wt")
        fh.write("This placeholder file was automatically generated by Toolkit.\n\n")
        
        fh.write("The placeholder file is needed when managing toolkit configurations\n")
        fh.write("in source control packages such as git and perforce. These systems\n")
        fh.write("do not handle empty folders so a placeholder file is required for the \n")
        fh.write("folder to be tracked and managed properly.\n")
        fh.close()
    

def _copy_folder(log, src, dst): 
    """
    Alternative implementation to shutil.copytree
    Copies recursively with very open permissions.
    Creates folders if they don't already exist.
    """
    
    if not os.path.exists(dst):
        log.debug("Creating folder %s..." % dst)
        os.mkdir(dst, 0775)

    names = os.listdir(src)     
    for name in names: 
        
        # get rid of system files
        if name in [".svn", ".git", ".gitignore", "__MACOSX"]: 
            continue
        
        srcname = os.path.join(src, name) 
        dstname = os.path.join(dst, name) 

        try: 
            if os.path.isdir(srcname): 
                _copy_folder(log, srcname, dstname)             
            else: 
                log.debug("Copying %s --> %s" % (srcname, dstname))
                shutil.copy(srcname, dstname) 
        
        except (IOError, os.error), why: 
            raise TankError("Can't copy %s to %s: %s" % (srcname, dstname, str(why))) 
    
def _install_environment(env_obj, log):
    """
    Make sure that all apps and engines exist in the local repo.
    """
    
    # populate a list of descriptors
    descriptors = []
    
    for engine in env_obj.get_engines():
        descriptors.append( env_obj.get_engine_descriptor(engine) )
        
        for app in env_obj.get_apps(engine):
            descriptors.append( env_obj.get_app_descriptor(engine, app) )
            
    for framework in env_obj.get_frameworks():
        descriptors.append( env_obj.get_framework_descriptor(framework) )
            
    # ensure all apps are local - if not then download them
    for descriptor in descriptors:
        if not descriptor.exists_local():
            log.info("Downloading %s to the local Toolkit install location..." % descriptor)            
            descriptor.download_local()
            
        else:
            log.info("Item %s is already locally installed." % descriptor)

    # create required shotgun fields
    for descriptor in descriptors:
        descriptor.ensure_shotgun_fields_exist()
        # run post install hook
        descriptor.run_post_install()
    
def _get_published_file_entity_type(log, sg):
    """
    Find the published file entity type to use for this project.
    
    Returns 'PublishedFile' if the PublishedFile entity type has
    been enabled, otherwise returns 'TankPublishedFile'
    """
    log.debug("Retrieving schema from Shotgun to determine entity type " 
              "to use for published files")
    
    pf_entity_type = "TankPublishedFile"
    try:
        sg_schema = sg.schema_read()
        if ("PublishedFile" in sg_schema
            and "PublishedFileType" in sg_schema
            and "PublishedFileDependency" in sg_schema):
            pf_entity_type = "PublishedFile"
    except Exception, e:
        raise TankError("Could not retrieve the Shotgun schema: %s" % e)

    log.debug(" > Using %s entity type for published files" % pf_entity_type)

    return pf_entity_type
    
