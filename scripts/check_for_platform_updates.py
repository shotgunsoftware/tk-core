"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Looks for update to the core.

"""

import optparse
import os
import logging
import sys
import re
import shutil
import datetime
import pprint
import textwrap

# make sure that the core API is part of the pythonpath
python_path = os.path.abspath(os.path.join( os.path.dirname(__file__), "..", "python"))
sys.path.append(python_path)

from tank.platform import environment
from tank.deploy import descriptor
from tank.platform import constants
from tank.deploy.core_upgrader import TankCoreUpgrader
from tank.deploy import administrator
from tank.errors import TankError

##########################################################################################
# helpers

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
 
##########################################################################################
# main script and startup

def main(log):
    """
    App entry point
    """
    
    if len(sys.argv) != 2:
        log.info("")
        log.info("")
        log.info("Check if the Tank Platform is up to date.")
        log.info("")
        log.info("Usage: %s studio_root" % sys.argv[0])
        log.info("")
        log.info("")
        log.info("")
        sys.exit(1)

    studio_root = sys.argv[1]

    log.info("Welcome to the Tank update checker!")
    log.info("This script will check if the Tank Platform is up to date.")
    log.info("for the installation at %s" % studio_root)
    log.info("")
    
    installer = TankCoreUpgrader(studio_root, log)
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
        


if __name__ == "__main__":
    
    log = logging.getLogger("tank.update")
    log.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    formatter = logging.Formatter("%(levelname)s %(message)s")
    ch.setFormatter(formatter)
    log.addHandler(ch)

    exit_code = 1
    try:
        main(log)
        exit_code = 0
    except TankError, e:
        # one line report
        log.error("An error occurred: %s" % e)
    except Exception, e:
        # callstack
        log.exception("An error occurred: %s" % e)
        
    sys.exit(exit_code)