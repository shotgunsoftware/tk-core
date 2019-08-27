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
    wipe_folder, automated_setup_documentation
)

# set up logging
logger = LogManager.get_logger("build_plugin")

# required keys in the info.yml plugin manifest file
REQUIRED_MANIFEST_PARAMETERS = ["base_configuration", "plugin_id"]

# the folder where all items will be cached
BUNDLE_CACHE_ROOT_FOLDER_NAME = "bundle_cache"

# generation of the build syntax
BUILD_GENERATION = 2


def _bake_configuration(sg_connection, manifest_data):
    """
    Bake the given configuration by ensuring it is locally cached and by modifying
    the manifest_data.

    :param sg_connection: Shotgun connection
    :param manifest_data: Manifest data as a dictionary
    :returns: The baked descriptor dictionary issued from configuration descriptor.
    """
    logger.info(
        "Baking your configuration definition into an immutable state. "
        "This means that the plugin will be frozen and no automatic updates "
        "will be performed at startup."
    )
    base_config_def = manifest_data["base_configuration"]
    if isinstance(base_config_def, str):
        # convert to dict so we can introspect
        base_config_uri_dict = descriptor_uri_to_dict(base_config_def)
    else:
        base_config_uri_dict = base_config_def

    using_latest_config = is_descriptor_version_missing(base_config_uri_dict)
    if using_latest_config:
        logger.info(
            "Your configuration definition does not contain a version number. "
            "Retrieving the latest version of the configuration for baking."
        )

    cfg_descriptor = create_descriptor(
        sg_connection,
        Descriptor.CONFIG,
        base_config_uri_dict,
        resolve_latest=using_latest_config
    )
    cfg_descriptor.ensure_local()
    local_path = cfg_descriptor.get_path()
    if not local_path:
        raise ValueError("Unable to get a local copy of %s" % cfg_descriptor)
    baked_descriptor = {
        "type": bootstrap_constants.BAKED_DESCRIPTOR_TYPE,
        "path": local_path,
        "name": cfg_descriptor.system_name,
        "version": cfg_descriptor.version
    }
    manifest_data["base_configuration"] = baked_descriptor
    return baked_descriptor


def _process_configuration(sg_connection, source_path, target_path, bundle_cache_root, manifest_data, use_system_core):
    """
    Given data in the plugin manifest, download resolve and
    cache the configuration.

    :param sg_connection: Shotgun connection
    :param source_path: Root path of plugin source.
    :param target_path: Build target path
    :param bundle_cache_root: Bundle cache root
    :param manifest_data: Manifest data as a dictionary
    :param bool use_system_core: If True, use a globally installed tk-core instead
                                 of the one specified in the configuration.
    :return: (Resolved config descriptor object, config descriptor uri to use at runtime, install path)
    """
    logger.info("Analyzing configuration")

    install_path = None

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

        # A baked config descriptor does not require a name nor a version, so
        # if these keys are not available, use the current date time for the
        # version and an arbitrary name for the config. Please note that this
        # only happens if the baked descriptor was set in the original config.
        # When baking a plugin with the --bake option, which is the recommended
        # workflow, these values are automatically set.
        baked_name = base_config_uri_dict.get("name") or "tk-config-plugin"
        baked_version = (
            base_config_uri_dict.get("version") or
            datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        )
        install_path = os.path.join(
            bundle_cache_root,
            bootstrap_constants.BAKED_DESCRIPTOR_FOLDER_NAME,
            baked_name,
            baked_version
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
                "name": baked_name,
                "version": baked_version
            }
        )
        if use_system_core:
            # If asked to use a globally installed tk-core instead of the one
            # specified by the config, we remove the local copy which was created
            # in the scaffold step.
            logger.info("Removing core reference in %s" % install_path)
            wipe_folder(os.path.join(install_path, "install"))
            # And make sure we don't have any reference to a tk-core in the config,
            # otherwise it would be picked up when bootstrapping.
            filesystem.safe_delete_file(os.path.join(install_path, "config", "core", "core_api.yml"))
        else:
            # Workaround for tk-core bootstrap needing a shotgun.yml file: when swapping
            # tk-core, this file is checked to see if a script user was specified and
            # should be used in place of the authenticated user. So we create a dummy
            # file with an "unspecified" host, as the key is required by the tk-core
            # code parsing the file.
            # It is not clear if this workaround is needed for non baked configs as
            # their workflow is different, so for now we just keep it for bake configs
            # only.
            shotgun_yaml_path = os.path.join(install_path, "config", "core", "shotgun.yml")
            if not os.path.exists(shotgun_yaml_path):
                logger.info("Patching %s" % shotgun_yaml_path)
                with open(shotgun_yaml_path, "w") as pf:
                    pf.write("# Workaround for tk-core bootstrap\nhost: unspecified")
    else:

        # if the descriptor in the config contains a version number
        # we will go into a fixed update mode.
        using_latest_config = is_descriptor_version_missing(base_config_uri_dict)
        if using_latest_config:
            logger.info(
                "Your configuration definition does not contain a version number. "
                "This means that the plugin will attempt to auto update at startup."
            )
        else:
            logger.info(
                "Your configuration definition contains a version number. "
                "This means that the plugin will be frozen and no automatic updates "
                "will be performed at startup."
            )

        cfg_descriptor = create_descriptor(
            sg_connection,
            Descriptor.CONFIG,
            base_config_uri_dict,
            resolve_latest=using_latest_config
        )
    logger.info("Resolved config %r" % cfg_descriptor)
    logger.info("Runtime config descriptor uri will be %s" % base_config_uri_str)
    if install_path:
        logger.info("The config was baked in %s" % install_path)
    return cfg_descriptor, base_config_uri_str, install_path


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
            if not core_descriptor:
                # If we don't have core_descriptor, the plugin will use the
                # system installed tk-core. Arguably in that case we don't need
                # this method, but let's keep things consistent.
                fh.write("\n\n")
                fh.write("def get_sgtk_pythonpath(plugin_root):\n")
                fh.write("    \"\"\" \n")
                fh.write("    Auto generated helper method which returns the \n")
                fh.write("    path to the core bundled with the plugin.\n")
                fh.write("    \n")
                fh.write("    For more information, see the documentation.\n")
                fh.write("    \"\"\" \n")
                fh.write("    import os\n")
                fh.write("    import sgtk\n")
                fh.write("    return os.path.dirname(os.path.dirname(sgtk.__file__))\n")
                fh.write("\n\n")

            elif core_descriptor.get_path().startswith(plugin_root):
                # The core descriptor is cached inside our plugin, build a relative
                # path from the plugin root.
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
        logger.exception(e)
        raise TankError("Cannot write manifest file: %s" % e)


def build_plugin(sg_connection, source_path, target_path, bootstrap_core_uri=None, do_bake=False, use_system_core=False):
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
    :param bool do_bake: If True, bake the plugin prior to building it.
    :param bool use_system_core: If True, use a globally installed tk-core instead
                                 of the one specified in the configuration.
    """
    logger.info("Your toolkit plugin in '%s' will be processed." % source_path)
    logger.info("The build will %s into '%s'" % (["generated", "baked"][do_bake], target_path))

    # check for existence
    if not os.path.exists(source_path):
        raise TankError("Source path '%s' cannot be found on disk!" % source_path)

    # check manifest
    manifest_data = _validate_manifest(source_path)

    if do_bake:
        baked_descriptor = _bake_configuration(
            sg_connection,
            manifest_data,
        )
        # When baking we control the output path by adding a folder based on the
        # configuration descriptor and version.
        target_path = os.path.join(target_path, "%s-%s" % (
            baked_descriptor["name"],
            baked_descriptor["version"]
        ))

    # check that target path doesn't exist
    if os.path.exists(target_path):
        logger.info("The folder '%s' already exists on disk. Removing it" % target_path)
        wipe_folder(target_path)

    # try to create target path
    filesystem.ensure_folder_exists(target_path)

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
    # contains a manual descriptor uri and install_path is set with the baked
    # folder.
    (cfg_descriptor, config_uri_str, install_path) = _process_configuration(
        sg_connection,
        source_path,
        target_path,
        bundle_cache_root,
        manifest_data,
        use_system_core
    )

    # cache config in bundle cache
    logger.info("Downloading and caching config...")

    # copy the config payload across to the plugin bundle cache
    cfg_descriptor.clone_cache(bundle_cache_root)

    # cache all apps, engines and frameworks
    cache_apps(sg_connection, cfg_descriptor, bundle_cache_root)

    if use_system_core:
        logger.info("An external core will be used for this plugin, not caching it")
        bootstrap_core_desc = None
    else:
        # get core - cache it directly into the plugin root folder
        if bootstrap_core_uri:
            logger.info("Caching custom core for boostrap (%s)" % bootstrap_core_uri)
            bootstrap_core_desc = create_descriptor(
                sg_connection,
                Descriptor.CORE,
                bootstrap_core_uri,
                resolve_latest=is_descriptor_version_missing(bootstrap_core_uri),
                bundle_cache_root_override=bundle_cache_root
            )
            # cache it
            bootstrap_core_desc.ensure_local()

        elif not cfg_descriptor.associated_core_descriptor:
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
        else:
            # The bootstrap core will be derived from the associated core desc below.
            bootstrap_core_desc = None

    # now analyze what core the config needs
    if not use_system_core and cfg_descriptor.associated_core_descriptor:
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
        if bootstrap_core_desc is None:
            # Use the same version as the one specified by the config.
            if install_path:
                # Install path is set only if the config was baked. We re-use the
                # install path as an optimisation to avoid core swapping when the
                # config is bootstrapped.
                logger.info(
                    "Bootstrapping will use installed %s required by the config" %
                    associated_core_desc
                )
                # If the core was installed we directly use it.
                bootstrap_core_desc = create_descriptor(
                    sg_connection,
                    Descriptor.CORE, {
                        "type": "path",
                        "name": "tk-core",
                        "path": os.path.join(install_path, "install", "core"),
                        "version": associated_core_desc.version,
                    },
                    resolve_latest=False,
                    bundle_cache_root_override=bundle_cache_root
                )
            else:
                logger.info(
                    "Bootstrapping will use core %s required by the config" %
                    associated_core_desc
                )
                bootstrap_core_desc = associated_core_desc

    # make a python folder where we put our manifest
    logger.info("Creating configuration manifest...")

    # bake out the manifest into python files.
    _bake_manifest(
        manifest_data,
        config_uri_str,
        bootstrap_core_desc,
        target_path
    )

    cleanup_bundle_cache(bundle_cache_root)

    logger.info("")
    logger.info("Build complete!")
    logger.info("")
    logger.info("- Your plugin is ready in '%s'" % target_path)
    logger.info("- Plugin uses config %r" % cfg_descriptor)
    if bootstrap_core_desc:
        logger.info("- Bootstrap core is %r" % bootstrap_core_desc)
    else:
        logger.info("- Plugin will need an external installed core.")
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

By default, the build script will use the latest app store core for its bootstrapping.
If you want to use a specific core for the bootstrap, this can be specified via the
--bootstrap-core-uri option:

> python build_plugin.py
            --bootstrap-core-uri='sgtk:descriptor:dev?path=~/dev/tk-core'
            ~/dev/tk-maya/plugins/basic /tmp/maya-plugin

By using the '--bake' option, you can build a plugin with an immutable configuration
where every single Toolkit component is cached and frozen to the version retrieved at
build time. This can be useful to distribute a self contained plugin to third party
users.

> python build_plugin.py
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

    parser.add_option(
        "-c",
        "--bootstrap-core-uri",
        default=None,
        action="store",
        help=("Specify which version of core to be used by the bootstrap process. "
              "If not specified, defaults to the most recently released core.")
    )

    parser.add_option(
        "--bake",
        default=False,
        action="store_true",
        help="Bake the plugin with an immutable configuration."
    )

    parser.add_option(
        "--system-core",
        default=False,
        action="store_true",
        help="Use tk-core installed on the system rather than a private copy in the config."
    )

    add_authentication_options(parser)

    # parse cmd line
    (options, remaining_args) = parser.parse_args()

    logger.info("Welcome to the Toolkit plugin builder.")
    logger.info("")

    if options.debug:
        LogManager().global_debug = True

    if options.system_core:
        if options.bootstrap_core_uri:
            parser.error(
                "bootstrap-core-uri and system-core options are incompatible. "
                "Please use one or the other but not both."
            )
        if not options.bake:
            parser.error(
                "system-core option can only be used for baked plugins. "
                "Please use the --bake option or do not use --system-core."
            )

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
        bootstrap_core_uri,
        options.bake,
        options.system_core
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
