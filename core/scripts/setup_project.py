"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Creates a new Project in Tank based on a starter configuration template

"""

########################################################################################
# imports

import optparse
import os
import tempfile
import logging
import sys
import uuid
import re
import shutil
import datetime
import pprint
import platform

# make sure that the core API is part of the pythonpath
python_path = os.path.abspath(os.path.join( os.path.dirname(__file__), "..", "python"))
sys.path.append(python_path)

from tank.util import shotgun
from tank.deploy import descriptor
from tank.platform import constants 
from tank.errors import TankError
from tank.platform import environment
from tank.errors import TankError

from tank.deploy.zipfilehelper import unzip_file

TANK_APP_STORE_DUMMY_PROJECT = {"type": "Project", "id": 64} 

TANK_CONFIG_ENTITY = "CustomNonProjectEntity07"
TANK_CONFIG_VERSION_ENTITY = "CustomNonProjectEntity08"
TANK_CODE_PAYLOAD_FIELD = "sg_payload"


########################################################################################
# helpers


def _validate_proj_disk_name(name):
    """
    Ensure that the project name is valid.
    Returns true if valid, false if not.
    """
    return (re.match("^[a-zA-Z0-9_-]+$", name) != None)

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
    
def _install_environment(proj_root, env_cfg, log):
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
            
    # ensure all apps are local - if not then download them
    for descriptor in descriptors:
        if not descriptor.exists_local():
            log.info("Downloading %s to the local Tank install location..." % descriptor)            
            descriptor.download_local()
            
        else:
            log.info("Item %s is already locally installed." % descriptor)

    # create required shotgun fields
    for descriptor in descriptors:
        descriptor.ensure_shotgun_fields_exist(proj_root)
    
def _process_config_project(studio_root, project_name, log):
    
    dir_path = os.path.join(studio_root, project_name, "tank", "config")

    log.info("Using the configuration from project %s" % project_name)
    log.info("Looking for a configuration in %s" % dir_path)
    
    if not os.path.exists(dir_path):
        raise TankError("Config location '%s' does not exist!" % dir_path)

    template_items = os.listdir(dir_path)
    for item in ["core", "env", "hooks"]:
        if item not in template_items:
            raise TankError("Config location '%s' missing a %s folder!" % (dir_path, item))
    
    log.info("Configuration looks valid!")
    
    return dir_path

def _process_config_zip(studio_root, zip_path, log):
    
    # unzip into temp location
    log.info("Unzipping configuration and inspecting it...")
    zip_unpack_tmp = os.path.join(tempfile.gettempdir(), uuid.uuid4().hex)
    unzip_file(zip_path, zip_unpack_tmp)
    template_items = os.listdir(zip_unpack_tmp)
    for item in ["core", "env", "hooks"]:
        if item not in template_items:
            raise TankError("Config zip '%s' is missing a %s folder!" % (zip_path, item))
    
    log.info("Configuration looks valid!")
    
    return zip_unpack_tmp

def _process_config_app_store(sg_app_store, script_user, studio_root, cfg_string, log):
    
    # try download from app store...
    parent_entity = sg_app_store.find_one(TANK_CONFIG_ENTITY, 
                                          [["sg_system_name", "is", cfg_string ]],
                                          ["code"]) 
    if parent_entity is None:
        raise Exception("Cannot find a config in the app store named %s!" % cfg_string)
    
    # get latest code
    latest_cfg = sg_app_store.find_one(TANK_CONFIG_VERSION_ENTITY, 
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

    log.info("Begin downloading Config %s %s from the Tank App Store..." % (cfg_string, latest_cfg["code"]))
    
    zip_tmp = os.path.join(tempfile.gettempdir(), "%s_tank_cfg.zip" % uuid.uuid4().hex)

    bundle_content = sg_app_store.download_attachment(attachment_id)
    fh = open(zip_tmp, "wb")
    fh.write(bundle_content)
    fh.close()

    # and write a custom event to the shotgun event log to indicate that a download
    # has happened.
    data = {}
    data["description"] = "Config %s %s was downloaded" % (cfg_string, latest_cfg["code"])
    data["event_type"] = "TankAppStore_Config_Download"
    data["entity"] = latest_cfg
    data["user"] = script_user
    data["project"] = TANK_APP_STORE_DUMMY_PROJECT
    data["attribute_name"] = TANK_CODE_PAYLOAD_FIELD
    sg_app_store.create("EventLogEntry", data)

    # got a zip! Pass to zip extractor...
    return _process_config_zip(studio_root, zip_tmp, log)


def _process_config_dir(studio_root, dir_path, log):
    
    template_items = os.listdir(dir_path)
    for item in ["core", "env", "hooks"]:
        if item not in template_items:
            raise TankError("Config location '%s' missing a %s folder!" % (dir_path, item))
    
    log.info("Configuration looks valid!")
    
    return dir_path
    
    
def _process_config(sg_app_store, script_user, studio_root, cfg_string, log):
    """
    Looks at the starter config string and tries to convert it into a folder
    Returns a string
    """
    # three cases:
    # project_name
    # /path/to/file.zip
    # /path/to/folder
    if os.path.sep in cfg_string:
        # probably a file path!
        if os.path.exists(cfg_string):
            # either a folder or zip file!
            if cfg_string.endswith(".zip"):
                return _process_config_zip(studio_root, cfg_string, log)
            else:
                return _process_config_dir(studio_root, cfg_string, log)
        else:
            raise TankError("File path %s does not exist on disk!" % cfg_string)    
    elif cfg_string.startswith("tk-"):
        # app store!
        return _process_config_app_store(sg_app_store, script_user, studio_root, cfg_string, log)
    else:
        # is this a project?
        return _process_config_project(studio_root, cfg_string, log)
    


def _validate_tank_root(studio_root):
    """
    Checks that the studio root is valid.
    raises TankError if not valid
    """
    # check tank root
    if not os.path.exists(studio_root):
        raise TankError("Studio Root '%s' does not exist!" % studio_root)
    
    # check tank_root/tank/config location
    config_folder = os.path.join(studio_root, "tank", "config")
    if not os.path.exists(config_folder):
        msg = "Studio Root does not have a config folder %s!" % config_folder
        raise TankError(msg)
    

def _get_studio_root(log):
    """
    Get the tank studio root. Ask the user.
    """
    
    # we are in /studio/tank/install/core/scripts
    # studio_root /studio
    
    # try to deduce a path based on the location of this file
    suggested_studio_root = os.path.abspath(os.path.join( os.path.dirname(__file__), "..", "..", "..", ".."))
    
    try:
        _validate_tank_root(suggested_studio_root)
    except TankError:
        suggested_studio_root = ""        
    
    log.info("")
    log.info("Please enter the tank studio root.")
    log.info("If you are not sure what the studio root is, ")
    log.info("you can find it by looking in the Shotgun site ")
    log.info("preferences, under the local file storage section. ")
    log.info("The Local Storage named 'Tank' points to the studio root.")
    
    done = False
    studio_root = None
    while not done:
        if suggested_studio_root == "":
            answer = raw_input("Please type in studio root: ")
        else:
            answer = raw_input("Please type in studio root, enter to accept default [%s]: " % suggested_studio_root)
        
        if answer == "":
            answer = suggested_studio_root
        
        try:
            _validate_tank_root(answer)
        except TankError, e:
            log.warning("Not a valid studio root: %s" % e)
        else:
            done = True
            studio_root = answer
            
    return studio_root
########################################################################################
# main installer

def setup_project(log, starter_config_input):
    """
    main method.
    """
    
    log.info("")
    log.info("Welcome to the Tank Setup Project tool!")
    
    tank_root = _get_studio_root(log)
    
    # now connect to shotgun
    try:
        log.info("Connecting to Shotgun...")
        sg = shotgun.create_sg_connection_studio_root(tank_root)        
        sg_version = ".".join([ str(x) for x in sg.server_info["version"]])
        log.info("Connected to target Shotgun server! (v%s)" % sg_version)
    except Exception, e:
        raise TankError("Could not connect to Shotgun server: %s" % e)
    
    try:
        log.info("Connecting to the Tank App Store...")
        (sg_app_store, script_user) = shotgun.create_sg_app_store_connection(tank_root)
        sg_version = ".".join([ str(x) for x in sg_app_store.server_info["version"]])
        log.info("Connected to Tank App Store! (v%s)" % sg_version)
    except Exception, e:
        raise TankError("Could not connect to App Store: %s" % e)
        
    # validate and process input data
    starter_config = _process_config(sg_app_store, 
                                     script_user,
                                     tank_root, 
                                     starter_config_input, 
                                     log)    
        
    # get projects 
    projs = sg.find("Project", [["tank_name", "is", None]], ["id", "name", "sg_description"])

    if len(projs) == 0:
        raise TankError("Could not find any suitable Shotgun projects!")

    log.info("")
    log.info("")
    log.info("The following Shotgun projects have not yet been set up with Tank:")
    log.info("")
    
    projs_found = 0
    
    for x in projs:
        if x.get("name") == "Template Project":
            # don't show the template project in the listing
            continue
        
        desc = x.get("sg_description")
        if desc is None:
            desc = "[No description]"
        
        # chop a long description
        if len(desc) > 50:
            desc = "%s..." % desc[:50]
        
        log.info("[%2d] %s" % (x.get("id"), x.get("name")))
        log.info("     %s" % desc)
        log.info("")
        projs_found += 1
    
    if projs_found == 0:
        raise TankError("No Shotgun projects suitable for Tank setup were found!")
    
    log.info("")
    answer = raw_input("Please type in the id of the project to connect to or ENTER to exit: " )
    if answer == "":
        raise TankError("Aborted by user.")
    try:
        proj_id = int(answer)
    except:
        raise TankError("Please enter a number!")
    
    if proj_id not in [ x["id"] for x in projs]:
        raise TankError("Id %d was not found in the list of projects!" % proj_id)
    
    # try to propose a project name
    for x in projs:
        if x["id"] == proj_id:
            proj_name = x["name"].lower().replace(" ", "_")
    # make sure that what we suggest is valid...
    if not _validate_proj_disk_name(proj_name):
        proj_name = "proj"
    
    log.info("")
    log.info("")
    log.info("Now you need to choose a name for your project on disk.")
    log.info("This will be the name of the root project folder.")
    log.info("Please stick to alphanumerics, underscore and dash.")
    log.info("Press ENTER to go with the suggested name.")
    log.info("")
    answer = raw_input("Enter project root folder name: [%s] " % proj_name )
    if answer != "":
        proj_name = answer
    if not _validate_proj_disk_name(proj_name):
        raise TankError("Invalid characters in project name!")
    
    ########################################################################################
    # we are good to go    
    
    log.info("")
    log.info("")
    proj_root = os.path.join(tank_root, proj_name)
    log.info("The project will be created in the root point %s" % proj_root)
    log.info("")
    if not os.path.exists(proj_root):
        log.info("Attempting to create this folder.")
        try:
            os.mkdir(proj_root, 0777)
        except:
            raise TankError("Could not create folder '%s' - Try creating it manually and with the "
                            "appropriate permissions!")
    
    # check that there isn't a tank folder already
    tank_folder = os.path.join(proj_root, "tank")
    if os.path.exists(tank_folder):
        raise TankError("Found a tank folder in '%s' - looks like Tank has already been used "
                        "with this project!" % proj_root)
    
    # create a tank folder
    os.mkdir(tank_folder, 0775)
    
    # all good. Register tank_name in shotgun
    sg.update("Project", proj_id, {"tank_name": proj_name})
    log.info("Updated shotgun (Project.tank_name) with the project disk name.")
    
    # now copy the template data across
    log.info("Now copying template across into project location.")
    os.mkdir(os.path.join(tank_folder, "cache"), 0775)
    os.mkdir(os.path.join(tank_folder, "config"), 0775)
    _copy_folder(starter_config, os.path.join(tank_folder, "config"))
 
    # and write a custom event to the shotgun event log
    data = {}
    data["description"] = "%s: A Tank Project named %s was created" % (sg.base_url, proj_name)
    data["event_type"] = "TankAppStore_Project_Created"
    data["user"] = script_user
    data["project"] = TANK_APP_STORE_DUMMY_PROJECT
    data["attribute_name"] = proj_name
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
        after_project_create.create(sg=sg, project_id=proj_id, log=log)
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



def main(log):
    
    
    if len(sys.argv) == 1 or (len(sys.argv) == 2 and sys.argv[1] == "-h"):     

        desc = """ 
This utility script sets up a new project for Tank.
You can call this command in the following ways:

Using an App Store Config
-----------------------------------------------------------

> %(cmd)s tk-config-xyz
For a list of available configs, see https://tank.shotgunsoftware.com

Using an existing project
-----------------------------------------------------------

> %(cmd)s gunstlinger
If your Tank studio root is set to /mnt/projects, the above command will
look for a configuration in the location /mnt/projects/gunstlinger/tank/config

Pointing it to a specific folder or zip file
-----------------------------------------------------------

> %(cmd)s /path/to/configuration.zip
> %(cmd)s /path/to/tank/config
To point the installer directly at the gunstlinger config
above, you would use the following syntax:
> %(cmd)s /mnt/projects/gunstlinger/tank/config

-----------------------------------------------------------
For help and support, contact the Tank support: tanksupport@shotgunsoftware.com

""" % {"cmd": sys.argv[0]} 

        print desc
        return
    else:
        starter_config = sys.argv[1]
        
    # run actual activation
    setup_project(log, starter_config)

#######################################################################
if __name__ == "__main__":
    
    # set up logging channel for this script
    log = logging.getLogger("tank.setup_project")
    log.setLevel(logging.INFO)
    
    ch = logging.StreamHandler()
    formatter = logging.Formatter("%(levelname)s %(message)s")
    ch.setFormatter(formatter)
    log.addHandler(ch)

    exit_code = 1
    try:
        # clear the umask so permissions are respected
        old_umask = os.umask(0)
        main(log)
        exit_code = 0
    except TankError, e:
        # one line report
        log.error("An error occurred: %s" % e)
    except Exception, e:
        # callstack
        log.exception("An error occurred: %s" % e)
    finally:
        os.umask(old_umask)
        
    sys.exit(exit_code)
