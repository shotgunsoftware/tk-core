"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

debugging script that validates the environments for a project.

"""

import os
import sys
import logging
import textwrap

# make sure that the core API is part of the pythonpath
python_path = os.path.abspath(os.path.join( os.path.dirname(__file__), "..", "python"))
sys.path.append(python_path)

from tank.errors import TankError
from tank.platform import constants
from tank.deploy import administrator
from tank.platform import environment
from tank.deploy.descriptor import AppDescriptor
from tank.deploy.app_store_descriptor import TankAppStoreDescriptor
from tank.platform.environment import Environment

def validate_bundle(log, name, settings, manifest):
    
    log.info("")
    log.info("Validating %s..." % name)
    settings = settings.keys()
    required = manifest["configuration"].keys()
    
    for r in required:
        if r not in settings:
            log.info("Parameter missing: %s" % r)
    for s in settings:
        if s not in required:
            log.info("Parameter not needed: %s" % s)


def process_environment(log, env_path):
    
    log.info("Processing environment %s" % env_path)
    env = Environment(env_path)

    for e in env.get_engines():  
        s = env.get_engine_settings(e)
        m = env.get_engine_metadata(e)
        validate_bundle(log, e, s, m)
        for a in env.get_apps(e):
            s = env.get_app_settings(e, a)
            m = env.get_app_metadata(e, a)
            validate_bundle(log, a, s, m)
    
    
    
def validate_project(log, project_root):
    """
    Adds an app to an environment
    """
    log.info("")
    log.info("")
    log.info("Welcome to the Tank Configuration validator!")
    log.info("")

    try:
        envs = constants.get_environments_for_proj(project_root)
    except Exception, e:
        raise TankError("Could not find any environments for Tank project root %s: %s" % (project_root, e))

    log.info("Found the following environments:")
    for x in envs:
        log.info("    %s" % x)
    log.info("")
    log.info("")

    
    for x in envs:
        process_environment(log, x)
        

    log.info("")
    log.info("")
    log.info("")
    
     


def main(log):
    if len(sys.argv) == 1 or len(sys.argv) != 2:

        desc = """

Validates the settings for all apps and engines in a Tank Environment.

    Syntax:  %(cmd)s project_root


""" % {"cmd": sys.argv[0]}
        print desc
        return
    else:
        project_root = sys.argv[1]

    # run actual activation
    validate_project(log, project_root)

#######################################################################
if __name__ == "__main__":

    # set up logging channel for this script
    log = logging.getLogger("tank.validate")
    log.setLevel(logging.INFO)

    ch = logging.StreamHandler()
    formatter = logging.Formatter("%(levelname)s %(message)s")
    ch.setFormatter(formatter)
    log.addHandler(ch)

    exit_code = 1
    try:
        # clear the umask so permissions are respected
        old_umask = os.umask(0)
        main(log)
        exit_code = 0
    except TankError, e:
        # one line report
        log.error("An error occurred: %s" % e)
    except Exception, e:
        # callstack
        log.exception("An error occurred: %s" % e)
    finally:
        os.umask(old_umask)

    sys.exit(exit_code)
