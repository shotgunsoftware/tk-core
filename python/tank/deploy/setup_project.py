"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Utils and logic for creating new tank projects
"""

# tank app store constants
TANK_APP_STORE_DUMMY_PROJECT = {"type": "Project", "id": 64} 
TANK_CONFIG_ENTITY = "CustomNonProjectEntity07"
TANK_CONFIG_VERSION_ENTITY = "CustomNonProjectEntity08"
TANK_CODE_PAYLOAD_FIELD = "sg_payload"
PIPELINE_CONFIGURATION_ENTITY = "CustomNonProjectEntity02"
PIPELINE_CONFIGURATION_ENTITY_PROJ_LINK = "sg_project"
DEFAULT_CFG = "tk-config-default"

SG_LOCAL_STORAGE_OS_MAP = {"linux2": "linux_path", "win32": "windows_path", "darwin": "mac_path" }

import re
import sys
import os
import shutil
import tempfile
import uuid
from ..errors import TankError
from ..platform import environment
from ..util import shotgun
from ..platform import constants
from . import util as deploy_util
from . import console_utils

from .zipfilehelper import unzip_file

from tank_vendor import yaml


########################################################################################
# User Interaction

class CmdlineSetupInteraction(object):
    
    def __init__(self, log, sg):
        self._log = log
        self._sg = sg
            
    def confirm_continue(self):
        """
        Yes no confirm to continue
        """
        val = raw_input("Continue with project setup (Yes/No)? [Yes]: ")
        if val == "" or val.lower().startswith("y"):
            return True
        elif val.lower().startswith("n"):
            return False
        else:
            raise TankError("Please answer Yes, y, no, n or press ENTER!")
        
    
    def get_disk_location(self, hinted_default):
        """
        Ask the user where the pipeline configuration should be located on disk.
        Returns a dictionary with keys according to sys.platform: win32, darwin, linux2
        """
        os_nice_name = {"darwin": "Macosx", "linux2": "Linux", "win32": "Windows"}
        curr_os = sys.platform
        
        self._log.info("")
        self._log.info("")
        self._log.info("Where on disk would you like this tank configuration to be located?")
        self._log.info("You can press ENTER to accept the default value or to skip.")
        self._log.info("If you skip, this configuration will not be available on that platform.")
        
        # start by asking for the current platform, the the other two platforms
        location = {"darwin": None, "linux2": None, "win32": None}
        
        # set default values
        if curr_os in ["darwin", "linux2"]:
            location["darwin"] = hinted_default
            location["linux2"] = hinted_default
        elif curr_os == "win32":
            location["win32"] = hinted_default
        
        # first ask about current platform
        val = raw_input("%s [%s]: " % (os_nice_name[curr_os], location[curr_os]))
        if val == "":
            val = location[curr_os]
        location[curr_os] = val
        
        # do other platforms
        for x in [k for k in location.keys() if k != curr_os]:
            curr_val = location[x]
            if curr_val is None:
                val = raw_input("%s : " % os_nice_name[x])
            else:
                val = raw_input("%s [%s]: " % (os_nice_name[x], location[x]))
                        
            if val == "":
                self._log.info("Skipping. This Pipeline configuration will not support %s." % os_nice_name[x])
            else:
                location[x] = val

        return location

        
    def get_config(self):
        """
        Ask the user which config to use. Returns a config string.
        """
        self._log.info("")
        self._log.info("")
        self._log.info("Which configuration would you like to associate with this project?")
        self._log.info("You can either type in a name of a config in the Tank Store")
        self._log.info("or specify a path to a config on disk. Hit enter to use the ")
        self._log.info("standard Tank Starter configuration.")
        config_name = raw_input("[%s]: " % DEFAULT_CFG)
        if config_name == "":
            config_name = DEFAULT_CFG
        return config_name
        
    def get_project_folder_name(self, suggested_folder_name):
        """
        Returns a project name given a project folder
        """
        self._log.info("")
        self._log.info("")
        self._log.info("Now you need to decide folder name on disk for your project.")
        self._log.info("This will be used as the root folder for all project related data.")
        self._log.info("Please enter a folder name of hit ENTER to accept the suggested value.")
        config_name = raw_input("[%s]: " % suggested_folder_name)
        if config_name == "":
            config_name = suggested_folder_name
        return config_name


        
    def get_project(self):
        """
        Returns the project id and name for a project for which setup should be done.
        Will request the user to input console input to select project.
        """
    
        filters = [["name", "is_not", "Template Project"], 
                   ["sg_status", "is_not", "Archive"],
                   ["sg_status", "is_not", "Lost"],
                   ["tank_name", "is", None]]
         
        projs = self._sg.find("Project", filters, ["id", "name", "sg_description"])
    
        if len(projs) == 0:
            raise TankError("Sorry, not projects found! All projects seem to have already been "
                            "set up with Tank.")
            
        self._log.info("")
        self._log.info("")
        self._log.info("Below are all projects that have not yet been set up with Tank:")
        self._log.info("------------------------------------------------------------------")
        self._log.info("")
        
        for x in projs:
            # helper that formats a single project
            desc = x.get("sg_description")
            if desc is None:
                desc = "[No description]"
            
            # chop a long description
            if len(desc) > 50:
                desc = "%s..." % desc[:50]
            
            self._log.info("[%2d] %s" % (x.get("id"), x.get("name")))
            self._log.info("     %s" % desc)
            self._log.info("")
            
        self._log.info("")
        answer = raw_input("Please type in the id of the project to connect to or ENTER to exit: " )
        if answer == "":
            raise TankError("Aborted by user.")
        try:
            project_id = int(answer)
        except:
            raise TankError("Please enter a number!")
        
        if project_id not in [ x["id"] for x in projs]:
            raise TankError("Id %d was not found in the list of projects!" % project_id)
        
        # get the project name
        project_name = None
        for p in projs:
            if p.get("id") == project_id:
                project_name = p.get("name")
                break
                            
        return (project_id, project_name)
    
    
###############################################################################################
# config processing    

class TankConfigInstaller(object):
    """
    Functionality for handling installation and validation of tank configs
    """
    
    def __init__(self, config_name, sg, sg_app_store, script_user, log):
        self._sg = sg
        self._sg_app_store = sg_app_store
        self._script_user = script_user
        self._log = log
        # now extract the cfg and validate        
        self._cfg_folder = self._process_config(config_name)
        self._roots_data = self._read_roots_file()


    def _read_roots_file(self):
        """
        Read, validate and return the roots data from the config
        """
        # get the roots definition
        root_file_path = os.path.join(self._cfg_folder, "core", "roots.yml")
        if os.path.exists(root_file_path):
            root_file = open(root_file_path, "r")
            try:
                roots_data = yaml.load(root_file)
            finally:
                root_file.close()
            
            # validate it
            for x in roots_data:
                if "mac_path" not in roots_data[x]:
                    roots_data[x]["mac_path"] = None
                if "linux_path" not in roots_data[x]:
                    roots_data[x]["linux_path"] = None
                if "windows_path" not in roots_data[x]:
                    roots_data[x]["windows_path"] = None
            
        else: 
            # set up default roots data
            roots_data = { "primary": 
                            { "description": "A location where the primary data is located.",
                              "mac_path": "/studio/projects", 
                              "linux_path": "/studio/projects", 
                              "windows_path": "\\\\network\\projects"
                            },                          
                          }
            
        return roots_data
        
    
    def _process_config_zip(self, zip_path):
        """
        unpacks a zip config into a temp location
        """
        # unzip into temp location
        self._log.debug("Unzipping configuration and inspecting it...")
        zip_unpack_tmp = os.path.join(tempfile.gettempdir(), uuid.uuid4().hex)
        unzip_file(zip_path, zip_unpack_tmp)
        template_items = os.listdir(zip_unpack_tmp)
        for item in ["core", "env", "hooks"]:
            if item not in template_items:
                raise TankError("Config zip '%s' is missing a %s folder!" % (zip_path, item))
        self._log.debug("Configuration looks valid!")
        
        return zip_unpack_tmp
    
    def _process_config_app_store(self, config_name):
        """
        Downloads a config zip from the app store and unzips it
        """
        
        # try download from app store...
        parent_entity = self._sg_app_store.find_one(TANK_CONFIG_ENTITY, 
                                              [["sg_system_name", "is", config_name ]],
                                              ["code"]) 
        if parent_entity is None:
            raise Exception("Cannot find a config in the app store named %s!" % config_name)
        
        # get latest code
        latest_cfg = self._sg_app_store.find_one(TANK_CONFIG_VERSION_ENTITY, 
                                           filters = [["sg_tank_config", "is", parent_entity],
                                                      ["sg_status_list", "is_not", "rev" ],
                                                      ["sg_status_list", "is_not", "bad" ]], 
                                           fields=["code", TANK_CODE_PAYLOAD_FIELD],
                                           order=[{"field_name": "created_at", "direction": "desc"}])
        if latest_cfg is None:
            raise Exception("It looks like this configuration doesn't have any versions uploaded yet!")
        
        # now have to get the attachment id from the data we obtained. This is a bit hacky.
        # data example for the payload field, as returned by the query above:
        # {'url': 'http://tank.shotgunstudio.com/file_serve/attachment/21', 'name': 'tank_core.zip',
        #  'content_type': 'application/zip', 'link_type': 'upload'}
        #
        # grab the attachment id off the url field and pass that to the download_attachment()
        # method below.
        try:
            attachment_id = int(latest_cfg[TANK_CODE_PAYLOAD_FIELD]["url"].split("/")[-1])
        except:
            raise TankError("Could not extract attachment id from data %s" % latest_cfg)
    
        self._log.info("Downloading Config %s %s from the Tank Store..." % (config_name, latest_cfg["code"]))
        
        zip_tmp = os.path.join(tempfile.gettempdir(), "%s_tank_cfg.zip" % uuid.uuid4().hex)
    
        bundle_content = self._sg_app_store.download_attachment(attachment_id)
        fh = open(zip_tmp, "wb")
        fh.write(bundle_content)
        fh.close()
    
        # and write a custom event to the shotgun event log to indicate that a download
        # has happened.
        data = {}
        data["description"] = "Config %s %s was downloaded" % (config_name, latest_cfg["code"])
        data["event_type"] = "TankAppStore_Config_Download"
        data["entity"] = latest_cfg
        data["user"] = self._script_user
        data["project"] = TANK_APP_STORE_DUMMY_PROJECT
        data["attribute_name"] = TANK_CODE_PAYLOAD_FIELD
        self._sg_app_store.create("EventLogEntry", data)
    
        # got a zip! Pass to zip extractor...
        return self._process_config_zip(zip_tmp)
    
    def _process_config_dir(self, dir_path):
        """
        Validates that the directory contains a tank config
        """
        template_items = os.listdir(dir_path)
        for item in ["core", "env", "hooks"]:
            if item not in template_items:
                raise TankError("Config location '%s' missing a %s folder!" % (dir_path, item))
        self._log.debug("Configuration looks valid!")
        return dir_path
        
    def _process_config(self, cfg_string):
        """
        Looks at the starter config string and tries to convert it into a folder
        Returns a path to a config.
        """
        # three cases:
        # tk-config-xyz
        # /path/to/file.zip
        # /path/to/folder
        if os.path.sep in cfg_string:
            # probably a file path!
            if os.path.exists(cfg_string):
                # either a folder or zip file!
                if cfg_string.endswith(".zip"):
                    return self._process_config_zip(cfg_string)
                else:
                    return self._process_config_dir(cfg_string)
            else:
                raise TankError("File path %s does not exist on disk!" % cfg_string)    
        
        elif cfg_string.startswith("tk-"):
            # app store!
            return self._process_config_app_store(cfg_string)
        
        else:
            raise TankError("Don't know how to handle config '%s'" % cfg_string)
    
    
    def validate_roots(self):
        """
        Validate that the roots exist in shotgun. 
        Returns the root paths from shotgun for each storage.
        """
        #
        sg_storage = self._sg.find("LocalStorage", [],
                                    fields=["code", "linux_path", "mac_path", "windows_path"])

        storages = []

        # make sure that there is a storage in shotgun matching all storages for this config
        sg_storage_codes = [x.get("code") for x in sg_storage]
        cfg_storages = self._roots_data.keys()
        missing_storage_defs = False
        for s in cfg_storages:
            if s not in sg_storage_codes:
                missing_storage_defs = True
                self._log.error("")
                self._log.error("Missing Local File Storage in Shotgun!")
                self._log.error("The Tank configuration is referring to a storage location")
                self._log.error("named '%s'. However, no such storage has been defined " % s)
                self._log.error("in Shotgun. Each Tank configuration defines one or more")
                self._log.error("data roots, to which files are written - all of these roots ")
                self._log.error("need to be defined in Shotgun as Local File Storages.")
                self._log.error("In order to fix this, go to your Shotgun, go into the ")
                self._log.error("site preferences and set up local file storage named ")
                self._log.error("'%s'. Note that you shouldn't include the project name" % s)
                self._log.error("when you set up this storage.")
            else:
                # find the sg storage paths and add to return data
                for x in sg_storage:
                    if x.get("code") == s:
                        storages.append(x) 

        if missing_storage_defs:
            raise TankError("Looks like there are some missing Local File Storages in Shotgun. "
                            "Please create those and re-run the tank project setup.")
        
        return storages

    def get_path(self):
        """
        Returns a path to a location on disk where this config resides
        """
        return self._cfg_folder

    def check_manifest(self, sg_version_str):
        """
        Looks for an info.yml manifest in the config and validates it
        """
        
        self._log.info("")
        
        info_yml = os.path.join(self._cfg_folder, constants.BUNDLE_METADATA_FILE)
        if not os.path.exists(info_yml):
            self._log.warning("Could not find manifest file %s. Project setup will proceed without validation." % info_yml)
            return
    
        try:
            file_data = open(info_yml)
            try:
                metadata = yaml.load(file_data)
            finally:
                file_data.close()
        except Exception, exp:
            raise TankError("Cannot load configuration manifest '%s'. Error: %s" % (info_yml, exp))
    
        # display name
        if "display_name" in metadata:
            self._log.info("This is the '%s' config." % metadata["display_name"])
    
        # perform checks
        if "requires_shotgun_version" in metadata:
            # there is a sg min version required - make sure we have that!
            
            required_version = metadata["requires_shotgun_version"]
    
            if deploy_util.is_version_newer(required_version, sg_version_str):
                raise TankError("This configuration requires Shotgun version %s "
                                "but you are running version %s" % (required_version, sg_version_str))
            else:
                self._log.debug("Config requires shotgun %s. You are running %s which is fine." % (required_version, sg_version_str))
                    
        if "requires_core_version" in metadata:
            # there is a core min version required - make sure we have that!
            
            required_version = metadata["requires_core_version"]
            
            # now figure out the current version of the core api
            curr_core_version = constants.get_core_api_version()
    
            if deploy_util.is_version_newer(required_version, curr_core_version):        
                raise TankError("This configuration requires Tank Core version %s "
                                "but you are running version %s" % (required_version, curr_core_version))
            else:
                self._log.debug("Config requires Tank Core %s. You are running %s which is fine." % (required_version, curr_core_version))






########################################################################################
# helper methods


def _copy_folder(src, dst): 
    """
    Alternative implementation to shutil.copytree
    Copies recursively with very open permissions.
    Creates folders if they don't already exist.
    """
    
    if not os.path.exists(dst):
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
                _copy_folder(srcname, dstname)             
            else: 
                shutil.copy(srcname, dstname) 
        
        except (IOError, os.error), why: 
            raise TankError("Can't copy %s to %s: %s" % (srcname, dstname, str(why))) 
    
def _install_environment(env_cfg, log):
    """
    Make sure that all apps and engines exist in the local repo.
    """
    
    # get a wrapper object for the config
    ed = environment.Environment(env_cfg)
    
    # populate a list of descriptors
    descriptors = []
    
    for engine in ed.get_engines():
        descriptors.append( ed.get_engine_descriptor(engine) )
        
        for app in ed.get_apps(engine):
            descriptors.append( ed.get_app_descriptor(engine, app) )
            
    for framework in ed.get_frameworks():
        descriptors.append( ed.get_framework_descriptor(framework) )
            
    # ensure all apps are local - if not then download them
    for descriptor in descriptors:
        if not descriptor.exists_local():
            log.info("Downloading %s to the local Tank install location..." % descriptor)            
            descriptor.download_local()
            
        else:
            log.info("Item %s is already locally installed." % descriptor)

    # create required shotgun fields
    for descriptor in descriptors:
        descriptor.ensure_shotgun_fields_exist()
    
    



########################################################################################
# main methods and entry points

def interactive_setup(log, pipeline_config_root):
    old_umask = os.umask(0)
    try:
        return _interactive_setup(log, pipeline_config_root)
    finally:
        os.umask(old_umask)
    
def _interactive_setup(log, pipeline_config_root):
    """
    interactive setup which will ask questions via the console.
    """
    log.info("")
    log.info("Welcome to the Tank Project Setup!")
    log.info("")
        
    # now connect to shotgun
    try:
        log.info("Connecting to Shotgun...")
        sg = shotgun.create_sg_connection()        
        sg_version = ".".join([ str(x) for x in sg.server_info["version"]])
        log.debug("Connected to target Shotgun server! (v%s)" % sg_version)
    except Exception, e:
        raise TankError("Could not connect to Shotgun server: %s" % e)
    
    try:
        log.info("Connecting to the Tank App Store...")
        (sg_app_store, script_user) = shotgun.create_sg_app_store_connection()
        sg_version = ".".join([ str(x) for x in sg_app_store.server_info["version"]])
        log.debug("Connected to Tank App Store! (v%s)" % sg_version)
    except Exception, e:
        raise TankError("Could not connect to App Store: %s" % e)
    
    ###############################################################################################
    # Stage 1 - information gathering
    
    cmdline_ui = CmdlineSetupInteraction(log, sg)
    
    # ask which project to operate on
    (project_id, project_name) = cmdline_ui.get_project()
    
    # construct a valid name - replace white space with underscore and lower case it.
    project_disk_folder = re.sub("\W", "_", project_name).lower()
    
    # ask the user to confirm the folder name
    project_disk_folder = cmdline_ui.get_project_folder_name(project_disk_folder)
    
    # validate that this is not crazy
    if re.match("^[a-zA-Z0-9_-]+$", project_disk_folder) is None:
        # bad name
        raise TankError("Invalid project folder '%s'! Please stick to alphanumerics, "
                        "underscores and dashes." % project_disk_folder)
    
    # now ask which config to use. Download if necessary and examine
    config_name = cmdline_ui.get_config()

    # now try to load the config
    cfg_installer = TankConfigInstaller(config_name, sg, sg_app_store, script_user, log)
    
    # validate the config against the shotgun where we are installing it 
    cfg_installer.check_manifest(sg_version)
    
    # now look at the roots yml in the config
    resolved_storages = cfg_installer.validate_roots()

    # create pipeline configuration record - ask for paths
    # disk friendly name for project by replacing white space by underscore    
    suggested_path = os.path.abspath( os.path.join(pipeline_config_root, "..", project_disk_folder) )
    locations_dict = cmdline_ui.get_disk_location(suggested_path)

    ##################################################################
    # validate the local storages
    #
    
    for s in resolved_storages:
        current_os_path = s.get( SG_LOCAL_STORAGE_OS_MAP[sys.platform] )
        
        if current_os_path is None:
            raise TankError("The Storage %s does not have a path defined for the current os. "
                            "Please set a path and try again!" % s.get("code"))
        
        project_path = os.path.join(current_os_path, project_disk_folder)
        if not os.path.exists(project_path):
            raise TankError("The Project path %s for storage %s does not exist on disk! "
                            "Please create it and try again!" % (project_path, s.get("code")))
    
        tank_folder = os.path.join(project_path, "tank")
        if os.path.exists(tank_folder):
            # tank folder exists - make sure it is writable
            if not os.access(tank_folder, os.W_OK|os.R_OK|os.X_OK):
                raise TankError("The permissions setting for '%s' is too strict. The current user "
                                "cannot create files or folders in this location." % tank_folder)
        else:
            # not tank folder has been created in this storage
            # make sure we can create it
            if not os.access(project_path, os.W_OK|os.R_OK|os.X_OK):
                raise TankError("The permissions setting for '%s' is too strict. The current user "
                                "cannot create a tank folder in this location." % project_path)
            

    
    
    ##################################################################
    # validate the install location
    #
    current_os_pc_location = locations_dict[sys.platform]
    
    if os.path.exists(current_os_pc_location):
        # pc location already exists - make sure it doesn't already contain
        # an install
        if os.path.exists(os.path.join(current_os_pc_location, "install")) or \
           os.path.exists(os.path.join(current_os_pc_location, "config")):
            raise TankError("Looks like the location '%s' already contains a "
                            "tank config!" % current_os_pc_location)
        # also make sure it has right permissions
        if not os.access(current_os_pc_location, os.W_OK|os.R_OK|os.X_OK):
            raise TankError("The permissions setting for '%s' is too strict. The current user "
                            "cannot create files or folders in this location." % current_os_pc_location)
        
    else:
        # path does not exist! 
        # make sure parent exists and is writable
    
        parent_os_pc_location = os.path.dirname(current_os_pc_location)
        if not os.path.exists(parent_os_pc_location):
            raise TankError("The folder '%s' does not exist! Please create "
                            "it before proceeding!" % parent_os_pc_location)
    
        # and make sure we can create a folder in it
        if not os.access(parent_os_pc_location, os.W_OK|os.R_OK|os.X_OK):
            raise TankError("The permissions setting for '%s' is too strict. The current user "
                            "cannot create folders in this location." % parent_os_pc_location)
    
    
    ###############################################################################################
    # Stage 2 - summary and confirmation
    
    log.info("")
    log.info("")
    log.info("Project Creation Summary:")
    log.info("-------------------------")
    log.info("")
    log.info("You are about to set up Tank for Project %s - %s " % (project_id, project_name))
    log.info("The following items will be created:")
    log.info("")
    log.info("* A Tank Pipeline configuration will be created:" )
    log.info("  - on Macosx:  %s" % locations_dict["darwin"])
    log.info("  - on Linux:   %s" % locations_dict["linux2"])
    log.info("  - on Windows: %s" % locations_dict["win32"])
    log.info("")

    for x in resolved_storages:

        log.info("* Tank will connect to the project folder in Storage '%s':" % x["code"] )
        
        if x["mac_path"] is None:
            log.info("  - on Macosx: No path defined")
        else:
            # not using path.join because it only works with current platform
            path_str = "%s/%s" % (x["mac_path"], project_disk_folder)
            log.info("  - on Macosx: %s" % path_str)
            
        if x["linux_path"] is None:
            log.info("  - on Linux:  No path defined")
        else:
            # not using path.join because it only works with current platform
            path_str = "%s/%s" % (x["linux_path"], project_disk_folder)
            log.info("  - on Linux:  %s" % path_str)

        if x["windows_path"] is None:
            log.info("  - on Windows: No path defined")
        else:
            # not using path.join because it only works with current platform
            path_str = "%s\\%s" % (x["windows_path"], project_disk_folder)
            log.info("  - on Windows: %s" % path_str)

    log.info("")
    log.info("")
    
    if not cmdline_ui.confirm_continue():
        raise TankError("Installation Aborted.")    
    
    ###############################################################################################
    # Stage 3 - execution
    
    log.info("")
    log.info("Starting project setup.")
    
    # first do disk structure setup, this is most likely to fail.
    current_os_pc_location = locations_dict[sys.platform]    
    log.info("Installing configuration into '%s'..." % current_os_pc_location )
    if not os.path.exists(current_os_pc_location):
        # note that we have already validated that creation is possible
        os.mkdir(current_os_pc_location, 0775)
    
    # create pipeline config base folder structure            
    os.mkdir(os.path.join(current_os_pc_location, "cache"), 0775)    
    os.mkdir(os.path.join(current_os_pc_location, "config"), 0775)
    os.mkdir(os.path.join(current_os_pc_location, "install"), 0775)
    os.mkdir(os.path.join(current_os_pc_location, "install", "core"), 0777)
    os.mkdir(os.path.join(current_os_pc_location, "install", "core", "python"), 0777)
    os.mkdir(os.path.join(current_os_pc_location, "install", "core.backup"), 0777)
    os.mkdir(os.path.join(current_os_pc_location, "install", "engines"), 0777)
    os.mkdir(os.path.join(current_os_pc_location, "install", "apps"), 0777)
    os.mkdir(os.path.join(current_os_pc_location, "install", "frameworks"), 0777)
    
    # copy the configuration into place
    _copy_folder(cfg_installer.get_path(), os.path.join(current_os_pc_location, "config"))
    
    # copy the tank binaries to the top of the config
    core_api_root = os.path.abspath(os.path.join( os.path.dirname(__file__), "..", "..", ".."))
    root_binaries_folder = os.path.join(core_api_root, "setup", "root_binaries")
    if not os.path.exists(root_binaries_folder):
        raise Exception("Looks like you are using an old version of Tank! "
                        "Please contact tanksupport@shotgunsoftware.com.")
    for file_name in os.listdir(root_binaries_folder):
        src_file = os.path.join(root_binaries_folder, file_name)
        tgt_file = os.path.join(current_os_pc_location, file_name)
        shutil.copy(src_file, tgt_file)
        os.chmod(tgt_file, 0775)
    
    # copy the python stubs
    tank_proxy = os.path.join(core_api_root, "setup", "tank_api_proxy")
    _copy_folder(tank_proxy, os.path.join(current_os_pc_location, "install", "core", "python"))
    
    # now ensure there is a tank folder in every storage
    for s in resolved_storages:
        log.info("Setting up %s storage..." % s.get("code") )
        current_os_path = s.get( SG_LOCAL_STORAGE_OS_MAP[sys.platform] )
        tank_path = os.path.join(current_os_path, project_disk_folder, "tank")
        if not os.path.exists(tank_path):
            os.mkdir(tank_path, 0777)
    
    # create path cache db
    # create file for configuration backlinks
    # add our confg to that file
    
    
    raise Exception("fo")
    
    # creating project.tank_name record
    log.debug("Shotgun: Setting Project.tank_name to %s" % project_disk_folder)
    sg.update("Project", project_id, {"tank_name": project_disk_folder})
    
    # create pipeline configuration record
    
    
        
    
    
    
    
    
    # and write a custom event to the shotgun event log
    data = {}
    data["description"] = "%s: A Tank Project named %s was created" % (sg.base_url, project_disk_folder)
    data["event_type"] = "TankAppStore_Project_Created"
    data["user"] = script_user
    data["project"] = TANK_APP_STORE_DUMMY_PROJECT
    data["attribute_name"] = project_disk_folder
    sg_app_store.create("EventLogEntry", data)
    
    
    ##########################################################################################
    # install apps
    
    # each entry in the config template contains instructions about which version of the app
    # to use.
    
    for env in constants.get_environments_for_proj(proj_root):
        log.info("Installing apps for environment %s..." % env)
        _install_environment(proj_root, env, log)

    ##########################################################################################
    # post processing of the install
    
    # run after project create script if it exists
    after_script_path = os.path.join(tank_folder, "config", "after_project_create.py")
    if os.path.exists(after_script_path):
        log.info("Found a tank post-install script %s" % after_script_path)
        log.info("Executing post-install commands...")
        sys.path.insert(0, os.path.dirname(after_script_path))
        import after_project_create
        after_project_create.create(sg=sg, project_id=project_id, log=log)
        sys.path.pop(0)
        log.info("Post install phase complete!")

    log.info("")
    log.info("Tank Project Creation Complete.")
    log.info("")

    # show the readme file if it exists
    readme_file = os.path.join(starter_config, "README")
    if os.path.exists(readme_file):
        log.info("")
        log.info("README file for template:")
        fh = open(readme_file)
        for line in fh:
            print line.strip()
        fh.close()
    
    log.info("")
    log.info("We now recommend that you run the update script to ensure that all")
    log.info("the Apps and Engines that came with the config are up to date! ")
    log.info("You can do this by executing the check_for_updates script ")
    log.info("that is located in this folder.")
    log.info("")
    log.info("For more Apps, Support, Documentation and the Tank Community, go to")
    log.info("https://tank.shotgunsoftware.com")
    log.info("")        
    log.info("Tank Project Script exiting.")

    
    