"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Methods for pushing an associated version of the tank Core API
into its appropriate install location. This script is typically 
loaded and executed from another script (either an activation script
or an upgrade script) but can be executed manually if needed.

The script assumes that there is a tank core payload located
next to it in the file system. This is what it will attempt to install. 

"""

import os
import logging
import sys
import stat
import datetime
import shutil

SG_LOCAL_STORAGE_OS_MAP = {"linux2": "linux_path", "win32": "windows_path", "darwin": "mac_path" }

# get yaml and our shotgun API from the local install
# which comes with the upgrader. This is the code we are about to upgrade TO.
vendor = os.path.abspath(os.path.join( os.path.dirname(__file__), "python", "tank_vendor"))
sys.path.append(vendor)
import yaml
from shotgun_api3 import Shotgun


def __create_sg_connection(log, shotgun_cfg_path):
    """
    Creates a standard tank shotgun connection.
    """
    
    log.debug("Reading shotgun config from %s..." % shotgun_cfg_path)
    if not os.path.exists(shotgun_cfg_path):
        raise Exception("Could not find shotgun configuration file '%s'!" % shotgun_cfg_path)

    # load the config file
    try:
        open_file = open(shotgun_cfg_path)
        config_data = yaml.load(open_file)
    except Exception, error:
        raise Exception("Cannot load config file '%s'. Error: %s" % (shotgun_cfg_path, error))
    finally:
        open_file.close()

    # validate the config file
    if "host" not in config_data:
        raise Exception("Missing required field 'host' in config '%s'" % shotgun_cfg_path)
    if "api_script" not in config_data:
        raise Exception("Missing required field 'api_script' in config '%s'" % shotgun_cfg_path)
    if "api_key" not in config_data:
        raise Exception("Missing required field 'api_key' in config '%s'" % shotgun_cfg_path)
    if "http_proxy" not in config_data:
        http_proxy = None
    else:
        http_proxy = config_data["http_proxy"]

    # create API
    sg = Shotgun(config_data["host"],
                 config_data["api_script"],
                 config_data["api_key"],
                 http_proxy=http_proxy)

    return sg


def _make_folder(log, folder, permissions):
    if not os.path.exists(folder):
        log.debug("Creating folder %s.." % folder)
        os.mkdir(folder, permissions)
    

def _upgrade_to_013(tank_install_root, log):
    """
    Migration to upgrade from 0.12.x to 0.13.
    Can be run at any point in time. Will
    gracefully do the right thing if a new version is already in place.
    """
    
    # first need a connection to the associated shotgun site
    shotgun_cfg = os.path.abspath(os.path.join(tank_install_root, "..", "config", "core", "shotgun.yml"))
    sg = __create_sg_connection(log, shotgun_cfg)
    log.debug("Shotgun API: %s" % sg)
    
    pcs = sg.find("PipelineConfiguration", [], [])
    if len(pcs) > 0:
        log.debug("Found pipeline configurations in the system. Assuming this install is 0.13 compliant.")
        return
    
    # check if there is a tank storage. In that case we assume there is an upgrade happening
    tank_storage = sg.find_one("LocalStorage", [["code", "is", "Tank"]], ["mac_path", "linux_path", "windows_path"])
    if tank_storage is None:
        # no tank storage. Assume that we are in a clean install - no need to migrate!
        return


    log.info("---------------------------------------------------------------------")
    log.info("Welcome to Tank v0.13!")
    log.info("---------------------------------------------------------------------")
    log.info("")
    log.info("Tank v0.13 contains a number of structural changes. Therefore, ")
    log.info("a migration script will upgrade all your existing Tank projects.")
    log.info("")
    log.info("Here's what will happen when you upgrade:")
    log.info("")
    log.info("- Additional configuration files will be created for each project.")
    log.info("- Pipeline Configurations will be created for each project in Shotgun.")
    log.info("- Tank commands will be added to all projects and to the central install.")
    log.info("")
    log.info("If you have any questions or concerns, you can always contact us prior")
    log.info("to upgrading. Just drop us a line on tanksupport@shotgunsoftware.com")
    log.info("")
    val = raw_input("Continue with Tank v0.13 upgrade (Yes/No)? [Yes]: ")
    if val != "" and not val.lower().startswith("y"):
        raise Exception("You have aborted the upgrade.")

    # okay so no pipeline configurations! Means we need to upgrade!
    log.info("Converting your Tank installation from v0.12 -> v0.13...")
    log.debug("Tank Storage: %s" % tank_storage)
    
    # first see if there is a storage named primary - if not, create it and set
    # it to be a copy of the tank storage
    primary_storage = sg.find_one("LocalStorage", [["code", "is", "primary"]], ["mac_path", "linux_path", "windows_path"])
    # also see if there is one in the discard pile
    deleted_primary_storage = sg.find("LocalStorage", [["code", "is", "primary"]], ["mac_path", "linux_path", "windows_path"], retired_only=True)
    if len(deleted_primary_storage) > 0:
        raise Exception("Cannot upgrade! There is a deleted storage named 'primary'. Please "
                        "contact support.")
    
    if primary_storage is None:
        data = {"code": "primary", 
                "mac_path": tank_storage.get("mac_path"),
                "linux_path": tank_storage.get("linux_path"),
                "windows_path": tank_storage.get("windows_path")
                }
        
        sg.create("LocalStorage", data)
        log.info("Created primary storage in Shotgun...")
    
    
    new_code_root = os.path.abspath(os.path.dirname(__file__))
    studio_root = os.path.abspath(os.path.join(tank_install_root, ".."))
    
    tank_commands = []
    
    ############################################################################################
    # first stage -- upgrade the studio location
    
    log.debug("Upgrading studio location %s..." % studio_root)
    
    tank_commands.append(os.path.join(studio_root, "tank"))
    
    log.debug("Copying tank binary files to studio location...")
    src_dir = os.path.join(new_code_root, "setup", "root_binaries")
    for file_name in os.listdir(src_dir):
        src_file = os.path.join(src_dir, file_name)
        tgt_file = os.path.join(studio_root, file_name)
        if not os.path.exists(tgt_file):
            log.debug("copying %s -> %s" % (src_file, tgt_file))
            shutil.copy(src_file, tgt_file)
            os.chmod(tgt_file, 0775)
    
    log.debug("Creating install_location yml file...")
    
    core_file_locations = {"Darwin": None, "Linux": None, "Windows": None}
    if tank_storage["mac_path"]:
        core_file_locations["Darwin"] = "%s/tank" % tank_storage["mac_path"]
    if tank_storage["linux_path"]:
        core_file_locations["Linux"] = "%s/tank" % tank_storage["linux_path"]
    if tank_storage["windows_path"]:
        core_file_locations["Windows"] = "%s\\tank" % tank_storage["windows_path"]
    
    
    install_location = os.path.join(studio_root, "config", "core", "install_location.yml")
    if not os.path.exists(install_location):
        
        fh = open(install_location, "wt")
        fh.write("# Tank configuration file\n")
        fh.write("# This file was automatically created by the 0.12 migration\n")
        fh.write("\n")                
        for (uname, path) in core_file_locations.items():
            fh.write("%s: '%s'\n" % (uname, path))
        fh.write("\n")
        fh.write("# End of file.\n")
        fh.close()    
        os.chmod(install_location, 0444)
            
    ############################################################################################
    # second stage -- upgrade projects

    projects = sg.find("Project", [["tank_name", "is_not", ""]], ["tank_name", "name"])
    for p in projects:
        log.info("Processing Project %s..." % p.get("name"))
        
        try:
            main_studio_folder = os.path.abspath(os.path.join(studio_root, ".."))
            project_tank_folder = os.path.join(main_studio_folder, p.get("tank_name"), "tank")
            
            if not os.path.exists(project_tank_folder):
                log.info("Project does not exist on disk (%s) - skipping..." % project_tank_folder)
                continue
            
            tank_commands.append(os.path.join(project_tank_folder, "tank"))
            
            log.debug("Project tank folder is %s" % project_tank_folder)
            
            log.debug("Copying tank binary files to project location...")
            src_dir = os.path.join(new_code_root, "setup", "root_binaries")
            for file_name in os.listdir(src_dir):
                src_file = os.path.join(src_dir, file_name)
                tgt_file = os.path.join(project_tank_folder, file_name)
                if not os.path.exists(tgt_file):
                    log.debug("copying %s -> %s" % (src_file, tgt_file))
                    shutil.copy(src_file, tgt_file)
                    os.chmod(tgt_file, 0775)
            
            _make_folder(log, os.path.join(project_tank_folder, "install"), 0775)
            _make_folder(log, os.path.join(project_tank_folder, "install", "core"), 0777)
            _make_folder(log, os.path.join(project_tank_folder, "install", "core", "python"), 0777)
            _make_folder(log, os.path.join(project_tank_folder, "install", "core", "setup"), 0777)
            _make_folder(log, os.path.join(project_tank_folder, "install", "core.backup"), 0777)
            _make_folder(log, os.path.join(project_tank_folder, "install", "core.backup", "activation_13"), 0777)
            _make_folder(log, os.path.join(project_tank_folder, "install", "engines"), 0777)
            _make_folder(log, os.path.join(project_tank_folder, "install", "apps"), 0777)
            _make_folder(log, os.path.join(project_tank_folder, "install", "frameworks"), 0777)
                        
            # copy the python stubs
            log.debug("Copying python stubs...")
            _copy_folder(log, 
                         os.path.join(new_code_root, "setup", "tank_api_proxy"), 
                         os.path.join(project_tank_folder, "install", "core", "python"))
            
            log.debug("Copying windows utils...")
            _copy_folder(log, 
                         os.path.join(new_code_root, "setup", "windows"), 
                         os.path.join(project_tank_folder, "install", "core", "setup", "windows"))
                        
            project_file_locations = {"Darwin": None, "Linux": None, "Windows": None}
            if tank_storage["mac_path"]:
                project_file_locations["Darwin"] = "%s/%s/tank" % (tank_storage["mac_path"], p.get("tank_name"))
            if tank_storage["linux_path"]:
                project_file_locations["Linux"] = "%s/%s/tank" % (tank_storage["linux_path"], p.get("tank_name"))
            if tank_storage["windows_path"]:
                project_file_locations["Windows"] = "%s\\%s\\tank" % (tank_storage["windows_path"], p.get("tank_name"))
            
            
            # write a file location file for our new setup
            install_location = os.path.join(project_tank_folder, "config", "core", "install_location.yml")
            if not os.path.exists(install_location):
            
                fh = open(install_location, "wt")
                fh.write("# Tank configuration file\n")
                fh.write("# This file was automatically created by the 0.12 migration\n")
                fh.write("\n")
                for (uname, path) in project_file_locations.items():
                    fh.write("%s: '%s'\n" % (uname, path))                        
                fh.write("\n")
                fh.write("# End of file.\n")
                fh.close()    
                os.chmod(install_location, 0444)
                
            
            # parent files for the interpreter:
            # core_Darwin.cfg
            # core_Linux.cfg
            # core_Windows.cfg
            log.debug("Creating core redirection config files...")            
            for (uname, path) in core_file_locations.items():
                core_path = os.path.join(project_tank_folder, "install", "core", "core_%s.cfg" % uname)
                if not os.path.exists(core_path):
                    fh = open(core_path, "wt")
                    if path is None:
                        fh.write("undefined")
                    else:
                        fh.write(path)
                    fh.close()
                    log.debug("Created %s" % core_path)
                    
            # create a pipeline_configuration.yml and write the project to it
            log.debug("Checking pipeline_configuration file...")
            pc_config_file = os.path.join(project_tank_folder, "config", "core", "pipeline_configuration.yml")
            if not os.path.exists(pc_config_file):
                fh = open(pc_config_file, "wt")
                fh.write("{'project_name': '%s'}\n" % p.get("tank_name"))
                fh.close()
                log.debug("Created %s" % pc_config_file)            
            
            # now check if there is a roots.
            log.debug("Checking roots file...")
            roots_file = os.path.join(project_tank_folder, "config", "core", "roots.yml")
            if not os.path.exists(roots_file):
                
                # primary: {linux_path: null, mac_path: /tank_demo/project_data, windows_path: null}
                
                data = {"linux_path": tank_storage["linux_path"], 
                        "mac_path": tank_storage["mac_path"], 
                        "windows_path": tank_storage["windows_path"]}
                                
                fh = open(roots_file, "wt")
                yaml.dump({"primary": data }, fh)
                fh.close()
                log.debug("Created %s" % roots_file)            
                
            
            # now read roots.yml back in to find all our target storages
            fh = open(roots_file)
            roots_data = yaml.load(fh)
            fh.close()
            
            # primary: {linux_path: null, mac_path: /tank_demo/project_data, windows_path: null}
            for (storage_name, storage_data) in roots_data.items():
                current_os_path = storage_data.get( SG_LOCAL_STORAGE_OS_MAP[sys.platform] )
                if current_os_path is not None and os.path.exists(current_os_path):
                    # get the project root which is the storage + project root
                    project_root = os.path.join(current_os_path, p.get("tank_name"))
                    back_config = os.path.join(project_root, "tank", "config", "tank_configs.yml")
            
                    if os.path.exists(back_config):
                        # we have a config already - so read it in
                        fh = open(back_config, "rt")
                        data = yaml.load(fh)
                        fh.close()
                    else:
                        data = []
                    
                    # now add our new mapping to this data structure
                    new_item = {"darwin": project_file_locations["Darwin"], 
                                "win32": project_file_locations["Windows"], 
                                "linux2": project_file_locations["Linux"]}
                    if new_item not in data:
                        data.append(new_item)
                    
                    # and write the file
                    fh = open(back_config, "wt")
                    yaml.dump(data, fh)
                    fh.close()                
            
            # if there is a asset and a shot yml, see if we can add in a std shell engine            
            std_shell_engine = {"apps": {}, 
                                "debug_logging": False, 
                                "location": {"name": "tk-shell", 
                                             "type": "app_store", 
                                             "version": "v0.2.2"} }
            
            shot_env = os.path.join(project_tank_folder, "config", "env", "shot.yml")
            asset_env = os.path.join(project_tank_folder, "config", "env", "asset.yml")

            for env_file in [shot_env, asset_env]:            
                if os.path.exists(env_file):
                    try:
                        fh = open(env_file)
                        env_data = yaml.load(fh)
                        fh.close()
                    
                        if "tk-shell" not in env_data["engines"].keys():
                            env_data["engines"]["tk-shell"] = std_shell_engine
                    
                        fh = open(env_file, "wt")
                        yaml.dump(env_data, fh)
                        fh.close()                
                    except:
                        log.warning("Could not add shell engine to environemnt!")
            
            # convert the shotgun.yml environment into multiple encs.
            sg_env_file = os.path.join(project_tank_folder, "config", "env", "shotgun.yml")
            if os.path.exists(sg_env_file):
                log.debug("Splitting %s" % sg_env_file)
                fh = open(sg_env_file)
                sg_env_data = yaml.load(fh)
                fh.close()
                
                new_envs = {}
                
                # split up env per type
                for (app_instance, app_config) in sg_env_data["engines"]["tk-shotgun"]["apps"].items():
                    entity_types = app_config.get("entity_types")
                    if entity_types is None:
                        entity_types = []
                    
                    # special case for launch publish which may not have a type param
                    if app_instance == "tk-shotgun-launchpublish":
                        entity_types = ["TankPublishedFile"]
                    
                    # special case for all the launch apps - these need to
                    # be added to the published file environment explicitly
                    launch_apps = [ "tk-shotgun-launch3dsmax",
                                    "tk-shotgun-launchmaya",
                                    "tk-shotgun-launchmotionbuilder",
                                    "tk-shotgun-launchnuke",
                                    "tk-shotgun-launchphotoshop",
                                    "tk-shotgun-launchhiero",
                                    "tk-shotgun-launchsoftimage" ]  
                    if app_instance in launch_apps:
                        entity_types.append("TankPublishedFile")
                     
                    for et in entity_types:
                        if et not in new_envs:
                            new_envs[et] = {}
                        new_envs[et][app_instance] = app_config
                
                # now write out all these files
                for (et, apps) in new_envs.items():
                    file_name = "shotgun_%s.yml" % et.lower()
                    full_path = os.path.join(project_tank_folder, "config", "env", file_name)
                    full_env_data = {}
                    full_env_data["engines"] = {}
                    full_env_data["engines"]["tk-shotgun"] = {"apps": {}, 
                                                              "debug_logging": False,
                                                              "location": sg_env_data["engines"]["tk-shotgun"]["location"]}
                    full_env_data["engines"]["tk-shotgun"]["apps"] = apps
                    fh = open(full_path, "wt")
                    yaml.dump(full_env_data, fh)
                    fh.close()                
                    
                # lastly, rename the shotgun file
                try:
                    os.rename(sg_env_file, "%s.bak" % sg_env_file)
                except:
                    log.warning("Could not rename %s" % sg_env_file)
            

            # create PC record in SG
            log.info("Setting up pipeline configuration for project %s..." % p.get("name"))
            pc_data = {"code": "Primary", 
                       "project": p, 
                       "windows_path": project_file_locations["Windows"],
                       "mac_path": project_file_locations["Darwin"],
                       "linux_path": project_file_locations["Linux"]}
            sg.create("PipelineConfiguration", pc_data)
            
            
            
        except Exception, e:
            log.error("\n\nCould not upgrade project %s! Please contact support! \nError: %s" % (p, e))
    
    
    log.info("")
    log.info("")
    log.info("Tank v0.12 --> v0.13 Migration complete!")
    log.info("---------------------------------------------------------------------")
    log.info("")
    log.info("A tank command has been added which makes it easy to reach common Tank ")
    log.info("operations across multiple projects. We recommend that you add ")
    log.info("this to your PATH for easy access. The studio level tank command ")
    log.info("is located here: %s" % tank_commands[0])
    log.info("")
    log.info("Each project also has its own tank command. This is used when you want ")
    log.info("to perform operations on an specific project, such as checking for updates ")
    log.info("or creating dev sandboxes. The following project level tank commands ")
    log.info("have been created:")
    log.info("")
    for x in tank_commands[1:]:
        log.info("> %s" % x)
    log.info("")
    log.info("")
    log.info("NOTE! The 0.13 core release is accompanied by several app and engine ")
    log.info("updates. We strongly recommend that you now run the tank app and engine ")
    log.info("update for all your projects. You can do this by running the 'updates'")
    log.info("command for each project, like this:")
    log.info("")
    for x in tank_commands[1:]:
        log.info("> %s updates" % x)
    log.info("")
    log.info("---------------------------------------------------------------------")
    
        
    

def _copy_folder(log, src, dst): 
    """
    Alternative implementation to shutil.copytree
    Copies recursively with very open permissions.
    Creates folders if they don't already exist.
    """
    files = []
    
    if not os.path.exists(dst):
        log.debug("mkdir 0777 %s" % dst)
        os.mkdir(dst, 0777)

    names = os.listdir(src) 
    for name in names:

        srcname = os.path.join(src, name) 
        dstname = os.path.join(dst, name) 
        
        # get rid of system files
        if name in [".svn", ".git", ".gitignore", "__MACOSX", ".DS_Store"]: 
            log.debug("SKIP %s" % srcname)
            continue
        
        try: 
            if os.path.isdir(srcname): 
                files.extend( _copy_folder(log, srcname, dstname) )             
            else: 
                shutil.copy(srcname, dstname)
                log.debug("Copy %s -> %s" % (srcname, dstname))
                files.append(srcname)
                # if the file extension is sh, set executable permissions
                if dstname.endswith(".sh") or dstname.endswith(".bat") or dstname.endswith(".exe"):
                    try:
                        # make it readable and executable for everybody
                        os.chmod(dstname, 0777)
                        log.debug("CHMOD 777 %s" % dstname)
                    except Exception, e:
                        log.error("Can't set executable permissions on %s: %s" % (dstname, e))
        
        except Exception, e: 
            log.error("Can't copy %s to %s: %s" % (srcname, dstname, e)) 
    
    return files

def upgrade_tank(tank_install_root, log):
    """
    Upgrades the tank core API located in tank_install_root
    based on files located locally to this script
    """
        
    # ensure permissions are not overridden by umask
    old_umask = os.umask(0)
    try:

        log.debug("First running migrations...")
        _upgrade_to_013(tank_install_root, log)    
        log.debug("Migrations have completed. Now doing the actual upgrade...")

        # check that the tank_install_root looks sane
        # expect folders: core, engines, apps
        valid = True
        valid &= os.path.exists(os.path.join(tank_install_root)) 
        valid &= os.path.exists(os.path.join(tank_install_root, "engines"))
        valid &= os.path.exists(os.path.join(tank_install_root, "core"))
        valid &= os.path.exists(os.path.join(tank_install_root, "core.backup"))
        valid &= os.path.exists(os.path.join(tank_install_root, "apps"))
        if not valid:
            log.error("The specified tank install root '%s' doesn't look valid!\n"
                      "Typically the install root path ends with /install." % tank_install_root)
            return

        # get our location
        this_folder = os.path.abspath(os.path.join( os.path.dirname(__file__)))
        
        # get target locations
        core_install_location = os.path.join(tank_install_root, "core")
        core_backup_location = os.path.join(tank_install_root, "core.backup")

        # check that the activation script version is acceptable if this is the very first
        # time an upgrade happens. Old pre012 activation script would leave the backup
        # location empty - new 0.13+ scripts write an initial folder.
        backups = os.listdir(core_backup_location)
        if len(backups) == 0:
            # empty backup directory! This is an indication that an old activation script was used.
            log.error("")
            log.error("")
            log.error("")
            log.error("")
            log.error("")
            log.error("------------------------------------------------------------------------")
            log.error("A critical error has occurred! Installation cannot proceed!")
            log.error("")
            log.error("The activation script you are using was designed to be used with")
            log.error("an older version of Tank. Please contact support to get a new version")
            log.error("of the Tank activation script. ")
            log.error("------------------------------------------------------------------------")
            log.error("")
            log.error("")
            log.error("")
            log.error("")
            log.error("")
            log.error("")
            return
        
        if os.path.exists(core_install_location):
            # move this into backup location
            backup_folder_name = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(core_backup_location, backup_folder_name)
            log.info("Backing up Core API: %s -> %s" % (core_install_location, backup_path))
            
            # first copy the content in the core folder
            src_files = _copy_folder(log, core_install_location, backup_path)
            
            # now clear out the install location
            log.info("Clearing out target location...")
            for f in src_files:
                try:
                    # on windows, ensure all files are writable
                    if sys.platform == "win32":
                        attr = os.stat(f)[0]
                        if (not attr & stat.S_IWRITE):
                            # file is readonly! - turn off this attribute
                            os.chmod(f, stat.S_IWRITE)
                    os.remove(f)
                    log.debug("Deleted %s" % f)
                except Exception, e:
                    log.error("Could not delete file %s: %s" % (f, e))
            
        # create new core folder
        log.info("Installing %s -> %s" % (this_folder, core_install_location))
        _copy_folder(log, this_folder, core_install_location)
        
        log.info("Core upgrade complete.")
    finally:
        os.umask(old_umask)

#######################################################################
if __name__ == "__main__":
    
    if len(sys.argv) == 3 and sys.argv[1] == "migrate":
        path = sys.argv[2]
        log = logging.getLogger("tank.update")
        log.setLevel(logging.INFO)
        ch = logging.StreamHandler()
        formatter = logging.Formatter("%(levelname)s %(message)s")
        ch.setFormatter(formatter)
        log.addHandler(ch)
        upgrade_tank(path, log)
        sys.exit(0)
        
    else:
    
        desc = """
    This is a system script used by the upgrade process.
    
    If you want to upgrade Tank, please run one of the upgrade
    utilities located in the scripts folder.
    
    """
        print desc
        sys.exit(1)
