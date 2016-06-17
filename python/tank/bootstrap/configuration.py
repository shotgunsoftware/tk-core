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
import inspect

from . import constants
from .import_handler import CoreImportHandler

from .errors import TankBootstrapError
from ..descriptor import Descriptor, create_descriptor

from ..util import filesystem
from ..util import ShotgunPath

from tank_vendor import yaml

from .. import LogManager

log = LogManager.get_logger(__name__)

class Configuration(object):
    """
    An abstraction around a toolkit configuration.

    The configuration is identified by a ConfigurationDescriptor
    object and may or may not exist on disk.
    """

    (LOCAL_CFG_UP_TO_DATE, LOCAL_CFG_MISSING, LOCAL_CFG_DIFFERENT, LOCAL_CFG_INVALID) = range(4)

    def __init__(
            self,
            path,
            sg,
            descriptor,
            project_id,
            entry_point,
            pipeline_config_id,
            bundle_cache_fallback_paths
    ):
        """
        Constructor.

        :param path: ShotgunPath object describing the path to this configuration
        :param sg: Shotgun API instance
        :param descriptor: ConfigDescriptor for the associated config
        :param project_id: Project id for the shotgun project associated with the
                           configuration. For a site-level configuration, this
                           can be set to None.
        :param entry_point: Entry point string to identify the scope for a particular plugin
                            or integration. For more information,
                            see :meth:`~sgtk.bootstrap.ToolkitManager.entry_point`. For
                            non-plugin based toolkit projects, this value is None.
        :param pipeline_config_id: Pipeline Configuration id for the shotgun
                                   pipeline config id associated. If a config does
                                   not have an associated entity in Shotgun, this
                                   should be set to None.
        :param bundle_cache_fallback_paths: List of additional paths where apps are cached.
        """
        self._path = path
        self._sg_connection = sg
        self._descriptor = descriptor
        self._project_id = project_id
        self._entry_point = entry_point
        self._pipeline_config_id = pipeline_config_id
        self._bundle_cache_fallback_paths = bundle_cache_fallback_paths

    def __repr__(self):
        return "<Config with id %s, project id %s, ep %s and base %r>" % (
            self._pipeline_config_id,
            self._project_id,
            self._entry_point,
            self._descriptor
        )

    def get_descriptor(self):
        """
        Returns the descriptor that is associated with this configuration

        :return: ConfigDescriptor Object
        """
        return self._descriptor

    def status(self):
        """
        Compares the actual configuration installed on disk against the
        associated configuration described by the descriptor passed in via
        the class constructor.

        :returns: LOCAL_CFG_UP_TO_DATE, LOCAL_CFG_MISSING,
                  LOCAL_CFG_DIFFERENT, or LOCAL_CFG_INVALID
        """
        log.debug("Checking status of %r" % self)

        # Pass 1:
        # first check if there is any config at all
        # probe for info.yaml manifest file
        sg_config_file = os.path.join(
            self._path.current_os,
            "config",
            constants.BUNDLE_METADATA_FILE
        )
        if not os.path.exists(sg_config_file):
            return self.LOCAL_CFG_MISSING

        # Pass 2:
        # local config exists. See if it is up to date.
        # get the path to a potential config metadata file
        config_info_file = self._get_descriptor_metadata_file()

        if not os.path.exists(config_info_file):
            # not sure what version this is.
            return self.LOCAL_CFG_INVALID

        fh = open(config_info_file, "rt")
        try:
            data = yaml.load(fh)
            deploy_generation = data["deploy_generation"]
            descriptor_dict = data["config_descriptor"]
        except Exception, e:
            # yaml info not valid.
            log.warning("Cannot parse file '%s' - ignoring. Error: %s" % (config_info_file, e))
            return self.LOCAL_CFG_INVALID
        finally:
            fh.close()

        if deploy_generation != constants.BOOTSTRAP_LOGIC_GENERATION:
            # different format or logic of the deploy itself.
            # trigger a redeploy
            log.debug("Config was installed with an old generation of the logic.")
            return self.LOCAL_CFG_DIFFERENT

        if descriptor_dict != self._descriptor.get_dict():
            log.debug(
                "Local Config %r does not match "
                "associated descriptor %r" % (descriptor_dict, self._descriptor.get_dict())
            )
            return self.LOCAL_CFG_DIFFERENT

        elif not self._descriptor.is_immutable():
            # our desired configuration's descriptor matches
            # the config that is already installed however the descriptor
            # reports that it is not immutable, e.g. it can change at any
            # point (e.g like a dev or path descriptor). Assume a worst case
            # in this case - that the config that is cached locally is
            # not the same as the source descriptor it is based on.
            log.debug("The installed config is not immutable, so it is per "
                      "definition always out of date.")
            return self.LOCAL_CFG_DIFFERENT

        else:
            log.debug("Local config is up to date")
            return self.LOCAL_CFG_UP_TO_DATE

    def update_configuration(self):
        """
        Ensure that the configuration is up to date with the one
        given by the associated descriptor.

        This method fails gracefully and attempts to roll back to a
        stable state on failure.
        """
        # make sure a scaffold is in place
        self._ensure_project_scaffold()

        # stow away any previous versions of core and config folders
        (config_backup_path, core_backup_path) = self._move_to_backup()

        # copy the configuration into place
        try:
            self._descriptor.copy(os.path.join(self._path.current_os, "config"))


            # write out config files
            self._write_install_location_file()
            self._write_config_info_file()
            self._write_shotgun_file()
            self._write_pipeline_config_file()

            # make sure roots file reflects current paths
            self._update_roots_file()

            # and lastly install core
            self._install_core()

        except Exception, e:
            log.exception("Failed to update configuration. Attempting Rollback. Error Traceback:")
            # step 1 - clear core and config locations
            log.debug("Cleaning out faulty config location...")
            self._move_to_backup()
            # step 2 - recover previous core and backup
            if config_backup_path is None or core_backup_path is None:
                # there is nothing to restore!
                log.error(
                    "Irrecoverable error - failed to update config but no previous config to "
                    "fall back on. Raising TankBootstrapError to abort bootstrap."
                    )
                raise TankBootstrapError("Configuration could not be installed: %s." % e)

            else:
                # ok to restore
                log.debug("Restoring previous config %s" % config_backup_path)
                filesystem.copy_folder(
                    config_backup_path,
                    os.path.join(self._path.current_os, "config")
                )
                log.debug("Previous config restore complete...")

                log.debug("Restoring previous core %s" % core_backup_path)
                filesystem.copy_folder(
                    core_backup_path,
                    os.path.join(self._path.current_os, "install", "core")
                )
                log.debug("Previous core restore complete...")

        # @todo - prime caches (yaml, path cache)

        # make sure tank command and interpreter files are up to date
        self._create_tank_command()

        if self._pipeline_config_id:
            # make sure there is a pipeline config entry in Shotgun
            # and that this is up to date. We may not have permission
            # to write to this configuration, so take a conservative
            # approach where we first check if the record exists and is
            # up to date and only if it differs we attempt to update it.
            log.debug(
                "Checking that shotgun pipeline config entry "
                "id %s exists and is up to date..." % self._pipeline_config_id
            )

            pc_data = self._sg_connection.find_one(
                constants.PIPELINE_CONFIGURATION_ENTITY_TYPE,
                [["id", "is", self._pipeline_config_id]],
                ShotgunPath.SHOTGUN_PATH_FIELDS
            )

            log.debug("Shotgun data returned: %s" % pc_data)

            shotgun_path = ShotgunPath.from_shotgun_dict(pc_data)

            if shotgun_path != self._path:

                log.debug("Attempting to update pipeline configuration with new paths...")

                self._sg_connection.update(
                    constants.PIPELINE_CONFIGURATION_ENTITY_TYPE,
                    self._pipeline_config_id,
                    self.path.as_shotgun_dict()
                )

    def get_tk_instance(self, sg_user):
        """
        Returns a tk instance for this configuration.

        :param sg_user: Authenticated Shotgun user to associate
                        the tk instance with.
        """
        path = self._path.current_os
        core_path = os.path.join(path, "install", "core", "python")

        # swap the core out
        CoreImportHandler.swap_core(core_path)

        # perform a local import here to make sure we are getting
        # the newly swapped in core code
        from .. import api
        api.set_authenticated_user(sg_user)
        tk = api.tank_from_path(path)

        log.debug("Bootstrapped into tk instance %r" % tk)
        log.debug("Core API code located here: %s" % inspect.getfile(tk.__class__))

        return tk

    def _get_descriptor_metadata_file(self):
        """
        Returns the path to the metadata file holding descriptor information
        :return: path
        """
        path = os.path.join(
            self._path.current_os,
            "cache",
            "descriptor_info.yml"
        )
        filesystem.ensure_folder_exists(os.path.dirname(path))
        return path

    def _ensure_project_scaffold(self):
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

    def _move_to_backup(self):
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
    def _create_tank_command(self, win_python=None, mac_python=None, linux_python=None):
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


    def _install_core(self):
        """
        Install a core into the given configuration.

        This will copy the core API from the given location into
        the configuration, effectively mimicing a localized setup.
        """
        core_uri_or_dict = self._descriptor.associated_core_descriptor

        if core_uri_or_dict is None:
            # we don't have a core descriptor specified. Get latest from app store.
            log.info("Config does not define which core to use. Will use latest.")
            core_uri_or_dict = constants.LATEST_CORE_DESCRIPTOR
            # resolve latest core
            use_latest = True
        else:
            # we have an exact core descriptor. Get a descriptor for it
            log.debug("Config needs core %s" % core_uri_or_dict)
            # when core is specified, it is always a specific version
            use_latest = False

        core_descriptor = create_descriptor(
            self._sg_connection,
            Descriptor.CORE,
            core_uri_or_dict,
            fallback_roots=self._bundle_cache_fallback_paths,
            resolve_latest=use_latest
        )

        # make sure we have our core on disk
        core_descriptor.ensure_local()
        config_root_path = self._path.current_os
        core_target_path = os.path.join(config_root_path, "install", "core")

        log.debug("Copying core into place")
        core_descriptor.copy(core_target_path)

    def _write_install_location_file(self):
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

        with self.__open_auto_created_yml(sg_code_location) as fh:

            fh.write("# This file reflects the paths in the pipeline\n")
            fh.write("# configuration defined for this project.\n")
            fh.write("\n")
            fh.write("Windows: '%s'\n" % self._path.windows)
            fh.write("Darwin: '%s'\n" % self._path.macosx)
            fh.write("Linux: '%s'\n" % self._path.linux)
            fh.write("\n")
            fh.write("# End of file.\n")

    def _write_config_info_file(self):
        """
        Writes a cache file with info about where the config came from.
        """
        config_info_file = self._get_descriptor_metadata_file()

        with self.__open_auto_created_yml(config_info_file) as fh:
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
            metadata["config_descriptor"] = self._descriptor.get_dict()

            # write yaml
            yaml.safe_dump(metadata, fh)
            fh.write("\n")
            fh.write("# End of file.\n")

    def _write_shotgun_file(self):
        """
        Writes config/core/shotgun.yml
        """
        sg_file = os.path.join(
            self._path.current_os,
            "config",
            "core",
            constants.CONFIG_SHOTGUN_FILE
        )

        with self.__open_auto_created_yml(sg_file) as fh:

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

    def _write_pipeline_config_file(self):
        """
        Writes out the config/core/pipeline_config.yml
        """
        # the pipeline config metadata
        # resolve project name and pipeline config name from shotgun.
        if self._pipeline_config_id:
            # look up pipeline config name and project name via the pc
            log.debug("Checking pipeline config in Shotgun...")

            sg_data = self._sg_connection.find_one(
                constants.PIPELINE_CONFIGURATION_ENTITY_TYPE,
                [["id", "is", self._pipeline_config_id]],
                ["code", "project.Project.tank_name"]
            )

            project_name = sg_data["project.Project.tank_name"] or constants.UNNAMED_PROJECT_NAME
            pipeline_config_name = sg_data["code"] or constants.UNMANAGED_PIPELINE_CONFIG_NAME

        elif self._project_id:
            # no pc. look up the project name via the project id
            log.debug("Checking project in Shotgun...")

            sg_data = self._sg_connection.find_one(
                "Project",
                [["id", "is", self._project_id]],
                ["tank_name"]
            )

            project_name = sg_data["tank_name"] or constants.UNNAMED_PROJECT_NAME
            pipeline_config_name = constants.UNMANAGED_PIPELINE_CONFIG_NAME

        else:
            project_name = "Site"
            pipeline_config_name = constants.UNMANAGED_PIPELINE_CONFIG_NAME

        pipeline_config_content = {
            "pc_id": self._pipeline_config_id,
            "pc_name": pipeline_config_name,
            "project_id": self._project_id,
            "project_name": project_name,
            "entry_point": self._entry_point,
            "published_file_entity_type": "PublishedFile",
            "use_bundle_cache": True,
            "bundle_cache_fallback_roots": self._bundle_cache_fallback_paths,
            "use_shotgun_path_cache": True
        }

        # write pipeline_configuration.yml
        pipeline_config_path = os.path.join(
            self._path.current_os,
            "config",
            "core",
            constants.PIPELINECONFIG_FILE
        )

        with self.__open_auto_created_yml(pipeline_config_path) as fh:
            yaml.safe_dump(pipeline_config_content, fh)
            fh.write("\n")
            fh.write("# End of file.\n")

    def _update_roots_file(self):
        """
        Updates roots.yml based on local storage defs in shotgun.
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

        for storage_name in self._descriptor.required_storages:

            if storage_name not in storage_by_name:
                raise TankBootstrapError(
                    "A '%s' storage is defined by %s but is "
                    "not defined in Shotgun." % (storage_name, self._descriptor)
                )
            storage_path = ShotgunPath.from_shotgun_dict(storage_by_name[storage_name])
            roots_data[storage_name] = storage_path.as_shotgun_dict()

        roots_file = os.path.join(
            self._path.current_os,
            "config",
            "core",
            constants.STORAGE_ROOTS_FILE
        )

        with self.__open_auto_created_yml(roots_file) as fh:
            yaml.safe_dump(roots_data, fh)
            fh.write("\n")
            fh.write("# End of file.\n")

    @filesystem.with_cleared_umask
    def __open_auto_created_yml(self, path):
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
