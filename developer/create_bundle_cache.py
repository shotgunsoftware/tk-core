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
import os

import sys
import shutil
import optparse

# add sgtk API
this_folder = os.path.abspath(os.path.dirname(__file__))
python_folder = os.path.abspath(os.path.join(this_folder, "..", "python"))
sys.path.append(python_folder)

# sgtk imports
from tank import LogManager
from tank.util import filesystem
from tank.errors import TankError
from tank.descriptor import Descriptor, create_descriptor

from .utils import cache_apps, authenticate

# set up logging
logger = LogManager.get_logger("build_plugin")

# required keys in the info.yml plugin manifest file
REQUIRED_MANIFEST_PARAMETERS = ["base_configuration", "plugin_id"]

# the folder where all items will be cached
BUNDLE_CACHE_ROOT_FOLDER_NAME = "bundle_cache"


class OptionParserLineBreakingEpilog(optparse.OptionParser):
    """
    Subclassed version of the option parser that doesn't
    swallow white space in the epilog
    """
    def format_epilog(self, formatter):
        return self.epilog


def build_bundle_cache(sg_connection, target_path, config_descriptor_uri, bootstrap_core_uri):
    """
    Perform a build of the bundle cache.

    This will build the bundle cache for a given config descriptor.

    :param sg_connection: Shotgun connection
    :param target_path: Path to build
    :param config_descriptor_uri: Descriptor of the configuration to cache.
    :param bootstrap_core_uri: Descriptor of the core to cache if no core is associated with the
        configuration.
    """
    logger.info("The build will generated into '%s'" % target_path)

    # check that target path doesn't exist
    if os.path.exists(target_path):
        logger.info("The folder '%s' already exists on disk. Removing it" % target_path)
        shutil.rmtree(target_path)

    # try to create target path
    filesystem.ensure_folder_exists(target_path)

    # create bundle cache
    logger.info("Creating bundle cache folder...")
    bundle_cache_root = os.path.join(target_path, BUNDLE_CACHE_ROOT_FOLDER_NAME)
    filesystem.ensure_folder_exists(bundle_cache_root)

    # Resolve the configuration
    cfg_descriptor = create_descriptor(
        sg_connection,
        Descriptor.CONFIG,
        config_descriptor_uri,
        resolve_latest=False
    )

    logger.info("Resolved config %r" % cfg_descriptor)
    logger.info("Runtime config descriptor uri will be %s" % config_descriptor_uri)

    # cache config in bundle cache
    logger.info("Downloading and caching config...")

    # copy the config payload across to the plugin bundle cache
    cfg_descriptor.clone_cache(bundle_cache_root)

    # cache all apps, engines and frameworks
    cache_apps(sg_connection, cfg_descriptor, bundle_cache_root)

    if cfg_descriptor.associated_core_descriptor:
        logger.info("Config is specifying a custom core in config/core/core_api.yml.")
        logger.info("This will be used when the config is executing.")
        logger.info("Ensuring this core (%s) is cached..." % cfg_descriptor.associated_core_descriptor)
        associated_core_desc = create_descriptor(
            sg_connection,
            Descriptor.CORE,
            cfg_descriptor.associated_core_descriptor,
            bundle_cache_root_override=bundle_cache_root
        )
        associated_core_desc.ensure_local()
    elif bootstrap_core_uri:
        logger.info("Caching custom core for boostrap (%s)" % bootstrap_core_uri)
        bootstrap_core_desc = create_descriptor(
            sg_connection,
            Descriptor.CORE,
            bootstrap_core_uri,
            bundle_cache_root_override=bundle_cache_root
        )

    else:
        # by default, use latest core for bootstrap
        logger.info("Caching latest official core to use when bootstrapping plugin.")
        logger.info("(To use a specific config instead, specify a --bootstrap-core-uri flag.)")

        bootstrap_core_desc = create_descriptor(
            sg_connection,
            Descriptor.CORE,
            {"type": "app_store", "name": "tk-core"},
            resolve_latest=True,
            bundle_cache_root_override=bundle_cache_root
        )

    # cache it
    bootstrap_core_desc.ensure_local()

    logger.info("")
    logger.info("Build complete!")
    logger.info("")
    logger.info("- Your bundle cache is ready in '%s'" % target_path)
    logger.info("- All dependencies have been baked out into the bundle_cache folder")
    logger.info("")
    logger.info("")
    logger.info("")


def main():
    """
    Main entry point for script.

    Handles argument parsing and validation and then calls the script payload.
    """

    usage = "%prog [options] source_path target_path"

    desc = "Builds a standard toolkit plugin structure ready for testing and deploy"

    epilog = """

Details and Examples
--------------------

In its simplest form, just provide a source and target folder for the build.

> python build_plugin.py ~/dev/tk-maya/plugins/basic /tmp/maya-plugin

For automated build setups, you can provide a specific shotgun API script name and
and corresponding script key:

> python build_plugin.py
            --shotgun-host='https://mysite.shotgunstudio.com'
            --shotgun-script-name='plugin_build'
            --shotgun-script-key='<script-key-here>'
            ~/dev/tk-maya/plugins/basic /tmp/maya-plugin

By default, the build script will use the latest app store core for its bootstrapping.
If you want to use a specific core for the bootstrap, this can be specified via the
--bootstrap-core-uri option:

> python build_plugin.py
            --bootstrap-core-uri='sgtk:descriptor:dev?path=~/dev/tk-core'
            ~/dev/tk-maya/plugins/basic /tmp/maya-plugin

For information about the various descriptors that can be used, see
http://developer.shotgunsoftware.com/tk-core/descriptor


"""
    parser = OptionParserLineBreakingEpilog(usage=usage, description=desc, epilog=epilog)

    parser.add_option(
        "-d",
        "--debug",
        default=False,
        action="store_true",
        help="Enable debug logging"
    )

    parser.add_option(
        "-c",
        "--configuration",
        action="store",
        help="Descriptor pointing to the configuration to cache."
    )

    parser.add_option(
        "-c",
        "--bootstrap-core-uri",
        default=None,
        action="store",
        help=("Specify which version of core to be used by the bootstrap process. "
              "If not specified, defaults to the most recently released core. If the configuration "
              "has an associated core, this core descriptor is ignored.")
    )

    group = optparse.OptionGroup(
        parser,
        "Shotgun Authentication",
        "In order to download content from the Toolkit app store, the script will need to authenticate "
        "against any shotgun site. By default, it will use the toolkit authentication APIs stored "
        "credentials, and if such are not found, it will prompt for site, username and password."
    )

    group.add_option(
        "-s",
        "--shotgun-host",
        default=None,
        action="store",
        help="Shotgun host to authenticate with."
    )

    group.add_option(
        "-n",
        "--shotgun-script-name",
        default=None,
        action="store",
        help="Script to use to authenticate with the given host."
    )

    group.add_option(
        "-k",
        "--shotgun-script-key",
        default=None,
        action="store",
        help="Script key to use to authenticate with the given host."
    )

    parser.add_option_group(group)

    # parse cmd line
    (options, remaining_args) = parser.parse_args()

    logger.info("Welcome to the Toolkit bundle cache builder.")
    logger.info("")

    if options.debug:
        LogManager().global_debug = True

    if len(remaining_args) != 1:
        parser.print_help()
        return 2

    # get paths
    target_path = remaining_args[0]

    # convert any env vars and tildes
    target_path = os.path.expanduser(os.path.expandvars(target_path))

    sg_user = authenticate(options)

    # make sure we are properly connected
    sg_user.refresh_credentials()

    sg_connection = sg_user.create_sg_connection()

    # we are all set.
    build_bundle_cache(
        sg_connection,
        target_path,
        options.configuration
    )

    # all good!
    return 0


if __name__ == "__main__":

    # set up std toolkit logging to file
    LogManager().initialize_base_file_handler("build_plugin")

    # set up output of all sgtk log messages to stdout
    LogManager().initialize_custom_handler()

    exit_code = 1
    try:
        exit_code = main()
    except Exception, e:
        logger.exception("An exception was raised: %s" % e)

    sys.exit(exit_code)
