# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from __future__ import with_statement
import os
import sys
import optparse

# add sgtk API
this_folder = os.path.abspath(os.path.dirname(__file__))
python_folder = os.path.abspath(os.path.join(this_folder, "..", "python"))
sys.path.append(python_folder)

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
REQUIRED_MANIFEST_PARAMETERS = [
    "base_configuration",
    "entry_point",
    "display_name",
    "description",
    "configuration"
]

# the folder where all items will be cached
BUNDLE_CACHE_ROOT_FOLDER_NAME = "bundle_cache"



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
            )
            logger.info("Caching %s..." % desc)
            desc.clone_cache(bundle_cache_root)

            for app in env.get_apps(eng):
                # resolve descriptor and clone cache into bundle cache
                desc = create_descriptor(
                    sg_connection,
                    Descriptor.APP,
                    env.get_app_descriptor_dict(eng, app),
                )
                logger.info("Caching %s..." % desc)
                desc.clone_cache(bundle_cache_root)

        for framework in env.get_frameworks():
            desc = create_descriptor(
                sg_connection,
                Descriptor.FRAMEWORK,
                env.get_framework_descriptor_dict(framework),
            )
            logger.info("Caching %s..." % desc)
            desc.clone_cache(bundle_cache_root)

def _process_configuration(sg_connection, manifest_data):
    """
    Given data in the plugin manifest, download resolve and
    cache the configuration.

    :param sg_connection: Shotgun connection
    :param manifest_data: Manifest data as a dictionary
    :return: Resolved config descriptor object
    """
    logger.info("Analyzing configuration")

    base_config_def = manifest_data["base_configuration"]

    if isinstance(base_config_def, str):
        # convert to dict so we can introspect
        base_config_def = descriptor_uri_to_dict(base_config_def)

    # if the descriptor in the config contains a version number
    # we will go into a fixed update mode.
    if "version" in base_config_def:
        logger.info("Your configuration definition contains a version number. "
                    "This means that the plugin will be frozen and no automatic updates "
                    "will be performed at startup.")
        using_latest_config = False
    else:
        logger.debug("Your configuration definition does not contain a version number. "
                     "This means that the plugin will attempt to auto update at startup.")
        using_latest_config = True

    cfg_descriptor = create_descriptor(
        sg_connection,
        Descriptor.CONFIG,
        base_config_def,
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
        raise TankError("Target path '%s' already exists!" % target_path)

    # try to create target path
    filesystem.ensure_folder_exists(target_path)

    # check manifest
    manifest_data = _validate_manifest(source_path)

    # copy all plugin data across
    logger.info("Copying plugin data across...")
    filesystem.copy_folder(source_path, target_path)

    # create bundle cache
    logger.info("Creating bundle cache folder...")
    bundle_cache_root = os.path.join(target_path, BUNDLE_CACHE_ROOT_FOLDER_NAME)
    filesystem.ensure_folder_exists(bundle_cache_root)

    # resolve config descriptor
    cfg_descriptor = _process_configuration(sg_connection, manifest_data)

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
    logger.info("Copying into fixed bootstrap location bundle_cache/tk-core...")
    fixed_core_path = os.path.join(target_path, "bundle_cache", "tk-core")
    latest_core_desc.copy(fixed_core_path)

    # now analyze what core the config needs
    if cfg_descriptor.associated_core_descriptor:
        logger.info("Config is using a custom core...")
        associated_core_desc = create_descriptor(
            sg_connection,
            Descriptor.CORE,
            cfg_descriptor.associated_core_descriptor
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
    logger.info("- All dependencies have been written out to bundle_cache")
    logger.info("")
    logger.info("")
    logger.info("")





def main():
    """
    Main entry point for script.

    Handles argument parsing and validation and then calls the script payload.
    """

    usage = "%prog source_path target_path (run with --help for more information)"

    desc = "One line description"

    epilog = """
Examples:

Building docs for a tag named 'v1.2.3':

Shotgun API:       python api_docs_to_github.py -r python-api -l v1.2.3 --preview
Toolkit Core API:  python api_docs_to_github.py -r tk-core -l v1.2.3 --preview
Toolkit Framework: python api_docs_to_github.py -c /path/to/tk-core -r tk-framework-xyz -l v1.2.3 --preview

Building docs for a branch named 'branch_abc':

Shotgun API:       python api_docs_to_github.py -r python-api -l branch_abc --preview
Toolkit Core API:  python api_docs_to_github.py -r tk-core -l branch_abc --preview
Toolkit Framework: python api_docs_to_github.py -c /path/to/tk-core -r tk-framework-xyz -l branch_abc --preview

(Just omit the --preview flag to release)

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
