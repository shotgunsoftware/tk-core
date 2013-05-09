"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Classes for handling upgrading of the Tank Core API.

"""

import os
import sys
import textwrap
import uuid
import shutil
import stat
import tempfile
import datetime
from tank_vendor import yaml


from ..errors import TankError
from ..util import shotgun
from ..platform import constants
from .. import pipelineconfig
from .zipfilehelper import unzip_file
from . import util

def _ask_question(question):
    """
    Ask a yes-no-always question
    returns true if user pressed yes (or previously always)
    false if no
    """
    
    answer = raw_input("%s [yn]" % question )
    answer = answer.lower()
    if answer != "n" and answer != "y":
        print("Press y for YES, n for NO")
        answer = raw_input("%s [yn]" % question )
    
    if answer == "y":
        return True

    return False   

def show_upgrade_info(log, code_root, pc_root):
    """
    Display details of how to get latest apps
    """
    
    code_css_block = "display: block; padding: 0.5em 1em; border: 1px solid #bebab0; background: #faf8f0;"
    
    log.info("In order to check if your installed apps and engines are up to date, "
             "you can run the following command in a console:")
    
    log.info("")
    
    if sys.platform == "win32":
        tank_cmd = os.path.join(pc_root, "tank.bat")
    else:
        tank_cmd = os.path.join(pc_root, "tank")
    
    log.info("<code style='%s'>%s updates</code>" % (code_css_block, tank_cmd))
    
    log.info("")
                    
    
    

def show_core_info(log, code_root, pc_root):
    """
    Display details about the core version etc
    """
    
    code_css_block = "display: block; padding: 0.5em 1em; border: 1px solid #bebab0; background: #faf8f0;"
    
    installer = TankCoreUpgrader(code_root, log)
    cv = installer.get_current_version_number()
    lv = installer.get_latest_version_number()
    log.info("You are currently running version %s of the Tank Platform." % cv)
    
    if code_root != pc_root:
        log.info("")
        log.info("Your core API is located in <code>%s</code> and is shared with other "
                 "projects." % code_root)
    log.info("")
    
    status = installer.get_update_status()
    req_sg = installer.get_required_sg_version_for_upgrade()
    
    if status == TankCoreUpgrader.UP_TO_DATE:
        log.info("<b>There is no need to update the Tank Core API at this time!</b>")

    elif status == TankCoreUpgrader.UPGRADE_BLOCKED_BY_SG:
        log.warning("<b>A new version (%s) of the core API is available however "
                    "it requires a more recent version (%s) of Shotgun!</b>" % (lv, req_sg))
        
    elif status == TankCoreUpgrader.UPGRADE_POSSIBLE:
        
        (summary, url) = installer.get_release_notes()
                
        log.info("<b>A new version of the Tank API (%s) is available!</b>" % lv)
        log.info("")
        log.info("<b>Change Summary:</b> %s <a href='%s' target=_new>"
                 "Click for detailed Release Notes</a>" % (summary, url))
        log.info("")
        log.info("In order to upgrade, execute the following command in a shell:")
        log.info("")
        
        if sys.platform == "win32":
            tank_cmd = os.path.join(code_root, "tank.bat")
        else:
            tank_cmd = os.path.join(code_root, "tank")
        
        log.info("<code style='%s'>%s core</code>" % (code_css_block, tank_cmd))
        
        log.info("")
                    
    else:
        raise TankError("Unknown Upgrade state!")
    
    

def install_local_core(log, code_root, pc_root):
    """
    Install a local tank core into this pipeline configuration
    """
    log.debug("Executing the core localize command. Code root: %s. PC Root: %s" % (code_root, pc_root))
    
    log.info("")
    if code_root == pc_root:
        raise TankError("Looks like the pipeline configuration %s already has a local install "
                        "of the core!" % pc_root)
    
    log.info("This will copy the Core API in %s into the Pipeline configuration %s." % (code_root, pc_root) )
    log.info("")
    if _ask_question("Do you want to proceed"):
        log.info("")
        
        source_core = os.path.join(code_root, "install", "core")
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
                src = os.path.join(code_root, "config", "core", fn)
                tgt = os.path.join(pc_root, "config", "core", fn)
                log.debug("Copy %s -> %s" % (src, tgt))
                shutil.copy(src, tgt)
                os.chmod(tgt, 0444)
                
            # copy apps, engines, frameworks
            source_apps = os.path.join(code_root, "install", "apps")
            target_apps = os.path.join(pc_root, "install", "apps")
            log.info("Localizing Apps: %s -> %s" % (source_apps, target_apps))
            util._copy_folder(log, source_apps, target_apps)
            
            source_engines = os.path.join(code_root, "install", "engines")
            target_engines = os.path.join(pc_root, "install", "engines")
            log.info("Localizing Engines: %s -> %s" % (source_engines, target_engines))
            util._copy_folder(log, source_engines, target_engines)

            source_frameworks = os.path.join(code_root, "install", "frameworks")
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
        


def interactive_update(log, code_root):
    """
    Perform an interactive core check and update
    """
    log.info("")
    log.info("Welcome to the Tank update checker!")
    log.info("This script will check if the Tank Core API ")
    log.info("installed in %s" % code_root) 
    log.info("is up to date.")
    log.info("")
    
    installer = TankCoreUpgrader(code_root, log)
    cv = installer.get_current_version_number()
    lv = installer.get_latest_version_number()
    log.info("You are currently running version %s of the Tank Platform" % cv)
    
    status = installer.get_update_status()
    req_sg = installer.get_required_sg_version_for_upgrade()
    
    if status == TankCoreUpgrader.UP_TO_DATE:
        log.info("No need to update the Tank Core API at this time!")
    
    elif status == TankCoreUpgrader.UPGRADE_BLOCKED_BY_SG:
        log.warning("A new version (%s) of the core API is available however "
                    "it requires a more recent version (%s) of Shotgun!" % (lv, req_sg))
        
    elif status == TankCoreUpgrader.UPGRADE_POSSIBLE:
        
        (summary, url) = installer.get_release_notes()
                
        log.info("A new version of the Tank API (%s) is available!" % lv)
        log.info("")
        log.info("Change Summary:")
        for x in textwrap.wrap(summary, width=60):
            log.info(x)
        log.info("")
        log.info("Detailed Release Notes:")
        log.info("%s" % url)
        log.info("")
        log.info("Please note that this upgrade will affect all projects")
        log.info("Associated with this tank installation.")
        log.info("")
        
        if _ask_question("Update to the latest version of the Core API?"):
            # install it!
            log.info("Downloading and installing a new version of the core...")
            installer.do_install()
            log.info("")
            log.info("Now, please CLOSE THIS SHELL, as the upgrade process")
            log.info("has replaced the folder that this script resides in")
            log.info("with a more recent version. Continuing Tank related ")
            log.info("work in this shell beyond this point is not recommended.")
            log.info("")
        else:
            log.info("The Tank Platform will not be updated.")
            
    else:
        raise TankError("Unknown Upgrade state!")
        





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
        
        
    def __init__(self, code_root, logger):
        self._log = logger
        
        (sg_app_store, script_user) = shotgun.create_sg_app_store_connection()
        self._sg = sg_app_store
        self._sg_script_user = script_user
        
        self._local_sg = shotgun.create_sg_connection()      
        self._latest_ver = self.__get_latest_version()
        
        self._install_root = os.path.join(code_root, "install")
        
        self._current_ver = pipelineconfig.get_core_api_version_based_on_current_code()
         
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
        if self._latest_ver[constants.TANK_CODE_PAYLOAD_FIELD] is None:
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
        
        
        self._log.info("Extraction complete - now installing Tank Core")
        sys.path.insert(0, extract_tmp)
        try:
            import _core_upgrader            
            _core_upgrader.upgrade_tank(self._install_root, self._log)
        except Exception, e:
            self._log.exception(e)
            raise Exception("Could not run upgrade script! Error reported: %s" % e)
