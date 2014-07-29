# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

from ...errors import TankError
from .action_base import Action

import os
import sys
import textwrap
import uuid
import shutil
import stat
import tempfile
import datetime

from ...util import shotgun
from ...platform import constants
from ... import pipelineconfig
from ..zipfilehelper import unzip_file
from .. import util

from . import console_utils





class CoreLocalizeAction(Action):
    """
    Action to localize the Core API
    """
    def __init__(self):
        Action.__init__(self, 
                        "localize", 
                        Action.TK_INSTANCE, 
                        ("Installs the Core API into your current Configuration. This is typically "
                         "done when you want to test a Core API upgrade in an isolated way. If you "
                         "want to safely test an API upgrade, first clone your production configuration, "
                         "then run the localize command from your clone's tank command."), 
                        "Admin")
        
        # this method can be executed via the API
        self.supports_api = True
        

    def run_noninteractive(self, log, parameters):
        """
        API accessor
        """
        return self._run(log, True)
    
    def run_interactive(self, log, args):
        """
        Tank command accessor
        """
        if len(args) != 0:
            raise TankError("This command takes no arguments!")

        return self._run(log, False)
    
    def _run(self, log, suppress_prompts):
        """
        Actual execution payload
        """ 

        log.debug("Executing the localize command for %r" % self.tk)
        
        log.info("")
        if self.tk.pipeline_configuration.is_localized():
            raise TankError("Looks like your current pipeline configuration already has a local install of the core!")
        
        core_api_root = self.tk.pipeline_configuration.get_install_location()
        pc_root = self.tk.pipeline_configuration.get_path()
        
        log.info("This will copy the Core API in %s into the Pipeline configuration %s." % (core_api_root, 
                                                                                            pc_root) )
        log.info("")
        if suppress_prompts or console_utils.ask_yn_question("Do you want to proceed"):
            log.info("")
            
            source_core = os.path.join(core_api_root, "install", "core")
            target_core = os.path.join(pc_root, "install", "core")
            backup_location = os.path.join(pc_root, "install", "core.backup")
            
            # move this into backup location
            backup_folder_name = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(backup_location, backup_folder_name)
            log.debug("Backing up Core API: %s -> %s" % (target_core, backup_path))
            shutil.move(target_core, backup_path)                
            
            old_umask = os.umask(0)
            try:
                
                # copy core distro
                log.info("Localizing Core: %s -> %s" % (source_core, target_core))
                util._copy_folder(log, source_core, target_core)
                
                # copy some core config files across
                log.info("Copying Core Configuration Files...")
                file_names = ["app_store.yml", 
                              "shotgun.yml", 
                              "interpreter_Darwin.cfg", 
                              "interpreter_Linux.cfg", 
                              "interpreter_Windows.cfg"]
                for fn in file_names:
                    src = os.path.join(core_api_root, "config", "core", fn)
                    tgt = os.path.join(pc_root, "config", "core", fn)
                    log.debug("Copy %s -> %s" % (src, tgt))
                    shutil.copy(src, tgt)
                    
                # copy apps, engines, frameworks
                source_apps = os.path.join(core_api_root, "install", "apps")
                target_apps = os.path.join(pc_root, "install", "apps")
                log.info("Localizing Apps: %s -> %s" % (source_apps, target_apps))
                util._copy_folder(log, source_apps, target_apps)
                
                source_engines = os.path.join(core_api_root, "install", "engines")
                target_engines = os.path.join(pc_root, "install", "engines")
                log.info("Localizing Engines: %s -> %s" % (source_engines, target_engines))
                util._copy_folder(log, source_engines, target_engines)
    
                source_frameworks = os.path.join(core_api_root, "install", "frameworks")
                target_frameworks = os.path.join(pc_root, "install", "frameworks")
                log.info("Localizing Frameworks: %s -> %s" % (source_frameworks, target_frameworks))
                util._copy_folder(log, source_frameworks, target_frameworks)
                    
            except Exception, e:
                raise TankError("Could not localize: %s" % e)
            finally:
                os.umask(old_umask)
                
            log.info("The Core API was successfully localized.")
    
            log.info("")
            log.info("Localize complete! This pipeline configuration now has an independent API. "
                     "If you upgrade the API for this configuration (using the 'tank core' command), "
                     "no other configurations or projects will be affected.")
            log.info("")
            log.info("")
            
        else:
            log.info("Operation cancelled.")
            







    

class CoreRelocateAction(Action):
    """
    Action to take a localized core and move it out into an external location on disk.
    """
    def __init__(self):
        Action.__init__(self, 
                        "relocate_core", 
                        Action.TK_INSTANCE, 
                        ("When new projects are created, these are often created in a state where each project "
                         "maintains its own independent copy of the core API. This command allows you to take "
                         "the core for such a project and move it out into a separate location on disk. This "
                         "makes it possible to create a shared core, where several projects share a single copy "
                         "of the Core API. Note: if you already have a shared Core API that you would like this " 
                         "configuration to use, instead use the attach_core command."), 
                        "Admin")
        
        # this method can be executed via the API
        self.supports_api = True
        
        self.parameters = {}
        
        
        # note how the current platform's default value is None in order to make that required
        self.parameters["core_path_mac"] = { "description": ("The path on disk where the core API should be "
                                                             "installed on Macosx."),
                                               "default": ( None if sys.platform == "darwin" else "" ),
                                               "type": "str" }

        self.parameters["core_path_win"] = { "description": ("The path on disk where the core API should be "
                                                             "installed on Windows."),
                                               "default": ( None if sys.platform == "win32" else "" ),
                                               "type": "str" }

        self.parameters["core_path_linux"] = { "description": ("The path on disk where the core API should be "
                                                               "installed on Linux."),
                                               "default": ( None if sys.platform == "linux2" else "" ),
                                               "type": "str" }
        

    def run_noninteractive(self, log, parameters):
        """
        API accessor
        """
        
        # validate params and seed default values
        computed_params = self._validate_parameters(parameters)
        
        return self._run(log, 
                         computed_params["core_path_mac"], 
                         computed_params["core_path_win"], 
                         computed_params["core_path_linux"],
                         suppress_prompts=True)
    
    def run_interactive(self, log, args):
        """
        Tank command accessor
        """
        
        if len(args) != 3:
            log.info("Syntax: relocate_core linux_path windows_path mac_path")
            log.info("")
            log.info("This command is only relevant for configurations which maintain their "
                     "own copy of the Core API (so called localized configurations). For such configurations, "
                     "this command will move the embedded core API out into an external location on disk.")
            log.info("")
            log.info("You typically need to quote your paths, like this:")
            log.info("")
            log.info('> tank relocate_core "/mnt/shotgun/studio" "p:\\shotgun\\studio" "/mnt/shotgun/studio"')
            log.info("")
            log.info("If you want to leave a platform blank, just use empty quotes. For example, "
                     "if you want a setup which only works on windows, do like this: ")
            log.info("")
            log.info('> tank relocate_core "" "p:\\shotgun\\studio" ""')
            log.info("")
            raise TankError("Please specify three target locations!")
        
        linux_path = args[0]
        windows_path = args[1]
        mac_path = args[2]

        return self._run(log, mac_path, windows_path, linux_path, suppress_prompts=False)
    
    def _run(self, log, mac_path, windows_path, linux_path, suppress_prompts):
        """
        Actual execution payload
        """ 

        log.debug("Executing the relocate_core command for %r" % self.tk)
        log.debug("Mac path: '%s'" % mac_path)
        log.debug("Windows path: '%s'" % windows_path)
        log.debug("Linux path: '%s'" % linux_path)
        log.info("")
        
        # some basic checks first
        if not self.tk.pipeline_configuration.is_localized():
            raise TankError("Looks like your current pipeline configuration is not localized and therefore "
                            "does not contain its own copy of the Core API!")
        
        # we need to have at least a path for the current os, otherwise we cannot introspect the API
        lookup = {"win32": windows_path, "linux2": linux_path, "darwin": mac_path}
        new_core_path_local = lookup[sys.platform] 
        
        if not new_core_path_local:
            raise TankError("You must specify a path to the core API for your current operating system.")
        
        pc_root = self.tk.pipeline_configuration.get_path()
        
        log.info("This will move the embedded core API in the configuration '%s'." % pc_root )
        log.info("After this command has completed, the configuration will not contain an "
                 "embedded copy of the core but instead it will be picked up from "
                 "the following locations:")
        log.info("")
        log.info(" - Linux: '%s'" % linux_path if linux_path else " - Linux: Not supported") 
        log.info(" - Windows: '%s'" % windows_path if windows_path else " - Windows: Not supported")
        log.info(" - Mac: '%s'" % mac_path if mac_path else " - Mac: Not supported")
        log.info("")
        
        if suppress_prompts or console_utils.ask_yn_question("Do you want to proceed"):
            log.info("")
            
            old_umask = os.umask(0)
            try:
            
                # first make the basic structure
                log.info("Setting up base structure...")
                os.mkdir(new_core_path_local, 0775)
                
                # copy across the tank commands
                shutil.copy(os.path.join(pc_root, "tank"), os.path.join(new_core_path_local, "tank"))
                shutil.copy(os.path.join(pc_root, "tank.bat"), os.path.join(new_core_path_local, "tank.bat"))
                
                # make the config folder
                log.info("Copying configuration files...")
                os.mkdir(os.path.join(new_core_path_local, "config"), 0775)
                os.mkdir(os.path.join(new_core_path_local, "config", "core"), 0775)

                # copy key config files
                core_config_file_names = ["app_store.yml", 
                                          "shotgun.yml", 
                                          "interpreter_Darwin.cfg", 
                                          "interpreter_Linux.cfg", 
                                          "interpreter_Windows.cfg"]

                for fn in core_config_file_names:
                    log.debug("Copy %s..." % fn)
                    shutil.copy(os.path.join(pc_root, "config", "core", fn), 
                                os.path.join(new_core_path_local, "config", "core", fn))
                    
                # copy the install
                log.info("Copying core installation...")
                src_files = util._copy_folder(log, 
                                              os.path.join(pc_root, "install"), 
                                              os.path.join(new_core_path_local, "install"))
                                
                # now clear out the install location of the config
                log.info("Removing core from configuration...")
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

                # remove core config files
                for fn in core_config_file_names:
                    path = os.path.join(pc_root, "config", "core", fn)
                    if os.path.exists(path):
                        os.chmod(path, 0666)
                        log.debug("Removing system file %s" % path )
                        os.remove(path)
                
                # create the install_location.yml file
                log.info("Creating install location file...")
                core_path = os.path.join(new_core_path_local, "config", "core", "install_location.yml")
                fh = open(core_path, "wt")
                fh.write("# Tank configuration file")
                fh.write("# This file was automatically created")
                fh.write("")
                fh.write("# This file stores the location on disk where this")
                fh.write("# configuration is located. It is needed to ensure")
                fh.write("# that deployment works correctly on all os platforms.")
                fh.write("Windows: '%s'" % windows_path if windows_path else "undefined_location")
                fh.write("Darwin: '%s'" % mac_path if mac_path else "undefined_location")
                fh.write("Linux: '%s'" % linux_path if linux_path else "undefined_location")
                fh.write("# End of file.")
                
                
                               

            except Exception, e:
                raise TankError("Could not unlocalize: %s" % e)
            finally:
                os.umask(old_umask)
                
            log.info("The Core API was successfully unlocalized.")    
            log.info("")
            
        else:
            log.info("Operation cancelled.")
            
            
            
            
            
            
            
            







class CoreAttachAction(Action):
    """
    Action to take a localized core and move it out into an external location on disk.
    """
    def __init__(self):
        Action.__init__(self, 
                        "attach_to_core", 
                        Action.TK_INSTANCE, 
                        ("When new projects are created, these are often created in a state where each project "
                         "maintains its own independent copy of the core API. This command allows you to take "
                         "the core for such a project and move it out into a separate location on disk. This "
                         "makes it possible to create a shared core, where several projects share a single copy "
                         "of the Core API. Note: if you already have a shared Core API that you would like this " 
                         "configuration to use, instead use the attach_core command."), 
                        "Admin")
        
        # this method can be executed via the API
        self.supports_api = True
        
        self.parameters = {}
        
        
        # note how the current platform's default value is None in order to make that required
        self.parameters["core_path_mac"] = { "description": ("The path on disk where the core API should be "
                                                             "installed on Macosx."),
                                               "default": ( None if sys.platform == "darwin" else "" ),
                                               "type": "str" }

        self.parameters["core_path_win"] = { "description": ("The path on disk where the core API should be "
                                                             "installed on Windows."),
                                               "default": ( None if sys.platform == "win32" else "" ),
                                               "type": "str" }

        self.parameters["core_path_linux"] = { "description": ("The path on disk where the core API should be "
                                                               "installed on Linux."),
                                               "default": ( None if sys.platform == "linux2" else "" ),
                                               "type": "str" }
        

    def run_noninteractive(self, log, parameters):
        """
        API accessor
        """
        
        # validate params and seed default values
        computed_params = self._validate_parameters(parameters)
        
        return self._run(log, 
                         computed_params["core_path_mac"], 
                         computed_params["core_path_win"], 
                         computed_params["core_path_linux"],
                         suppress_prompts=True)
    
    def run_interactive(self, log, args):
        """
        Tank command accessor
        """
        
        if len(args) != 3:
            log.info("Syntax: relocate_core linux_path windows_path mac_path")
            log.info("")
            log.info("This command is only relevant for configurations which maintain their "
                     "own copy of the Core API (so called localized configurations). For such configurations, "
                     "this command will move the embedded core API out into an external location on disk.")
            log.info("")
            log.info("You typically need to quote your paths, like this:")
            log.info("")
            log.info('> tank unlocalize "/mnt/shotgun/studio" "p:\\shotgun\\studio" "/mnt/shotgun/studio"')
            log.info("")
            log.info("If you want to leave a platform blank, just use empty quotes. For example, "
                     "if you want a setup which only works on windows, do like this: ")
            log.info("")
            log.info('> tank unlocalize "" "p:\\shotgun\\studio" ""')
            log.info("")
            raise TankError("Please specify three target locations!")
        
        linux_path = args[0]
        windows_path = args[1]
        mac_path = args[2]

        return self._run(log, mac_path, windows_path, linux_path, suppress_prompts=False)
    
    def _run(self, log, mac_path, windows_path, linux_path, suppress_prompts):
        """
        Actual execution payload
        """ 

        log.debug("Executing the relocate_core command for %r" % self.tk)
        log.debug("Mac path: '%s'" % mac_path)
        log.debug("Windows path: '%s'" % windows_path)
        log.debug("Linux path: '%s'" % linux_path)
        log.info("")
        
        # some basic checks first
        if not self.tk.pipeline_configuration.is_localized():
            raise TankError("Looks like your current pipeline configuration is not localized and therefore "
                            "does not contain its own copy of the Core API!")
        
        # we need to have at least a path for the current os, otherwise we cannot introspect the API
        lookup = {"win32": windows_path, "linux2": linux_path, "darwin": mac_path}
        new_core_path_local = lookup[sys.platform] 
        
        if not new_core_path_local:
            raise TankError("You must specify a path to the core API for your current operating system.")
        
        if not os.path.exists(new_core_path_local):
            raise TankError("The core '%s' cannot be found!" % new_core_path_local)
        
        # check that there is a new_core_path_local/install/core
        if not os.path.exists(os.path.join(new_core_path_local, "install", "core")):
            raise TankError("The core '%s' does not seem to point to a core API location or localized"
                            "pipeline configuration!" % new_core_path_local)
        
        
        
        pc_root = self.tk.pipeline_configuration.get_path()
        
        log.info("This will unlocalize '%s'." % pc_root )
        log.info("After this command has completed, the core API will be picked up from "
                 "the following locations:")
        log.info("")
        log.info(" - Linux: '%s'" % linux_path if linux_path else " - Linux: Not supported") 
        log.info(" - Windows: '%s'" % windows_path if windows_path else " - Windows: Not supported")
        log.info(" - Mac: '%s'" % mac_path if mac_path else " - Mac: Not supported")
        log.info("")
        
        if suppress_prompts or console_utils.ask_yn_question("Do you want to proceed"):
            log.info("")
            
            # back up current core API
            target_core = os.path.join(pc_root, "install", "core")
            backup_location = os.path.join(pc_root, "install", "core.backup")
            
            # move this into backup location
            backup_folder_name = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(backup_location, backup_folder_name)
            log.info("Backing up Core API: %s -> %s" % (target_core, backup_path))
            src_files = util._copy_folder(log, target_core, backup_path)
            
            # now clear out the install location
            log.debug("Clearing out target location...")
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

                        
            old_umask = os.umask(0)
            try:
                
                # remove core config files
                log.info("Removing Core Configuration Files...")
                file_names = ["app_store.yml", 
                              "shotgun.yml", 
                              "interpreter_Darwin.cfg", 
                              "interpreter_Linux.cfg", 
                              "interpreter_Windows.cfg"]
                for fn in file_names:
                    path = os.path.join(pc_root, "config", "core", fn)
                    if os.path.exists(path):
                        os.chmod(path, 0666)
                        log.debug("Removing system file %s" % path )
                        os.remove(path)
                
                # copy the python stubs
                log.info("Copying python stubs...")
                os.mkdir(os.path.join(pc_root, "install", "core"), 0777)
                tank_proxy = os.path.join(new_core_path_local, "install", "core", "setup", "tank_api_proxy")
                util._copy_folder(log, tank_proxy, os.path.join(pc_root, "install", "core", "python"))
                    
                # specify the parent files in install/core/core_PLATFORM.cfg
                log.info("Creating core redirection config files...")

                core_path = os.path.join(pc_root, "install", "core", "core_Darwin.cfg")
                fh = open(core_path, "wt")
                if mac_path:
                    fh.write(mac_path)
                else:
                    fh.write("undefined")
                fh.close()
                
                core_path = os.path.join(pc_root, "install", "core", "core_Linux.cfg")
                fh = open(core_path, "wt")
                if linux_path:
                    fh.write(linux_path)
                else:
                    fh.write("undefined")
                fh.close()

                core_path = os.path.join(pc_root, "install", "core", "core_Windows.cfg")
                fh = open(core_path, "wt")
                if windows_path:
                    fh.write(windows_path)
                else:
                    fh.write("undefined")
                fh.close()

            except Exception, e:
                raise TankError("Could not unlocalize: %s" % e)
            finally:
                os.umask(old_umask)
                
            log.info("The Core API was successfully unlocalized.")    
            log.info("")
            
        else:
            log.info("Operation cancelled.")
            






