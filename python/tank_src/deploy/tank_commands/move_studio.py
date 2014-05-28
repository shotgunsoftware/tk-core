# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

from ...util import shotgun
from ...platform import constants
from ...errors import TankError
from ... import pipelineconfig
from ... import pipelineconfig_utils

from .action_base import Action

from tank_vendor import yaml

import sys
import os
import shutil



class MoveStudioInstallAction(Action):
    """
    Action that moves the studio installation location. 
    """
    
    def __init__(self):
        Action.__init__(self, 
                        "move_studio_install", 
                        Action.GLOBAL, 
                        ("Moves the Toolkit studio code installation to a different location."), 
                        "Admin")
    
    def _cleanup_old_location(self, log, path):
        
        for root, dirs, files in os.walk(path, topdown=False):
            for name in files:
                full_path = os.path.join(root, name)
                log.debug("Removing %s..." % full_path)
                try:
                    os.remove(full_path)
                except Exception, e:
                    log.warning("Could not delete file %s. Error Reported: %s" % (full_path, e))
                        
            for name in dirs:
                full_path = os.path.join(root, name)
                log.debug("Deleting folder %s..." % full_path)
                try:
                    os.rmdir(full_path)
                except Exception, e:
                    log.warning("Could not remove folder %s. Error Reported: %s" % (full_path, e))
                            
    
    def _copy_folder(self, log, level, src, dst): 
        """
        Alternative implementation to shutil.copytree
        Copies recursively with very open permissions.
        Creates folders if they don't already exist.
        """

        if not os.path.exists(dst):
            log.debug("mkdir 0777 %s" % dst)
            os.mkdir(dst, 0777)
    
        names = os.listdir(src) 
        for name in names:
    
            srcname = os.path.join(src, name) 
            dstname = os.path.join(dst, name) 
                    
            if os.path.isdir(srcname): 
                if level < 3:
                    log.info("Copying %s..." % srcname)
                self._copy_folder(log, level+1, srcname, dstname)             
            else: 
                shutil.copy(srcname, dstname)
                log.debug("Copy %s -> %s" % (srcname, dstname))
                # if the file extension is sh, set executable permissions
                if dstname.endswith(".sh") or dstname.endswith(".bat"):
                    # make it readable and executable for everybody
                    os.chmod(dstname, 0777)
                    log.debug("CHMOD 777 %s" % dstname)
        
        
    
    def update_pipeline_config(self, log, shotgun_pc_data, current_studio_paths, new_studio_paths ):
        """
        Update the studio pointer for a PC, if it is matching.
        """
        storage_map = {"linux2": "linux_path", "win32": "windows_path", "darwin": "mac_path" }
        
        log.info("")
        log.info("Analyzing Config %s:%s..." % (shotgun_pc_data["project"]["name"], 
                                                                shotgun_pc_data["code"]))                
        
        local_pc_path = shotgun_pc_data.get(storage_map[sys.platform])
        
        if local_pc_path is None:
            log.error("> This configuration is not defined for the current OS. Please update by hand. ")
            return
                
        if not os.path.exists(local_pc_path):
            log.error(">The location '%s' does not exist on disk! Skipping." % local_pc_path)
            return
        
        studio_linkback_files = {"windows_path": os.path.join(local_pc_path, "install", "core", "core_Windows.cfg"), 
                                 "linux_path": os.path.join(local_pc_path, "install", "core", "core_Linux.cfg"), 
                                 "mac_path": os.path.join(local_pc_path, "install", "core", "core_Darwin.cfg")}
        
        # check if this PC has a studio link (checking one OS only, should be enough)
        if not os.path.exists(studio_linkback_files["windows_path"]):
            log.info("> This Config has its own API. No changes needed.")
            return
           
        # read in all the existing data
        current_studio_refs = {}
        for x in ["windows_path", "linux_path", "mac_path"]:
            try:
                fh = open(studio_linkback_files[x], "rt")
                data = fh.read().strip() # remove any whitespace, keep text
                # check if env vars are used in the files instead of explicit paths. Don't try
                # to magically figure anything out -- safer to have the user manually fix these! 
                # For example, you could have an env variable 
                # $STUDIO_TANK_PATH=/sgtk/software/shotgun/studio and your linkback file may just 
                # contain "$STUDIO_TANK_PATH" instead of an explicit path.
                # NOTE: This is only supported on Linux and OSX so we don't check for any 
                #       Windows-style %PATTERNS% here.
                if "$" in data:
                    log.warning("Your pipeline configuration '%s:%s' at '%s' is pointing to the core API "
                                "using an environment variable '%s' on '%s'. Please update the "
                                "environment variable (and the file if necessary) so it points to the new "
                                "studio location: '%s'!" % (shotgun_pc_data["project"]["name"], 
                                                            shotgun_pc_data["code"], 
                                                            studio_linkback_files[x], 
                                                            data, 
                                                            x.split("_")[0], 
                                                            new_studio_paths[x]))
                    
                if data in ["None", "undefined"]:
                    current_studio_refs[x] = None
                else:
                    current_studio_refs[x] = data
                fh.close()
            except Exception, e:
                log.warning("Could not read the file in %s: %s" % (studio_linkback_files[x], e))
            
        # now, for all storages that have a path, check if this path is matching
        # the previous studio path
        matching = True
        for x in ["windows_path", "linux_path", "mac_path"]:
            if current_studio_refs[x] and current_studio_refs[x] != current_studio_paths[x]:
                matching = False
        
        if not matching:
            log.info("> This config is not associated with the studio root you are moving. "
                     "It is using the following studio roots: %s" % str(current_studio_refs))
            return
            
        # all right, all looks good. Write new locations to the files.
        errors = False
        for x in ["windows_path", "linux_path", "mac_path"]:
            try:
                os.chmod(studio_linkback_files[x], 0666)
                fh = open(studio_linkback_files[x], "wt")
                fh.write(str(new_studio_paths[x]))
                fh.close()
            except Exception, e:
                log.error("> Could not update the file %s: %s" % (studio_linkback_files[x], e))
                errors = True
            else:
                log.debug("> Updated %s to point to %s..." % (new_studio_paths[x], studio_linkback_files[x]))
        
        if not errors:
            log.info("> Pipeline Config updated to point at new Studio location.")
    
    
    def run_interactive(self, log, args):
        if len(args) != 4:

            log.info("Syntax: move_studio_install current_path linux_path windows_path mac_path")
            log.info("")
            log.info("This command will move the main location of the Toolkit config.")
            log.info("")
            log.info("Specify the current location of your studio install in the first parameter. "
                     "Specify the new location for each platform in the subsequent parameters.")
            log.info("")
            log.info("You typically need to quote your paths, like this:")
            log.info("")
            log.info('> tank move_studio_install /projects/tank /tank_install/studio "p:\\tank_install\\studio" /tank_install/studio')
            log.info("")
            log.info("If you want to leave a platform blank, just just empty quotes:")
            log.info("")
            log.info('> tank move_studio_install "P:\\projects\\tank" "" "p:\\tank_install\\studio" ""')
            raise TankError("Wrong number of parameters!")
        
        current_path = args[0]
        linux_path = args[1]
        windows_path = args[2]
        mac_path = args[3]
        new_paths = {"mac_path": mac_path, 
                     "windows_path": windows_path, 
                     "linux_path": linux_path}
        storage_map = {"linux2": "linux_path", "win32": "windows_path", "darwin": "mac_path" }
        local_target_path = new_paths.get(storage_map[sys.platform])

        # basic checks
        if not os.path.exists(current_path):
            raise TankError("Path '%s' does not exist!" % current_path)
        
        if os.path.exists(local_target_path):
            raise TankError("The path %s already exists on disk!" % local_target_path)
        
        # probe for some key file
        if not pipelineconfig_utils.is_localized(current_path):
            raise TankError("Path '%s' does not look like an Toolkit install!" % current_path)
            
        # make sure this is NOT a PC
        pc_file = os.path.join(current_path, "config", "info.yml")
        if os.path.exists(pc_file):
            raise TankError("Path '%s' does not look like a pipeline configuration. Move it "
                            "using the move_configuration command instead!" % current_path)
                
        # now read in the pipeline_configuration.yml file
        # to find out the locations for all other platforms
        cfg_yml = os.path.join(current_path, "config", "core", "install_location.yml")
        if not os.path.exists(cfg_yml):
            raise TankError("Location metadata file '%s' missing!" % cfg_yml)
        fh = open(cfg_yml, "rt")
        try:
            data = yaml.load(fh)
        except Exception, e:
            raise TankError("Config file %s is invalid: %s" % (cfg_yml, e))
        finally:
            fh.close()
        
        current_paths = { "linux_path": data.get("Linux"), 
                         "windows_path": data.get("Windows"),
                         "mac_path": data.get("Darwin") }

        ######################################################################################
        
        
        log.info("Toolkit Core API Move Overview")
        log.info("--------------------------------------------------------------")
        log.info("")
        log.info("Current Linux Path:   %s" % current_paths["linux_path"])
        log.info("Current Windows Path: %s" % current_paths["windows_path"])
        log.info("Current Mac Path:     %s" % current_paths["mac_path"])
        log.info("")
        log.info("New Linux Path:       %s" % new_paths["linux_path"])
        log.info("New Windows Path:     %s" % new_paths["windows_path"])
        log.info("New Mac Path:         %s" % new_paths["mac_path"])
        log.info("")
        
        log.info("This will move the studio API location and update all connected projects"
                 "to point at this new location.")
        log.info("")
        
        val = raw_input("Are you sure you want to move your Core API? [Yes/No] ")
        if not val.lower().startswith("y"):
            raise TankError("Aborted by User.")

        
        # ok let's do it!
        
        # sanity check target folder
        parent_target = os.path.dirname(local_target_path)
        if not os.path.exists(parent_target):
            raise TankError("The path '%s' does not exist!" % parent_target)
        
        if not os.access(parent_target, os.W_OK|os.R_OK|os.X_OK):
            raise TankError("The permissions setting for '%s' is too strict. The current user "
                            "cannot create folders in this location." % parent_target)

        # first copy the data across
        old_umask = os.umask(0)
        try:

            log.info("Copying '%s' -> '%s'" % (current_path, local_target_path))            
            self._copy_folder(log, 0, current_path, local_target_path)
            
            sg_code_location = os.path.join(local_target_path, "config", "core", "install_location.yml")
            log.info("Updating cached locations in %s..." % sg_code_location)
            os.chmod(sg_code_location, 0666)
            fh = open(sg_code_location, "wt")
            fh.write("# Shotgun Pipeline Toolkit configuration file\n")
            fh.write("# This file reflects the paths in the pipeline configuration\n")
            fh.write("# entity which is associated with this location\n")
            fh.write("\n")
            fh.write("Windows: '%s'\n" % windows_path)
            fh.write("Darwin: '%s'\n" % mac_path)    
            fh.write("Linux: '%s'\n" % linux_path)                    
            fh.write("\n")
            fh.write("# End of file.\n")
            fh.close()

            # get all PCs, update the ones that are using this studio code.
            sg = shotgun.create_sg_connection()
            data = sg.find(constants.PIPELINE_CONFIGURATION_ENTITY, [],
                           ["code", "mac_path", "windows_path", "linux_path", "project"])
            
            for pc in data:                
                self.update_pipeline_config(log, pc, current_paths, new_paths)
                
                

        except Exception, e:
            raise TankError("Could not copy studio install! This may be because of system "
                            "permissions or system setup. This studio install will "
                            "still be functional, however data may have been partially copied "
                            "to '%s' so we recommend that that location is cleaned up. " 
                            "Error Details: %s" % (local_target_path, e))
        finally:
            os.umask(old_umask)
            

        # finally clean up the previous location
        log.info("Deleting original files...")
        self._cleanup_old_location(log, current_path)
        log.info("")
        log.info("All done! Your studio location has been successfully moved.")
        log.info("If you have added the studio level tank command to your PATH, "
                 "don't forget to change it to point at the new location.")
            
            
        
