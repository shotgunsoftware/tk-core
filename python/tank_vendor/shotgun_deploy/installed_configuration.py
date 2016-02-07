# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import sys
from . import constants
from . import Descriptor
from . import descriptor_factory
from . import paths
from .errors import ShotgunDeployError
from . import util

from ..shotgun_base import copy_file

from .. import yaml
from ..shotgun_base import copy_folder, ensure_folder_exists

log = util.get_shotgun_deploy_logger()

class InstalledConfiguration(object):
    """
    Represents a configuration that has been installed on disk
    """

    (LOCAL_CFG_UP_TO_DATE, LOCAL_CFG_MISSING, LOCAL_CFG_OLD, LOCAL_CFG_INVALID) = range(4)

    def __init__(self, sg, bundle_cache_root, descriptor, project_id, pipeline_config_id):
        """

        :param sg:
        :param descriptor:
        :param project_id:
        :param pipeline_config_id:
        """
        self._sg_connection = sg
        self._descriptor = descriptor
        self._project_id = project_id
        self._pipeline_config_id = pipeline_config_id
        self._bundle_cache_root = bundle_cache_root

    def __repr__(self):
        return "<Config with id %s, project id %s and base %s>" % (
            self._pipeline_config_id,
            self._project_id,
            self._descriptor
        )

    def get_path(self):
        """
        Returns the path to this configuration on the current os

        :return: path on disk as string
        """
        if self._descriptor.needs_installation():
            # this is a config that needs to be copied into place
            # and installed
            path = paths.get_configuration_cache_root(
                self._sg_connection.base_url,
                self._project_id,
                self._pipeline_config_id)
        else:
            path = os.path.abspath(os.path.join(self._descriptor.get_path(), ".."))

        return path

    def status(self):
        """
        Compares the configuration against the source descriptor

        :return:
        """
        log.debug("Checking status of %r" % self)
        if not self._descriptor.needs_installation():
            return self.LOCAL_CFG_UP_TO_DATE

        config_root = self.get_path()

        # first check if there is any config at all
        # probe for shotgun.yml connection params file
        if not os.path.exists(os.path.join(config_root, "config", "core", "shotgun.yml")):
            return self.LOCAL_CFG_MISSING

        # local config exists. See if it is up to date.
        # look at the attachment id to determine the generation of the config.
        config_info_file = os.path.join(config_root, "cache", constants.CONFIG_INFO_CACHE)

        if not os.path.exists(config_info_file):
            # not sure what version this is.
            return self.LOCAL_CFG_INVALID

        fh = open(config_info_file, "rt")
        try:
            data = yaml.load(fh)
            deploy_generation = data["deploy_generation"]
            location = data["config_location"]
        except Exception, e:
            # yaml info not valid.
            log.warning("Cannot parse file '%s' - ignoring. Error: %s" % (config_info_file, e))
            return self.LOCAL_CFG_INVALID
        finally:
            fh.close()

        if deploy_generation != constants.CLOUD_CONFIG_DEPLOY_LOGIC_GENERATION:
            # different format or logic of the deploy itself.
            # trigger a redeploy
            log.debug("Config was installed with an old generation of the logic.")
            return self.LOCAL_CFG_OLD

        if location != self._descriptor.get_location():
            log.debug("Local Config %r <> Tracked descriptor %r" % (location, self._descriptor.get_location()))
            return self.LOCAL_CFG_OLD

        else:
            log.debug("Local config is up to date")
            return self.LOCAL_CFG_UP_TO_DATE


    def move_to_backup(self):
        """
        Move the config to a backup location.
        """
        if not self._descriptor.needs_installation():
            raise ShotgunDeployError("%s does not support backups." % self._descriptor)

        config_path = self.get_path()
        backup_path = paths.get_configuration_backup(
                self._sg_connection.base_url,
                self._project_id,
                self._pipeline_config_id)

        log.debug("Backing up config %s -> %s" % (config_path, backup_path))

        # the config_backup_path has already been created by the hook, so we
        # are moving the config folder *into* the backup folder to make
        # the system as permissions friendly as possible and give maximum
        # flexibility to the hook logic to do whatever it needs to do.
        backup_target_path = os.path.join(backup_path, os.path.basename(config_path))
        os.rename(config_path, backup_target_path)

        log.debug("backup complete.")


    def set_up_project_scaffold(self, create_tank_command=False):
        """
        Creates all the necessary files on disk for a basic config scaffold.

        - Sets up basic folder structure for a config
        - Copies the configuration into place.

        Once this scaffold is set up, the core need to be installed.
        This is done via _install_core() or _reference_external_core()
        """

        config_path = self.get_path()

        log.info("Installing configuration into '%s'..." % config_path)

        ensure_folder_exists(config_path)

        # create pipeline config base folder structure
        ensure_folder_exists(os.path.join(config_path, "cache"))
        ensure_folder_exists(os.path.join(config_path, "config"))
        ensure_folder_exists(os.path.join(config_path, "install"))
        ensure_folder_exists(os.path.join(config_path, "install", "core", "python"))
        ensure_folder_exists(os.path.join(config_path, "install", "core.backup"), create_placeholder_file=True)
        ensure_folder_exists(os.path.join(config_path, "install", "engines"), create_placeholder_file=True)
        ensure_folder_exists(os.path.join(config_path, "install", "apps"), create_placeholder_file=True)
        ensure_folder_exists(os.path.join(config_path, "install", "frameworks"), create_placeholder_file=True)

        self._descriptor.ensure_local()

        # copy the configuration into place
        copy_folder(self._descriptor.get_path(), os.path.join(config_path, "config"))


        #
        self._write_install_location_file()
        self._write_config_info_file()
        self._write_shotgun_file()
        self._write_pipeline_config_file()
        self._update_roots_file()

        # and lastly install core
        self._install_core(create_tank_command)

        # @todo - prime caches
        # @todo - fetch path cache
        # @todo - bake yaml caches
        # @todo - look at actions baking


    def _install_core(self, create_tank_command):
        """
        Install a core into the given configuration.

        This will copy the core API from the given location into
        the configuration, effectively mimicing a localized setup.

        :param log: python logger object
        :param config_paths: Path to configuration. Dictionary with keys
            darwin, win32 and linux2. Entries in this dictionary can be None.
        :param core_path: Path to core to copy
        """

        core_location = self._descriptor.get_associated_core_location()

        if core_location is None:
            # we don't have a core location specified. Get latest from app store.
            log.debug("Config does not define which core to use. Will use latest.")
            core_location = {"type": "app_store", "name": "tk-core"}
            core_descriptor = descriptor_factory.create_latest_descriptor(
                    self._sg_connection,
                    Descriptor.CORE,
                    core_location,
                    self._bundle_cache_root
            )
        else:
            # we have an exact core location. Get a descriptor for it
            log.debug("Config needs core %s" % core_location)
            core_descriptor = descriptor_factory.create_descriptor(
                    self._sg_connection,
                    Descriptor.CORE,
                    core_location,
                    self._bundle_cache_root
            )

        log.debug("Config will use Core %s" % core_descriptor)

        # make sure we have our core on disk
        core_descriptor.ensure_local()
        core_path = core_descriptor.get_path()
        config_root_path = self.get_path()
        core_target_path = os.path.join(config_root_path, "install", "core")

        log.debug("Copying core into place")
        copy_folder(core_path, core_target_path)

        if create_tank_command:
            # copy the tank binaries to the top of the config
            # grab these from the currently executing core API
            log.debug("Copying Toolkit binaries...")
            root_binaries_folder = os.path.join(core_target_path, "setup", "root_binaries")
            for file_name in os.listdir(root_binaries_folder):
                src_file = os.path.join(root_binaries_folder, file_name)
                tgt_file = os.path.join(config_root_path, file_name)
                copy_file(src_file, tgt_file, 0775)


    def get_tk_instance(self, sg_user):
        """
        Returns a tk instance for this configuration
        """
        # @todo - check if there is already a tank instance, in that case unload or warn
        path = self.get_path()
        core_path = os.path.join(path, "install", "core", "python")
        sys.path.insert(0, core_path)
        import tank
        tank.set_authenticated_user(sg_user)
        tk = tank.tank_from_path(path)
        log.info("API created: %s" % tk)
        return tk

    def _write_install_location_file(self):
        """
        Writes the install location file
        :return:
        """
        config_path = self.get_path()

        # write a file location file for our new setup
        sg_code_location = os.path.join(config_path, "config", "core", "install_location.yml")

        log.debug("Creating install_location file...")

        # platforms other than the current OS will not be supposed
        # by this config scaffold
        config_paths = {"darwin": None, "win32": None, "linux2": None}
        config_paths[sys.platform] = config_path

        fh = open(sg_code_location, "wt")
        fh.write("# Shotgun Pipeline Toolkit configuration file\n")
        fh.write("# This file was automatically created\n")
        fh.write("# This file reflects the paths in the pipeline\n")
        fh.write("# configuration defined for this project.\n")
        fh.write("\n")
        fh.write("Windows: '%s'\n" % config_paths["win32"])
        fh.write("Darwin: '%s'\n" % config_paths["darwin"])
        fh.write("Linux: '%s'\n" % config_paths["linux2"])
        fh.write("\n")
        fh.write("# End of file.\n")
        fh.close()


    def _write_config_info_file(self):
        """
        Writes a cache file with info about where the config came from.
        """
        config_info_file = os.path.join(self.get_path(), "cache", constants.CONFIG_INFO_CACHE)
        fh = open(config_info_file, "wt")

        fh.write("# This file contains metadata describing what exact version\n")
        fh.write("# Of the config that was downloaded from Shotgun\n")
        fh.write("\n")
        fh.write("# Below follows details for the sg attachment that is\n")
        fh.write("# reflected within this local configuration.\n")
        fh.write("\n")

        metadata = {}
        # bake in which version of the deploy logic was used to push this config
        metadata["deploy_generation"] = constants.CLOUD_CONFIG_DEPLOY_LOGIC_GENERATION
        # and include details about where the config came from
        metadata["config_location"] = self._descriptor.get_location()

        # write yaml
        yaml.safe_dump(metadata, fh)
        fh.write("\n")
        fh.close()


    def _write_shotgun_file(self):
        """
        Writes config/core/shotgun.yml
        """
        config_info_file = os.path.join(self.get_path(), "config", "core", constants.CONFIG_SHOTGUN_FILE)
        fh = open(config_info_file, "wt")

        fh.write("# This file was auto generated\n")

        metadata = {}
        # bake in which version of the deploy logic was used to push this config
        metadata["host"] = self._sg_connection.base_url
        # and include details about where the config came from
        metadata["http_proxy"] = self._sg_connection.config.raw_http_proxy

        # write yaml
        yaml.safe_dump(metadata, fh)
        fh.write("\n")
        fh.close()

        log.debug("Wrote %s" % config_info_file)

    def _write_pipeline_config_file(self):
        """
        Writes pipeline configuration yml
        """
        # the pipeline config metadata
        # resolve project name and pipeline config name from shotgun.
        if self._pipeline_config_id:
            # look up pc name and project name via the pc
            log.debug("Checking pipeline config in Shotgun...")
            sg_data = self._sg_connection.find_one(
                    "PipelineConfiguration",
                    [["id", "is", self._pipeline_config_id]],
                    ["code", "project.Project.name"])
            project_name = sg_data["project.Project.name"] or "Site"
            pipeline_config_name = sg_data["code"] or constants.UNMANAGED_PIPELINE_CONFIG_NAME

        elif self._project_id:
            # no pc. look up the project name via the project id
            log.debug("Checking project in Shotgun...")
            sg_data = self._sg_connection.find_one(
                    "Project",
                    [["id", "is", self._project_id]],
                    ["name"]
            )
            project_name = sg_data["name"] or "Unnamed"
            pipeline_config_name = constants.UNMANAGED_PIPELINE_CONFIG_NAME

        else:
            project_name = "Site"
            pipeline_config_name = constants.UNMANAGED_PIPELINE_CONFIG_NAME

        data = {
            "pc_id": self._pipeline_config_id or 0,
            "pc_name": pipeline_config_name,
            "project_id": self._project_id,
            "project_name": project_name,
            "published_file_entity_type": "PublishedFile",
            "use_global_bundle_cache": True,
            "use_shotgun_path_cache": True}

        config_info_file = os.path.join(self.get_path(), "config", "core", constants.PIPELINECONFIG_FILE)
        fh = open(config_info_file, "wt")

        fh.write("# This file was auto generated\n")

        # write yaml
        yaml.safe_dump(data, fh)
        fh.write("\n")
        fh.close()

        log.debug("Wrote %s" % config_info_file)

    def _update_roots_file(self):
        """
        Updates roots.yml based on local storage defs in shotugn
        """
        # get list of storages in Shotgun
        sg_data = self._sg_connection.find(
            "LocalStorage",
            [],
            fields=["id", "code", "linux_path", "mac_path", "windows_path"])

        # organize them by name
        storage_by_name = {}
        for storage in sg_data:
            storage_by_name[storage["code"]] = storage

        # now write out roots data
        roots_data = {}

        for storage in self._descriptor.get_required_storages():
            roots_data[storage] = {}
            if storage not in storage_by_name:
                raise ShotgunDeployError("A '%s' storage is defined by %s but is not defined in Shotgun." % (storage, self._descriptor))
            roots_data[storage]["mac_path"] = storage_by_name[storage]["mac_path"]
            roots_data[storage]["linux_path"] = storage_by_name[storage]["linux_path"]
            roots_data[storage]["windows_path"] = storage_by_name[storage]["windows_path"]

        config_info_file = os.path.join(self.get_path(), "config", "core", constants.STORAGE_ROOTS_FILE)
        fh = open(config_info_file, "wt")

        fh.write("# This file was auto generated\n")

        # write yaml
        yaml.safe_dump(roots_data, fh)
        fh.write("\n")
        fh.close()

        log.debug("Wrote %s" % config_info_file)



