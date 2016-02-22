# Copyright (c) 2016 Shotgun Software Inc.
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
import datetime
from . import constants
from . import Descriptor, create_descriptor
from . import paths
from .errors import ShotgunDeployError
from . import util

from ..shotgun_base import copy_file, append_folder_to_path

from .. import yaml
from ..shotgun_base import copy_folder, ensure_folder_exists

log = util.get_shotgun_deploy_logger()

def create_unmanaged_configuration(sg, descriptor, project_id, pipeline_config_id, namespace):
    """
    Factory method for creating an unmanaged configuration object. Unmanaged configurations
    are auto-installed on disk and the user doesn't have any power over where they are located.

    :param sg: Shotgun API instance
    :param descriptor: ConfigDescriptor for the associated config
    :param project_id: Project id for the shotgun project associated with the
                       configuration. For a site-level configuration, this
                       can be set to None.
    :param pipeline_config_id: Pipeline Configuration id for the shotgun
                               pipeline config id associated. If a config does
                               not have an associated entity in Shotgun, this
                               should be set to None.
    :param namespace: name space string, typically one short word,
                      e.g. 'maya', 'rv', 'desktop'.
    :returns: Configuration instance
    """
    log.debug("Creating a configuration wrapper for unmanaged config %r" % descriptor)
    return UnmanagedConfiguration(sg, descriptor, project_id, pipeline_config_id, namespace)


def create_managed_configuration(
    sg,
    bundle_cache_root,
    project_id,
    pipeline_config_id,
    namespace,
    win_path,
    linux_path,
    mac_path
):
    """
    Factory method for creating a managed configuration wrapper object.

    :param sg: Shotgun API instance
    :param bundle_cache_root: Folder where descriptors are being cached
    :param project_id: Project id for the shotgun project associated with the
                       configuration. For a site-level configuration, this
                       can be set to None.
    :param pipeline_config_id: Pipeline Configuration id for the shotgun
                               pipeline config id associated. For managed
                               configs, this option cannot be None.
    :param namespace: name space string, typically one short word,
                      e.g. 'maya', 'rv', 'desktop'.
    :param win_path: Path on windows where the config should be located
    :param linux_path: Path on linux where the config should be located
    :param mac_path: Path on macosx where the config should be located
    :returns: ManagedConfiguration instance
    """
    log.debug("Creating a configuration wrapper for managed config.")

    if pipeline_config_id is None:
        raise ValueError("Managed configurations require a Pipeline Configuration id.")

    config_root = {
        "win32": win_path,
        "linux2": linux_path,
        "darwin": mac_path
    }

    # first determine the descriptor. This resides inside the config folder of the path
    config_path_win = append_folder_to_path("win32", win_path, "config")
    config_path_linux = append_folder_to_path("linux2", linux_path, "config")
    config_path_mac = append_folder_to_path("darwin", mac_path, "config")

    config_location = {
        "type": "path",
        "linux_path": config_path_linux,
        "mac_path": config_path_mac,
        "windows_path": config_path_win
    }

    config_descriptor = create_descriptor(
        sg,
        Descriptor.CONFIG,
        config_location,
        bundle_cache_root
    )

    return ManagedConfiguration(
        sg,
        config_descriptor,
        project_id,
        pipeline_config_id,
        namespace,
        config_root)


class Configuration(object):
    """
    An abstraction around a toolkit configuration.

    The configuration is identified by a ConfigurationDescriptor
    object and may or may not exist on disk.
    """

    (LOCAL_CFG_UP_TO_DATE, LOCAL_CFG_MISSING, LOCAL_CFG_OLD, LOCAL_CFG_INVALID) = range(4)

    def __init__(self, sg, descriptor, project_id, pipeline_config_id, namespace):
        """
        Constructor.

        :param sg: Shotgun API instance
        :param descriptor: ConfigDescriptor for the associated config
        :param project_id: Project id for the shotgun project associated with the
                           configuration. For a site-level configuration, this
                           can be set to None.
        :param pipeline_config_id: Pipeline Configuration id for the shotgun
                                   pipeline config id associated. If a config does
                                   not have an associated entity in Shotgun, this
                                   should be set to None.
        :param namespace: name space string, typically one short word,
                          e.g. 'maya', 'rv', 'desktop'.
        """
        self._sg_connection = sg
        self._descriptor = descriptor
        self._project_id = project_id
        self._pipeline_config_id = pipeline_config_id
        self._namespace = namespace

    def __repr__(self):
        return "<Config with id %s, project id %s and base %s>" % (
            self._pipeline_config_id,
            self._project_id,
            self._descriptor
        )

    def get_path(self, platform=sys.platform):
        """
        Returns the path to the installed configuration
        on the given os. Note how the location returned by
        this method is the root folder of an installed configuration.

        This root folder in turn contains a 'config' folder which contains
        the configuration described by the config descriptor.

        :param platform: Operating system platform
        :return: path on disk as string
        """
        raise NotImplementedError

    def status(self):
        """
        Compares the actual configuration installed on disk against the
        associated configuration described by the descriptor passed in via
        the class constructor.

        :returns: LOCAL_CFG_UP_TO_DATE, LOCAL_CFG_MISSING,
                  LOCAL_CFG_OLD, or LOCAL_CFG_INVALID
        """
        raise NotImplementedError

    def update_configuration(self):
        """
        Ensure that the configuration is up to date with the one
        given by the associated descriptor.
        """
        raise NotImplementedError

    def get_tk_instance(self, sg_user):
        """
        Returns a tk instance for this configuration.

        :param sg_user: Authenticated Shotgun user to associate
                        the tk instance with.
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

    def _ensure_project_scaffold(self):
        """
        Creates all the necessary files on disk for a basic config scaffold.

        - Sets up basic folder structure for a config
        - Copies the configuration into place.

        :returns: True if a scaffold was created, False if a complete or
                  partial configuration already existed on disk.
        """
        config_path = self.get_path()
        log.info("Ensuring project scaffold in '%s'..." % config_path)

        config_exists = os.path.exists(config_path)

        ensure_folder_exists(config_path)
        ensure_folder_exists(os.path.join(config_path, "cache"))

        ensure_folder_exists(
            os.path.join(config_path, "install", "config.backup"),
            create_placeholder_file=True
        )
        ensure_folder_exists(
            os.path.join(config_path, "install", "core.backup"),
            create_placeholder_file=True
        )
        ensure_folder_exists(
            os.path.join(config_path, "install", "engines"),
            create_placeholder_file=True
        )
        ensure_folder_exists(
            os.path.join(config_path, "install", "apps"),
            create_placeholder_file=True
        )
        ensure_folder_exists(
            os.path.join(config_path, "install", "frameworks"),
            create_placeholder_file=True
        )

        return config_exists

    def _move_to_backup(self):
        """
        Move any existing config and core to a backup location.

        After this method has been executed, there is no config and
        no install/core folder present in the configuration scaffold.
        Both have been moved into their respective backup locations.

        """
        # get backup root location
        config_path = self.get_path()

        configuration_payload = os.path.join(config_path, "config")

        if os.path.exists(configuration_payload):

            config_backup_root = os.path.join(config_path, "install", "config.backup")

            # make sure we have a backup folder present
            config_backup_path = os.path.join(
                config_backup_root,
                datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            )
            ensure_folder_exists(config_backup_path)

            log.debug("Moving config %s -> %s" % (configuration_payload, config_backup_path))
            backup_target_path = os.path.join(config_backup_path, os.path.basename(configuration_payload))
            os.rename(configuration_payload, backup_target_path)
            log.debug("Backup complete.")

        # now back up the core API
        core_payload = os.path.join(config_path, "install", "core")

        if os.path.exists(core_payload):
            core_backup_root = os.path.join(config_path, "install", "core.backup")
            # should not be necessary but just in case.
            ensure_folder_exists(core_backup_root)

            # make sure we have a backup folder present
            core_backup_path = os.path.join(
                core_backup_root,
                datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            )

            log.debug("Moving core %s -> %s" % (core_payload, core_backup_path))
            os.rename(core_payload, core_backup_path)
            log.debug("Backup complete.")

    def _create_tank_command(self, win_python=None, mac_python=None, linux_python=None):
        """
        Create a tank command for this configuration.
        This will overwrites existing binaries and create interpreter files.
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

        config_root_path = self.get_path()

        for platform in executables:
            sg_config_location = os.path.join(
                config_root_path,
                "config",
                "core",
                "interpreter_%s.cfg" % platform
            )
            fh = open(sg_config_location, "wt")
            fh.write(executables[platform])
            fh.close()

        # now deploy the actual tank command
        core_target_path = os.path.join(config_root_path, "install", "core")
        root_binaries_folder = os.path.join(core_target_path, "setup", "root_binaries")
        for file_name in os.listdir(root_binaries_folder):
            src_file = os.path.join(root_binaries_folder, file_name)
            tgt_file = os.path.join(config_root_path, file_name)
            if os.path.exists(tgt_file):
                log.debug("File already exists, replacing.")
                try:
                    os.remove(tgt_file)
                    copy_file(src_file, tgt_file, 0775)
                except Exception, e:
                    log.warning(
                        "Could not replace existing file '%s': %s" % (tgt_file, e)
                    )
            else:
                log.debug("Installing brand new tank command")
                copy_file(src_file, tgt_file, 0775)


    def _install_core(self):
        """
        Install a core into the given configuration.

        This will copy the core API from the given location into
        the configuration, effectively mimicing a localized setup.
        """
        core_location = self._descriptor.get_associated_core_location()

        if core_location is None:
            # we don't have a core location specified. Get latest from app store.
            log.info("Config does not define which core to use. Will use latest.")
            core_location = constants.LATEST_CORE_LOCATION
        else:
            # we have an exact core location. Get a descriptor for it
            log.debug("Config needs core %s" % core_location)

        core_descriptor = create_descriptor(
            self._sg_connection,
            Descriptor.CORE,
            core_location,
            self._descriptor.get_bundle_cache_root()
        )

        log.debug("Config will use Core %s" % core_descriptor)

        # make sure we have our core on disk
        core_descriptor.ensure_local()
        config_root_path = self.get_path()
        core_target_path = os.path.join(config_root_path, "install", "core")

        log.debug("Copying core into place")
        core_descriptor.copy(core_target_path)

    def _write_install_location_file(self):
        """
        Writes the install location file
        """
        config_path = self.get_path()

        # write a file location file for our new setup
        sg_code_location = os.path.join(
            config_path,
            "config",
            "core",
            "install_location.yml"
        )

        log.debug("Creating install_location file...")

        # platforms other than the current OS will not be supposed
        # by this config scaffold
        config_paths = {
            "darwin": self.get_path("darwin"),
            "win32": self.get_path("win32"),
            "linux2": self.get_path("linux2")
        }

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
        config_info_file = os.path.join(
            self.get_path(),
            "cache",
            constants.CONFIG_INFO_CACHE
        )
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

        log.debug("Wrote %s" % config_info_file)

    def _write_shotgun_file(self):
        """
        Writes config/core/shotgun.yml
        """
        sg_file = os.path.join(
            self.get_path(),
            "config",
            "core",
            constants.CONFIG_SHOTGUN_FILE
        )
        fh = open(sg_file, "wt")

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

        log.debug("Wrote %s" % sg_file)

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
                constants.PIPELINE_CONFIGURATION_ENTITY,
                [["id", "is", self._pipeline_config_id]],
                ["code", "project.Project.tank_name"]
            )

            project_name = sg_data["project.Project.tank_name"] or "Unnamed"
            pipeline_config_name = sg_data["code"] or constants.UNMANAGED_PIPELINE_CONFIG_NAME

        elif self._project_id:
            # no pc. look up the project name via the project id
            log.debug("Checking project in Shotgun...")

            sg_data = self._sg_connection.find_one(
                "Project",
                [["id", "is", self._project_id]],
                ["tank_name"]
            )

            project_name = sg_data["tank_name"] or "Unnamed"
            pipeline_config_name = constants.UNMANAGED_PIPELINE_CONFIG_NAME

        else:
            project_name = "Site"
            pipeline_config_name = constants.UNMANAGED_PIPELINE_CONFIG_NAME

        data = {
            "pc_id": self._pipeline_config_id,
            "pc_name": pipeline_config_name,
            "project_id": self._project_id,
            "project_name": project_name,
            "published_file_entity_type": "PublishedFile",
            "bundle_cache_root": self._descriptor.get_bundle_cache_root(),
            "use_shotgun_path_cache": True}

        pipeline_config_file = os.path.join(
            self.get_path(),
            "config",
            "core",
            constants.PIPELINECONFIG_FILE
        )
        fh = open(pipeline_config_file, "wt")

        fh.write("# This file was auto generated\n")

        # write yaml
        yaml.safe_dump(data, fh)
        fh.write("\n")
        fh.close()

        log.debug("Wrote %s" % pipeline_config_file)

    def _update_roots_file(self):
        """
        Updates roots.yml based on local storage defs in shotugn
        """
        log.debug("Creating storage roots file...")

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
                raise ShotgunDeployError(
                    "A '%s' storage is defined by %s but is "
                    "not defined in Shotgun." % (storage, self._descriptor)
                )
            roots_data[storage]["mac_path"] = storage_by_name[storage]["mac_path"]
            roots_data[storage]["linux_path"] = storage_by_name[storage]["linux_path"]
            roots_data[storage]["windows_path"] = storage_by_name[storage]["windows_path"]

        roots_file = os.path.join(
            self.get_path(),
            "config",
            "core",
            constants.STORAGE_ROOTS_FILE
        )
        fh = open(roots_file, "wt")

        fh.write("# This file was auto generated\n")

        # write yaml
        yaml.safe_dump(roots_data, fh)
        fh.write("\n")
        fh.close()
        log.debug("Wrote %s" % roots_file)


class UnmanagedConfiguration(Configuration):
    """
    An abstraction around an unmanaged Toolkit configuration.
    Unmanaged configs are not installed in a particular location
    on disk, but their life cycle is managed by toolkit internally.

    An unmanaged configuration tracks against a config descriptor
    and the locally cached configuration can be up to date with the
    descriptor or out of date. You can execute the status() method
    to determine this.

    For configurations that are not up to date, the update() method
    will ensure that they are gracefully brought to the version that
    is defined in the descriptor.
    """

    def __init__(self, sg, descriptor, project_id, pipeline_config_id, namespace):
        """
        Constructor.

        :param sg: Shotgun API instance
        :param descriptor: ConfigDescriptor for the associated config
        :param project_id: Project id for the shotgun project associated with the
                           configuration. For a site-level configuration, this
                           can be set to None.
        :param pipeline_config_id: Pipeline Configuration id for the shotgun
                                   pipeline config id associated. If a config does
                                   not have an associated entity in Shotgun, this
                                   should be set to None.
        :param namespace: name space string, typically one short word,
                          e.g. 'maya', 'rv', 'desktop'.
        """
        super(UnmanagedConfiguration, self).__init__(
            sg,
            descriptor,
            project_id,
            pipeline_config_id,
            namespace
        )

    def get_path(self, platform=sys.platform):
        """
        Returns the path to the installed configuration
        on the given os. Note how the location returned by
        this method is the root folder of an installed configuration.

        This root folder in turn contains a 'config' folder which contains
        the configuration described by the config descriptor.

        :param platform: Operating system platform
        :return: path on disk as string
        """
        if platform != sys.platform:
            path = None
        else:
            path = paths.get_configuration_cache_root(
                self._sg_connection.base_url,
                self._project_id,
                self._pipeline_config_id,
                self._namespace
            )

        return path

    def status(self):
        """
        Compares the actual configuration installed on disk against the
        associated configuration described by the descriptor passed in via
        the class constructor.

        :returns: LOCAL_CFG_UP_TO_DATE, LOCAL_CFG_MISSING,
                  LOCAL_CFG_OLD, or LOCAL_CFG_INVALID
        """
        log.debug("Checking status of %r" % self)

        config_root = self.get_path()

        # first check if there is any config at all
        # probe for shotgun.yml connection params file
        if not os.path.exists(os.path.join(config_root, "config", "core", "shotgun.yml")):
            return self.LOCAL_CFG_MISSING

        # local config exists. See if it is up to date.
        # look at the attachment id to determine the generation of the config.
        config_info_file = os.path.join(
            config_root,
            "cache",
            constants.CONFIG_INFO_CACHE
        )

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
            log.debug(
                "Local Config %r does not match "
                "associated descriptor %r" % (location, self._descriptor.get_location())
            )
            return self.LOCAL_CFG_OLD

        else:
            log.debug("Local config is up to date")
            return self.LOCAL_CFG_UP_TO_DATE

    def update_configuration(self):
        """
        Ensure that the configuration is up to date with the one
        given by the associated descriptor.
        """
        # make sure a scaffold is in place
        self._ensure_project_scaffold()

        # stow away any previous versions of core or config
        self._move_to_backup()

        # copy the configuration into place
        config_path = self.get_path()
        self._descriptor.copy(os.path.join(config_path, "config"))

        # write out config files
        self._write_install_location_file()
        self._write_config_info_file()
        self._write_shotgun_file()
        self._write_pipeline_config_file()
        self._update_roots_file()

        # and lastly install core
        self._install_core()

        # @todo - prime caches (yaml, path cache)


class ManagedConfiguration(Configuration):
    """
    Represents a configuration that has been installed on disk in a specific location.
    """

    def __init__(self, sg, descriptor, project_id, pipeline_config_id, namespace, config_root):
        """
        Constructor.

        :param sg: Shotgun API instance
        :param descriptor: ConfigDescriptor for the associated config
        :param project_id: Project id for the shotgun project associated with the
                           configuration. For a site-level configuration, this
                           can be set to None.
        :param pipeline_config_id: Pipeline Configuration id for the shotgun
                                   pipeline config id associated. If a config does
                                   not have an associated entity in Shotgun, this
                                   should be set to None.
        :param namespace: name space string, typically one short word,
                          e.g. 'maya', 'rv', 'desktop'.
        :param config_root: Root path where the installed configuration should be located
                            This is the same path that is being referenced by absolute paths
                            in a pipeline configuration. Note that the configuration itself
                            is installed inside a CONFIG_ROOT/config folder.
        """
        self._config_root = config_root
        super(ManagedConfiguration, self).__init__(
            sg,
            descriptor,
            project_id,
            pipeline_config_id,
            namespace
        )

    def get_path(self, platform=sys.platform):
        """
        Returns the path to the configuration on the given os.

        :return: path on disk as string
        """
        return self._config_root[platform]

    def status(self):
        """
        Compares the actual configuration installed on disk against the
        associated configuration described by the descriptor passed in via
        the class constructor.

        :returns: LOCAL_CFG_UP_TO_DATE, LOCAL_CFG_MISSING,
                  LOCAL_CFG_OLD, or LOCAL_CFG_INVALID
        """
        # managed configs are always up to date - they track
        # their status against themselves.
        return self.LOCAL_CFG_UP_TO_DATE

    def update_configuration(self):
        """
        Ensure that the configuration is up to date with the one
        given by the associated descriptor.
        """
        # we are always up to date with ourselves.
        return

    def install_external_configuration(
            self,
            source_descriptor,
            win_python=None,
            mac_python=None,
            linux_python=None
    ):
        """
        Installs the configuration described by the source descriptor.

        Akin to a project setup, this method will take the configuration
        described by the source descriptor and copy this config folder
        of this configuration object.

        :param source_descriptor: Config to install
        :param win_python: Optional path to a python interpreter
        :param mac_python: Optional path to a python interpreter
        :param linux_python: Optional path to a python interpreter

        """
        # make sure a scaffold is in place
        self._ensure_project_scaffold()

        # stow away any previous versions of core or config
        self._move_to_backup()

        # copy the configuration into place
        config_path = self.get_path()
        source_descriptor.copy(os.path.join(config_path, "config"))

        # write out config files
        self._write_install_location_file()
        self._write_config_info_file()
        self._write_shotgun_file()
        self._write_pipeline_config_file()
        self._update_roots_file()

        # install core
        self._install_core()

        # @todo - prime caches (yaml, path cache)

        # create tank executable for this config
        self._create_tank_command(win_python, mac_python, linux_python)

        # create pipeline configuration entry in Shotgun
        log.debug("Updating pipeline configuration %s with new paths..." % self._pipeline_config_id)
        self._sg_connection.update(
            constants.PIPELINE_CONFIGURATION_ENTITY,
            self._pipeline_config_id,
            {"linux_path": self.get_path("linux2"),
             "windows_path": self.get_path("win32"),
             "mac_path": self.get_path("darwin")}
        )
