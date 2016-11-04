# Copyright (c) 2016 Shotgun Software Inc.
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
import datetime

from . import constants

from .errors import TankBootstrapError
from ..descriptor import Descriptor, create_descriptor

from ..util import filesystem
from ..util import ShotgunPath

from tank_vendor import yaml

from .. import LogManager

log = LogManager.get_logger(__name__)


class ConfigurationWriter(object):
    """
    Class used to write and update Toolkit configurations on disk.
    """

    def __init__(self, path, sg):
        """
        Constructor.

        :param path: ShotgunPath object describing the path to this configuration
        :param sg: Shotgun API instance
        """
        self._path = path
        self._sg_connection = sg

    def ensure_project_scaffold(self):
        """
        Creates all the necessary files on disk for a basic config scaffold.
        """
        config_path = self._path.current_os
        log.info("Ensuring project scaffold in '%s'..." % config_path)

        filesystem.ensure_folder_exists(config_path)
        filesystem.ensure_folder_exists(os.path.join(config_path, "cache"))

        filesystem.ensure_folder_exists(
            os.path.join(config_path, "install", "config.backup"),
            create_placeholder_file=True
        )
        filesystem.ensure_folder_exists(
            os.path.join(config_path, "install", "core.backup"),
            create_placeholder_file=True
        )

    def install_core(self, config_descriptor, bundle_cache_fallback_paths):
        """
        Install a core into the given configuration.

        This will copy the core API from the given location into
        the configuration, effectively mimicing a localized setup.

        :param config_descriptor: Config descriptor to use to determine core version
        :param bundle_cache_fallback_paths: bundle cache search path
        """
        core_uri_or_dict = config_descriptor.associated_core_descriptor

        if core_uri_or_dict is None:
            # we don't have a core descriptor specified. Get latest from app store.
            log.info(
                "Config does not have a core/core_api.yml file to define which core to use. "
                "Will use the latest approved core in the app store."
            )
            core_uri_or_dict = constants.LATEST_CORE_DESCRIPTOR
            # resolve latest core
            use_latest = True
        else:
            # we have an exact core descriptor. Get a descriptor for it
            log.debug("Config has a specific core defined in core/core_api.yml: %s" % core_uri_or_dict)
            # when core is specified, it is always a specific version
            use_latest = False

        core_descriptor = create_descriptor(
            self._sg_connection,
            Descriptor.CORE,
            core_uri_or_dict,
            fallback_roots=bundle_cache_fallback_paths,
            resolve_latest=use_latest
        )

        # make sure we have our core on disk
        core_descriptor.ensure_local()
        config_root_path = self._path.current_os
        core_target_path = os.path.join(config_root_path, "install", "core")

        log.debug("Copying core into place")
        core_descriptor.copy(core_target_path)

    def get_descriptor_metadata_file(self):
        """
        Returns the path to the metadata file holding descriptor information.

        :return: path
        """
        path = os.path.join(
            self._path.current_os,
            "cache",
            "descriptor_info.yml"
        )
        filesystem.ensure_folder_exists(os.path.dirname(path))
        return path

    def move_to_backup(self):
        """
        Move any existing config and core to a backup location.

        After this method has been executed, there is no config and
        no install/core folder present in the configuration scaffold.
        Both have been moved into their respective backup locations.

        :returns: (config_backup_path, core_backup_path) where the paths
                  can be None in case nothing was carried over.

        """
        config_backup_path = None
        core_backup_path = None

        # get backup root location
        config_path = self._path.current_os
        configuration_payload = os.path.join(config_path, "config")

        # timestamp for rollback backup folders
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        if os.path.exists(configuration_payload):

            config_backup_root = os.path.join(config_path, "install", "config.backup")

            # make sure we have a backup folder present
            # sometimes, execution and rollback is so quick that several backup folders
            # are created in a single second. In that case, append a suffix
            config_backup_path = os.path.join(config_backup_root, timestamp)
            counter = 0
            while os.path.exists(config_backup_path):
                # that backup path already exists. Try another one
                counter += 1
                config_backup_path = os.path.join(config_backup_root, "%s.%d" % (timestamp, counter))

            # now that we have found a spot for our backup, make sure folder exists
            # and then move the existing config *into* this folder.
            filesystem.ensure_folder_exists(config_backup_path)

            log.debug("Moving config %s -> %s" % (configuration_payload, config_backup_path))
            backup_target_path = os.path.join(config_backup_path, os.path.basename(configuration_payload))
            os.rename(configuration_payload, backup_target_path)
            log.debug("Backup complete.")
            config_backup_path = backup_target_path

        # now back up the core API
        core_payload = os.path.join(config_path, "install", "core")

        if os.path.exists(core_payload):
            core_backup_root = os.path.join(config_path, "install", "core.backup")
            # should not be necessary but just in case.
            filesystem.ensure_folder_exists(core_backup_root)

            # make sure we have a backup folder present
            # sometimes, execution and rollback is so quick that several backup folders
            # are created in a single second. In that case, append a suffix
            core_backup_path = os.path.join(core_backup_root, timestamp)
            counter = 0
            while os.path.exists(core_backup_path):
                # that backup path already exists. Try another one
                counter += 1
                core_backup_path = os.path.join(core_backup_root, "%s.%d" % (timestamp, counter))

            log.debug("Moving core %s -> %s" % (core_payload, core_backup_path))
            os.rename(core_payload, core_backup_path)
            log.debug("Backup complete.")
            core_backup_path = core_backup_path

        return (config_backup_path, core_backup_path)

    @filesystem.with_cleared_umask
    def create_tank_command(self, win_python=None, mac_python=None, linux_python=None):
        """
        Create a tank command for this configuration.

        The tank command binaries will be copied from the current core distribution
        The interpreter_xxx.cfg files will be created based on the given interpreter settings.
        Uses sg desktop python if no interpreter paths are provided.

        :param win_python: Optional path to a python interpreter
        :param mac_python: Optional path to a python interpreter
        :param linux_python: Optional path to a python interpreter
        """
        log.debug("Installing tank command...")

        # first set up the interpreter_xxx files needed for the tank command
        # default to the shotgun desktop python
        executables = {}
        executables["Linux"] = linux_python or constants.DESKTOP_PYTHON_LINUX
        executables["Darwin"] = mac_python or constants.DESKTOP_PYTHON_MAC
        executables["Windows"] = win_python or constants.DESKTOP_PYTHON_WIN

        config_root_path = self._path.current_os

        for platform in executables:
            sg_config_location = os.path.join(
                config_root_path,
                "config",
                "core",
                "interpreter_%s.cfg" % platform
            )
            # clean out any existing files
            filesystem.safe_delete_file(sg_config_location)
            # create new file
            with open(sg_config_location, "wt") as fh:
                fh.write(executables[platform])

        # now deploy the actual tank command
        core_target_path = os.path.join(config_root_path, "install", "core")
        root_binaries_folder = os.path.join(core_target_path, "setup", "root_binaries")
        for file_name in os.listdir(root_binaries_folder):
            src_file = os.path.join(root_binaries_folder, file_name)
            tgt_file = os.path.join(config_root_path, file_name)
            # clear out any existing files
            filesystem.safe_delete_file(tgt_file)
            # and copy new one into place
            log.debug("Installing tank command %s -> %s" % (src_file, tgt_file))
            filesystem.copy_file(src_file, tgt_file, 0775)

    def write_install_location_file(self):
        """
        Writes the install location file
        """
        config_path = self._path.current_os

        # write the install_location file for our new setup
        sg_code_location = os.path.join(
            config_path,
            "config",
            "core",
            "install_location.yml"
        )

        with self._open_auto_created_yml(sg_code_location) as fh:

            fh.write("# This file reflects the paths in the pipeline\n")
            fh.write("# configuration defined for this project.\n")
            fh.write("\n")
            fh.write("Windows: '%s'\n" % self._path.windows)
            fh.write("Darwin: '%s'\n" % self._path.macosx)
            fh.write("Linux: '%s'\n" % self._path.linux)
            fh.write("\n")
            fh.write("# End of file.\n")

    def write_config_info_file(self, config_descriptor):
        """
        Writes a cache file with info about where the config came from.

        :param config_descriptor: Config descriptor object
        """
        config_info_file = self.get_descriptor_metadata_file()

        with self._open_auto_created_yml(config_info_file) as fh:
            fh.write("# This file contains metadata describing what exact version\n")
            fh.write("# Of the config that was downloaded from Shotgun\n")
            fh.write("\n")
            fh.write("# Below follows details for the sg attachment that is\n")
            fh.write("# reflected within this local configuration.\n")
            fh.write("\n")

            metadata = {}
            # bake in which version of the deploy logic was used to push this config
            metadata["deploy_generation"] = constants.BOOTSTRAP_LOGIC_GENERATION
            # and include details about where the config came from
            metadata["config_descriptor"] = config_descriptor.get_dict()

            # write yaml
            yaml.safe_dump(metadata, fh)
            fh.write("\n")
            fh.write("# End of file.\n")

    def write_shotgun_file(self):
        """
        Writes config/core/shotgun.yml
        """
        sg_file = os.path.join(
            self._path.current_os,
            "config",
            "core",
            constants.CONFIG_SHOTGUN_FILE
        )

        with self._open_auto_created_yml(sg_file) as fh:

            metadata = {}
            # bake in which version of the deploy logic was used to push this config
            metadata["host"] = self._sg_connection.base_url
            # and include details about where the config came from
            metadata["http_proxy"] = self._sg_connection.config.raw_http_proxy
            # write yaml
            yaml.safe_dump(metadata, fh)
            fh.write("\n")
            fh.write("# End of file.\n")

        log.debug("Wrote %s" % sg_file)

    def write_pipeline_config_file(self, pipeline_config_id, project_id, plugin_id, bundle_cache_fallback_paths):
        """
        Writes out the the pipeline configuration file config/core/pipeline_config.yml

        This will populate all relevant parameters required for a toolkit runtime setup.
        Project and pipeline configuration names will be resolved from Shotgun.

        :param pipeline_config_id: Pipeline config id or None for an unmanaged config.
        :param project_id: Project id or None for the site config or for a baked config.
        :param plugin_id: Plugin id string to identify the scope for a particular plugin
                          or integration. For more information,
                          see :meth:`~sgtk.bootstrap.ToolkitManager.plugin_id`. For
                          non-plugin based toolkit projects, this value is None.
        :param bundle_cache_fallback_paths: List of bundle cache fallback paths.
        """
        # the pipeline config metadata
        # resolve project name and pipeline config name from shotgun.
        if pipeline_config_id:
            # look up pipeline config name and project name via the pc
            log.debug("Checking pipeline config in Shotgun...")

            sg_data = self._sg_connection.find_one(
                constants.PIPELINE_CONFIGURATION_ENTITY_TYPE,
                [["id", "is", pipeline_config_id]],
                ["code", "project.Project.tank_name"]
            )

            project_name = sg_data["project.Project.tank_name"] or constants.UNNAMED_PROJECT_NAME
            pipeline_config_name = sg_data["code"] or constants.UNMANAGED_PIPELINE_CONFIG_NAME

        elif project_id:
            # no pc. look up the project name via the project id
            log.debug("Checking project in Shotgun...")

            sg_data = self._sg_connection.find_one(
                "Project",
                [["id", "is", project_id]],
                ["tank_name"]
            )

            project_name = sg_data["tank_name"] or constants.UNNAMED_PROJECT_NAME
            pipeline_config_name = constants.UNMANAGED_PIPELINE_CONFIG_NAME

        else:
            # this is either a site config or a baked config.
            # in the latter case, the project name will be overridden at
            # runtime (along with many other parameters).
            project_name = "Site"
            pipeline_config_name = constants.UNMANAGED_PIPELINE_CONFIG_NAME

        pipeline_config_content = {
            "pc_id": pipeline_config_id,
            "pc_name": pipeline_config_name,
            "project_id": project_id,
            "project_name": project_name,
            "plugin_id": plugin_id,
            "published_file_entity_type": "PublishedFile",
            "use_bundle_cache": True,
            "bundle_cache_fallback_roots": bundle_cache_fallback_paths,
            "use_shotgun_path_cache": True
        }

        # write pipeline_configuration.yml
        pipeline_config_path = os.path.join(
            self._path.current_os,
            "config",
            "core",
            constants.PIPELINECONFIG_FILE
        )

        with self._open_auto_created_yml(pipeline_config_path) as fh:
            yaml.safe_dump(pipeline_config_content, fh)
            fh.write("\n")
            fh.write("# End of file.\n")

    def update_roots_file(self, config_descriptor):
        """
        Updates roots.yml based on local storage defs in shotgun.

        :param config_descriptor: Config descriptor object
        """
        log.debug("Creating storage roots file...")

        # get list of storages in Shotgun
        sg_data = self._sg_connection.find(
            "LocalStorage",
            [],
            fields=["id", "code"] + ShotgunPath.SHOTGUN_PATH_FIELDS)

        # organize them by name
        storage_by_name = {}
        for storage in sg_data:
            storage_by_name[storage["code"]] = storage

        # now write out roots data
        roots_data = {}

        for storage_name in config_descriptor.required_storages:

            if storage_name not in storage_by_name:
                raise TankBootstrapError(
                    "A '%s' storage is defined by %s but is "
                    "not defined in Shotgun." % (storage_name, config_descriptor)
                )
            storage_path = ShotgunPath.from_shotgun_dict(storage_by_name[storage_name])
            roots_data[storage_name] = storage_path.as_shotgun_dict()

        roots_file = os.path.join(
            self._path.current_os,
            "config",
            "core",
            constants.STORAGE_ROOTS_FILE
        )

        with self._open_auto_created_yml(roots_file) as fh:
            yaml.safe_dump(roots_data, fh)
            fh.write("\n")
            fh.write("# End of file.\n")

    @filesystem.with_cleared_umask
    def _open_auto_created_yml(self, path):
        """
        Open a standard auto generated yml for writing.

        - any existing files will be removed
        - the given path will be open for writing in text mode
        - a standard header will be added

        :param path: path to yml file to open for writing
        :return: file handle. It's the respoponsibility of the caller to close this.
        """
        log.debug("Creating auto-generated config file %s" % path)
        # clean out any existing file and replace it with a new one.
        filesystem.safe_delete_file(path)

        # open file for writing
        fh = open(path, "wt")

        fh.write("# This file was auto generated by the Shotgun Pipeline Toolkit.\n")
        fh.write("# Please do not modify by hand as it may be overwritten at any point.\n")
        fh.write("# Created %s\n" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        fh.write("# \n")

        return fh
