# Copyright (c) 2018 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Helper script to bake a Toolkit pipeline configuration given a descriptor uri or
a local path.
"""

# system imports
from __future__ import with_statement
import os
import sys
import shutil

# add sgtk API
this_folder = os.path.abspath(os.path.dirname(__file__))
python_folder = os.path.abspath(os.path.join(this_folder, "..", "python"))
sys.path.append(python_folder)

# sgtk imports
from tank import LogManager
from tank.util import filesystem
from tank.errors import TankError
from tank.descriptor import Descriptor, descriptor_uri_to_dict
from tank.descriptor import create_descriptor, is_descriptor_version_missing
from tank.descriptor.errors import TankDescriptorError
from tank.bootstrap import constants as bootstrap_constants

from utils import (
    cache_apps, authenticate, add_authentication_options,
    OptionParserLineBreakingEpilog, cleanup_bundle_cache,
    wipe_folder, automated_setup_documentation
)

# Set up logging
logger = LogManager.get_logger("bake_config")

# The folder where all items will be cached
BUNDLE_CACHE_ROOT_FOLDER_NAME = "bundle_cache"


def _should_skip_caching_sparse(desc):
    """
    Returns if a descriptor's content should not be cached.

    We should not attempt to cache descriptors that are path-based. Not only don't they
    need to be cached, but they might be using special tokens like CONFIG_FOLDER
    that can't be understood outside a pipeline configuration. We also skip caching
    app_store descriptors in sparse configs since SG Desktop will take care of downloading
    these automatically from the app store at runtime.

    :param dict desc: Descriptor to check.
    :returns: ``True`` if the contents should be skipped, ``False`` otherwise.
    """
    return desc["type"] in ["dev", "path", "app_store"]


def _process_configuration(sg_connection, config_uri_str):
    """
    Resolve and download the given Toolkit configuration.

    :param sg_connection: Shotgun connection.
    :param config_uri_str: Toolkit config descriptor as a string.
    :returns: Resolved config descriptor object.
    :raises: ValueError for "baked" descriptors.
    """
    logger.info("Analyzing configuration")

    config_uri_dict = descriptor_uri_to_dict(config_uri_str)
    if config_uri_dict["type"] == bootstrap_constants.BAKED_DESCRIPTOR_TYPE:
        raise ValueError("The given config is already baked")

    # If the config descriptor does not contain a version number, get the
    # latest.
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


def bake_config(sg_connection, config_uri, target_path, do_zip=False, sparse_caching=False):
    """
    Bake a Toolkit Pipeline configuration.

    This will ensure a local copy of the configuration, copy it over into target
    path and then establish a bundle cache containing a reflection of all items
    required by the config.

    :param sg_connection: Shotgun connection
    :param config_uri: A TK config descriptor uri.
    :param target_path: Path to build
    :param do_zip: Optionally zip up config once it's baked. Defaults to False.
    :param sparse_caching: Don't cache app_store bundles into the config. Defaults to False.
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
        logger.info(
            "The folder '%s' already exists on disk. Removing it" % target_path
        )
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

    # If sparse_caching is True, we use our own descriptor filter which skips
    # app_store descriptors to keep our bundle cache small and lets Toolkit
    # download the bundles from the app store at runtime.
    if sparse_caching:
        logger.info("Performing sparse caching. Will not cache standard app_store bundles.")
        cache_apps(sg_connection, config_descriptor, bundle_cache_root, _should_skip_caching_sparse)
    else:
        cache_apps(sg_connection, config_descriptor, bundle_cache_root)

    # Now analyze what core the config needs and cache it if needed.
    core_descriptor = config_descriptor.associated_core_descriptor
    if core_descriptor:
        logger.info("Config defines a specific core in config/core/core_api.yml.")
        logger.info("This will be used when the config is executing.")
        # If sparse_caching is True, check if we need to cache tk-core or not
        if not sparse_caching or not _should_skip_caching_sparse(core_descriptor):
            logger.info(
                "Ensuring this core (%s) is cached..." % core_descriptor
            )
            associated_core_desc = create_descriptor(
                sg_connection,
                Descriptor.CORE,
                core_descriptor,
                bundle_cache_root_override=bundle_cache_root
            )
            associated_core_desc.ensure_local()
        else:
            logger.info(
                "No need to cache this core (%s), it will be cached at runtime." %
                config_descriptor.associated_core_descriptor
            )

    # Remove unwanted files, e.g. git history.
    cleanup_bundle_cache(bundle_cache_root)

    logger.info("")
    logger.info("Bake complete")
    logger.info("")
    logger.info("- Your configuration %r is ready in '%s'" % (config_descriptor, target_path))
    logger.info("- All dependencies have been baked out into the bundle_cache folder")
    logger.info("")
    logger.info("")
    logger.info("")
    if do_zip:
        logger.info("Zip archiving the baked configuration...")
        archive_path = shutil.make_archive(
            target_path,
            "zip",
            root_dir=target_path
        )
        logger.info("Zip archive available here: %s" % archive_path)


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

In its simplest form, just provide a local path and target folder for the build.

> python bake_config.py ~/dev/tk-config-myconfig /tmp/baked_configurations

Or you can specify a version with a Toolkit config descriptor uri.

> python bake_config.py "sgtk:descriptor:dev?version=v1.0.9&path=../tk-config-myconfig" /tmp/baked_configurations

Any type of Toolkit config descriptor uri can be used, if a version is not specified, the latest for the descriptor is resolved.

> python bake_config.py "sgtk:descriptor:app_store?name=tk-config-basic" /tmp/baked_configurations

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

    parser.add_option(
        "-z",
        "--zip",
        default=False,
        action="store_true",
        help="Zip archive the config"
    )

    parser.add_option(
        "-r",
        "--sparse",
        default=False,
        action="store_true",
        help="Don't cache any app_store bundles"
    )

    add_authentication_options(parser)

    # parse cmd line
    (options, remaining_args) = parser.parse_args()

    logger.info("Welcome to the Toolkit config baker.")
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
            # TODO: try to retrieve a valid version from the folder, e.g. with a
            # git tag from the folder.
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
        options.zip,
        options.sparse
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
