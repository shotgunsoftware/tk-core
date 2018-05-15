# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Helper script to generate a toolkit plugin given a plugin source location.

This will analyse the info.yml found in the plugin source location
and create a plugin scaffold, complete with standard helpers and
a primed bundle cache.
"""

# system imports
from __future__ import with_statement
import re
import os
import sys
import shutil
import datetime

# add sgtk API
this_folder = os.path.abspath(os.path.dirname(__file__))
python_folder = os.path.abspath(os.path.join(this_folder, "..", "python"))
sys.path.append(python_folder)

# sgtk imports
from tank import LogManager
from tank.util import filesystem
from tank.errors import TankError
from tank.descriptor import Descriptor, descriptor_uri_to_dict, descriptor_dict_to_uri
from tank.descriptor import create_descriptor, is_descriptor_version_missing
from tank.descriptor.errors import TankDescriptorError
from tank.bootstrap.baked_configuration import BakedConfiguration
from tank.bootstrap import constants as bootstrap_constants
from tank_vendor import yaml

from utils import (
    cache_apps, authenticate, add_authentication_options, OptionParserLineBreakingEpilog, cleanup_bundle_cache,
    wipe_folder, automated_setup_documentation
)

# Set up logging
logger = LogManager.get_logger("bake_config")

# The folder where all items will be cached
BUNDLE_CACHE_ROOT_FOLDER_NAME = "bundle_cache"


def _process_configuration(sg_connection, config_uri_str):
    """
    Resolve and download the given Toolkit configuration.

    :param sg_connection: Shotgun connection.
    :param config_uri_str: Toolkit config descriptor as a string.
    :returns: Resolved config descriptor object.
    """
    logger.info("Analyzing configuration")

    config_uri_dict = descriptor_uri_to_dict(config_uri_str)
    if config_uri_dict["type"] == bootstrap_constants.BAKED_DESCRIPTOR_TYPE:
        raise ValueError("The given config is already baked")

    # If the descriptor in the config contains a version number
    # we will go into a fixed update mode.
    using_latest_config = is_descriptor_version_missing(config_uri_dict)
    if using_latest_config:
        logger.info(
            "Your configuration definition does not contain a version number. "
            "Retrieving the latest version..."
        )
    cfg_descriptor = create_descriptor(
        sg_connection,
        Descriptor.CONFIG,
        config_uri_dict,
        resolve_latest=using_latest_config
    )
    cfg_descriptor.ensure_local()
    logger.info("Resolved config %r" % cfg_descriptor)
    return cfg_descriptor


def bake_config(sg_connection, config_uri, target_path, use_system_core=False):
    """
    Bake a Toolkit Pipeline configuration.

    This will ensure a local copy of the configuration, copy it over into target
    path and then establish a bundle cache containing a reflection of all items
    required by the config.

    :param sg_connection: Shotgun connection
    :param config_descriptor: A TK config descriptor.
    :param target_path: Path to build
    """
    logger.info("Your Toolkit config '%s' will be processed." % config_uri)
    logger.info("Baking into '%s'" % (target_path))

    config_uri_dict = descriptor_uri_to_dict(config_uri)
    config_descriptor = _process_configuration(sg_connection, config_uri)
    # Control the output path by adding a folder based on the
    # configuration descriptor and version.
    target_path = os.path.join(target_path, "%s-%s" % (
        config_descriptor.system_name,
        config_descriptor.version,
    ))

    # Check that target path doesn't exist
    if os.path.exists(target_path):
        logger.info("The folder '%s' already exists on disk. Removing it" % target_path)
        wipe_folder(target_path)

    # Create target path
    filesystem.ensure_folder_exists(target_path)
    # Copy the config data
    logger.info("Copying config data across...")
    filesystem.copy_folder(config_descriptor.get_path(), target_path)

    # Create bundle cache and cache all apps, engines and frameworks
    logger.info("Creating bundle cache folder...")
    bundle_cache_root = os.path.join(target_path, BUNDLE_CACHE_ROOT_FOLDER_NAME)
    filesystem.ensure_folder_exists(bundle_cache_root)
    logger.info("Downloading and caching config...")
    config_descriptor.clone_cache(bundle_cache_root)
    cache_apps(sg_connection, config_descriptor, bundle_cache_root)

    # Now analyze what core the config needs and cache it if needed.
    if config_descriptor.associated_core_descriptor:
        logger.info("Config is specifying a custom core in config/core/core_api.yml.")
        logger.info("This will be used when the config is executing.")
        logger.info(
            "Ensuring this core (%s) is cached..." % config_descriptor.associated_core_descriptor
        )
        associated_core_desc = create_descriptor(
            sg_connection,
            Descriptor.CORE,
            config_descriptor.associated_core_descriptor,
            bundle_cache_root_override=bundle_cache_root
        )
        associated_core_desc.ensure_local()
    cleanup_bundle_cache(bundle_cache_root)

    logger.info("")
    logger.info("Bake complete")
    logger.info("")
    logger.info("- Your configuration %r is ready in '%s'" % (config_descriptor, target_path))
    logger.info("- All dependencies have been baked out into the bundle_cache folder")
    logger.info("")
    logger.info("")
    logger.info("")


def main():
    """
    Main entry point for script.

    Handles argument parsing and validation and then calls the script payload.
    """

    usage = "%prog [options] config_descriptor target_path"

    desc = "Bake a self contained Toolkit config from a descriptor"

    epilog = """

Details and Examples
--------------------

In its simplest form, just provide a source and target folder for the build.

> python bake_config.py ~/dev/tk-maya/plugins/basic /tmp/maya-plugin

By default, the build script will use the latest app store core for its bootstrapping.
If you want to use a specific core for the bootstrap, this can be specified via the
--bootstrap-core-uri option:

> python bake_config.py
            --bootstrap-core-uri='sgtk:descriptor:dev?path=~/dev/tk-core'
            ~/dev/tk-maya/plugins/basic /tmp/maya-plugin

By using the '--bake' option, you can build a plugin with an immutable configuration
where every single Toolkit component is cached and frozen to the version retrieved at
build time. This can be useful to distribute a self contained plugin to third party
users.

> python bake_config.py
            ~/dev/tk-maya/plugins/basic /tmp/maya-plugin
            --bake

{automated_setup_documentation}

For information about the various descriptors that can be used, see
http://developer.shotgunsoftware.com/tk-core/descriptor


""".format(automated_setup_documentation=automated_setup_documentation)
    parser = OptionParserLineBreakingEpilog(usage=usage, description=desc, epilog=epilog)

    parser.add_option(
        "-d",
        "--debug",
        default=False,
        action="store_true",
        help="Enable debug logging"
    )

    add_authentication_options(parser)

    # parse cmd line
    (options, remaining_args) = parser.parse_args()

    logger.info("Welcome to the Toolkit config baker builder.")
    logger.info("")

    if options.debug:
        LogManager().global_debug = True

    if len(remaining_args) != 2:
        parser.print_help()
        return 2

    # Get config descriptor
    config_descriptor = remaining_args[0]
    # Try to parse it, check if it is a local path if it fails
    try:
        descriptor_uri_to_dict(config_descriptor)
    except TankDescriptorError as e:
        # Check if it is a local path
        path = os.path.abspath(
            os.path.expanduser(
                os.path.expandvars(config_descriptor)
            )
        )
        if os.path.isdir(path):
            logger.info("Using a dev descriptor for local path %s" % path)
            # Forge a dev descriptor, using "latest" for the version.
            # TODO: try to retrieve a git tag from the folder.
            config_descriptor = "sgtk:descriptor:dev?name=%s&path=%s&version=latest" % (
                os.path.basename(path), path
            )
        else:
            logger.error("%s is not a valid descriptor nor a local path." % config_descriptor)
            raise
    # Get output path
    target_path = remaining_args[1]
    target_path = os.path.expanduser(os.path.expandvars(target_path))

    sg_user = authenticate(options)

    sg_connection = sg_user.create_sg_connection()
    # make sure we are properly connected
    try:
        sg_connection.find_one("HumanUser", [])
    except Exception, e:
        logger.error("Could not communicate with Shotgun: %s" % e)
        return 3

    # we are all set.
    bake_config(
        sg_connection,
        config_descriptor,
        target_path,
    )

    # all good!
    return 0


if __name__ == "__main__":

    # set up std toolkit logging to file
    LogManager().initialize_base_file_handler("bake_config")

    # set up output of all sgtk log messages to stdout
    LogManager().initialize_custom_handler()

    exit_code = 1
    try:
        exit_code = main()
    except Exception, e:
        logger.exception("An exception was raised: %s" % e)

    sys.exit(exit_code)