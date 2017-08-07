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

from . import constants

from .errors import TankBootstrapError

from ..util import filesystem

from tank_vendor import yaml
from .configuration import Configuration
from .configuration_writer import ConfigurationWriter

from .. import LogManager

log = LogManager.get_logger(__name__)


class CachedConfiguration(Configuration):
    """
    Represents a configuration which is cached in temp space at runtime
    and kept continously up to date, usually through the means of
    automatic updates.
    """

    def __init__(
            self,
            path,
            sg,
            descriptor,
            project_id,
            plugin_id,
            pipeline_config_id,
            bundle_cache_fallback_paths
    ):
        """
        :param path: ShotgunPath object describing the path to this configuration
        :param sg: Shotgun API instance
        :param descriptor: ConfigDescriptor for the associated config
        :param project_id: Project id for the shotgun project associated with the
                           configuration. For a site-level configuration, this
                           can be set to None.
        :param plugin_id: Plugin id string to identify the scope for a particular plugin
                          or integration. For more information,
                          see :meth:`~sgtk.bootstrap.ToolkitManager.plugin_id`. For
                          non-plugin based toolkit projects, this value is None.
        :param pipeline_config_id: Pipeline Configuration id for the shotgun
                                   pipeline config id associated. If a config does
                                   not have an associated entity in Shotgun, this
                                   should be set to None.
        :param bundle_cache_fallback_paths: List of additional paths where apps are cached.
        """
        super(CachedConfiguration, self).__init__(path, descriptor)
        self._path = path
        self._sg_connection = sg
        self._descriptor = descriptor
        self._project_id = project_id
        self._plugin_id = plugin_id
        self._pipeline_config_id = pipeline_config_id
        self._bundle_cache_fallback_paths = bundle_cache_fallback_paths

        self._config_writer = ConfigurationWriter(self._path, self._sg_connection)

    def __str__(self):
        """
        User friendly representation of the config
        """
        return str(self._descriptor)

    def __repr__(self):
        """
        Low level representation of the config.
        """
        return "<Config with id %s, project id %s, id %s and base %r>" % (
            self._pipeline_config_id,
            self._project_id,
            self._plugin_id,
            self._descriptor
        )

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

        if self._config_writer.is_transaction_pending():
            return self.LOCAL_CFG_INVALID

        # Pass 2:
        # local config exists. See if it is up to date.
        # get the path to a potential config metadata file
        config_info_file = self._config_writer.get_descriptor_metadata_file()

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
            log.debug(
                "Config was installed with a different generation of the logic. "
                "Was expecting %s but got %s.",
                constants.BOOTSTRAP_LOGIC_GENERATION, deploy_generation
            )
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
            log.debug("Your configuration contains dev or path descriptors. "
                      "Triggering full config rebuild.")

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

        self._config_writer.start_transaction()

        # make sure a scaffold is in place
        self._config_writer.ensure_project_scaffold()

        # stow away any previous versions of core and config folders
        try:
            # Move to backup needs to undo changes when failing because we need to put the configuration
            # in a usable state.
            (config_backup_path, core_backup_path) = self._config_writer.move_to_backup(undo_on_error=True)
        except Exception, e:
            log.exception(
                "Unexpected error while making a backup of the configuration. Toolkit will use the "
                "original configuration."
            )
            return

        # copy the configuration into place
        try:
            self._descriptor.copy(os.path.join(self._path.current_os, "config"))

            # write out config files
            self._config_writer.write_install_location_file()
            self._config_writer.write_config_info_file(self._descriptor)
            self._config_writer.write_shotgun_file(self._descriptor)
            self._config_writer.write_pipeline_config_file(
                self._pipeline_config_id,
                self._project_id,
                self._plugin_id,
                self._bundle_cache_fallback_paths,
                self._descriptor
            )

            # make sure roots file reflects current paths
            self._config_writer.update_roots_file(self._descriptor)

            # and lastly install core
            self._config_writer.install_core(
                self._descriptor,
                self._bundle_cache_fallback_paths
            )

        except Exception, e:
            log.exception("Failed to update configuration. Attempting Rollback. Error Traceback:")
            # step 1 - clear core and config locations
            log.debug("Cleaning out faulty config location...")
            # we're purposefully moving the bad pipeline configuration out of the way so we can restore
            # the original one, so move the failed one to backup so it can hopefully be debugged in the future
            # and restore the original one.
            self._config_writer.move_to_backup(undo_on_error=False)
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
        else:
            # remove backup folders now that the update has completed successfully
            # note: config_path points at a config folder inside a timestamped
            # backup folder. It's this parent folder we want to clean up.
            self._cleanup_backup_folders(os.path.dirname(config_backup_path) if config_backup_path else None,
                                         core_backup_path)
            log.debug("Latest backup cleanup complete.")

        # @todo - prime caches (yaml, path cache)

        # make sure tank command and interpreter files are up to date
        self._config_writer.create_tank_command()

        self._config_writer.end_transaction()

    @property
    def has_local_bundle_cache(self):
        """
        If True, indicates that pipeline configuration has a local bundle cache. If False, it
        depends on the global bundle cache.
        """
        # CachedConfiguration always depend on the global bundle cache.
        return False

    def _cleanup_backup_folders(self, config_backup_folder_path, core_backup_folder_path):
        """
        Cleans up backup folders generated by a call to the update_configuration method

        :param config_backup_folder_path: Path to the configuration backup folder to be deleted
                                          or None.
        :param core_backup_folder_path:   Path to the core backup folder to be deleted or None.
        """
        for path in [config_backup_folder_path, core_backup_folder_path]:
            if path:
                try:
                    filesystem.safe_delete_folder(path)
                    log.debug("Deleted backup folder: %s", path)
                except Exception, e:
                    log.warning("Failed to clean up temporary backup folder '%s': %s" % (path, e))
