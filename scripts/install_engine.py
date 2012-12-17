"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Adds an engine to an environment.

"""

import optparse
import os
import logging
import sys
import re
import textwrap
import shutil
import datetime
import pprint
import platform

# make sure that the core API is part of the pythonpath
python_path = os.path.abspath(os.path.join( os.path.dirname(__file__), "..", "python"))
sys.path.append(python_path)

from tank.deploy.app_store_descriptor import TankAppStoreDescriptor
from tank.deploy.descriptor import AppDescriptor
from tank.platform import constants
from tank.platform import environment
from tank.deploy import administrator
from tank.errors import TankError
from tank.deploy import console_utils

###############################################################################################

def add_engine(log, project_root, env_name, engine_name):
    """
    Adds an engine to an environment
    """
    log.info("")
    log.info("")
    log.info("Welcome to the Tank Engine installer!")
    log.info("")

    try:
        env_file = constants.get_environment_path(env_name, project_root)
        env = environment.Environment(env_file)
    except Exception, e:
        raise TankError("Environment '%s' could not be loaded! Error reported: %s" % (env_name, e))

    # find engine
    engine_descriptor = TankAppStoreDescriptor.find_item(project_root, AppDescriptor.ENGINE, engine_name)
    log.info("Successfully located %s..." % engine_descriptor)
    log.info("")

    # now assume a convention where we will name the engine instance that we create in the environment
    # the same as the short name of the engine
    engine_instance_name = engine_descriptor.get_system_name()

    # check so that there is not an app with that name already!
    if engine_instance_name in env.get_engines():
        raise TankError("Engine %s exists in the environment!" % engine_instance_name)

    # now make sure all constraints are okay
    try:
        administrator.check_constraints_for_item(project_root, engine_descriptor, env)
    except TankError, e:
        raise TankError("Cannot install: %s" % e)


    # okay to install!

    # ensure that all required frameworks have been installed
    console_utils.ensure_frameworks_installed(log, project_root, engine_descriptor, env)

    # note! Some of these methods further down are likely to pull the apps local
    # in order to do deep introspection. In order to provide better error reporting,
    # pull the apps local before we start
    if not engine_descriptor.exists_local():
        log.info("Downloading from App Store, hold on...")
        engine_descriptor.download_local()
        log.info("")

    # create required shotgun fields
    engine_descriptor.ensure_shotgun_fields_exist()

    # now get data for all new settings values in the config
    params = console_utils.get_configuration(log, project_root, engine_descriptor, None)
    
    # next step is to add the new configuration values to the environment
    env.create_engine_settings(engine_instance_name)
    env.update_engine_settings(engine_instance_name, params)
    env.update_engine_location(engine_instance_name, engine_descriptor.get_location())

    log.info("")
    log.info("")
    log.info("Engine Installation Complete!")
    log.info("")
    if engine_descriptor.get_doc_url():
        log.info("For documentation, see %s" % engine_descriptor.get_doc_url())
    log.info("")
    log.info("")




def main(log):


    if len(sys.argv) == 1 or len(sys.argv) != 4:

        desc = """

Adds a new Engine to a Tank Environment.

    Syntax:  %(cmd)s project_root environment_name engine_name

    Example: %(cmd)s /mnt/shows/my_project rigging tk-maya

This command will download an engine from the Tank App Store and add it to
the specified project and environment. You will be prompted to fill in
the various configuration parameters that the app requires.
""" % {"cmd": sys.argv[0]}
        print desc
        return
    else:
        project_root = sys.argv[1]
        env_name = sys.argv[2]
        engine_name = sys.argv[3]

    # run actual activation
    add_engine(log, project_root, env_name, engine_name)

#######################################################################
if __name__ == "__main__":

    # set up logging channel for this script
    log = logging.getLogger("tank.add_engine")
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
