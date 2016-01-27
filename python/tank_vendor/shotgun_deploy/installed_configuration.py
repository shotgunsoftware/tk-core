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
import shutil
import uuid
import imp
from . import constants
from . import Descriptor
from . import descriptor_factory
from . import paths
from .errors import ShotgunDeployError
from . import util

from .. import yaml
from ..shotgun_base import copy_folder, ensure_folder_exists

log = util.get_shotgun_deploy_logger()



class InstalledConfiguration(object):
    """
    Represents a configuration that has been installed on disk
    """

    (LOCAL_CFG_UP_TO_DATE, LOCAL_CFG_MISSING, LOCAL_CFG_OLD, LOCAL_CFG_INVALID) = range(4)

    def __init__(self, sg, descriptor, project_id, pipeline_config_id=None):
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
        # probe for tank command
        if not os.path.exists(os.path.join(config_root, "tank")):
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


    def set_up_project_scaffold(self):
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
        # @todo - how do we handle git clone??
        # @todo - need to handle the traditional setup!
        copy_folder(self._descriptor.get_path(),
                    os.path.join(config_path, "config"))

        # write a file location file for our new setup
        sg_code_location = os.path.join(config_path, "config", "core", "install_location.yml")

        #
        log.debug("Creating install_location file file...")

        # @todo - support other platforms
        local_install_path = self.get_path()

        # platforms other than the current OS will not be supposed
        # by this config scaffold
        config_paths = {"darwin": None, "win32": None, "linux2": None}
        config_paths[sys.platform] = local_install_path

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

        self._write_shotgun_file()
        self._write_pipeline_config_file()


    def install_core(self):
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
            # @todo - find latest in app store
            core_location = {"type":"app_store", "name": "tk-core", "version": "v0.16.42"}

        core_descriptor = descriptor_factory.create_descriptor(self._sg_connection, Descriptor.CORE, core_location)
        core_descriptor.download_local()
        core_path = core_descriptor.get_path()

        config_root_path = self.get_path()

        core_target_path = os.path.join(config_root_path, "install", "core")


        log.debug("Copying core into place")
        copy_folder(core_path, core_target_path)

        # copy the tank binaries to the top of the config
        # grab these from the currently executing core API
        log.debug("Copying Toolkit binaries...")

        root_binaries_folder = os.path.join(core_target_path, "setup", "root_binaries")
        for file_name in os.listdir(root_binaries_folder):
            src_file = os.path.join(root_binaries_folder, file_name)
            tgt_file = os.path.join(config_root_path, file_name)
            shutil.copy(src_file, tgt_file)
            os.chmod(tgt_file, 0775)


    def __uuid_import(self, path):
        """
        Imports a module with a given name at a given location with a decorated
        namespace so that it can be reloaded multiple times at different locations.

        :param module: Name of the module we are importing.
        :param path: Path to the folder containing the module we are importing.

        :returns: The imported module.
        """
        log.debug("Trying to import module from path '%s'..." % path)
        module = imp.load_module(uuid.uuid4().hex, None, path, ("", "", imp.PKG_DIRECTORY) )
        log.debug("Successfully imported %s" % module)
        return module


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
        data = {
            "pc_id": 3,
            "pc_name": "Primary",
            "project_id": 65,
            "project_name": "big_buck_bunny",
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






    def _get_published_file_entity_type(self):
        """
        Find the published file entity type to use for this project.
        Communicates with Shotgun, introspects the sg schema.

        :returns: 'PublishedFile' if the PublishedFile entity type has
                  been enabled, otherwise returns 'TankPublishedFile'
        """
        log.debug("Retrieving schema from Shotgun to determine entity type to use for published files")

        pf_entity_type = "TankPublishedFile"
        try:
            sg_schema = self._sg_connection.schema_read()
            if ("PublishedFile" in sg_schema
                and "PublishedFileType" in sg_schema
                and "PublishedFileDependency" in sg_schema):
                pf_entity_type = "PublishedFile"
        except Exception, e:
            raise ShotgunDeployError("Could not retrieve the Shotgun schema: %s" % e)

        log.debug(" > Using %s entity type for published files" % pf_entity_type)

        return pf_entity_type



    def validate_storages(self):
        """
        Validate that the roots exist in shotgun. Communicates with Shotgun.

        Returns the root paths from shotgun for each storage.

        {
          "primary" : {
                        "exists_on_disk": False,
                        "defined_in_shotgun": True,
                        "shotgun_id": 12,
                        "darwin": "/mnt/foo",
                        "win32": "z:\mnt\foo",
                        "linux2": "/mnt/foo"},

          "textures" : {
                         "exists_on_disk": False,
                         "defined_in_shotgun": True,
                         "shotgun_id": 14,
                         "darwin": None,
                         "win32": "z:\mnt\foo",
                         "linux2": "/mnt/foo"}
        }

        The main dictionary is keyed by storage name. It will contain one entry
        for each local storage which is required by the configuration template.
        Each sub-dictionary contains the following items:

        - description: Description what the storage is used for. This comes from the
          configuration template and can be used to help a user to explain the purpose
          of a particular storage required by a configuration.
        - defined_in_shotgun: If false, no local storage with this name exists in Shotgun.
        - shotgun_id: If defined_in_shotgun is True, this will contain the entity id for
          the storage. If defined_in_shotgun is False, this will be set to none.
        - darwin/win32/linux: Paths to storages, as defined in Shotgun. These values can be
          None if a storage has not been defined.
        - exists_on_disk: Flag if the path defined for the current operating system exists on
          disk or not.

        :returns: dictionary with storage breakdown, see example above.
        """

        return_data = {}

        log.debug("Checking so that all the local storages are registered...")
        sg_storage = self._sg_connection.find(
            "LocalStorage",
            [],
            fields=["id", "code", "linux_path", "mac_path", "windows_path"])

        # make sure that there is a storage in shotgun matching all storages for this config
        sg_storage_codes = [x.get("code") for x in sg_storage]
        cfg_storages = self._descriptor.get_required_storages()

        for s in cfg_storages:

            return_data[s] = { "shotgun_id": None,
                               "darwin": None,
                               "win32": None,
                               "linux2": None}

            if s not in sg_storage_codes:
                return_data[s]["defined_in_shotgun"] = False
                return_data[s]["exists_on_disk"] = False
            else:
                return_data[s]["defined_in_shotgun"] = True

                # find the sg storage paths and add to return data
                for x in sg_storage:

                    if x.get("code") == s:

                        # copy the storage paths across
                        return_data[s]["darwin"] = x.get("mac_path")
                        return_data[s]["linux2"] = x.get("linux_path")
                        return_data[s]["win32"] = x.get("windows_path")
                        return_data[s]["shotgun_id"] = x.get("id")

                        # get the local path
                        lookup_dict = {"linux2": "linux_path", "win32": "windows_path", "darwin": "mac_path" }
                        local_storage_path = x.get(lookup_dict[sys.platform])

                        if local_storage_path is None:
                            # shotgun has no path for our local storage
                            return_data[s]["exists_on_disk"] = False

                        elif not os.path.exists(local_storage_path):
                            # path is defined but cannot be found
                            return_data[s]["exists_on_disk"] = False

                        else:
                            # path exists! yay!
                            return_data[s]["exists_on_disk"] = True

        return return_data
