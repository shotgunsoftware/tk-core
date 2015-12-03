# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import sys
import os
import tempfile
import re
import uuid
from .action_base import Action
from ..zipfilehelper import unzip_file
from ...errors import TankError
from ...util import shotgun
from ...platform import constants

from .setup_project_core import synchronize_project

class SynchronizeConfigurationAction(Action):
    """
    Action that sets up a new Toolkit Project.
    
    This is the standard command that is exposed via the setup_project tank command
    and API equivalent.
    """    
    def __init__(self):
        """
        Constructor
        """
        Action.__init__(self, 
                        "synchronize", 
                        Action.TK_INSTANCE, 
                        "Synchronizes a pipeline configuration.", 
                        "Configuration")
        
        # this method can be executed via the API
        self.supports_api = True

        self._progress_cb = None

        self.parameters = {}
        
        self.parameters["pipeline_configuration"] = { "description": "Pipeline config id to sync",
                                                      "default": "Primary",
                                                      "type": "str" }
        
        self.parameters["project_id"] = { "description": "Shotgun id for the project you want to set up.",
                                          "default": None,
                                          "type": "int" }
        
        self.parameters["progress_callback"] = { "description": "Progress callback",
                                                "default": None,
                                                "type": "function" }

        
    def run_noninteractive(self, log, parameters):
        """
        Tank command API accessor. 
        Called when someone runs a tank command through the core API.
        
        :param log: std python logger
        :param parameters: dictionary with tank command parameters
        """
        # validate params and seed default values
        computed_params = self._validate_parameters(parameters)
        
        self._progress_cb = computed_params["progress_callback"] 
        
        return self._synchronize(log, parameters["project_id"], parameters["pipeline_configuration"])
                        
    def run_interactive(self, log, args):
        """
        Tank command accessor
        
        :param log: std python logger
        :param args: command line args
        """
        
        if len(args) != 2:
            raise TankError("Syntax: synchronize project_id config")

        project_id = int(args[0])
        config_name = args[1]
        
        self._synchronize(log, project_id, config_name)
    
    
    def _synchronize(self, log, project_id, pipeline_config_name):
        
        log.debug("Running synchronize for project id %d and pipeline config '%s'" % (project_id, pipeline_config_name))
        
        # now connect to shotgun
        try:
            log.info("Connecting to Shotgun...")
            sg = shotgun.create_sg_connection()
            sg_version = ".".join([ str(x) for x in sg.server_info["version"]])
            log.debug("Connected to target Shotgun server! (v%s)" % sg_version)
        except Exception, e:
            raise TankError("Could not connect to Shotgun server: %s" % e)
        
        
        # 
        pc = sg.find_one("PipelineConfiguration", 
                                   [["code", "is", pipeline_config_name], 
                                    ["project", "is", {"type": "Project", "id": project_id}]],
                         ["id", "windows_path", "mac_path", "linux_path", "sg_config"])
        if pc is None:    
            raise TankError("Couldn't find a pipeline configuration named '%s' for the given project" % pipeline_config_name)
        
        log.debug("Resolved pipeline configuration %s" % pc)

        if pc["sg_config"] is None:
            log.info("No zip config found!") 
            return

        # locate zip - there are three different forms
        #
        #
        # Web url:
        # {'name': 'config in github', 
        #  'url': 'https://github.com/shotgunsoftware/tk-config-default',
        #  'content_type': None, 
        #  'type': 'Attachment', 
        #  'id': 141, 
        #  'link_type': 'web'}
        #
        # Uploaded file:
        # {'name': 'v1.2.3.zip',
        #  'url': 'https://sg-media-usor-01.s3.amazonaws.com/...',
        #  'content_type': 'application/zip', 
        #  'type': 'Attachment', 
        #  'id': 139,
        #  'link_type': 'upload'}
        #
        # Locally linked via file system:
        #         
        # {'local_path_windows': 'D:\\toolkit\\manne-dev-2\\project\\zip_test\\v1.2.3.zip', 
        #  'name': 'v1.2.3.zip', 
        #  'local_path_linux': '/mnt/manne-dev-2/project/zip_test/v1.2.3.zip', 
        #  'url': 'file:///mnt/manne-dev-2/project/zip_test/v1.2.3.zip', 
        #  'local_storage': {'type': 'LocalStorage', 'id': 1, 'name': 'primary'}, 
        #  'local_path': '/mnt/manne-dev-2/project/zip_test/v1.2.3.zip', 
        #  'content_type': 'application/zip', 
        #  'local_path_mac': '/mnt/manne-dev-2/project/zip_test/v1.2.3.zip', 
        #  'type': 'Attachment', 
        #  'id': 142, 
        #  'link_type': 'local'}        


        if pc["sg_config"]["link_type"] != "upload":
            raise TankError("Type not supported")
        
        zip_path = os.path.join(tempfile.gettempdir(), "tk_cfg_%s.zip" % uuid.uuid4().hex)
        
        log.debug("downloading attachment to '%s'" % zip_path)
        bundle_content = sg.download_attachment(pc["sg_config"]["id"])
        fh = open(zip_path, "wb")
        fh.write(bundle_content)
        fh.close()
        
        zip_unpack_tmp = os.path.join(tempfile.gettempdir(), uuid.uuid4().hex)
        log.debug("Unzipping configuration and inspecting it to '%s'" % zip_unpack_tmp)
         
        unzip_file(zip_path, zip_unpack_tmp)
        template_items = os.listdir(zip_unpack_tmp)
        for item in ["core", "env", "hooks"]:
            if item not in template_items:
                raise TankError("Config zip '%s' is missing a %s folder!" % (zip_path, item))
        log.debug("Configuration looks valid!")

        def progress_cb(chapter, progress):
            log.info("PROGRESS [%d]: %s" % (chapter, progress))

        # HACK!
        path_to_core = os.path.abspath(os.path.join( os.path.dirname(__file__), "..", "..", "..", ".."))

        config_root = self.tk.execute_core_hook_method(constants.CACHE_LOCATION_HOOK_NAME,
                                                       "managed_config",
                                                       project_id=project_id,
                                                       pipeline_configuration_id=pc["id"])
        
        log.debug("Will synchronize into '%s'" % config_root)

        # figure out where our 
        synchronize_project(log, progress_cb, sg, zip_unpack_tmp, config_root, path_to_core)




