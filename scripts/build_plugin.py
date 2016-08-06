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
import socket
import shutil
import optparse
import datetime
import getpass

# add sgtk API
this_folder = os.path.abspath(os.path.dirname(__file__))
python_folder = os.path.abspath(os.path.join(this_folder, "..", "python"))
sys.path.append(python_folder)

# sgtk imports
from tank import LogManager
from tank.util import filesystem
from tank.errors import TankError
from tank.platform import environment
from tank.descriptor import Descriptor, descriptor_uri_to_dict, create_descriptor
from tank.authentication import ShotgunAuthenticator
from tank_vendor import yaml

# set up logging
logger = LogManager.get_logger("build_plugin")

# required keys in the info.yml plugin manifest file
REQUIRED_MANIFEST_PARAMETERS = ["base_configuration", "entry_point"]

# the folder where all items will be cached
BUNDLE_CACHE_ROOT_FOLDER_NAME = "bundle_cache"

# when we are baking a config, use these settings
BAKED_BUNDLE_NAME = "tk-config-plugin"
BAKED_BUNDLE_VERSION = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


class OptionParserLineBreakingEpilog(optparse.OptionParser):
    """
    Subclassed version of the option parser that doesn't
    swallow white space in the epilog
    """
    def format_epilog(self, formatter):
        return self.epilog

def _cache_apps(sg_connection, cfg_descriptor, bundle_cache_root):
    """
    Iterates over all environments within the given configuration descriptor
    and caches all items into the bundle cache root.

    :param sg_connection: Shotgun connection
    :param cfg_descriptor: Config descriptor
    :param bundle_cache_root: Root where to cache payload
    """
    # introspect the config and cache everything
    logger.info("Introspecting environments...")
    env_path = os.path.join(cfg_descriptor.get_path(), "env")

    # find all environment files
    env_filenames = []
    for filename in os.listdir(env_path):
        if filename.endswith(".yml"):
            # matching the env filter (or no filter set)
            logger.info("> found %s" % filename)
            env_filenames.append(os.path.join(env_path, filename))

    # traverse and cache
    for env_path in env_filenames:
        logger.info("Processing %s..." % env_path)
        env = environment.Environment(env_path)

        for eng in env.get_engines():
            # resolve descriptor and clone cache into bundle cache
            desc = create_descriptor(
                sg_connection,
                Descriptor.ENGINE,
                env.get_engine_descriptor_dict(eng),
                fallback_roots=[bundle_cache_root]
            )
            logger.info("Caching %s..." % desc)
            desc.clone_cache(bundle_cache_root)

            for app in env.get_apps(eng):
                # resolve descriptor and clone cache into bundle cache
                desc = create_descriptor(
                    sg_connection,
                    Descriptor.APP,
                    env.get_app_descriptor_dict(eng, app),
                    fallback_roots=[bundle_cache_root]
                )
                logger.info("Caching %s..." % desc)
                desc.clone_cache(bundle_cache_root)

        for framework in env.get_frameworks():
            desc = create_descriptor(
                sg_connection,
                Descriptor.FRAMEWORK,
                env.get_framework_descriptor_dict(framework),
                fallback_roots=[bundle_cache_root]
            )
            logger.info("Caching %s..." % desc)
            desc.clone_cache(bundle_cache_root)

def _process_configuration(sg_connection, source_path, target_path, bundle_cache_root, manifest_data):
    """
    Given data in the plugin manifest, download resolve and
    cache the configuration.

    :param sg_connection: Shotgun connection
    :param manifest_data: Manifest data as a dictionary
    :param source_path: Root path of plugin source.
    :param target_path: Build target path
    :param bundle_cache_root: Bundle cache root
    :return: Resolved config descriptor object
    """
    logger.info("Analyzing configuration")

    base_config_def = manifest_data["base_configuration"]

    if isinstance(base_config_def, str):
        # convert to dict so we can introspect
        base_config_def = descriptor_uri_to_dict(base_config_def)

    # special case - check for the 'baked' descriptor type
    # and process it
    if base_config_def["type"] == "baked":
        logger.info("Baked descriptor detected.")

        baked_path = os.path.expanduser(os.path.expandvars(base_config_def["path"]))

        # if it's a relative path, expand it
        if not os.path.isabs(baked_path):
            full_baked_path = os.path.abspath(os.path.join(source_path, baked_path))

            # if it's a relative path, we have already copied it to the build
            # target location. In this case, attempt to locate it and remove it.
            baked_target_path = os.path.abspath(os.path.join(target_path, baked_path))
            if baked_target_path.startswith(baked_target_path):
                logger.debug("Removing '%s' from build" % baked_target_path)
                shutil.rmtree(baked_target_path)
        else:
            # path is absolute
            full_baked_path = os.path.abspath(baked_path)

        logger.info("Will bake config from '%s'" % full_baked_path)

        manual_location = os.path.join(bundle_cache_root, "manual", BAKED_BUNDLE_NAME, BAKED_BUNDLE_VERSION)
        logger.info("Copying %s -> %s" % (full_baked_path, manual_location))
        filesystem.ensure_folder_exists(manual_location)
        filesystem.copy_folder(full_baked_path, manual_location)

        # now make a manual descriptor
        descriptor = {
            "type": "manual",
            "version": BAKED_BUNDLE_VERSION,
            "name": BAKED_BUNDLE_NAME
        }

        cfg_descriptor = create_descriptor(
            sg_connection,
            Descriptor.CONFIG,
            descriptor,
            fallback_roots=[bundle_cache_root]
        )

    else:

        # if the descriptor in the config contains a version number
        # we will go into a fixed update mode.
        if "version" in base_config_def:
            logger.info(
                "Your configuration definition contains a version number. "
                "This means that the plugin will be frozen and no automatic updates "
                "will be performed at startup."
            )
            using_latest_config = False
        else:
            logger.info(
                "Your configuration definition does not contain a version number. "
                "This means that the plugin will attempt to auto update at startup."
            )
            using_latest_config = True

        cfg_descriptor = create_descriptor(
            sg_connection,
            Descriptor.CONFIG,
            base_config_def,
            fallback_roots=[bundle_cache_root],
            resolve_latest=using_latest_config
        )

    logger.info("Resolved config %r" % cfg_descriptor)
    return cfg_descriptor

def _validate_manifest(source_path):
    """
    Validate that the manifest file is present and valid.

    :param source_path: Source path to plugin
    :return: parsed yaml content of manifest file
    """
    # check for source manifest file
    manifest_path = os.path.join(source_path, "info.yml")
    if not os.path.exists(manifest_path):
        raise TankError("Cannot find plugin manifest '%s'" % manifest_path)

    logger.debug("Reading %s" % manifest_path)
    with open(manifest_path, "rt") as fh:
        manifest_data = yaml.load(fh)

    logger.debug("Validating manifest...")
    for parameter in REQUIRED_MANIFEST_PARAMETERS:
        if parameter not in manifest_data:
            raise TankError(
                "Required plugin manifest parameter '%s' missing in '%s'" % (parameter, manifest_path)
            )

    return manifest_data

def _bake_manifest(manifest_data, cfg_descriptor, python_bundle_cache):
    """
    Bake the info.yml manifest into a python file.

    :param manifest_data: info.yml manifest data
    :param cfg_descriptor: descriptor object pointing at the config to use
    :param sgtk_plugin_path: path to std bundle_cache/python location
    """
    # add entry point to our module to ensure multiple plugins can live side by side
    module_name = "sgtk_plugin_%s" % manifest_data["entry_point"]
    full_module_path = os.path.join(python_bundle_cache, module_name)
    filesystem.ensure_folder_exists(full_module_path)

    # write init.py
    with open(os.path.join(full_module_path, "__init__.py"), "wt") as fh:
        fh.write("# this file was auto generated.\n")
        fh.write("from . import manifest\n")
        fh.write("# end of file.\n")

    # now bake out the manifest into code
    params_path = os.path.join(full_module_path, "manifest.py")
    with open(params_path, "wt") as fh:

        fh.write("# this file was auto generated.\n")

        fh.write("\nbase_configuration=\"%s\"\n\n" % cfg_descriptor.get_uri())

        for (parameter, value) in manifest_data.iteritems():

            if parameter == "base_configuration":
                # configuration is processed separately
                continue

            if isinstance(value, str):
               fh.write("%s=\"%s\"\n" % (parameter, value.replace("\"", "'")))
            elif isinstance(value, int):
                fh.write("%s=%d\n" % (parameter, value))
            elif isinstance(value, bool):
                fh.write("%s=%s\n" % (parameter, value))
            else:
                raise ValueError(
                    "Invalid manifest value %s: %s - data type not supported!" % (parameter, value)
                )

        fh.write("\n\n# system generated parameters\n")
        fh.write(
            "BUILD_INFO=\"%s %s@%s\"\n" % (
                datetime.datetime.now().strftime("%Y%m%d_%H%M%S"),
                socket.getfqdn(),
                getpass.getuser()
            )
        )
        fh.write("\n# end of file.\n")

def build_plugin(sg_connection, source_path, target_path):
    """
    Perform a build of a plugin.

    This will introspect the info.yml in the source path,
    copy over everything in the source path into target path
    and then establish a bundle cache containing a reflection
    of all items required by the config.

    :param sg_connection: Shotgun connection
    :param source_path: Path to plugin.
    :param target_path: Path to build
    """
    logger.info("Your toolkit plugin in '%s' will be processed." % source_path)
    logger.info("The build will generated into '%s'" % target_path)

    # check for existence
    if not os.path.exists(source_path):
        raise TankError("Source path '%s' cannot be found on disk!" % source_path)

    # check that target path doesn't exist
    if os.path.exists(target_path):
        logger.info("The folder '%s' already exists on disk." % target_path)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = "%s.%s" % (target_path, timestamp)
        filesystem.move_folder(target_path, backup_path)
        logger.info("...moved it to '%s'" % backup_path)

    # try to create target path
    filesystem.ensure_folder_exists(target_path)

    # check manifest
    manifest_data = _validate_manifest(source_path)

    # copy all plugin data across
    # skip info.yml, this is baked into the manifest python code
    logger.info("Copying plugin data across...")
    filesystem.copy_folder(source_path, target_path, skip_list=["info.yml"])

    # create bundle cache
    logger.info("Creating bundle cache folder...")
    bundle_cache_root = os.path.join(target_path, BUNDLE_CACHE_ROOT_FOLDER_NAME)
    filesystem.ensure_folder_exists(bundle_cache_root)

    # resolve config descriptor
    cfg_descriptor = _process_configuration(sg_connection, source_path, target_path, bundle_cache_root, manifest_data)

    # cache config in bundle cache
    logger.info("Downloading and caching config...")
    cfg_descriptor.clone_cache(bundle_cache_root)

    # cache all apps, engines and frameworks
    _cache_apps(sg_connection, cfg_descriptor, bundle_cache_root)

    # get latest core
    latest_core_desc = create_descriptor(
        sg_connection,
        Descriptor.CORE,
        {"type": "app_store", "name": "tk-core"},
        resolve_latest=True
    )

    logger.info("Downloading latest official core %s" % latest_core_desc)
    latest_core_desc.ensure_local()

    # copy into bundle_cache/tk-core
    logger.info("Copying raw core libs into fixed bootstrap location bundle_cache/python...")

    python_bundle_cache = os.path.join(target_path, "bundle_cache", "python")

    filesystem.copy_folder(
        os.path.join(latest_core_desc.get_path(), "python"),
        python_bundle_cache
    )
    logger.info("Copying sgtk_plugin module into bundle_cache/python...")
    # bake out the manifest into python files.
    _bake_manifest(manifest_data, cfg_descriptor, python_bundle_cache)

    # now analyze what core the config needs
    if cfg_descriptor.associated_core_descriptor:
        logger.info("Config is using a custom core...")
        associated_core_desc = create_descriptor(
            sg_connection,
            Descriptor.CORE,
            cfg_descriptor.associated_core_descriptor,
            fallback_roots=[bundle_cache_root]
        )
        logger.info("Caching %s" % associated_core_desc)
        associated_core_desc.clone_cache(bundle_cache_root)

    else:
        # config requires latest core
        logger.info("Caching latest core %s" % latest_core_desc)
        latest_core_desc.clone_cache(bundle_cache_root)


    logger.info("")
    logger.info("Build complete!")
    logger.info("")
    logger.info("- Your plugin is ready in '%s'" % target_path)
    logger.info("- Plugin uses config %s" % cfg_descriptor)
    logger.info("- A bootstrap core has been installed into bundle_cache/tk-core")
    logger.info("- Bootstrap core is %s" % latest_core_desc)
    logger.info("- All dependencies have been baked out into the bundle_cache folder")
    logger.info("")
    logger.info("")
    logger.info("")



def main():
    """
    Main entry point for script.

    Handles argument parsing and validation and then calls the script payload.
    """

    usage = "%prog source_path target_path (run with --help for more information)"

    desc = "Builds a standard toolkit plugin structure ready for testing and deploy"

    epilog = """
Examples:

> python build_plugin.py ~/dev/tk-maya/plugins/basic /tmp/maya-plugin

"""
    parser = OptionParserLineBreakingEpilog(usage=usage, description=desc, epilog=epilog)

    parser.add_option("-d", "--debug",
                      default=False,
                      action="store_true",
                      help="Enable debug logging"
                      )

    # parse cmd line
    (options, remaining_args) = parser.parse_args()

    logger.info("Welcome to the Toolkit plugin builder.")
    logger.info("")

    if options.debug:
        LogManager().global_debug = True

    if len(remaining_args) != 2:
        parser.print_help()
        return

    # get paths
    source_path = remaining_args[0]
    target_path = remaining_args[1]

    # convert any env vars and tildes
    source_path = os.path.expanduser(os.path.expandvars(source_path))
    target_path = os.path.expanduser(os.path.expandvars(target_path))

    # now authenticate to shotgun
    sg_auth = ShotgunAuthenticator()
    sg_user = sg_auth.get_user()
    sg_connection = sg_user.create_sg_connection()

    # we are all set.
    build_plugin(sg_connection, source_path, target_path)


if __name__ == "__main__":

    # set up std toolkit logging to file
    LogManager().initialize_base_file_handler("build_plugin")

    # set up output of all sgtk log messages to stdout
    LogManager().initialize_custom_handler()

    exit_code = 1
    try:
        main()
        exit_code = 0
    except TankError, e:
        logger.error(str(e))
    except Exception, e:
        logger.exception("An exception was raised: %s" % e)

    sys.exit(exit_code)
