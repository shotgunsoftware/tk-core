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
                if dstname.endswith(".sh"):
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

        # check that the tank_install_root looks sane
        # expect folders: core, engines, apps
        valid = True
        valid &= os.path.exists(os.path.join(tank_install_root)) 
        valid &= os.path.exists(os.path.join(tank_install_root, "engines"))
        valid &= os.path.exists(os.path.join(tank_install_root, "core"))
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
    
    desc = """
This is a system script used by the upgrade process.

If you want to upgrade Tank, please run one of the upgrade
utilities located in the scripts folder.

"""
    print desc
    sys.exit(1)
