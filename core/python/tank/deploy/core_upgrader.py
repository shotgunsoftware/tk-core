"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Classes for handling upgrading of the Tank Core API.

"""

import os
import sys
import uuid
import tempfile
from tank_vendor import yaml


from ..errors import TankError
from ..util import shotgun
from ..platform import constants
from .zipfilehelper import unzip_file
from . import util

TANK_CORE_VERSION_ENTITY = "CustomNonProjectEntity01"
TANK_CODE_PAYLOAD_FIELD = "sg_payload"
TANK_APP_STORE_DUMMY_PROJECT = {"type": "Project", "id": 64} 

class TankCoreUpgrader(object):
    """
    Class which handles the upgrade of the core API.
    Note that this is not part of the descriptor framework since it is a bit different.
    """
        
    
    # possible update status states
    (UP_TO_DATE,                    # all good, no update necessary  
     UPGRADE_POSSIBLE,              # more recent version exists
     UPGRADE_BLOCKED_BY_SG          # more recent version exists but SG version is too low.
     ) = range(3)
        
        
    def __init__(self, studio_root, logger):
        self._log = logger
        
        (sg_app_store, script_user) = shotgun.create_sg_app_store_connection(studio_root)
        self._sg = sg_app_store
        self._sg_script_user = script_user
        
        self._local_sg = shotgun.create_sg_connection_studio_root(studio_root)      
        self._latest_ver = self.__get_latest_version()
        
        self._current_ver = constants.get_core_api_version()
        
        self._studio_root = studio_root
         
        # now also extract the version of shotgun currently running
        try:
            self._sg_studio_version = ".".join([ str(x) for x in self._local_sg.server_info["version"]])        
        except Exception, e:
            raise TankError("Could not extract version number for studio shotgun: %s" % e)
    
            
    def __get_latest_version(self):
        """
        Returns info about the latest version of the Tank API from shotgun.
        Returns None if there is no latest version, otherwise a dictionary.
        """
        if constants.APP_STORE_QA_MODE_ENV_VAR in os.environ:
            latest_filter = [["sg_status_list", "is_not", "bad" ]]
        else:
            latest_filter = [["sg_status_list", "is_not", "rev" ],
                             ["sg_status_list", "is_not", "bad" ]]
        
        # connect to the app store
        latest_core = self._sg.find_one(TANK_CORE_VERSION_ENTITY, 
                                        filters = latest_filter, 
                                        fields=["sg_min_shotgun_version", 
                                                "code",
                                                "sg_detailed_release_notes",
                                                "description",
                                                TANK_CODE_PAYLOAD_FIELD],
                                        order=[{"field_name": "created_at", "direction": "desc"}])

        if latest_core is None:
            # technical problems?
            raise TankError("Could not find any version of the Core API in the app store!")
            
        return latest_core    
    
    def get_latest_version_number(self):
        """
        Returns the latest version of the Tank API from shotgun
        Returns None if there is no latest version
        """
        return self._latest_ver["code"]

    def get_current_version_number(self):
        """
        Returns the currently installed version of the Tank API
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
        Returns the release notes for the most recent version of the tank API
        
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
        if self._latest_ver[TANK_CODE_PAYLOAD_FIELD] is None:
            raise Exception("Cannot find a tank binary bundle for %s. Please contact support" % self._latest_ver["code"])
        
        self._log.info("Begin downloading Tank Core API %s from the Tank App Store..." % self._latest_ver["code"])
        
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
            attachment_id = int(self._latest_ver[TANK_CODE_PAYLOAD_FIELD]["url"].split("/")[-1])
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
        data["project"] = TANK_APP_STORE_DUMMY_PROJECT
        data["attribute_name"] = TANK_CODE_PAYLOAD_FIELD
        self._sg.create("EventLogEntry", data)
        
        
        self._log.info("Extraction complete - now installing Tank Core")
        sys.path.insert(0, extract_tmp)
        try:
            import _core_upgrader
            
            # compute the install root based on the studio root
            #
            # studio                    
            #   |--tank                 
            #        |--config          
            #        |--install         # <<<--- install root
            #            |--core
            #                |--python  
            #            |--apps         
            #            |--engines     
            #
            install_folder = os.path.join(self._studio_root, "tank", "install")
            _core_upgrader.upgrade_tank(install_folder, self._log)
        except Exception, e:
            self._log.exception(e)
            raise Exception("Could not run upgrade script! Error reported: %s" % e)
