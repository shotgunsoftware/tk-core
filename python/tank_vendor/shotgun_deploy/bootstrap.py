# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

from . import util
from . import Descriptor
from . import descriptor_factory
from .errors import ShotgunDeployError
from .installed_configuration import InstalledConfiguration

log = util.get_shotgun_deploy_logger()


def bootstrap(sg_user, config_location, project_id, pipeline_config_id=None):
    """
    Given a config location
    """

    sg = sg_user.create_sg_connection()

    # resolve the config as a descriptor object
    cfg_descriptor = descriptor_factory.create_descriptor(sg, Descriptor.CONFIG, config_location)

    # create an object to represent our configuration install
    config = InstalledConfiguration(sg, cfg_descriptor, project_id, pipeline_config_id)

    # see what we have locally
    status = config.status()

    if status == InstalledConfiguration.LOCAL_CFG_UP_TO_DATE:
        log.info("Your configuration is up to date.")

    elif status == InstalledConfiguration.LOCAL_CFG_MISSING:
        log.info("A brand new configuration will be created locally.")
        config.set_up_project_scaffold()
        config.install_core()

    elif status == InstalledConfiguration.LOCAL_CFG_OLD:
        log.info("Your local configuration is out of date and will be updated.")
        config.move_to_backup()
        config.set_up_project_scaffold()
        config.install_core()

    elif status == InstalledConfiguration.LOCAL_CFG_INVALID:
        log.info("Your local configuration looks invalid and will be replaced.")
        config.move_to_backup()
        config.set_up_project_scaffold()
        config.install_core()

    else:
        raise ShotgunDeployError("Unknown configuration update status!")

    # @todo - add rollback logic from zip config branch

    # we can now boot up this config.
    tk = config.get_tk_instance(sg_user)

    _cache_apps(tk)

    return tk


def _cache_apps(tk):
    # each entry in the config template contains instructions about which version of the app
    # to use. First loop over all environments and gather all descriptors we should download,
    # then go ahead and download and post-install them

    pc = tk.pipeline_configuration
    import inspect

    print inspect.getfile(tk.__class__)
    print inspect.getfile(pc.__class__)

    log.info("Downloading and installing apps...")

    # pass 1 - populate list of all descriptors
    descriptors = []
    for env_name in pc.get_environments():

        env_obj = pc.get_environment(env_name)

        for engine in env_obj.get_engines():
            descriptors.append(env_obj.get_engine_descriptor(engine))

            for app in env_obj.get_apps(engine):
                descriptors.append(env_obj.get_app_descriptor(engine, app))

        for framework in env_obj.get_frameworks():
            descriptors.append(env_obj.get_framework_descriptor(framework))

    # pass 2 - download all apps
    num_descriptors = len(descriptors)
    for idx, descriptor in enumerate(descriptors):

        if not descriptor.exists_local():
            log.info("Downloading %s to the local Toolkit install location..." % descriptor)
            descriptor.download_local()

        else:
            log.info("Item %s is already locally installed." % descriptor)

    # # create required shotgun fields
    # if run_post_install:
    #     progress_cb("Running post install processes...")
    #     for descriptor in descriptors:
    #         log.debug("Post install for %s" % descriptor)
    #         descriptor.ensure_shotgun_fields_exist()
    #         descriptor.run_post_install(tk)




