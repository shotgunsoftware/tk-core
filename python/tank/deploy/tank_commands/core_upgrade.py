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
from ... import pipelineconfig_utils
from ..zipfilehelper import unzip_file
from .. import util

from . import console_utils

        
class CoreUpgradeAction(Action):
    """
    Action to upgrade the Core API code that is associated with the currently running code.
    """
    
    def __init__(self):
        Action.__init__(self, 
                        "core", 
                        Action.GLOBAL, 
                        "Checks that your Toolkit Core API install is up to date.", 
                        "Configuration")
        
        # this method can be executed via the API
        self.supports_api = True
        
        ret_val_doc = "Returns a dictionary with keys status (str) optional keys. The following status codes "
        ret_val_doc += "are returned: 'up_to_date' if no update was needed, 'updated' if an update was "
        ret_val_doc += "applied and 'update_blocked' if an update was available but could not be applied. "
        ret_val_doc += "For the 'updated' status, data will contain new_version key with the version "
        ret_val_doc += "number of the core that was updated to. "
        ret_val_doc += "For the 'update_blocked' status, data will contain a reason key containing an explanation."

        self.parameters = {"return_value": {"description": ret_val_doc, "type": "dict" }}
            
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
        self._run(log, False)
        
    def _run(self, log, suppress_prompts):
        """
        Actual execution payload
        """ 

        return_status = {"status": "unknown"}

        # get the core api root of this installation by looking at the relative location of the running code.
        code_install_root = pipelineconfig_utils.get_path_to_current_core() 
        
        log.info("")
        log.info("Welcome to the Shotgun Pipeline Toolkit update checker!")
        log.info("This script will check if the Toolkit Core API installed")
        log.info("in %s" % code_install_root) 
        log.info("is up to date.")
        log.info("")
        log.info("")
        log.info("Please note that when you upgrade the core API, you typically affect "
                 "more than one project. If you want to test a Core API upgrade in isolation "
                 "prior to rolling it out to multiple projects, we recommend creating a "
                 "special *localized* pipeline configuration. For more information about this, please "
                 "see the Toolkit documentation.")
        log.info("")
        log.info("")    
        
        installer = TankCoreUpgrader(code_install_root, log)
        cv = installer.get_current_version_number()
        lv = installer.get_latest_version_number()
        log.info("You are currently running version %s of the Shotgun Pipeline Toolkit" % cv)
        
        status = installer.get_update_status()
        req_sg = installer.get_required_sg_version_for_upgrade()
        
        if status == TankCoreUpgrader.UP_TO_DATE:
            log.info("No need to update the Toolkit Core API at this time!")
            return_status = {"status": "up_to_date"}
        
        elif status == TankCoreUpgrader.UPGRADE_BLOCKED_BY_SG:
            msg = ("A new version (%s) of the core API is available however "
                        "it requires a more recent version (%s) of Shotgun!" % (lv, req_sg))
            log.warning(msg)
            return_status = {"status": "update_blocked", "reason": msg}
            
        elif status == TankCoreUpgrader.UPGRADE_POSSIBLE:
            
            (summary, url) = installer.get_release_notes()
                    
            log.info("A new version of the Toolkit API (%s) is available!" % lv)
            log.info("")
            log.info("Change Summary:")
            for x in textwrap.wrap(summary, width=60):
                log.info(x)
            log.info("")
            log.info("Detailed Release Notes:")
            log.info("%s" % url)
            log.info("")
            log.info("Please note that this upgrade will affect all projects")
            log.info("Associated with this Shotgun Pipeline Toolkit installation.")
            log.info("")
            
            if suppress_prompts or console_utils.ask_yn_question("Update to the latest version of the Core API?"):
                # install it!
                log.info("Downloading and installing a new version of the core...")
                installer.do_install()
                log.info("")
                log.info("")
                log.info("----------------------------------------------------------------")
                log.info("The Toolkit Core API has been upgraded!")
                log.info("")
                log.info("")
                log.info("Please note the following:")
                log.info("")
                log.info("- You need to restart any applications (such as Maya or Nuke)")
                log.info("  in order for them to pick up the API upgrade.")
                log.info("")
                log.info("- Please close this shell, as the upgrade process")
                log.info("  has replaced the folder that this script resides in")
                log.info("  with a more recent version. ")            
                log.info("")
                log.info("----------------------------------------------------------------")
                log.info("")
                return_status = {"status": "updated", "new_version": lv}
                
            else:
                log.info("The Shotgun Pipeline Toolkit will not be updated.")
            
        else:
            raise TankError("Unknown Upgrade state!")
        
        return return_status
    


class TankCoreUpgrader(object):
    """
    Class which handles the upgrade of the core API.
    """
    
    # possible update status states
    (UP_TO_DATE,                    # all good, no update necessary  
     UPGRADE_POSSIBLE,              # more recent version exists
     UPGRADE_BLOCKED_BY_SG          # more recent version exists but SG version is too low.
     ) = range(3)
        
        
    def __init__(self, installation_root, logger):
        """
        Constructor
        
        :param installation_root: The path to the installation to check. This is either a localized
                                  Pipeline Configuration or a studio code location (omit the install folder).
                                  Because we are passing this parameter in explicitly, the currently running
                                  code base does not have to be related to the code base that is being upgraded,
                                  e.g. you can run the upgrader as a totally separate thing.
        :param logger: Logger to send output to.
        """
        self._log = logger
        
        (sg_app_store, script_user) = shotgun.create_sg_app_store_connection()
        self._sg = sg_app_store
        self._sg_script_user = script_user
        
        self._local_sg = shotgun.get_sg_connection()      
        self._latest_ver = self.__get_latest_version()
        
        self._install_root = os.path.join(installation_root, "install")
        
        self._current_ver = pipelineconfig_utils.get_currently_running_api_version()
         
        # now also extract the version of shotgun currently running
        try:
            self._sg_studio_version = ".".join([ str(x) for x in self._local_sg.server_info["version"]])        
        except Exception, e:
            raise TankError("Could not extract version number for studio shotgun: %s" % e)
    
            
    def __get_latest_version(self):
        """
        Returns info about the latest version of the Toolkit API from shotgun.
        Returns None if there is no latest version, otherwise a dictionary.
        """
        if constants.APP_STORE_QA_MODE_ENV_VAR in os.environ:
            latest_filter = [["sg_status_list", "is_not", "bad" ]]
        else:
            latest_filter = [["sg_status_list", "is_not", "rev" ],
                             ["sg_status_list", "is_not", "bad" ]]
        
        # connect to the app store
        latest_core = self._sg.find_one(constants.TANK_CORE_VERSION_ENTITY, 
                                        filters = latest_filter, 
                                        fields=["sg_min_shotgun_version", 
                                                "code",
                                                "sg_detailed_release_notes",
                                                "description",
                                                constants.TANK_CODE_PAYLOAD_FIELD],
                                        order=[{"field_name": "created_at", "direction": "desc"}])

        if latest_core is None:
            # technical problems?
            raise TankError("Could not find any version of the Core API in the app store!")
            
        return latest_core    
    
    def get_latest_version_number(self):
        """
        Returns the latest version of the Toolkit API from shotgun
        Returns None if there is no latest version
        """
        return self._latest_ver["code"]

    def get_current_version_number(self):
        """
        Returns the currently installed version of the Toolkit API
        """
        return self._current_ver

    def get_required_sg_version_for_upgrade(self):
        """
        Returns the SG version that is required in order to upgrade to the most recent 
        version of the Tank Core API.
        
        :returns: sg version number as a string or None if no version is required. 
        """
        return self._latest_ver["sg_min_shotgun_version"]

    def get_release_notes(self):
        """
        Returns the release notes for the most recent version of the Toolkit API
        
        :returns: tuple with (summary_string, details_url_string)
        """
        summary = self._latest_ver.get("description", "")
        if self._latest_ver:
            url = self._latest_ver["sg_detailed_release_notes"].get("url", "")
        else:
            url = ""
        return (summary, url)

    def get_update_status(self):
        """
        Returns true if an update is recommended
        """
        if self._current_ver == "HEAD":
            # head is the verison number which is stored in tank core trunk
            # getting this as a result means that we are not actually running
            # a version of tank that came from the app store, but some sort 
            # of dev version
            return TankCoreUpgrader.UP_TO_DATE
        
        elif self.get_latest_version_number() == self.get_current_version_number():
            # running latest version already
            return TankCoreUpgrader.UP_TO_DATE

        else:
            # running an older version. Make sure that shotgun has the required version
            req_sg = self.get_required_sg_version_for_upgrade()
            if req_sg is None:
                # no particular version required! We are good to go!
                return TankCoreUpgrader.UPGRADE_POSSIBLE
            
            else:
                # there is a sg min version required - make sure we have that!
                if util.is_version_newer(req_sg, self._sg_studio_version):
                    return TankCoreUpgrader.UPGRADE_BLOCKED_BY_SG
                else:
                    return TankCoreUpgrader.UPGRADE_POSSIBLE

        
    def do_install(self):
        """
        Performs the actual installation of the new version of the core API
        """
        
        # validation
        if self.get_update_status() != TankCoreUpgrader.UPGRADE_POSSIBLE:
            raise Exception("Upgrade not allowed at this point. Run get_update_status for details.")
        
        # download attachment
        if self._latest_ver[constants.TANK_CODE_PAYLOAD_FIELD] is None:
            raise Exception("Cannot find a binary bundle for %s. Please contact support" % self._latest_ver["code"])
        
        self._log.info("Begin downloading Toolkit Core API %s from the App Store..." % self._latest_ver["code"])
        
        zip_tmp = os.path.join(tempfile.gettempdir(), "%s_tank_core.zip" % uuid.uuid4().hex)
        extract_tmp = os.path.join(tempfile.gettempdir(), "%s_tank_unzip" % uuid.uuid4().hex)
        
        # now have to get the attachment id from the data we obtained. This is a bit hacky.
        # data example for the payload field, as returned by the query above: 
        # {'url': 'http://tank.shotgunstudio.com/file_serve/attachment/21', 'name': 'tank_core.zip', 
        #  'content_type': 'application/zip', 'link_type': 'upload'}
        # 
        # grab the attachment id off the url field and pass that to the download_attachment()
        # method below.
        
        try:
            attachment_id = int(self._latest_ver[constants.TANK_CODE_PAYLOAD_FIELD]["url"].split("/")[-1])
        except:
            raise Exception("Could not extract attachment id from data %s" %  self._latest_ver)
        
        bundle_content = self._sg.download_attachment(attachment_id)
        fh = open(zip_tmp, "wb")
        fh.write(bundle_content)
        fh.close()
        
        self._log.info("Download complete - now extracting content...")
        # unzip core zip file to temp location and run updater
        unzip_file(zip_tmp, extract_tmp)
        
        # and write a custom event to the shotgun event log
        data = {}
        data["description"] = "%s: Core API was downloaded" % self._local_sg.base_url
        data["event_type"] = "TankAppStore_CoreApi_Download"
        data["entity"] = self._latest_ver
        data["user"] = self._sg_script_user
        data["project"] = constants.TANK_APP_STORE_DUMMY_PROJECT
        data["attribute_name"] = constants.TANK_CODE_PAYLOAD_FIELD
        self._sg.create("EventLogEntry", data)
        
        
        self._log.info("Extraction complete - now installing Toolkit Core")
        sys.path.insert(0, extract_tmp)
        try:
            import _core_upgrader            
            _core_upgrader.upgrade_tank(self._install_root, self._log)
        except Exception, e:
            self._log.exception(e)
            raise Exception("Could not run upgrade script! Error reported: %s" % e)
