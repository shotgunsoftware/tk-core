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
from ... import pipelineconfig_factory

from tank_vendor import yaml
    
def run_project_setup(log, sg, sg_app_store, sg_app_store_script_user, setup_params):
    """
    Execute the project setup.
    No validation is happening at this point - ensure that you have run the necessary validation
    methods in the parameters object.

    :param log: python logger object
    :param sg: shotgun api connection to the associated site
    :param sg_app_store: toolkit app store sg connection
    :param sg_app_store_script_user: The script user used to connect to the app store, as a shotgun link-dict
    :param setup_params: Parameters object which holds gathered project settings
    """
    old_umask = os.umask(0)
    try:
        _project_setup_internal(log, sg, sg_app_store, sg_app_store_script_user, setup_params)
    finally:
        os.umask(old_umask)

def _project_setup_internal(log, sg, sg_app_store, sg_app_store_script_user, setup_params):
    """
    Project setup, internal method.

    :param log: python logger object
    :param sg: shotgun api connection to the associated site
    :param sg_app_store: toolkit app store sg connection
    :param sg_app_store_script_user: The script user used to connect to the app store, as a shotgun link-dict
    :param setup_params: Parameters object which holds gathered project settings
    """
    log.info("")
    log.info("Starting project setup.")
    
    # get the location of the configuration
    config_location_curr_os = setup_params.get_configuration_location(sys.platform)
    config_location_mac = setup_params.get_configuration_location("darwin")
    config_location_linux = setup_params.get_configuration_location("linux2")
    config_location_win = setup_params.get_configuration_location("win32")
    
    # project id
    project_id = setup_params.get_project_id()
    if project_id:
        sg_project_link = {"id": project_id, "type": "Project"}
    else:
        sg_project_link = None

    # get all existing pipeline configurations
    setup_params.report_progress_from_installer("Checking Pipeline Configurations...")
    
    pcs = sg.find(constants.PIPELINE_CONFIGURATION_ENTITY, 
                  [["project", "is", sg_project_link]],
                  ["code", "linux_path", "windows_path", "mac_path"])
    
    
    if len(pcs) > 0:
        if setup_params.get_force_setup():
            # if we have the force flag enabled, remove any pipeline configurations
            for x in pcs:
                log.warning("Force mode: Deleting old pipeline configuration %s..." % x["code"])
                sg.delete(constants.PIPELINE_CONFIGURATION_ENTITY, x["id"])

        elif not setup_params.get_auto_path_mode():
            # this is a normal setup, e.g. not with the force flag on 
            # nor an auto-path where each machine effectively manages its own config
            # for this case, we don't allow the process to proceed if a config exists
            raise TankError("Cannot set up this project! Pipeline configuration entries already exist in Shotgun.")
        
        else:
            # auto path mode
            # make sure that all PCs have empty paths set, either None values or ""
            for x in pcs:
                if x["linux_path"] or x["windows_path"] or x["mac_path"]:
                    raise TankError("Cannot set up this project! Non-auto-path style pipeline "
                                    "configuration entries already exist in Shotgun.")
            
    # first do disk structure setup, this is most likely to fail.
    setup_params.report_progress_from_installer("Creating main folder structure...")
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
    _make_folder(log, os.path.join(config_location_curr_os, "install", "core.backup"), 0777, True)
    _make_folder(log, os.path.join(config_location_curr_os, "install", "engines"), 0777, True)
    _make_folder(log, os.path.join(config_location_curr_os, "install", "apps"), 0777, True)
    _make_folder(log, os.path.join(config_location_curr_os, "install", "frameworks"), 0777, True)
        
    # copy the configuration into place
    setup_params.report_progress_from_installer("Setting up template configuration...")
    setup_params.create_configuration(os.path.join(config_location_curr_os, "config"))

    # copy the tank binaries to the top of the config
    setup_params.report_progress_from_installer("Copying binaries and API proxies...")
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
    setup_params.report_progress_from_installer("Writing configuration files...")
    
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

    log.debug("Writing %s..." % constants.STORAGE_ROOTS_FILE)
    roots_path = os.path.join(config_location_curr_os, "config", "core", constants.STORAGE_ROOTS_FILE)
    
    roots_data = {}
    for storage_name in setup_params.get_required_storages():
    
        roots_data[storage_name] = {"windows_path": setup_params.get_storage_path(storage_name, "win32"),
                                    "linux_path": setup_params.get_storage_path(storage_name, "linux2"),
                                    "mac_path": setup_params.get_storage_path(storage_name, "darwin")}
    
    try:
        fh = open(roots_path, "wt")
        yaml.dump(roots_data, fh)
        fh.close()
    except Exception, exp:
        raise TankError("Could not write to roots file %s. "
                        "Error reported: %s" % (roots_path, exp))
    
    # now ensure there is a tank folder in every storage
    setup_params.report_progress_from_installer("Setting up project storage folders...")
    for storage_name in setup_params.get_required_storages():
        
        log.info("Setting up %s storage..." % storage_name )
        
        # get the project path for this storage
        current_os_path = setup_params.get_project_path(storage_name, sys.platform)
        log.debug("Project path: %s" % current_os_path )
                        
    
    # Create Project.tank_name and PipelineConfiguration records in Shotgun
    #
    # This logic has some special complexity when the auto_path mode is in use.
    
    setup_params.report_progress_from_installer("Registering in Shotgun...")
    
    if setup_params.get_auto_path_mode():
        # first, check the project name. If there is no project name in Shotgun, populate it
        # with the project name which is specified via the project name parameter.
        # if there isn't yet an entry, create it.
        # This is consistent with the anticipated future behaviour we expect when we 
        # switch from auto_path to a zip file based approach. 

        project_name = setup_params.get_project_disk_name()

        # Site configs are not associated to a project, so no need to look for tank_name on a project
        # that doesn't exist.
        if project_id is not None:
            data = sg.find_one("Project", [["id", "is", project_id]], ["tank_name"])
            if data["tank_name"] is None:
                log.info("Registering project in Shotgun...")
                log.debug("Shotgun: Setting Project.tank_name to %s" % project_name)
                sg.update("Project", project_id, {"tank_name": project_name})

            else:
                # there is already a name. Check that it matches the name in the project params
                # if not, then use the existing name and issue a warning!
                if data["tank_name"] != project_name:
                    log.warning("You have supplied the project disk name '%s' as part of the project setup "
                                "parameters, however the name '%s' has already been registered in Shotgun for "
                                "this project. This name will be used instead of the suggested disk "
                                "name." % (project_name, data["tank_name"]) )
                    project_name = data["tank_name"]

        log.info("Creating Pipeline Configuration in Shotgun...")
        # this is an auto-path project, meaning that shotgun doesn't store the location
        # to the pipeline configuration. Because an auto-path location is often set up 
        # on multiple machines, check first if the entry exists and in that case skip creation
        data = sg.find_one(constants.PIPELINE_CONFIGURATION_ENTITY,
                           [["code", "is", constants.PRIMARY_PIPELINE_CONFIG_NAME],
                            ["project", "is", sg_project_link]],
                           ["id"])
        
        if data is None:
            log.info("Creating Pipeline Configuration in Shotgun...")
            data = {"project": sg_project_link, "code": constants.PRIMARY_PIPELINE_CONFIG_NAME}
            pc_entity = sg.create(constants.PIPELINE_CONFIGURATION_ENTITY, data)
            pipeline_config_id = pc_entity["id"]
            log.debug("Created data: %s" % pc_entity)
        else:
            pipeline_config_id = data["id"]
        
    else:
        # normal mode.
        if project_id:
            log.info("Registering project in Shotgun...")
            project_name = setup_params.get_project_disk_name()
            log.debug("Shotgun: Setting Project.tank_name to %s" % project_name)
            sg.update("Project", project_id, {"tank_name": project_name})
        
        log.info("Creating Pipeline Configuration in Shotgun...")
        data = {"project": sg_project_link,
                "linux_path": config_location_linux,
                "windows_path": config_location_win,
                "mac_path": config_location_mac,
                "code": constants.PRIMARY_PIPELINE_CONFIG_NAME}
    
        # create pipeline configuration record
        pc_entity = sg.create(constants.PIPELINE_CONFIGURATION_ENTITY, data)
        pipeline_config_id = pc_entity["id"] 
        log.debug("Created data: %s" % pc_entity)
    
    # write the record to disk
    pipe_config_sg_id_path = os.path.join(config_location_curr_os, "config", "core", "pipeline_configuration.yml")
    log.debug("Writing to pc cache file %s" % pipe_config_sg_id_path)
    
    # determine the entity type to use for Published Files:
    pf_entity_type = _get_published_file_entity_type(log, sg)
    
    data = {}
    data["project_name"] = project_name
    data["pc_id"] = pipeline_config_id
    data["project_id"] = project_id
    data["pc_name"] = constants.PRIMARY_PIPELINE_CONFIG_NAME 
    data["published_file_entity_type"] = pf_entity_type
    
    # all 0.15+ projects are pushing folders to Shotgun by default
    data["use_shotgun_path_cache"] = True 
    
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
    pc = pipelineconfig_factory.from_path(config_location_curr_os)
    
    # each entry in the config template contains instructions about which version of the app
    # to use. First loop over all environments and gather all descriptors we should download,
    # then go ahead and download and post-install them 
    
    log.info("Downloading and installing apps...")
    
    # pass 1 - populate list of all descriptors    
    descriptors = []
    for env_name in pc.get_environments():
        
        env_obj = pc.get_environment(env_name)
        
        for engine in env_obj.get_engines():
            descriptors.append( env_obj.get_engine_descriptor(engine) )
            
            for app in env_obj.get_apps(engine):
                descriptors.append( env_obj.get_app_descriptor(engine, app) )
                
        for framework in env_obj.get_frameworks():
            descriptors.append( env_obj.get_framework_descriptor(framework) )
                
    # pass 2 - download all apps
    num_descriptors = len(descriptors)
    for idx, descriptor in enumerate(descriptors):
        
        # note that we push percentages here to the progress bar callback
        # going from 0 to 100
        progress = (int)((float)(idx)/(float)(num_descriptors)*100)
        setup_params.report_progress_from_installer("Downloading apps...", progress)
        
        if not descriptor.exists_local():
            log.info("Downloading %s to the local Toolkit install location..." % descriptor)            
            descriptor.download_local()
            
        else:
            log.info("Item %s is already locally installed." % descriptor)

    # create required shotgun fields
    setup_params.report_progress_from_installer("Running post install...")
    for descriptor in descriptors:
        descriptor.ensure_shotgun_fields_exist()
        # run post install hook
        descriptor.run_post_install()
        

    ##########################################################################################
    # post processing of the install
    
    # run after project create script if it exists
    setup_params.report_progress_from_installer("Running post-setup scripts...")
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
        
    
def _get_published_file_entity_type(log, sg):
    """
    Find the published file entity type to use for this project.
    Communicates with Shotgun, introspects the sg schema.
    
    :returns: 'PublishedFile' if the PublishedFile entity type has
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
    
