# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import importlib.metadata
import os
import inspect
import sys

import sgtk
import tank

from tank import pipelineconfig_utils
from tank import (
    TankInvalidInterpreterLocationError,
    TankFileDoesNotExistError,
    TankInvalidCoreLocationError,
    TankNotPipelineConfigurationError,
)
from tank.util import ShotgunPath, is_windows

from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import (
    mock,
    ShotgunTestBase,
    temp_env_var,
)

class TestGetConfigInstallLocationPathSlashes(ShotgunTestBase):
    """
    Tests the case where a Windows config location uses double slashes.
    """

    @mock.patch("tank.pipelineconfig_utils._get_install_locations")
    def test_config_path_cleanup(self, get_install_locations_mock):
        pass
class TestPipelineConfigUtils(ShotgunTestBase):
    """
    Tests pipeline configuration utilities.
    """

    def _create_interpreter_file(self, config_root, path):
        """
        Creates an interpreter file in a configuration.

        :param str config_root_name: Path to the configuration root.
        :param str path: Path to write in the interpreter file.
        """
        self.create_file(
            ShotgunPath.get_file_name_from_template(
                os.path.join(config_root, "config", "core", "interpreter_%s.cfg")
            ),
            path,
        )

    def _create_core_file(self, config_root, path):
        """
        Creates a core file in a configuration.

        :param str config_root_name: Path to the configuration root.
        :param str path: Path to write in the interpreter file.
        """
        self.create_file(
            ShotgunPath.get_file_name_from_template(
                os.path.join(config_root, "install", "core", "core_%s.cfg")
            ),
            path,
        )

    def _create_core(self, core_root):
        """
        Creates a core at a given location.

        :param core_root: Path to the core to create.

        :returns: Path to the created core.
        """

        self.create_file(
            os.path.join(core_root, "install", "core", "_core_upgrader.py"),
            "",  # Content is unimportant.
        )
        return core_root

    def _create_studio_core(self, core_name):
        """
        Create a standalone core with a given name.

        :param core_name: Name of the folder for the core.

        :returns: Path to the standalone core.
        """
        core_root = os.path.join(self.tank_temp, core_name)
        return self._create_core(core_root)

    def _create_unlocalized_pipeline_configuration(self, config_name):
        """
        Creates a pipeline configuration without a localized core.

        :param config_name: Name of the configuration.

        :returns: Root of the configuration.
        """
        config_root = os.path.join(self.tank_temp, config_name)
        self.create_file(
            os.path.join(config_root, "config", "core", "roots.yml"),
            "{}",  # We don't care for the content of that file
        )
        return config_root

    def _create_pipeline_configuration(self, config_name, core_location=None):
        """
        Creates a pipeline configuration with a localized core.

        :param config_name: Name of the configuration.

        :returns: Root of the configuration.
        """
        config_root = self._create_unlocalized_pipeline_configuration(config_name)
        # If we want to create a localized one.
        if core_location:
            self._create_core_file(config_root, core_location)
        else:
            # Make it localized.
            self._create_core(config_root)
        return config_root

    def test_with_invalid_pipelines(self):
        pass
    def test_localize_config_with_interpreter_as_env_var(self):
        pass
    def test_localized_config_interpreter_file(self):
        pass
    def test_core_location_retrieval(self):
        pass
    def test_shared_config_interpreter_file(self):
        pass
    def test_missing_core_location_file(self):
        pass
    def test_get_sgtk_module_path(self):
        pass
class TestGetCurrentlyRunningApiVersion(ShotgunTestBase):
    """
    Tests get_currently_running_api_version, including the importlib.metadata
    fallback used when info.yml is absent (e.g. flat pip install layout).
    """

    @mock.patch("tank.pipelineconfig_utils._get_version_from_manifest")
    def test_returns_manifest_version_when_present(self, manifest_mock):
        pass
    @mock.patch("tank.pipelineconfig_utils._get_version_from_manifest")
    def test_falls_back_to_dist_metadata_when_manifest_missing(self, manifest_mock):
        pass
    @mock.patch("tank.pipelineconfig_utils._get_version_from_manifest")
    def test_returns_unknown_when_manifest_and_dist_metadata_missing(
        self, manifest_mock
    ):
        pass
class TestGetCoreApiVersion(ShotgunTestBase):
    """
    Tests get_core_api_version, including the distribution-metadata fallback
    used when the requested core is the currently-running one and info.yml is
    absent (e.g. flat pip install layout).
    """

    @mock.patch("tank.pipelineconfig_utils._get_version_from_manifest")
    def test_returns_manifest_version_when_present(self, manifest_mock):
        pass
    @mock.patch("tank.pipelineconfig_utils._get_version_from_manifest")
    def test_returns_unknown_for_other_core_when_manifest_missing(
        self, manifest_mock
    ):
        pass
    @mock.patch("tank.pipelineconfig_utils._get_version_from_manifest")
    def test_falls_back_to_dist_metadata_for_current_core(self, manifest_mock):
        pass
    @mock.patch("tank.pipelineconfig_utils._get_version_from_manifest")
    def test_returns_unknown_when_current_core_resolution_fails(
        self, manifest_mock
    ):
        pass
