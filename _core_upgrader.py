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
Methods for pushing an associated version of the Toolkit Core API
into its appropriate install location. This script is typically 
loaded and executed from another script (either an activation script
or an upgrade script) but can be executed manually if needed.

The script assumes that there is an sgtk core payload located
next to it in the file system. This is what it will attempt to install. 

"""

import os
import logging
import sys
import stat
import datetime
import shutil
from distutils.version import LooseVersion

SG_LOCAL_STORAGE_OS_MAP = {"linux2": "linux_path", "win32": "windows_path", "darwin": "mac_path" }
CORE_CFG_OS_MAP = {"linux2": "core_Linux.cfg", "win32": "core_Windows.cfg", "darwin": "core_Darwin.cfg" }

# get yaml and our shotgun API from the local install
# which comes with the upgrader. This is the code we are about to upgrade TO.
vendor = os.path.abspath(os.path.join( os.path.dirname(__file__), "python", "tank_vendor"))
sys.path.append(vendor)
import yaml
from shotgun_api3 import Shotgun

###################################################################################################
# migration utilities

def __is_upgrade(sgtk_install_root):
    """
    Returns true if this is not the first time the sgtk code is being 
    installed (activation).
    
    :param sgtk_install_root: Location where the core is installed
    :returns: true if activation, false if not
    """
    return os.path.exists(os.path.join(sgtk_install_root, "core", "info.yml"))
    
def __current_version_less_than(log, sgtk_install_root, ver):
    """
    returns true if the current API version installed is less than the 
    specified version. ver is "v0.1.2"
    
    :param sgtk_install_root: Location where the core is installed
    :param ver: Version string to check (e.g. 'v0.1.2')
    :returns: true or false
    """
    log.debug("Checking if the currently installed version is less than %s..." % ver)
    
    if __is_upgrade(sgtk_install_root) == False:
        # there is no current version. So it is definitely
        # not at least version X
        log.debug("There is no current version. This is the first time the core is being installed.")
        return True
    
    try:
        current_api_manifest = os.path.join(sgtk_install_root, "core", "info.yml")
        fh = open(current_api_manifest, "r")
        try:
            data = yaml.load(fh)
        finally:
            fh.close()
        current_api_version = str(data.get("version"))
    except Exception, e:
        # current version unknown
        log.warning("Could not determine the version of the current code: %s" % e)
        # not sure to do here - report that current version is NOT less than XYZ
        return False
    
    log.debug("The current API version is '%s'" % current_api_version)
     
    if current_api_version.lower() in ["head", "master"]:
        # current version is greater than anything else
        return False
    
    if current_api_version.startswith("v"):
        current_api_version = current_api_version[1:]
    if ver.startswith("v"):
        ver = ver[1:]

    return LooseVersion(current_api_version) < LooseVersion(ver)


###################################################################################################
# helpers

def __create_sg_connection(log, shotgun_cfg_path):
    """
    Creates a standard sgtk shotgun connection.
    
    :param log: std python logger
    :param shotgun_cfg_path: path to shotgun.yml configuration file
    :returns: Shotgun API instance 
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
    log.debug("Connecting to %s..." % config_data["host"])
    sg = Shotgun(config_data["host"],
                 config_data["api_script"],
                 config_data["api_key"],
                 http_proxy=http_proxy)

    return sg

def __get_pc_core_install_root(pc_root, visited_paths = None):
    """
    Find the installed core root dir for the specified pipeline config root.
    
    :param pc_root:         The pipeline config root to find the corresponding core
                            install root for
    :param visited_paths:   The paths visited so far - used to catch cyclic references
    :returns:               The core install root directory for this pc
    """
    # check we haven't already visited this path:
    visited_paths = visited_paths or set()
    if pc_root in visited_paths:
        # found a cyclic config lookup - this is bad!
        raise Exception("Found cyclic reference in core config lookups: '%s'" % pc_root)
    visited_paths.add(pc_root)
    
    # check for the existence of a known file in the core location to determine if it is
    # a local core or not (this is similar logic to that used in the tank.bat/tank scripts):
    pc_install_root = os.path.join(pc_root, "install")
    tank_cmd_script = os.path.join(pc_install_root, "core", "scripts", "tank_cmd.py")
    if os.path.exists(tank_cmd_script):
        # found a core install
        return pc_install_root
    
    # look for the core location in the config file:
    pc_install_root = os.path.join(pc_root, "install")
    core_cfg_path = os.path.join(pc_install_root, "core", CORE_CFG_OS_MAP[sys.platform])
    if not os.path.exists(core_cfg_path):
        # cfg is missing!
        raise Exception("The config file '%s' could not be found on disk!" % core_cfg_path)
    
    # get the path from the config:
    cfg = open(core_cfg_path, "r")
    try:
        root_path = cfg.read().strip()
        root_path = os.path.expandvars(root_path)
        if root_path in ["None", "undefined"]:
            return None
        
        # recurse to this path:
        return __get_pc_core_install_root(root_path, visited_paths)
    finally:
        cfg.close()


def _make_folder(log, folder, permissions):
    """
    Create a folder on disk. Wrapper.
    
    :param log: std python logger
    :param folder: Path to folder to create
    :param permissions: Permissions to apply as an int
    """
    if not os.path.exists(folder):
        log.debug("Creating folder %s.." % folder)
        os.mkdir(folder, permissions)
    
    
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


###################################################################################################
# Migrations

def _upgrade_path_cache(log):
    """
    Migration to upgrade to 0.15. Info blurb only.
    
    :param log: std python logger
    """
    log.info("")
    log.info("")
    log.info("")
    log.info("")    
    log.info("---------------------------------------------------------------------")
    log.info("Welcome to Toolkit v0.15!")
    log.info("---------------------------------------------------------------------")
    log.info("")
    log.info("Toolkit v0.15 features centralized tracking of the folders that are ")
    log.info("created on disk. This makes it easier to work distributed and have local")
    log.info("data setups. (For more details, see the release notes.)")
    log.info("")
    log.info("Once Toolkit 0.15 has been installed, all new projects will automatically ")
    log.info("have this feature enabled. Existing projects can optionally use this feature ")
    log.info("if you like - you turn it on using the following command:")
    log.info("")
    log.info("> tank upgrade_folders")
    log.info("")
    log.info("---------------------------------------------------------------------")    
    log.info("")
    log.info("")
    log.info("")
    log.info("")


###################################################################################################
# Upgrade entry point

def __copy_tank_cmd_binaries(src_dir, dst_dir, tank_scripts, log):
    """
    Copy the tank cmd binaries from the source (core install) to the destination
    (pipeline config/studio root) locations.
    
    :param src_dir:         The source directory to copy them from
    :param dst_dir:         The destination directory to copy them to
    :param tank_scripts:    A list of the tank command binary scripts to copy
    """
    for tank_script in tank_scripts:
        dst_tank_script = os.path.join(dst_dir, tank_script)
        if not os.path.exists(dst_tank_script):
            log.warning("   Could not find file: '%s' to replace, skipping!" % dst_tank_script)
            continue
    
        log.info("   Updating '%s'" % dst_tank_script)
        src_tank_script = os.path.join(src_dir, tank_script)
        log.debug("  Copying '%s' -> '%s'" % (src_tank_script, dst_tank_script))
        os.chmod(dst_tank_script, 0777)
        shutil.copy(src_tank_script, dst_tank_script)
        os.chmod(dst_tank_script, 0775)

def _upgrade_tank_cmd_binaries(sgtk_install_root, log):
    """
    Upgrade the tank command binaries to the latest versions.  This 
    replaces the tank.bat and tank scripts for all projects with the 
    most current versions.
    
    Note, this will only update the scripts if this upgrade script has 
    access to the location they are installed to.
    
    :param sgtk_install_root:   The location core has been installed to
    :param log:                 The log instance to be used for all 
                                logging
    """
    log.info("Updating tank.bat & tank command scripts for all Pipeline Configurations "
             "in all projects that use this version of core.  Please note that only Pipeline "
             "Configurations in disk locations that are accessible will be updated."
             "Others can be updated manually by copying the tank command executables from "
             "'install/core/setup/root_binaries' if needed.")
    
    tank_scripts = ["tank.bat", "tank"]
    
    # first need a connection to the associated shotgun site
    shotgun_cfg = os.path.abspath(os.path.join(sgtk_install_root, "..", "config", "core", "shotgun.yml"))
    sg = __create_sg_connection(log, shotgun_cfg)
    log.debug("Shotgun API: %s" % sg)

    this_folder = os.path.abspath(os.path.join( os.path.dirname(__file__)))
    new_tank_root = os.path.join(this_folder, "setup", "root_binaries")
    
    # first do the versions in the studio location:
    studio_tank_root = os.path.abspath(os.path.join(sgtk_install_root, ".."))
    log.info(" - Processing studio location '%s'" % studio_tank_root) 
    __copy_tank_cmd_binaries(new_tank_root, studio_tank_root, tank_scripts, log)
    
    # now do the project pc locations (if we can access them):
    pcs = sg.find("PipelineConfiguration", [], ["code", "project", "windows_path", "mac_path", "linux_path"])
    for pc in pcs:
        try:        
            # get the pc root for this platform and make sure it exists:
            pc_tank_root = pc.get(SG_LOCAL_STORAGE_OS_MAP[sys.platform])
            if pc_tank_root is None:
                continue
            if not os.path.exists(pc_tank_root):
                continue
                    
            # need to determine if this pc is using core located at sgtk_install_root
            pc_core_install_root = __get_pc_core_install_root(pc_tank_root)
            if not pc_core_install_root or pc_core_install_root != sgtk_install_root:
                # this pc doesn't use the same core so skip it!
                continue
    
            # all good so lets process this config:
            log.info(" - Processing Pipeline Configuration %s (Project %s)" % (pc.get("code"), 
                                                                           pc.get("project").get("name")))
            __copy_tank_cmd_binaries(new_tank_root, pc_tank_root, tank_scripts, log)
            
        except Exception, e:
            log.error("\n   Could not upgrade Pipeline Configuration '%s'! Please contact "
                      "toolkitsupport@shotgunsoftware.com.\nError: %s\n\n\n" % (str(pc), e))


def upgrade_tank(sgtk_install_root, log):
    """
    Upgrades the sgtk core API located in sgtk_install_root
    based on files located locally to this script
    """
    
    # get our location
    this_folder = os.path.abspath(os.path.join( os.path.dirname(__file__)))
    
    # ensure permissions are not overridden by umask
    old_umask = os.umask(0)
    try:
        log.debug("First running migrations...")

        # check that noone is still on 0.12/early 0.13 and in that case ask them to contact us
        # so that we can advise that they reinstall their setup from scratch.     
        if __is_upgrade(sgtk_install_root) and __current_version_less_than(log, sgtk_install_root, "v0.13.16"):
            log.error("You are running a very old version of the Toolkit Core API. Automatic upgrades "
                      "are no longer supported. Please contact toolkitsupport@shotgunsoftware.com.")
            return

        # Make sure the tank.bat and tank scripts are up to date:
        if __is_upgrade(sgtk_install_root) and __current_version_less_than(log, sgtk_install_root, "v0.14.72"):
            log.debug("Running tank command replacement migration...")
            _upgrade_tank_cmd_binaries(sgtk_install_root, log)

        if __is_upgrade(sgtk_install_root) and __current_version_less_than(log, sgtk_install_root, "v0.15.0"):
            log.debug("Upgrading to v0.15.0. Prompting for path cache changes.")
            _upgrade_path_cache(log)
            
        log.debug("Migrations have completed. Now doing the actual upgrade...")

        # check that the sgtk_install_root looks sane
        # - check the root exists:
        if not os.path.exists(os.path.join(sgtk_install_root)):
            log.error("The specified sgtk install root '%s' doesn't look valid!\n"
                      "Typically the install root path ends with /install." % sgtk_install_root)
            return
        # - check for expected folders: core, engines, apps, etc.
        dirs_to_check = ["engines", "core", "core.backup", "apps"]
        for dir in dirs_to_check:
            if not os.path.exists(os.path.join(sgtk_install_root, dir)):
                log.error("The specified sgtk install root '%s' doesn't look valid - "
                          "an expected sub-directory '/%s' couldn't be found!\n"
                          "Typically the install root path ends with /install." 
                          % (sgtk_install_root, dir))
                return                
        
        # get target locations
        core_install_location = os.path.join(sgtk_install_root, "core")
        core_backup_location = os.path.join(sgtk_install_root, "core.backup")
        
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
    
    # for debugging purposes, can run this command with the following syntax
    # > python _core_upgrader.py migrate /mnt/software/shotgun/studio/install
    
    if len(sys.argv) == 3 and sys.argv[1] == "migrate":
        path = sys.argv[2]
        migrate_log = logging.getLogger("tank.update")
        migrate_log.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        formatter = logging.Formatter("%(levelname)s %(message)s")
        ch.setFormatter(formatter)
        migrate_log.addHandler(ch)
        upgrade_tank(path, migrate_log)
        sys.exit(0)
        
    else:
    
        desc = """
    This is a system script used by the upgrade process.
    
    If you want to upgrade the toolkit Core API, run the
    'tank core' command.
    
    """
        print desc
        sys.exit(1)
