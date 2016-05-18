# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

from ..util import filesystem
from . import constants
from ..errors import TankError
from ..pipelineconfig import PipelineConfiguration

from . import console_utils

from .action_base import Action

from ..util import ShotgunPath

import os
import datetime
import shutil

# core configuration files which are associated with the core API installation and not
# the pipeline configuration.
CORE_API_FILES = ["interpreter_Linux.cfg", 
                  "interpreter_Windows.cfg",
                  "interpreter_Darwin.cfg", 
                  "shotgun.yml"]

# core configuration files which are associated with a particular
# pipeline config and should not be moved
CORE_PC_FILES = ["install_location.yml", "pipeline_configuration.yml"]



class PushPCAction(Action):
    """
    Action that pushes a config from one pipeline configuration up to its parent
    """
    def __init__(self):
        Action.__init__(self, 
                        "push_configuration", 
                        Action.TK_INSTANCE, 
                        ("Pushes any configuration changes made here to another configuration. "
                         "This is typically used when you have cloned your production configuration "
                         "into a staging sandbox, updated the apps in this sandbox and want to push "
                         "those updates back to your production configuration."), 
                        "Configuration")
        
    def run_interactive(self, log, args):

        # get list of all PCs for this project
        if self.tk.pipeline_configuration.is_site_configuration():
            raise TankError("You can't push the site configuration.")

        if self.tk.pipeline_configuration.is_unmanaged():
            raise TankError("You can't push an unmanaged configuration.")

        project_id = self.tk.pipeline_configuration.get_project_id()

        current_pc_name = self.tk.pipeline_configuration.get_name()
        current_pc_id = self.tk.pipeline_configuration.get_shotgun_id()
        pipeline_configs = self.tk.shotgun.find(constants.PIPELINE_CONFIGURATION_ENTITY,
                                                [["project", "is", {"type": "Project", "id": project_id}]],
                                                ["code", "linux_path", "windows_path", "mac_path"])

        if len(args) == 1 and args[0] == "--symlink":
            use_symlink = True
        else:
            use_symlink = False
        
        if len(pipeline_configs) == 1:
            raise TankError("Only one pipeline configuration for this project! Need at least two "
                            "configurations in order to push. Please start by cloning a pipeline "
                            "configuration inside of Shotgun.")

    
        log.info("This command will push the configuration in the current pipeline configuration "
                 "('%s') to another pipeline configuration in the project. By default, the data "
                 "will be copied to the target config folder. If pass a --symlink parameter, it will "
                 "create a symlink instead." % current_pc_name) 
                 
        log.info("")
        log.info("Your existing configuration will be backed up.")
        
        if use_symlink:
            log.info("")
            log.info("A symlink will be used.")
        
        log.info("")
        
        log.info("The following pipeline configurations are available to push to:")
        path_hash = {}
        for pc in pipeline_configs:
            # skip self
            if pc["id"] == current_pc_id:
                continue
            local_path = ShotgunPath.from_shotgun_dict(pc).current_os
            path_hash[pc["id"]] = local_path
            log.info(" - [%d] %s (%s)" % (pc["id"], pc["code"], local_path))
        log.info("")
        
        answer = raw_input("Please type in the id of the configuration to push to (ENTER to exit): " )
        if answer == "":
            raise TankError("Aborted by user.")
        try:
            target_pc_id = int(answer)
        except:
            raise TankError("Please enter a number!")
        
        if target_pc_id not in [ x["id"] for x in pipeline_configs]:
            raise TankError("Id was not found in the list!")

        target_pc_path = path_hash[target_pc_id]
        target_pc = PipelineConfiguration(target_pc_path)
        
        # check that both pcs are using the same core version
        target_core_version = target_pc.get_associated_core_version()
        source_core_version = self.tk.pipeline_configuration.get_associated_core_version()
        
        if target_core_version != source_core_version:
            raise TankError("The configuration you are pushing to is using Core API %s and "
                            "the configuration you are pushing from is using Core API %s. "
                            "This is not supported - before pushing the changes, make sure "
                            "that both configurations are using the "
                            "same Core API!" % (target_core_version, source_core_version))
        
        # check that there are no dev descriptors
        dev_desc = None
        for env_name in self.tk.pipeline_configuration.get_environments():
            env = self.tk.pipeline_configuration.get_environment(env_name)
            for eng in env.get_engines():
                desc = env.get_engine_descriptor(eng)
                if desc.is_dev():
                    dev_desc = desc
                    break
                for app in env.get_apps(eng):
                    desc = env.get_app_descriptor(eng, app)
                    if desc.is_dev():
                        dev_desc = desc
                        break
        if dev_desc:
            log.warning("Looks like you have one or more dev locations set up in your "
                        "configuration! We strongly recommend that you do not use dev locations "
                        "in any production based configs. Dev descriptors are for development "
                        "purposes only. You can easily switch a dev location using the "
                        "'tank switch_app' command.")
            if not console_utils.ask_yn_question("Okay to proceed?"):
                raise TankError("Aborted.")
        
        date_suffix = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        source_path = os.path.join(self.tk.pipeline_configuration.get_path(), "config")
        target_tmp_path = os.path.join(target_pc_path, "config.tmp.%s" % date_suffix)
        symlink_path = os.path.join(target_pc_path, "config.%s" % date_suffix)
        target_path = os.path.join(target_pc_path, "config")
        target_backup_path = os.path.join(target_pc_path, "config.bak.%s" % date_suffix)

        log.debug("Will push the config from %s to %s" % (source_path, target_path))
        log.info("Hold on, pushing config...")
        
        
        ##########################################################################################
        # I/O phase
        old_umask = os.umask(0)
        try:
        
            # copy to temp location
            try:
                # copy everything!
                log.debug("Copying %s -> %s" % (source_path, target_tmp_path))
                filesystem.copy_folder(source_path, target_tmp_path)
                
                # If the source and target configurations are both localized, then also copy the
                # core-related api files to the target config. Otherwise, skip them.
                copy_core_related_files = (self.tk.pipeline_configuration.is_localized() and
                                           target_pc.is_localized())

                # CORE_PC_FILES are specific to the pipeline configuration so we shouldn't copy them
                if copy_core_related_files:
                    core_files_to_remove = CORE_PC_FILES
                else:
                    core_files_to_remove = CORE_API_FILES + CORE_PC_FILES

                if self.tk.pipeline_configuration.is_localized() and not target_pc.is_localized():
                    log.warning("The source configuration contains a local core but the target "
                                "configuration uses a shared core. The following core-related api "
                                "files will not be copied to the target configuration: "
                                "%s" % CORE_API_FILES)

                # unlock and remove all the special core files from the temp dir so they aren't
                # copied to the target
                for core_file in core_files_to_remove:
                    path = os.path.join(target_tmp_path, "core", core_file)
                    if os.path.exists(path):
                        os.chmod(path, 0666)
                        log.debug("Removing system file %s" % path )
                        os.remove(path)
                
                # copy the pc specific special core files from target config to new config temp dir
                # in order to preserve them
                for core_file in CORE_PC_FILES:
                    curr_config_path = os.path.join(target_path, "core", core_file)
                    new_config_path = os.path.join(target_tmp_path, "core", core_file)
                    log.debug("Copying PC system file %s -> %s" % (curr_config_path, new_config_path) )
                    shutil.copy(curr_config_path, new_config_path)
                
            except Exception, e:
                raise TankError("Could not copy into temporary target folder '%s'. The target config "
                                "has not been altered. Check permissions and try again! "
                                "Error reported: %s" % (target_tmp_path, e))
            
            # backup original config
            try:
                if os.path.islink(target_path):
                    # if we are symlinked, no need to back up
                    # just delete the current symlink
                    os.remove(target_path)
                    created_backup = False
                else:
                    # move data to backup folder
                    shutil.move(target_path, target_backup_path)
                    created_backup = True
            except Exception, e:
                raise TankError("Could not move target folder from '%s' to '%s'. "
                                "Error reported: %s" % (target_path, target_backup_path, e))
                
            # lastly, move new config into place
            if use_symlink:
                try:
                    shutil.move(target_tmp_path, symlink_path)
                    os.symlink(os.path.basename(symlink_path), target_path)
                except Exception, e:
                    raise TankError("Could not move new config folder from '%s' to '%s' or create symlink."
                                    "Error reported: %s" % (target_tmp_path, symlink_path, e))                
            else:
                try:
                    shutil.move(target_tmp_path, target_path)
                except Exception, e:
                    raise TankError("Could not move new config folder from '%s' to '%s'. "
                                    "Error reported: %s" % (target_tmp_path, target_path, e))
        
        finally:
            os.umask(old_umask)
        
        ##########################################################################################
        # Post Process Phase
        
        # now download all apps
        log.info("Checking if there are any apps that need downloading...")        
        for env_name in target_pc.get_environments():
            env = target_pc.get_environment(env_name)
            for eng in env.get_engines():
                desc = env.get_engine_descriptor(eng)
                if not desc.exists_local():
                    log.info("Downloading Engine %s..." % eng)
                    desc.download_local()
                for app in env.get_apps(eng):
                    desc = env.get_app_descriptor(eng, app)
                    if not desc.exists_local():
                        log.info("Downloading App %s..." % app)
                        desc.download_local()

        log.info("Push Complete!")
        log.info("")
        if created_backup:
            log.info("Your old configuration has been backed up into the following folder: %s" % target_backup_path)
        log.info("")
        

