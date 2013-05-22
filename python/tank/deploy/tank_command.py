"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Methods for handling of the tank command

"""

from . import descriptor
from . import util
from .descriptor import AppDescriptor
from ..util import shotgun
from ..platform import constants
from ..platform import validation
from ..platform.engine import start_engine, get_environment_from_context
from .. import pipelineconfig
from ..errors import TankError, TankEngineInitError
from ..api import Tank
from .. import folder

from . import setup_project, validate_config, administrator, core_api_admin, env_admin

from tank_vendor import yaml

import sys
import os
import shutil

################################################################################################

class Action(object):
    """
    Describes an executable action
    """
    
    # GLOBAL - works everywhere, requires self.code_install_root only
    # PC_LOCAL - works when a PC exists. requires GLOBAL + self.pipeline_config_root + self.tk
    # CTX - works when a context exists. requires PC_LOCAL + self.context
    # ENGINE - works when an engine exists. requires CTX + self.engine 
    GLOBAL, PC_LOCAL, CTX, ENGINE = range(4)
    
    def __init__(self, name, mode, description, category):
        self.name = name
        self.mode = mode
        self.description = description
        self.category = category
        
        # these need to be filled in by calling code prior to execution
        self.tk = None
        self.context = None
        self.engine = None
        self.code_install_root = None
        self.pipeline_config_root = None
        
    def __repr__(self):
        
        mode_str = "UNKNOWN"
        if self.mode == Action.GLOBAL:
            mode_str = "GLOBAL"
        elif self.mode == Action.PC_LOCAL:
            mode_str = "PC_LOCAL"
        elif self.mode == Action.CTX:
            mode_str = "CTX"
        elif self.mode == Action.ENGINE:
            mode_str = "ENGINE"
        
        return "<Action Cmd: '%s' Category: '%s' MODE:%s>" % (self.name, self.category, mode_str)
            
        
    def run(self, log, args):
        raise Exception("Need to implement this")
             
################################################################################################             
             
class SetupProjectAction(Action):
    
    def __init__(self):
        Action.__init__(self, 
                        "setup_project", 
                        Action.GLOBAL, 
                        "Sets up a new project with Tank.", 
                        "Configuration")
        
    def run(self, log, args):
        if len(args) != 0:
            raise TankError("This command takes no arguments!")
        setup_project.interactive_setup(log, self.code_install_root)
        
################################################################################################
        
class CoreUpgradeAction(Action):
    
    def __init__(self):
        Action.__init__(self, 
                        "core", 
                        Action.GLOBAL, 
                        "Checks that your Tank Core API install is up to date.", 
                        "Configuration")
            
    def run(self, log, args):
        if len(args) != 0:
            raise TankError("This command takes no arguments!")
        if self.code_install_root != self.pipeline_config_root:
            # we are updating a parent install that is shared
            log.info("")
            log.warning("You are potentially about to update the Core API for multiple projects.")
            log.info("")
        core_api_admin.interactive_update(log, self.code_install_root)
    
################################################################################################

class CoreLocalizeAction(Action):
    
    def __init__(self):
        Action.__init__(self, 
                        "localize", 
                        Action.PC_LOCAL, 
                        ("Installs the Core API into your current Configuration. This is typically "
                         "done when you want to test a Core API upgrade in an isolated way. If you "
                         "want to safely test an API upgrade, first clone your production configuration, "
                         "then run the localize command from your clone's tank command."), 
                        "Admin")
    
    def run(self, log, args):
        if len(args) != 0:
            raise TankError("This command takes no arguments!")
        core_api_admin.install_local_core(log, self.code_install_root, self.pipeline_config_root)

################################################################################################

class MovePCAction(Action):
    
    def __init__(self):
        Action.__init__(self, 
                        "move_configuration", 
                        Action.PC_LOCAL, 
                        ("Moves this configuration from its current disk location to a new location."), 
                        "Admin")
    
    def _cleanup_old_location(self, log, path):
        
        found_storage_lookup_file = False
        for root, dirs, files in os.walk(path, topdown=False):
            for name in files:
                if name == "tank_configs.yml":
                    found_storage_lookup_file = True
                    
                else:
                    full_path = os.path.join(root, name)
                    log.debug("Removing %s..." % full_path)
                    try:
                        os.remove(full_path)
                    except Exception, e:
                        log.warning("Could not delete file %s. Error Reported: %s" % (full_path, e))
                        
            for name in dirs:
                full_path = os.path.join(root, name)
                if found_storage_lookup_file and full_path == os.path.join(path, "config"):
                    log.debug("Not deleting folder %s since we have a storage lookup file" % full_path)
                    
                else:
                    log.debug("Deleting folder %s..." % full_path)
                    try:
                        os.rmdir(full_path)
                    except Exception, e:
                        log.warning("Could not remove folder %s. Error Reported: %s" % (full_path, e))
                            
    
    def _copy_folder(self, log, src, dst): 
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
                    
            if os.path.isdir(srcname): 
                files.extend( self._copy_folder(log, srcname, dstname) )             
            else: 
                if dstname.endswith("tank_configs.yml") and os.path.dirname(dstname).endswith("config"):
                    log.debug("NOT COPYING CONFIG FILE %s -> %s" % (srcname, dstname))
                else:
                    shutil.copy(srcname, dstname)
                    log.debug("Copy %s -> %s" % (srcname, dstname))
                    files.append(srcname)
                    # if the file extension is sh, set executable permissions
                    if dstname.endswith(".sh") or dstname.endswith(".bat"):
                        # make it readable and executable for everybody
                        os.chmod(dstname, 0777)
                        log.debug("CHMOD 777 %s" % dstname)
        
        return files
    
    
    def run(self, log, args):
        
        if len(args) != 3:
            log.info("Syntax: move_configuration linux_path windows_path mac_path")
            log.info("")
            log.info("You typically need to quote your paths, like this:")
            log.info("")
            log.info('> tank move_configuration "/linux_root/my_config" "p:\\configs\\my_config" "/mac_root/my_config"')
            log.info("")
            log.info("If you want to leave a platform blank, just just empty quotes. For example, "
                     "if you want a configuration which only works on windows, do like this: ")
            log.info("")
            log.info('> tank move_configuration "" "p:\\configs\\my_config" ""')
            raise TankError("Wrong number of parameters!")
        
        linux_path = args[0]
        windows_path = args[1]
        mac_path = args[2]
        new_paths = {"mac_path": mac_path, 
                     "windows_path": windows_path, 
                     "linux_path": linux_path}
        
        sg = shotgun.create_sg_connection()
        pipeline_config_id = self.tk.pipeline_configuration.get_shotgun_id()
        data = sg.find_one(constants.PIPELINE_CONFIGURATION_ENTITY, 
                           [["id", "is", pipeline_config_id]],
                           ["code", "mac_path", "windows_path", "linux_path"])
        
        if data is None:
            raise TankError("Could not find this Pipeline Configuration in Shotgun!")
        
        log.info("Overview of Configuration '%s'" % data.get("code"))
        log.info("--------------------------------------------------------------")
        log.info("")
        log.info("Current Linux Path:   %s" % data.get("linux_path"))
        log.info("Current Windows Path: %s" % data.get("windows_path"))
        log.info("Current Mac Path:     %s" % data.get("mac_path"))
        log.info("")
        log.info("New Linux Path:   %s" % linux_path)
        log.info("New Windows Path: %s" % windows_path)
        log.info("New Mac Path:     %s" % mac_path)
        log.info("")
        
        val = raw_input("Are you sure you want to move your configuration? [Yes/No] ")
        if not val.lower().startswith("y"):
            raise TankError("Aborted by User.")

        # ok let's do it!
        storage_map = {"linux2": "linux_path", "win32": "windows_path", "darwin": "mac_path" }
        local_source_path = data.get(storage_map[sys.platform])
        local_target_path = new_paths.get(storage_map[sys.platform])
        source_sg_code_location = os.path.join(local_source_path, "config", "core", "install_location.yml")
        
        if not os.path.exists(local_source_path):
            raise TankError("The path %s does not exist on disk!" % local_source_path)
        if os.path.exists(local_target_path):
            raise TankError("The path %s already exists on disk!" % local_target_path)
        if not os.path.exists(source_sg_code_location):
            raise TankError("The required config file %s does not exist on disk!" % source_sg_code_location)

        # also - we currently don't support moving PCs which have a localized API
        # (because these may be referred to by other PCs that are using their API
        # TODO: later on, support moving these. For now, just error out.
        api_file = os.path.join(local_source_path, "install", "core", "_core_upgrader.py")
        if not os.path.exists(api_file):
            raise TankError("Looks like the Configuration you are trying to move has a localized "
                            "API. This is not currently supported.")
        

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

            log.info("Copying '%s' -> '%s'" % (local_source_path, local_target_path))            
            self._copy_folder(log, local_source_path, local_target_path)
            
            sg_code_location = os.path.join(local_target_path, "config", "core", "install_location.yml")
            log.info("Updating cached locations in %s..." % sg_code_location)
            os.chmod(sg_code_location, 0666)
            fh = open(sg_code_location, "wt")
            fh.write("# Tank configuration file\n")
            fh.write("# This file reflects the paths in the pipeline configuration\n")
            fh.write("# entity which is associated with this location\n")
            fh.write("\n")
            fh.write("Windows: '%s'\n" % windows_path)
            fh.write("Darwin: '%s'\n" % mac_path)    
            fh.write("Linux: '%s'\n" % linux_path)                    
            fh.write("\n")
            fh.write("# End of file.\n")
            fh.close()    
            os.chmod(sg_code_location, 0444)        

            for r in self.tk.pipeline_configuration.get_data_roots().values():
                log.info("Updating storage root reference in %s.." % r)
                scm = pipelineconfig.StorageConfigurationMapping(r)
                scm.add_pipeline_configuration(mac_path, windows_path, linux_path)

        except Exception, e:
            raise TankError("Could not copy configuration! This may be because of system "
                            "permissions or system setup. This configuration will "
                            "still be functional, however data may have been partially copied "
                            "to '%s' so we recommend that that location is cleaned up. " 
                            "Error Details: %s" % (local_target_path, e))
        finally:
            os.umask(old_umask)
        
        log.info("Updating Shotgun Configuration Record...")
        sg.update(constants.PIPELINE_CONFIGURATION_ENTITY, pipeline_config_id, new_paths)
        
        # finally clean up the previous location
        log.info("Deleting original configuration files...")
        self._cleanup_old_location(log, local_source_path)
        log.info("")
        log.info("All done! Your configuration has been successfully moved.")
        
        
        
        

################################################################################################

class MoveStudioInstallAction(Action):
    
    def __init__(self):
        Action.__init__(self, 
                        "move_studio_install", 
                        Action.GLOBAL, 
                        ("Moves the studio code installation of Tank to a different location."), 
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
                            
    
    def _copy_folder(self, log, src, dst): 
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
                    
            if os.path.isdir(srcname): 
                files.extend( self._copy_folder(log, srcname, dstname) )             
            else: 
                shutil.copy(srcname, dstname)
                log.debug("Copy %s -> %s" % (srcname, dstname))
                files.append(srcname)
                # if the file extension is sh, set executable permissions
                if dstname.endswith(".sh") or dstname.endswith(".bat"):
                    # make it readable and executable for everybody
                    os.chmod(dstname, 0777)
                    log.debug("CHMOD 777 %s" % dstname)
        
        return files
    
    def update_pipeline_config(self, log, shotgun_pc_data, current_studio_paths, new_studio_paths ):
        """
        Update the studio pointer for a PC, if it is matching.
        """
        storage_map = {"linux2": "linux_path", "win32": "windows_path", "darwin": "mac_path" }
        
        log.info("")
        log.info("Analyzing Pipeline Configuration %s:%s..." % (shotgun_pc_data["project"]["name"], 
                                                                shotgun_pc_data["code"]))                
        
        local_pc_path = shotgun_pc_data.get(storage_map[sys.platform])
        
        if local_pc_path is None:
            log.error("This configuration is not defined for the current OS. Please update by hand. ")
            return
                
        if not os.path.exists(local_pc_path):
            log.error("The location '%s' does not exist on disk! Skipping." % local_pc_path)
            return
        
        studio_linkback_files = {"windows_path": os.path.join(local_pc_path, "install", "core", "core_Windows.cfg"), 
                                 "linux_path": os.path.join(local_pc_path, "install", "core", "core_Linux.cfg"), 
                                 "mac_path": os.path.join(local_pc_path, "install", "core", "core_Darwin.cfg")}
        
        # check if this PC has a studio link (checking one OS only, should be enough)
        if not os.path.exists(studio_linkback_files["windows_path"]):
            log.info("This Config has its own API. No changes needed.")
            return
           
        # read in all the existing data
        current_studio_refs = {}
        for x in ["windows_path", "linux_path", "mac_path"]:
            try:
                fh = open(studio_linkback_files[x], "wt")
                data = fh.read()
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
            log.info("This config is not associated with the studio root you are moving. "
                     "It is using the following studio roots: %s" % str(current_studio_refs))
            return
            
        # all right, all looks good. Write new locations to the files.
        for x in ["windows_path", "linux_path", "mac_path"]:
            try:
                fh = open(studio_linkback_files[x], "wt")
                fh.write(str(new_studio_paths[x]))
                fh.close()
            except Exception, e:
                log.error("Could not update the file %s: %s" % (studio_linkback_files[x], e))
            else:
                log.info("Updated %s to point to %s..." % (new_studio_paths[x], studio_linkback_files[x]))
    
    
    def run(self, log, args):
        if len(args) != 4:

            log.info("Syntax: move_studio_install current_path linux_path windows_path mac_path")
            log.info("")
            log.info("This command will move the main location of the Tank config.")
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
        
        # probe for some key file
        api_file = os.path.join(current_path, "install", "core", "_core_upgrader.py")
        if not os.path.exists(api_file):
            raise TankError("Path '%s' does not look like a tank install!" % current_path)
            
        # make sure this is NOT a PC
        pc_file = os.path.join(current_path, "config", "info.yml")
        if not os.path.exists(pc_file):
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
        
        
        log.info("Tank Core API Move Overview")
        log.info("--------------------------------------------------------------")
        log.info("")
        log.info("Current Linux Path:   %s" % current_paths["linux_path"])
        log.info("Current Windows Path:   %s" % current_paths["windows_path"])
        log.info("Current Mac Path:   %s" % current_paths["mac_path"])
        log.info("")
        log.info("New Linux Path:   %s" % new_paths["linux_path"])
        log.info("New Windows Path: %s" % new_paths["windows_path"])
        log.info("New Mac Path:     %s" % new_paths["mac_path"])
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
            self._copy_folder(log, current_path, local_target_path)
            
            sg_code_location = os.path.join(local_target_path, "config", "core", "install_location.yml")
            log.info("Updating cached locations in %s..." % sg_code_location)
            if os.path.exists(sg_code_location):
                os.chmod(sg_code_location, 0666)
            fh = open(sg_code_location, "wt")
            fh.write("# Tank configuration file\n")
            fh.write("# This file reflects the paths in the pipeline configuration\n")
            fh.write("# entity which is associated with this location\n")
            fh.write("\n")
            fh.write("Windows: '%s'\n" % windows_path)
            fh.write("Darwin: '%s'\n" % mac_path)    
            fh.write("Linux: '%s'\n" % linux_path)                    
            fh.write("\n")
            fh.write("# End of file.\n")
            fh.close()    
            os.chmod(sg_code_location, 0444)        

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
            
            
        

################################################################################################

class PCBreakdownAction(Action):
    
    def __init__(self):
        Action.__init__(self, 
                        "configurations", 
                        Action.PC_LOCAL, 
                        ("Shows an overview of the different configurations registered with this project."), 
                        "Admin")
    
    def run(self, log, args):
        if len(args) != 0:
            raise TankError("This command takes no arguments!")
        
        log.info("Fetching data from Shotgun...")
        project_id = self.tk.pipeline_configuration.get_project_id()
        
        sg = shotgun.create_sg_connection()
        
        proj_data = sg.find_one("Project", [["id", "is", project_id]], ["name"])
        log.info("")
        log.info("")
        log.info("=" * 70)
        log.info("Available Configurations for Project '%s'" % proj_data.get("name"))
        log.info("=" * 70)
        log.info("")
        
        data = sg.find(constants.PIPELINE_CONFIGURATION_ENTITY, 
                       [["project", "is", {"type": "Project", "id": project_id}]],
                       ["code", "users", "mac_path", "windows_path", "linux_path"])
        for d in data:
            
            if len(d.get("users")) == 0:
                log.info("Configuration '%s' (Public)" % d.get("code"))
            else:
                log.info("Configuration '%s' (Private)" % d.get("code"))
                
            log.info("-------------------------------------------------------")
            log.info("")
            
            if d.get("code") == constants.PRIMARY_PIPELINE_CONFIG_NAME:
                log.info("This is the Project Master Configuration. It will be used whenever "
                         "this project is accessed from a studio level tank command or API "
                         "constructor.")
            
            log.info("")
            lp = d.get("linux_path")
            mp = d.get("mac_path")
            wp = d.get("windows_path")
            if lp is None:
                lp = "[Not defined]"
            if wp is None:
                wp = "[Not defined]"
            if mp is None:
                mp = "[Not defined]"
            
            log.info("Linux Location:  %s" % lp )
            log.info("Winows Location: %s" % wp )
            log.info("Mac Location:    %s" % mp )
            log.info("")
            
            
            # check for core API etc. 
            storage_map = {"linux2": "linux_path", "win32": "windows_path", "darwin": "mac_path" }
            local_path = d.get(storage_map[sys.platform])
            if local_path is None:
                log.info("The Configuration is not accessible from this computer!")
                
            elif not os.path.exists(local_path):
                log.info("The Configuration cannot be found on disk!")
                
            else:
                # yay, exists on disk
                local_tank_command = os.path.join(local_path, "tank")
                
                if os.path.exists(os.path.join(local_path, "install", "core", "_core_upgrader.py")):
                    api_version = pipelineconfig.get_core_api_version_for_pc(local_path)
                    log.info("This configuration is running its own version (%s)"
                             " of the Tank API." % api_version)
                    log.info("If you want to check for core API updates you can run:")
                    log.info("> %s core" % local_tank_command)
                    log.info("")
                    
                else:
                    
                    log.info("This configuration is using a shared version of the Tank API."
                             "If you want it to run its own independent version "
                             "of the Tank Core API, you can run:")
                    log.info("> %s localize" % local_tank_command)
                    log.info("")
                
                log.info("If you want to check for app or engine updates, you can run:")
                log.info("> %s updates" % local_tank_command)
                log.info("")
            
                log.info("If you want to change the location of this configuration, you can run:")
                log.info("> %s move_configuration" % local_tank_command)
                log.info("")
            
            if len(d.get("users")) == 0:
                log.info("This is a public configuration. In Shotgun, the actions defined in this "
                         "configuration will be on all users' menus.")
            
            elif len(d.get("users")) == 1:
                log.info("This is a private configuration. In Shotgun, only %s will see the actions "
                         "defined in this config. If you want to add additional members to this "
                         "configuration, navigate to the Shotgun Pipeline Configuration Page "
                         "and add them to the Users field." % d.get("users")[0]["name"])
            
            elif len(d.get("users")) > 1:
                users = ", ".join( [u.get("name") for u in d.get("users")] )
                log.info("This is a private configuration. In Shotgun, the following users will see "
                         "the actions defined in this config: %s. If you want to add additional "
                         "members to this configuration, navigate to the Shotgun Pipeline "
                         "Configuration Page and add them to the Users field." % users)
            
            log.info("")
            log.info("")
        
        
################################################################################################        

class ValidateConfigAction(Action):
    
    def __init__(self):
        Action.__init__(self, 
                        "validate", 
                        Action.PC_LOCAL, 
                        ("Validates your current Configuration to check that all "
                        "environments have been correctly configured."), 
                        "Configuration")
    
    def run(self, log, args):
        if len(args) != 0:
            raise TankError("This command takes no arguments!")
        validate_config.validate_configuration(log, self.tk)

################################################################################################

class ClearCacheAction(Action):
    
    def __init__(self):
        Action.__init__(self, 
                        "clear_cache", 
                        Action.PC_LOCAL, 
                        ("Clears the Shotgun Menu Cache associated with this Configuration. "
                         "This is sometimes useful after complex configuration changes if new "
                         "or modified Tank menu items are not appearing inside Shotgun."), 
                        "Admin")
    
    def run(self, log, args):
        if len(args) != 0:
            raise TankError("This command takes no arguments!")
        
        cache_folder = self.tk.pipeline_configuration.get_cache_location()
        # cache files are on the form shotgun_mac_project.txt
        for f in os.listdir(cache_folder):
            if f.startswith("shotgun") and f.endswith(".txt"):
                full_path = os.path.join(cache_folder, f)
                log.debug("Deleting cache file %s..." % full_path)
                try:
                    os.remove(full_path)
                except:
                    log.warning("Could not delete cache file '%s'!" % full_path)
        
        log.info("The Shotgun menu cache has been cleared.")
        
################################################################################################

class InstallAppAction(Action):
    
    def __init__(self):
        Action.__init__(self, 
                        "install_app", 
                        Action.PC_LOCAL, 
                        "Adds a new app to your tank configuration.", 
                        "Configuration")
    
    def run(self, log, args):

        if len(args) != 3:
            
            log.info("Please specify an app to install and an environment to install it into!")
            log.info("The following environments exist in the current configuration: ")
            for e in self.tk.pipeline_configuration.get_environments():
                log.info(" - %s" % e)            
            log.info("")
            log.info("Syntax:  install_app environment_name engine_name app_name")
            log.info("Example: install_app asset tk-shell tk-multi-about")
            raise TankError("Invalid number of parameters.")

        env_name = args[0]
        engine_name = args[1]
        app_name = args[2]
        env_admin.install_app(log, self.tk, env_name, engine_name, app_name)

################################################################################################

class InstallEngineAction(Action):
    
    def __init__(self):
        Action.__init__(self, 
                        "install_engine", 
                        Action.PC_LOCAL, 
                        "Adds a new engine to your tank configuration.", 
                        "Configuration")
    
    def run(self, log, args):

        if len(args) != 2:
            log.info("Please specify an engine to install and an environment to install it into!")
            log.info("The following environments exist in the current configuration: ")
            for e in self.tk.pipeline_configuration.get_environments():
                log.info(" - %s" % e)            
            log.info("")
            log.info("Syntax:  install_engine environment_name engine_name")
            log.info("Example: install_engine asset tk-shell")
            raise TankError("Invalid number of parameters.")
                    
        env_name = args[0]
        engine_name = args[1]   
        env_admin.install_engine(log, self.tk, env_name, engine_name)

################################################################################################

class AppUpdatesAction(Action):
    
    def __init__(self):
        Action.__init__(self, 
                        "updates", 
                        Action.PC_LOCAL, 
                        "Checks if there are any app or engine updates for the current configuration.", 
                        "Configuration")
    
    def run(self, log, args):
        if len(args) != 0:
            raise TankError("Invalid arguments! Run with --help for more details.")
        env_admin.check_for_updates(log, self.tk)

################################################################################################

class CreateFoldersAction(Action):
    
    def __init__(self):
        Action.__init__(self, 
                        "folders", 
                        Action.CTX, 
                        ("Creates folders on disk for your current context. This command is "
                         "typically used in conjunction with a Shotgun entity, for example "
                         "'tank Shot P01 folders' in order to create folders on disk for Shot P01."), 
                        "Production")
    
    def run(self, log, args):
        if len(args) != 0:
            raise TankError("This command takes no arguments!")

        if self.context.project is None:
            log.info("Looks like your context is empty! No folders to create!")
            return

        # first do project
        entity_type = self.context.project["type"]
        entity_id = self.context.project["id"]
        # if there is an entity then that takes precedence
        if self.context.entity:
            entity_type = self.context.entity["type"]
            entity_id = self.context.entity["id"]
        # and if there is a task that is even better
        if self.context.task:
            entity_type = self.context.task["type"]
            entity_id = self.context.task["id"]
        
        log.info("Creating folders, stand by...")
        f = folder.process_filesystem_structure(self.tk, entity_type, entity_id, False, None)
        log.info("")
        log.info("The following items were processed:")
        for x in f:
            log.info(" - %s" % x)
        log.info("")
        log.info("In total, %s folders were processed." % len(f))
        log.info("")

################################################################################################

class PreviewFoldersAction(Action):
    
    def __init__(self):
        Action.__init__(self, 
                        "preview_folders", 
                        Action.CTX, 
                        ("Previews folders on disk for your current context. This command is "
                         "typically used in conjunction with a Shotgun entity, for example "
                         "'tank Shot P01 preview_folders' in order to show what folders "
                         "would be created if you ran the folders command for Shot P01."), 
                        "Production")
    
    def run(self, log, args):
        if len(args) != 0:
            raise TankError("This command takes no arguments!")

        if self.context.project is None:
            log.info("Looks like your context is empty! No folders to preview!")
            return

        # first do project
        entity_type = self.context.project["type"]
        entity_id = self.context.project["id"]
        # if there is an entity then that takes precedence
        if self.context.entity:
            entity_type = self.context.entity["type"]
            entity_id = self.context.entity["id"]
        # and if there is a task that is even better
        if self.context.task:
            entity_type = self.context.task["type"]
            entity_id = self.context.task["id"]

        log.info("Previewing folder creation, stand by...")
        f = folder.process_filesystem_structure(self.tk, entity_type, entity_id, True, None)
        log.info("")
        log.info("The following items were processed:")
        for x in f:
            log.info(" - %s" % x)
        log.info("")
        log.info("In total, %s folders were processed." % len(f))
        log.info("Note - this was a preview and no actual folders were created.")            


################################################################################################




BUILT_IN_ACTIONS = [SetupProjectAction, 
                    CoreUpgradeAction, 
                    CoreLocalizeAction,
                    ValidateConfigAction,
                    ClearCacheAction,
                    InstallAppAction,
                    InstallEngineAction,
                    AppUpdatesAction,
                    CreateFoldersAction,
                    PreviewFoldersAction,
                    MovePCAction,
                    PCBreakdownAction,
                    MoveStudioInstallAction
                    ]


def _get_built_in_actions():
    """
    Returns a list of built in actions
    """
    actions = []
    for ClassObj in BUILT_IN_ACTIONS:
        actions.append(ClassObj())
    return actions

###############################################################################################
# Shell engine tank commands

class ShellEngineAction(Action):
    """
    Action wrapper around a shell engine command
    """
    def __init__(self, name, description, command_key):
        Action.__init__(self, name, Action.ENGINE, description, "Shell Engine")
        self._command_key = command_key
    
    def run(self, log, args):        
        self.engine.execute_command(self._command_key, args)
        


def get_shell_engine_actions(engine_obj):
    """
    Returns a list of shell engine actions
    """
    
    actions = []
    for c in engine_obj.commands:    
        
        # custom properties dict
        props = engine_obj.commands[c]["properties"]
        
        # the properties dict contains some goodies here that we can use
        # look for a short_name, if that does not exist, fall back on the command name
        # prefix will hold a prefix that guarantees uniqueness, if needed
        cmd_name = c
        if "short_name" in props:
            if props["prefix"]:
                # need a prefix to produce a unique command
                cmd_name = "%s:%s" % (props["prefix"], props["short_name"])
            else:
                # unique without a prefix
                cmd_name = props["short_name"]
        
        description = engine_obj.commands[c]["properties"].get("description", "No description available.")

        actions.append(ShellEngineAction(cmd_name, description, c))

    return actions


###############################################################################################
# Hook based tank commands



def get_actions(log, tk, ctx):
    """
    Returns a list of Action objects given the current context, api etc.
    tk and ctx may be none, indicating that tank is running in a 'partial' state.
    """
    engine = None

    if tk is not None and ctx is not None:          
        # we have all the necessary pieces needed to start an engine
        
        # check if there is an environment object for our context
        env = get_environment_from_context(tk, ctx)
        log.debug("Probing for a shell engine. ctx '%s' --> environment '%s'" % (ctx, env))
        if env and constants.SHELL_ENGINE in env.get_engines():
            log.debug("Looks like the environment has a tk-shell engine. Trying to start it.")
            # we have an environment and a shell engine. Looking good.
            engine = start_engine(constants.SHELL_ENGINE, tk, ctx)        
            log.debug("Started engine %s" % engine)
            log.info("- Started Shell Engine version %s" % engine.version)
            log.info("- Environment: %s." % engine.environment["disk_location"])

        
    actions = []
    
    # get all actions regardless of current scope first
    all_actions = _get_built_in_actions()
    if engine:
        all_actions.extend( get_shell_engine_actions(engine) )
    
    # now only pick the ones that are working with our current state
    for a in all_actions:
        
        if a.mode == Action.GLOBAL:
            # globals are always possible to run
            actions.append(a)
        if tk and a.mode == Action.PC_LOCAL:
            # we have a PC!
            actions.append(a)
        if ctx and a.mode == Action.CTX:
            # we have a command that needs a context
            actions.append(a)
        if engine and a.mode == Action.ENGINE:
            # needs the engine
            actions.append(a)
        
    return (actions, engine)


def _process_action(code_install_root, pipeline_config_root, log, tk, ctx, engine, action, args):
    """
    Does the actual execution of an action object
    """
    # seed the action object with all the handles it may need
    action.tk = tk
    action.context = ctx
    action.engine = engine
    action.code_install_root = code_install_root
    action.pipeline_config_root = pipeline_config_root
    
    # now check that we actually have passed enough stuff to work with this mode
    if action.mode in (Action.PC_LOCAL, Action.CTX, Action.ENGINE) and tk is None:
        # we are missing a tk instance
        log.error("Trying to launch %r without a tank instance." % action)
        raise TankError("The command '%s' needs a project to run." % action.name)
    
    if action.mode in (Action.CTX, Action.ENGINE) and ctx is None:
        # we have a command that needs a context
        log.error("Trying to launch %r without a context." % action)
        raise TankError("The command '%s' needs a work area to run." % action.name)
        
    if action.mode == Action.ENGINE and engine is None:
        # we have a command that needs an engine
        log.error("Trying to launch %r without an engine." % action)
        raise TankError("The command '%s' needs the shell engine running." % action.name)
    
    # ok all good
    log.info("- Running %s..." % action.name)
    log.info("")
    return action.run(log, args)
    
    

def run_action(code_install_root, pipeline_config_root, log, tk, ctx, command, args):
    """
    Find an action and start execution
    """
    engine = None

    # first see if we can find the action without starting the engine
    found_action = None
    for x in _get_built_in_actions():
        if x.name == command:
            found_action = x
            break
    
    if found_action and found_action.mode != Action.ENGINE:
        log.debug("No need to load up the engine for this command.")
    else:
        # try to load the engine.
        if tk is not None and ctx is not None:          
            # we have all the necessary pieces needed to start an engine  
            # check if there is an environment object for our context
            env = get_environment_from_context(tk, ctx)
            log.debug("Probing for a shell engine. ctx '%s' --> environment '%s'" % (ctx, env))
            if env and constants.SHELL_ENGINE in env.get_engines():
                log.debug("Looks like the environment has a tk-shell engine. Trying to start it.")
                # we have an environment and a shell engine. Looking good.
                engine = start_engine(constants.SHELL_ENGINE, tk, ctx)        
                log.debug("Started engine %s" % engine)
                log.info("- Started Shell Engine version %s" % engine.version)
                log.info("- Environment: %s." % engine.environment["disk_location"])
                        
                # now keep looking for our command
                if found_action is None: # may already be found (a core cmd which needs and engine)
                    for x in get_shell_engine_actions(engine):
                        if x.name == command:
                            found_action = x
                            break
                    
    # ok we now have all the pieces we need
    if found_action is None:
        log.error("The command '%s' could not be found!" % command)
    
    else:
        _process_action(code_install_root, 
                        pipeline_config_root, 
                        log, 
                        tk, 
                        ctx, 
                        engine, 
                        found_action, args)
    
