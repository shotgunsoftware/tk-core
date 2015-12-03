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
from . import core_localize
from ..zipfilehelper import unzip_file
from ...errors import TankError
from ...util import shotgun
from ...platform import constants
from ... import pipelineconfig_utils
from ... import pipelineconfig_factory

from tank_vendor import yaml

from .setup_project_core import run_project_setup
from .setup_project_params import ProjectSetupParameters

SG_LOCAL_STORAGE_OS_MAP = {"linux2": "linux_path", "win32": "windows_path", "darwin": "mac_path" }






def _get_cache_location():
    """
    Returns an OS specific cache location.

    :returns: Path to the OS specific cache folder.
    """
    if sys.platform == "darwin":
        root = os.path.expanduser("~/Library/Caches/Shotgun")
    elif sys.platform == "win32":
        root = os.path.join(os.environ["APPDATA"], "Shotgun")
    elif sys.platform.startswith("linux"):
        root = os.path.expanduser("~/.shotgun")
    return root


def _get_app_cache_location():
    """
    Returns an OS specific cache location.

    :returns: Path to the OS specific cache folder.
    """
    return os.path.join(_get_cache_location(), "app_cache")





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
                        Action.GLOBAL, 
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
    
    
    def _shotgun_connect(self, log):
        """
        
        TODO: This was duplicated from setup_project.
        
        Connects to the App store and to the associated shotgun site.
        Logging in to the app store is optional and in the case this fails,
        the app store parameters will return None. 
        
        The method returns a tuple with three parameters:
        
        - sg is an API handle associated with the associated site
        - sg_app_store is an API handle associated with the app store.
          Can be None if connection fails.
        - sg_app_store_script_user is a sg dict (with name, id and type) 
          representing the script user used to connect to the app store.
          Can be None if connection fails.
        
        :returns: (sg, sg_app_store, sg_app_store_script_user) - see above.
        """
        
        # now connect to shotgun
        try:
            log.info("Connecting to Shotgun...")
            sg = shotgun.create_sg_connection()
            sg_version = ".".join([ str(x) for x in sg.server_info["version"]])
            log.debug("Connected to target Shotgun server! (v%s)" % sg_version)
        except Exception, e:
            raise TankError("Could not connect to Shotgun server: %s" % e)
    
        try:
            log.info("Connecting to the App Store...")
            (sg_app_store, script_user) = shotgun.create_sg_app_store_connection()
            sg_version = ".".join([ str(x) for x in sg_app_store.server_info["version"]])
            log.debug("Connected to App Store! (v%s)" % sg_version)
        except Exception, e:
            log.warning("Could not establish a connection to the app store! You can "
                        "still create new projects, but you have to base them on "
                        "configurations that reside on your local disk.")
            log.debug("The following error was raised: %s" % e)
            sg_app_store = None
            script_user = None
        
        return (sg, sg_app_store, script_user)
    
    
    
    def _synchronize(self, log, project_id, pipeline_config_name):
        
        log.debug("Running synchronize for project id %d and pipeline config '%s'" % (project_id, pipeline_config_name))
        
        # connect to shotgun
        # TODO: lazily connect to app store in the future.
        (sg, sg_app_store, sg_app_store_script_user) = self._shotgun_connect(log)
        
        
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
        
#         zip_unpack_tmp = os.path.join(tempfile.gettempdir(), uuid.uuid4().hex)
#         log.debug("Unzipping configuration and inspecting it to '%s'" % zip_unpack_tmp)
#         
#         unzip_file(zip_path, zip_unpack_tmp)
#         template_items = os.listdir(zip_unpack_tmp)
#         for item in ["core", "env", "hooks"]:
#             if item not in template_items:
#                 raise TankError("Config zip '%s' is missing a %s folder!" % (zip_path, item))
#         log.debug("Configuration looks valid!")

        # create a parameters class
        params = ProjectSetupParameters(log, sg, sg_app_store, sg_app_store_script_user)
        
        # tell it which core to pick up. 
        
        
        
        
        curr_core_path = pipelineconfig_utils.get_path_to_current_core()
        core_roots = pipelineconfig_utils.resolve_all_os_paths_to_core(curr_core_path)
        params.set_associated_core_path(core_roots["linux2"], core_roots["win32"], core_roots["darwin"])
        
        # specify which config to use
        params.set_config_uri(zip_path)
                
        # set the project
        params.set_project_id(project_id)
        params.set_project_disk_name(computed_params["project_folder_name"])
        
        # set the config path
        params.set_configuration_location(computed_params["config_path_linux"], 
                                          computed_params["config_path_win"], 
                                          computed_params["config_path_mac"])        
        
        # run overall validation of the project setup
        params.pre_setup_validation()
        
        # and finally carry out the setup
        run_project_setup(log, sg, sg_app_store, sg_app_store_script_user, params)



