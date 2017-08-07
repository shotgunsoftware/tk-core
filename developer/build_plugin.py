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
from tank.bootstrap.baked_configuration import BakedConfiguration
from tank.bootstrap import constants as bootstrap_constants
from tank_vendor import yaml

from utils import (
    cache_apps, authenticate, add_authentication_options, OptionParserLineBreakingEpilog, cleanup_bundle_cache,
    wipe_folder
)

# set up logging
logger = LogManager.get_logger("build_plugin")

# required keys in the info.yml plugin manifest file
REQUIRED_MANIFEST_PARAMETERS = ["base_configuration", "plugin_id"]

# the folder where all items will be cached
BUNDLE_CACHE_ROOT_FOLDER_NAME = "bundle_cache"

# when we are baking a config, use these settings
BAKED_BUNDLE_NAME = "tk-config-plugin"
BAKED_BUNDLE_VERSION = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

# generation of the build syntax
BUILD_GENERATION = 2


def _process_configuration(sg_connection, source_path, target_path, bundle_cache_root, manifest_data):
    """
    Given data in the plugin manifest, download resolve and
    cache the configuration.

    :param sg_connection: Shotgun connection
    :param source_path: Root path of plugin source.
    :param target_path: Build target path
    :param bundle_cache_root: Bundle cache root
    :param manifest_data: Manifest data as a dictionary
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
    if base_config_uri_dict["type"] == bootstrap_constants.BAKED_DESCRIPTOR_TYPE:
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

        logger.info("Will bake an immutable config into the plugin from '%s'" % full_baked_path)

        install_path = os.path.join(
            bundle_cache_root,
            bootstrap_constants.BAKED_DESCRIPTOR_FOLDER_NAME,
            BAKED_BUNDLE_NAME,
            BAKED_BUNDLE_VERSION
        )

        cfg_descriptor = create_descriptor(
            sg_connection,
            Descriptor.CONFIG,
            {"type": "path", "path": full_baked_path}
        )

        BakedConfiguration.bake_config_scaffold(
            install_path,
            sg_connection,
            manifest_data["plugin_id"],
            cfg_descriptor
        )

        # now lastly,
        base_config_uri_str = descriptor_dict_to_uri(
            {
                "type": bootstrap_constants.BAKED_DESCRIPTOR_TYPE,
                "name": BAKED_BUNDLE_NAME,
                "version": BAKED_BUNDLE_VERSION
            }
        )

    else:

        # if the descriptor in the config contains a version number
        # we will go into a fixed update mode.
        if is_descriptor_version_missing(base_config_uri_dict):
            logger.info(
                "Your configuration definition does not contain a version number. "
                "This means that the plugin will attempt to auto update at startup."
            )
            using_latest_config = True
        else:
            logger.info(
                "Your configuration definition contains a version number. "
                "This means that the plugin will be frozen and no automatic updates "
                "will be performed at startup."
            )
            using_latest_config = False

        cfg_descriptor = create_descriptor(
            sg_connection,
            Descriptor.CONFIG,
            base_config_uri_dict,
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

    # legacy check - if we find entry_point, convert it across
    # to be plugin_id
    if "entry_point" in manifest_data:
        logger.warning("Found legacy entry_point syntax. Please upgrade to use plugin_id instead.")
        manifest_data["plugin_id"] = manifest_data["entry_point"]

    for parameter in REQUIRED_MANIFEST_PARAMETERS:
        if parameter not in manifest_data:
            raise TankError(
                "Required plugin manifest parameter '%s' missing in '%s'" % (parameter, manifest_path)
            )

    # plugin_id needs to be alpha numeric + period
    if re.search("^[a-zA-Z0-9_\.]+$", manifest_data["plugin_id"]) is None:
        raise TankError("Plugin id can only contain alphanumerics, period and underscore characters.")

    return manifest_data


def _bake_manifest(manifest_data, config_uri, core_descriptor, plugin_root):
    """
    Bake the info.yml manifest into a python file.

    :param manifest_data: info.yml manifest data
    :param config_uri: Configuration descriptor uri string to use at runtime
    :param core_descriptor: descriptor object pointing at core to use for bootstrap
    :param plugin_root: Root path for plugin
    """
    # suffix our generated python module with plugin id for uniqueness
    # replace all non-alphanumeric chars with underscores.
    module_name = "sgtk_plugin_%s" % re.sub("\W", "_", manifest_data["plugin_id"])
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
            fh.write("BUILD_DATE=\"%s\"\n" % datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
            fh.write("BUILD_GENERATION=%d\n" % BUILD_GENERATION)

            # Write out helper function 'get_sgtk_pythonpath()'.
            # this makes it easy for a plugin to import sgtk
            if core_descriptor.get_path().startswith(plugin_root):
                # the core descriptor is cached inside our plugin
                core_path_parts = os.path.normpath(core_descriptor.get_path()).split(os.path.sep)
                core_path_relative_parts = core_path_parts[core_path_parts.index(BUNDLE_CACHE_ROOT_FOLDER_NAME):]
                core_path_relative_parts.append("python")

                fh.write("\n\n")
                fh.write("def get_sgtk_pythonpath(plugin_root):\n")
                fh.write("    \"\"\" \n")
                fh.write("    Auto generated helper method which returns the \n")
                fh.write("    path to the core bundled with the plugin.\n")
                fh.write("    \n")
                fh.write("    For more information, see the documentation.\n")
                fh.write("    \"\"\" \n")
                fh.write("    import os\n")
                fh.write("    return os.path.join(plugin_root, %s)\n" %
                         ", ".join('"%s"' % dir for dir in core_path_relative_parts))
                fh.write("\n\n")

            else:
                # the core descriptor is outside of bundle cache!
                logger.warning("Your core %r has its payload outside the plugin bundle cache. "
                               "This plugin cannot be distributed to others." % core_descriptor)

                core_path_parts = os.path.normpath(core_descriptor.get_path()).split(os.path.sep)
                core_path_parts.append("python")

                # because we are using an external core, the plugin_root parameter
                # is simply ignored in any calls from the plugin code to
                # get_sgtk_pythonpath()
                fh.write("\n\n")
                fh.write("def get_sgtk_pythonpath(plugin_root):\n")
                fh.write("    # NOTE - this was built with a core that is not part of the plugin. \n")
                fh.write("    # The plugin_root parameter is therefore ignored.\n")
                fh.write("    # This is normally only done during development and \n")
                fh.write("    # typically means that the plugin cannot run on other machines \n")
                fh.write("    # than the one where it was built. \n")
                fh.write("    # \n")
                fh.write("    # For more information, see the documentation.\n")
                fh.write("    # \n")
                fh.write("    return r'%s'\n" % os.path.sep.join(core_path_parts))
                fh.write("\n\n")

            # Write out helper function 'initialize_manager()'.
            # This method is a convenience method to make it easier to
            # set up the bootstrap manager given a plugin config

            fh.write("\n\n")
            fh.write("def initialize_manager(manager, plugin_root):\n")
            fh.write("    \"\"\" \n")
            fh.write("    Auto generated helper method which initializes\n")
            fh.write("    a toolkit manager with common plugin parameters.\n")
            fh.write("    \n")
            fh.write("    For more information, see the documentation.\n")
            fh.write("    \"\"\" \n")
            fh.write("    import os\n")

            # set base configuration
            fh.write("    manager.base_configuration = '%s'\n" % config_uri)

            # set entry point
            fh.write("    manager.plugin_id = '%s'\n" % manifest_data["plugin_id"])

            # set shotgun config lookup flag if defined
            if "do_shotgun_config_lookup" in manifest_data:
                fh.write("    manager.do_shotgun_config_lookup = %s\n" % manifest_data["do_shotgun_config_lookup"])

            # set bundle cache fallback path
            fh.write("    bundle_cache_path = os.path.join(plugin_root, 'bundle_cache')\n")
            fh.write("    manager.bundle_cache_fallback_paths = [bundle_cache_path]\n")

            fh.write("    return manager\n")

            fh.write("\n\n")
            fh.write("# end of file.\n")

    except Exception, e:
        raise TankError("Cannot write manifest file: %s" % e)


def build_plugin(sg_connection, source_path, target_path, bootstrap_core_uri=None):
    """
    Perform a build of a plugin.

    This will introspect the info.yml in the source path,
    copy over everything in the source path into target path
    and then establish a bundle cache containing a reflection
    of all items required by the config.

    :param sg_connection: Shotgun connection
    :param source_path: Path to plugin.
    :param target_path: Path to build
    :param bootstrap_core_uri: Custom bootstrap core uri. If None,
                               the latest core from the app store will be used.
    """
    logger.info("Your toolkit plugin in '%s' will be processed." % source_path)
    logger.info("The build will generated into '%s'" % target_path)

    # check for existence
    if not os.path.exists(source_path):
        raise TankError("Source path '%s' cannot be found on disk!" % source_path)

    # check that target path doesn't exist
    if os.path.exists(target_path):
        logger.info("The folder '%s' already exists on disk. Removing it" % target_path)
        wipe_folder(target_path)

    # try to create target path
    filesystem.ensure_folder_exists(target_path)

    # check manifest
    manifest_data = _validate_manifest(source_path)

    # copy all plugin data across
    # skip info.yml, this is baked into the manifest python code
    logger.info("Copying plugin data across...")
    filesystem.copy_folder(source_path, target_path)

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

    # copy the config payload across to the plugin bundle cache
    cfg_descriptor.clone_cache(bundle_cache_root)

    # cache all apps, engines and frameworks
    cache_apps(sg_connection, cfg_descriptor, bundle_cache_root)

    # get latest core - cache it directly into the plugin root folder
    if bootstrap_core_uri:
        logger.info("Caching custom core for boostrap (%s)" % bootstrap_core_uri)
        bootstrap_core_desc = create_descriptor(
            sg_connection,
            Descriptor.CORE,
            bootstrap_core_uri,
            resolve_latest=is_descriptor_version_missing(bootstrap_core_uri),
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

    # make a python folder where we put our manifest
    logger.info("Creating configuration manifest...")

    # bake out the manifest into python files.
    _bake_manifest(
        manifest_data,
        config_uri_str,
        bootstrap_core_desc,
        target_path
    )

    # now analyze what core the config needs
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

    cleanup_bundle_cache(bundle_cache_root)

    logger.info("")
    logger.info("Build complete!")
    logger.info("")
    logger.info("- Your plugin is ready in '%s'" % target_path)
    logger.info("- Plugin uses config %r" % cfg_descriptor)
    logger.info("- Bootstrap core is %r" % bootstrap_core_desc)
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
        "--bootstrap-core-uri",
        default=None,
        action="store",
        help=("Specify which version of core to be used by the bootstrap process. "
              "If not specified, defaults to the most recently released core.")
    )

    add_authentication_options(parser)

    # parse cmd line
    (options, remaining_args) = parser.parse_args()

    logger.info("Welcome to the Toolkit plugin builder.")
    logger.info("")

    if options.debug:
        LogManager().global_debug = True

    if options.bootstrap_core_uri:
        bootstrap_core_uri = options.bootstrap_core_uri
    else:
        # default
        bootstrap_core_uri = None

    if len(remaining_args) != 2:
        parser.print_help()
        return 2

    # get paths
    source_path = remaining_args[0]
    target_path = remaining_args[1]

    # convert any env vars and tildes
    source_path = os.path.expanduser(os.path.expandvars(source_path))
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
    build_plugin(
        sg_connection,
        source_path,
        target_path,
        bootstrap_core_uri
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
