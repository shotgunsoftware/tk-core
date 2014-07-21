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
from distutils.version import LooseVersion

SG_LOCAL_STORAGE_OS_MAP = {"linux2": "linux_path", "win32": "windows_path", "darwin": "mac_path" }

# get yaml and our shotgun API from the local install
# which comes with the upgrader. This is the code we are about to upgrade TO.
vendor = os.path.abspath(os.path.join( os.path.dirname(__file__), "python", "tank_vendor"))
sys.path.append(vendor)
import yaml
from shotgun_api3 import Shotgun

###################################################################################################
# migration utilities

def __is_upgrade(tank_install_root):
    """
    Returns true if this is not the first time the tank code is being 
    installed (activation).
    """
    return os.path.exists(os.path.join(tank_install_root, "core", "info.yml"))
    
def __current_version_less_than(log, tank_install_root, ver):
    """
    returns true if the current API version installed is less than the 
    specified version. ver is "v0.1.2"
    """
    log.debug("Checking if the currently installed version is less than %s..." % ver)
    
    if __is_upgrade(tank_install_root) == False:
        # there is no current version. So it is definitely
        # not at least version X
        log.debug("There is no current version. This is the first time the core is being installed.")
        return True
    
    try:
        current_api_manifest = os.path.join(tank_install_root, "core", "info.yml")
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
    log.debug("Connecting to %s..." % config_data["host"])
    sg = Shotgun(config_data["host"],
                 config_data["api_script"],
                 config_data["api_key"],
                 http_proxy=http_proxy)

    return sg


def _make_folder(log, folder, permissions):
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

def upgrade_tank(tank_install_root, log):
    """
    Upgrades the tank core API located in tank_install_root
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
        if __is_upgrade(tank_install_root) and __current_version_less_than(log, tank_install_root, "v0.13.16"):
            log.error("You are running a very old version of the Toolkit Core API. Automatic upgrades "
                      "are no longer supported. Please contact toolkitsupport@shotgunsoftware.com.")
            return
            
        log.debug("Migrations have completed. Now doing the actual upgrade...")

        # check that the tank_install_root looks sane
        # - check the root exists:
        if not os.path.exists(os.path.join(tank_install_root)):
            log.error("The specified tank install root '%s' doesn't look valid!\n"
                      "Typically the install root path ends with /install." % tank_install_root)
            return
        # - check for expected folders: core, engines, apps, etc.
        dirs_to_check = ["engines", "core", "core.backup", "apps"]
        for dir in dirs_to_check:
            if not os.path.exists(os.path.join(tank_install_root, dir)):
                log.error("The specified tank install root '%s' doesn't look valid - "
                          "an expected sub-directory '/%s' couldn't be found!\n"
                          "Typically the install root path ends with /install." 
                          % (tank_install_root, dir))
                return                
        
        # get target locations
        core_install_location = os.path.join(tank_install_root, "core")
        core_backup_location = os.path.join(tank_install_root, "core.backup")
        
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
    
    If you want to upgrade Tank, please run one of the upgrade
    utilities located in the scripts folder.
    
    """
        print desc
        sys.exit(1)
