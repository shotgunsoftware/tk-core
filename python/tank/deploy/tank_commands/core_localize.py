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
            







    

class CoreUnLocalizeAction(Action):
    """
    Action to unlocalize an already localized pipeline configuration.
    """
    def __init__(self):
        Action.__init__(self, 
                        "unlocalize", 
                        Action.TK_INSTANCE, 
                        ("Reverts a localized pipeline configuration so that it no longer maintains an independent "
                         "Core API. The API version you are reverting to must be equal to or more recent than the "
                         "existing localized API version. This command can be useful if you want to join a previously "
                         "independent setup with a larger studio configuration."), 
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

        log.debug("Executing the unlocalize command for %r" % self.tk)
        
