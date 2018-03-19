# Copyright (c) 2017 Shotgun Software Inc.
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
import os

import sys

# add sgtk API
this_folder = os.path.abspath(os.path.dirname(__file__))
python_folder = os.path.abspath(os.path.join(this_folder, "..", "python"))
sys.path.append(python_folder)

# sgtk imports
from sgtk import LogManager
from sgtk.util import filesystem
from sgtk.descriptor import Descriptor, create_descriptor, is_descriptor_version_missing

from utils import (
    cache_apps, authenticate, add_authentication_options, OptionParserLineBreakingEpilog, cleanup_bundle_cache,
    automated_setup_documentation
)

# set up logging
logger = LogManager.get_logger("populate_bundle_cache")

# the folder where all items will be cached
BUNDLE_CACHE_ROOT_FOLDER_NAME = "bundle_cache"


def _build_bundle_cache(sg_connection, target_path, config_descriptor_uri):
    """
    Perform a build of the bundle cache.

    This will build the bundle cache for a given config descriptor.

    :param sg_connection: Shotgun connection
    :param target_path: Path to build
    :param config_descriptor_uri: Descriptor of the configuration to cache.
    """
    logger.info("The build will generated into '%s'" % target_path)

    bundle_cache_root = os.path.join(target_path, BUNDLE_CACHE_ROOT_FOLDER_NAME)

    # try to create target path
    logger.info("Creating bundle cache folder...")
    filesystem.ensure_folder_exists(bundle_cache_root)

    # Resolve the configuration
    cfg_descriptor = create_descriptor(
        sg_connection,
        Descriptor.CONFIG,
        config_descriptor_uri,
        # If the user hasn't specified the version to retrieve, resolve the latest from Shotgun.
        resolve_latest=is_descriptor_version_missing(config_descriptor_uri)
    )

    logger.info("Resolved config %r" % cfg_descriptor)
    logger.info("Runtime config descriptor uri will be %s" % config_descriptor_uri)

    # cache config in bundle cache
    logger.info("Downloading and caching config...")

    cfg_descriptor.ensure_local()

    # copy the config payload across to the plugin bundle cache
    cfg_descriptor.clone_cache(bundle_cache_root)

    # cache all apps, engines and frameworks
    cache_apps(sg_connection, cfg_descriptor, bundle_cache_root)

    if cfg_descriptor.associated_core_descriptor:
        logger.info("Config is specifying a custom core in config/core/core_api.yml.")
        logger.info("This will be used when the config is executing.")
        logger.info("Ensuring this core (%s) is cached..." % cfg_descriptor.associated_core_descriptor)
        bootstrap_core_desc = create_descriptor(
            sg_connection,
            Descriptor.CORE,
            cfg_descriptor.associated_core_descriptor,
            bundle_cache_root_override=bundle_cache_root
        )
        # cache it
        bootstrap_core_desc.ensure_local()
        bootstrap_core_desc.clone_cache(bundle_cache_root)

    cleanup_bundle_cache(bundle_cache_root)

    logger.info("")
    logger.info("Build complete!")
    logger.info("")
    logger.info("- Your bundle cache is ready in '%s'" % target_path)
    logger.info("- All dependencies have been baked out into the bundle_cache folder")
    logger.info("")


def main():
    """
    Main entry point for script.

    Handles argument parsing and validation and then calls the script payload.
    """

    usage = "%prog [options] config_descriptor target_path"

    desc = "Populates a bundle cache for a given configuration."

    epilog = """

Details and Examples
--------------------

In it's simplest form, provide a descriptor to a configuration and the location
where the bundle cache should be created.

> python populate_bundle_cache.py
            "sgtk:descriptor:app_store?version=v0.3.6&name=tk-config-basic"
            /tmp

Note that it is important to use quotes around the descriptor as shells usually
give special meaning to the & character.

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

    logger.info("Welcome to the Toolkit bundle cache builder.")
    logger.info("")

    if options.debug:
        LogManager().global_debug = True

    if len(remaining_args) != 2:
        parser.print_help()
        return 2

    # get paths
    config_descriptor_str = remaining_args[0]
    target_path = remaining_args[1]

    # convert any env vars and tildes
    target_path = os.path.expanduser(os.path.expandvars(target_path))

    sg_user = authenticate(options)

    sg_connection = sg_user.create_sg_connection()

    # we are all set.
    _build_bundle_cache(
        sg_connection,
        target_path,
        config_descriptor_str
    )

    # all good!
    return 0


if __name__ == "__main__":

    # set up std toolkit logging to file
    LogManager().initialize_base_file_handler("build_bundle_cache")

    # set up output of all sgtk log messages to stdout
    LogManager().initialize_custom_handler()

    exit_code = 1
    try:
        exit_code = main()
    except Exception, e:
        logger.exception("An exception was raised: %s" % e)

    sys.exit(exit_code)
