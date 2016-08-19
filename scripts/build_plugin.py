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
from tank.descriptor import Descriptor, descriptor_uri_to_dict, descriptor_dict_to_uri, create_descriptor
from tank.authentication import ShotgunAuthenticator
from tank.bootstrap.baked_configuration import BakedConfiguration
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

# generation of the build syntax
BUILD_GENERATION = 2

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
            if not desc._io_descriptor.is_immutable():
                logger.warning("Descriptor %r may not work for other users using the plugin!" % desc)
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
                if not desc._io_descriptor.is_immutable():
                    logger.warning("Descriptor %r may not work for other users using the plugin!" % desc)
                desc.clone_cache(bundle_cache_root)

        for framework in env.get_frameworks():
            desc = create_descriptor(
                sg_connection,
                Descriptor.FRAMEWORK,
                env.get_framework_descriptor_dict(framework),
                fallback_roots=[bundle_cache_root]
            )
            logger.info("Caching %s..." % desc)
            if not desc._io_descriptor.is_immutable():
                logger.warning("Descriptor %r may not work for other users using the plugin!" % desc)
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
    :return: (Resolved config descriptor object, config descriptor uri to use at runtime)
    """
    logger.info("Analyzing configuration")

    # get config def from info yml and generate both
    # dict and string uris.
    base_config_def = manifest_data["base_configuration"]
    if isinstance(base_config_def, str):
        # convert to dict so we can introspect
        base_config_uri_dict = descriptor_uri_to_dict(base_config_def)
        base_config_uri_str = base_config_def
    else:
        base_config_uri_dict = base_config_def
        base_config_uri_str = descriptor_dict_to_uri(base_config_def)

    # Special case - check for the 'baked' descriptor type
    # and process it. A baked descriptor is a special concept
    # that only exists in the build script. The baked descriptor
    # takes a single path parameter which can be a local or absolute
    # path. The path is copied across by the build script into a
    # manual descriptor, with a version number based on the current date.
    # This ensures that the manual descriptor will be correctly
    # re-cached at bootstrap time.
    if base_config_uri_dict["type"] == "baked":
        logger.info("Baked descriptor detected.")

        baked_path = os.path.expanduser(os.path.expandvars(base_config_uri_dict["path"]))

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

        install_path = os.path.join(target_path, "bundle_cache", "baked", BAKED_BUNDLE_NAME, BAKED_BUNDLE_VERSION)

        cfg_descriptor = create_descriptor(
            sg_connection,
            Descriptor.CONFIG,
            {"type": "path", "path": full_baked_path},
            fallback_roots=[bundle_cache_root]
        )

        BakedConfiguration.bake_config_scaffold(
            install_path,
            sg_connection,
            manifest_data["entry_point"],
            cfg_descriptor
        )

        # now lastly,
        base_config_uri_str = descriptor_dict_to_uri(
            {"type": "baked", "name": BAKED_BUNDLE_NAME, "version": BAKED_BUNDLE_VERSION}
        )

    else:

        # if the descriptor in the config contains a version number
        # we will go into a fixed update mode.
        if "version" in base_config_uri_dict:
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
            base_config_uri_dict,
            fallback_roots=[bundle_cache_root],
            resolve_latest=using_latest_config
        )

    logger.info("Resolved config %r" % cfg_descriptor)
    logger.info("Runtime config descriptor uri will be %s" % base_config_uri_str)
    return cfg_descriptor, base_config_uri_str

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
    try:
        with open(manifest_path, "rt") as fh:
            manifest_data = yaml.load(fh)
    except Exception, e:
        raise TankError("Cannot parse info.yml manifest: %s" % e)

    logger.debug("Validating manifest...")
    for parameter in REQUIRED_MANIFEST_PARAMETERS:
        if parameter not in manifest_data:
            raise TankError(
                "Required plugin manifest parameter '%s' missing in '%s'" % (parameter, manifest_path)
            )

    return manifest_data

def _bake_manifest(manifest_data, config_uri, core_descriptor, plugin_root):
    """
    Bake the info.yml manifest into a python file.

    :param manifest_data: info.yml manifest data
    :param config_uri: Configuration descriptor uri string to use at runtime
    :param core_descriptor: descriptor object pointing at core to use for bootstrap
    :param plugin_root: Root path for plugin
    """
    # add entry point to our module to ensure multiple plugins can live side by side
    module_name = "sgtk_plugin_%s" % manifest_data["entry_point"]
    full_module_path = os.path.join(plugin_root, "python", module_name)
    filesystem.ensure_folder_exists(full_module_path)

    # write __init__.py
    try:
        with open(os.path.join(full_module_path, "__init__.py"), "wt") as fh:
            fh.write("# this file was auto generated.\n")
            fh.write("from . import manifest\n")
            fh.write("# end of file.\n")
    except Exception, e:
        raise TankError("Cannot write __init__.py file: %s" % e)

    # now bake out the manifest into code
    params_path = os.path.join(full_module_path, "manifest.py")

    try:

        with open(params_path, "wt") as fh:

            fh.write("# this file was auto generated.\n\n\n")

            fh.write("base_configuration=\"%s\"\n" % config_uri)

            for (parameter, value) in manifest_data.iteritems():

                if parameter == "base_configuration":
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
                    getpass.getuser(),
                    socket.getfqdn(),
                )
            )
            fh.write("BUILD_GENERATION=%d\n" % BUILD_GENERATION)

            # Write out helper function 'get_sgtk_pythonpath()'.
            core_path_parts = os.path.normpath(core_descriptor.get_path()).split(os.path.sep)
            core_path_relative_parts = core_path_parts[core_path_parts.index(BUNDLE_CACHE_ROOT_FOLDER_NAME):]
            core_path_relative_parts.append("python")

            fh.write("\n\n")
            fh.write("def get_sgtk_pythonpath(plugin_root):\n")
            fh.write("    import os\n")
            fh.write("    return os.path.join(plugin_root, %s)\n" %
                     ", ".join('"%s"' % dir for dir in core_path_relative_parts))
            fh.write("\n\n")

            fh.write("# end of file.\n")

    except Exception, e:
        raise TankError("Cannot write manifest file: %s" % e)


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
        logger.info("The folder '%s' already exists on disk. Moving it to backup location" % target_path)
        filesystem.backup_folder(target_path)

    # try to create target path
    filesystem.ensure_folder_exists(target_path)

    # check manifest
    manifest_data = _validate_manifest(source_path)

    # copy all plugin data across
    # skip info.yml, this is baked into the manifest python code
    logger.info("Copying plugin data across...")
    filesystem.copy_folder(source_path, target_path, skip_list=["info.yml", ".git"])

    # create bundle cache
    logger.info("Creating bundle cache folder...")
    bundle_cache_root = os.path.join(target_path, BUNDLE_CACHE_ROOT_FOLDER_NAME)
    filesystem.ensure_folder_exists(bundle_cache_root)

    # resolve config descriptor
    # the config_uri_str returned by the method contains the fully resolved
    # uri to use at runtime - in the case of baked descriptors, the config_uri_str
    # contains a manual descriptor uri.
    (cfg_descriptor, config_uri_str) = _process_configuration(
        sg_connection,
        source_path,
        target_path,
        bundle_cache_root,
        manifest_data
    )

    # cache config in bundle cache
    logger.info("Downloading and caching config...")
    cfg_descriptor.clone_cache(bundle_cache_root)

    # cache all apps, engines and frameworks
    _cache_apps(sg_connection, cfg_descriptor, bundle_cache_root)

    # get latest core
    logger.info("Caching latest official core...")
    latest_core_desc = create_descriptor(
        sg_connection,
        Descriptor.CORE,
        {"type": "app_store", "name": "tk-core"},
        resolve_latest=True,
        fallback_roots=[bundle_cache_root]
    )

    latest_core_desc.clone_cache(bundle_cache_root)

    # make a python folder where we put our manifest
    logger.info("Creating configuration manifest...")

    # bake out the manifest into python files.
    _bake_manifest(
        manifest_data,
        config_uri_str,
        latest_core_desc,
        target_path
    )

    # now analyze what core the config needs
    if cfg_descriptor.associated_core_descriptor:
        logger.info("Config is using a custom core. Caching it...")
        associated_core_desc = create_descriptor(
            sg_connection,
            Descriptor.CORE,
            cfg_descriptor.associated_core_descriptor,
            fallback_roots=[bundle_cache_root]
        )
        associated_core_desc.clone_cache(bundle_cache_root)


    logger.info("")
    logger.info("Build complete!")
    logger.info("")
    logger.info("- Your plugin is ready in '%s'" % target_path)
    logger.info("- Plugin uses config %s" % cfg_descriptor)
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
    except Exception, e:
        logger.exception("An exception was raised: %s" % e)

    sys.exit(exit_code)
