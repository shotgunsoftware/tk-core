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
Methods for handling of the tank command

"""

from ...errors import TankError

from .. import setup_project
from .. import validate_config
from .. import core_api_admin
from ... import path_cache

from .action_base import Action

import code
import sys
import os

             
class SetupProjectAction(Action):
    
    def __init__(self):
        Action.__init__(self, 
                        "setup_project", 
                        Action.GLOBAL, 
                        "Sets up a new project with the Shotgun Pipeline Toolkit.", 
                        "Configuration")
        
    def run(self, log, args):
        if len(args) not in [0, 1]:
            raise TankError("Syntax: setup_project [--no-storage-check] [--force]")
        
        check_storage_path_exists = True
        force = False
        
        if len(args) == 1 and args[0] == "--no-storage-check":
            check_storage_path_exists = False
            log.info("no-storage-check mode: Will not verify that the storage exists. This "
                     "can be useful if the storage is pointing directly at a server via a "
                     "Windows UNC mapping.")
            
        if len(args) == 1 and args[0] == "--force":
            force = True
            log.info("force mode: Projects already set up with Toolkit can be set up again.")

        elif len(args) == 1 and args[0] not in ["--no-storage-check", "--force"]:
            raise TankError("Syntax: setup_project [--no-storage-check] [--force]")
            
            check_storage_path_exists = False
        setup_project.interactive_setup(log, self.code_install_root, check_storage_path_exists, force)
        
        
class CoreUpgradeAction(Action):
    
    def __init__(self):
        Action.__init__(self, 
                        "core", 
                        Action.GLOBAL, 
                        "Checks that your Toolkit Core API install is up to date.", 
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


class ClearCacheAction(Action):
    
    def __init__(self):
        Action.__init__(self, 
                        "clear_cache", 
                        Action.PC_LOCAL, 
                        ("Clears the Shotgun Menu Cache associated with this Configuration. "
                         "This is sometimes useful after complex configuration changes if new "
                         "or modified Toolkit menu items are not appearing inside Shotgun."), 
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
        

class SynchronizePathCache(Action):
    
    def __init__(self):
        Action.__init__(self, 
                        "sync_path_cache", 
                        Action.PC_LOCAL, 
                        ("Ensures that the local path cache file is up to date with Shotgun. Run "
                         "with a --full option to force a full resync."), 
                        "Admin")
    
    def run(self, log, args):
        
        if len(args) == 1 and args[1] == "--full":
            force = True
        
        elif len(args) == 0:
            force = False
            
        else:
            raise TankError("Syntax: sync_path_cache [--full]!")
        
        log.info("Ensuring the path cache file is up to date...")
        log.info("Will try to do an incremental sync. If you want to force a complete resync "
                 "to happen, run this command with a --full flag.")
        if force:
            log.info("Doing a full sync.")
        pc = path_cache.PathCache(self.tk)
        pc.synchronize(log, force)
        log.info("The path cache has been synchronized.")


class InteractiveShellAction(Action):
    
    def __init__(self):
        Action.__init__(self, 
                        "shell", 
                        Action.PC_LOCAL, 
                        "Starts an interactive Python shell for the current location.", 
                        "Developer")
        
        # hint that the shell engine should be started for this action, if possible
        self.wants_running_shell_engine = True
        
    def run(self, log, args):

        if len(args) != 0:
            raise TankError("This command takes no arguments!")
            
        msg = []
        msg.append("Welcome to Shotgun Pipeline Toolkit Python!")
        msg.append(sys.version)
        msg.append("Running on %s" % sys.platform)
        msg.append("")
            
        tk_locals = {}

        # add sgtk module to locals:
        import sgtk
        tk_locals["sgtk"] = sgtk

        # add some useful variables:
        if self.tk:
            tk_locals["tk"] = self.tk
            tk_locals["shotgun"] = self.tk.shotgun
            msg.append("- A tk API handle is available via the tk variable")
            msg.append("- A Shotgun API handle is available via the shotgun variable")
        
        if self.context:
            tk_locals["context"] = self.context
            msg.append("- Your current context is stored in the context variable")
            
        if self.engine:
            tk_locals["engine"] = self.engine
            msg.append("- The shell engine can be accessed via the engine variable")
            
        # attempt install tab command completion
        try:
            import rlcompleter
            import readline
        
            if "libedit" in readline.__doc__:
                # macosx, some versions - see 
                # http://stackoverflow.com/questions/7116038
                readline.parse_and_bind("bind ^I rl_complete")
            else:
                readline.parse_and_bind("tab: complete")
        except:
            pass        
        
        code.interact(banner = "\n".join(msg), local=tk_locals)
        
        
