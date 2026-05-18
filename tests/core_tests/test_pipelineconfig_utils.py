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
        """
        Check that any glitches in the path are correctly cleaned up.
        """
        # only run this test on windows
        if is_windows():

            # This path has multiple issues we've encountered in the wild
            # It without any escaping sequence, it reads as
            # "   C:/configs\\site//project   "
            # 1. it has whitespace at the begging and end.
            # 2. Uses double slashes instead of single backslash
            # 3. Uses slash instead of backslash
            # 4. Uses double backslashes as a folder separator.
            get_install_locations_mock.return_value = sgtk.util.ShotgunPath(
                "   C:/configs\\\\site//project   ", None, None
            )

            self.assertEqual(
                # We don't need to pass an actual path since _get_install_location is mocked.
                tank.pipelineconfig_utils.get_config_install_location(None),
                "C:\\configs\\site\\project",
            )


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
        """
        Test for folders that are not configuration.
        """
        with self.assertRaises(TankNotPipelineConfigurationError):
            sgtk.get_python_interpreter_for_config("/this/path/does/not/exist")

    def test_localize_config_with_interpreter_as_env_var(self):
        """
        Test for interpreter file in a localized config.
        """
        config_root = self._create_pipeline_configuration(
            "localized_core_with_interpreter_as_env_var"
        )
        # Create interpreter file for good config.
        self._create_interpreter_file(config_root, "$SGTK_TEST_INTERPRETER")

        # Patch os.path.exists since /i/wish/this/was/python3 is obviously not a real
        # file name.
        with mock.patch("os.path.exists", return_value=True):
            with temp_env_var(SGTK_TEST_INTERPRETER="/i/wish/this/was/python3"):
                self.assertEqual(
                    pipelineconfig_utils.get_python_interpreter_for_config(config_root),
                    "/i/wish/this/was/python3",
                )

    def test_localized_config_interpreter_file(self):
        """
        Test for interpreter file in a localized config.
        """
        config_root = self._create_pipeline_configuration(
            "localized_core_with_interpreter"
        )
        # Create interpreter file for good config.
        self._create_interpreter_file(config_root, sys.executable)

        # Create a localized config without an interpreter
        config_root_without_interpreter_file = self._create_pipeline_configuration(
            "localized_core_without_interpreter"
        )
        # Create a localized config with a bad interpreter path
        config_root_with_bad_interpreter = self._create_pipeline_configuration(
            "localized_core_with_bad_interpreter"
        )
        # Create interpreter file for config with bad interpreter location.
        self._create_interpreter_file(
            config_root_with_bad_interpreter, "/path/to/non/existing/python"
        )

        # Test when the interpreter file is present and has a valid python interpreter.
        self.assertEqual(
            pipelineconfig_utils.get_python_interpreter_for_config(config_root),
            sys.executable,
        )

        # Test when the interpreter file is present but the interpreter path is bad.
        with self.assertRaises(TankInvalidInterpreterLocationError):
            pipelineconfig_utils.get_python_interpreter_for_config(
                config_root_with_bad_interpreter
            )

        # Test when the interpreter file is missing
        with self.assertRaisesRegex(
            TankFileDoesNotExistError, "No interpreter file for"
        ):
            pipelineconfig_utils.get_python_interpreter_for_config(
                config_root_without_interpreter_file
            )

    def test_core_location_retrieval(self):
        """
        Ensure we can retrieve the core location for localize and unlocalized cores.
        """
        config_root = self._create_pipeline_configuration("localized_core")

        self.assertEqual(
            pipelineconfig_utils.get_core_python_path_for_config(config_root),
            os.path.join(config_root, "install", "core", "python"),
        )

        self.assertEqual(
            pipelineconfig_utils.get_core_path_for_config(config_root), config_root
        )

        unlocalized_core_root = self._create_studio_core("unlocalized_core")

        config_root = self._create_pipeline_configuration(
            "config_without_core", core_location=unlocalized_core_root
        )

        self.assertEqual(
            pipelineconfig_utils.get_core_python_path_for_config(config_root),
            os.path.join(unlocalized_core_root, "install", "core", "python"),
        )

        self.assertEqual(
            pipelineconfig_utils.get_core_path_for_config(config_root),
            unlocalized_core_root,
        )

    def test_shared_config_interpreter_file(self):
        """
        Test for interpreter file in a non-localized config.
        """

        # Shared config with valid core.
        valid_studio_core = self._create_studio_core("valid_studio_core")

        self._create_interpreter_file(valid_studio_core, sys.executable)
        self.assertEqual(
            pipelineconfig_utils.get_python_interpreter_for_config(
                self._create_pipeline_configuration(
                    "config_with_valid_studio_core", core_location=valid_studio_core
                )
            ),
            sys.executable,
        )

        # Test shared config with a bad interpreter location.
        studio_core_with_bad_interpreter_location = self._create_studio_core(
            "studio_core_with_bad_interpreter"
        )

        self._create_interpreter_file(
            studio_core_with_bad_interpreter_location, "/path/to/missing/python"
        )
        with self.assertRaises(TankInvalidInterpreterLocationError):
            pipelineconfig_utils.get_python_interpreter_for_config(
                self._create_pipeline_configuration(
                    "config_using_studio_core_with_bad_interpreter",
                    core_location=studio_core_with_bad_interpreter_location,
                )
            )

        # Test shared config with missing interpreter file.
        studio_core_with_missing_interpreter_file_location = self._create_studio_core(
            "studio_core_with_missing_interpreter_file"
        )
        with self.assertRaisesRegex(
            TankFileDoesNotExistError, "No interpreter file for"
        ):
            pipelineconfig_utils.get_python_interpreter_for_config(
                self._create_pipeline_configuration(
                    "config_using_studio_core_with_missing_interpreter_file",
                    core_location=studio_core_with_missing_interpreter_file_location,
                )
            )

        # Test with a core location that is invalid.
        config_with_invalid_core_location = self._create_unlocalized_pipeline_configuration(
            "config_with_invalid_core"
        )

        self._create_core_file(
            config_with_invalid_core_location, "/path/to/missing/core"
        )

        with self.assertRaises(TankInvalidCoreLocationError):
            pipelineconfig_utils.get_python_interpreter_for_config(
                config_with_invalid_core_location
            )

        # Test when the core file is missing.
        config_with_no_core_file_location = self._create_unlocalized_pipeline_configuration(
            "config_with_no_core_file"
        )

        with self.assertRaisesRegex(
            TankFileDoesNotExistError, "is missing a core location file"
        ):
            pipelineconfig_utils.get_python_interpreter_for_config(
                config_with_no_core_file_location
            )

    def test_missing_core_location_file(self):
        """
        Ensure we detect missing core location file.
        """
        config_root = self._create_unlocalized_pipeline_configuration(
            "missing_core_location_file"
        )

        self.assertIsNone(
            pipelineconfig_utils.get_core_path_for_config(config_root), None
        )

        with self.assertRaisesRegex(
            TankFileDoesNotExistError, "without a localized core is missing a core"
        ):
            pipelineconfig_utils.get_python_interpreter_for_config(config_root)

    def test_get_sgtk_module_path(self):
        """
        Ensures that the current core knows its place.
        """
        source = inspect.getsourcefile(self.test_get_sgtk_module_path)
        core_tests_folder = os.path.dirname(source)
        tests_folder = os.path.dirname(core_tests_folder)
        core_folder = os.path.dirname(tests_folder)
        python_path = os.path.join(core_folder, "python")

        import sgtk
        import tank

        self.assertEqual(sgtk.get_sgtk_module_path(), python_path)
        self.assertEqual(sgtk.get_sgtk_module_path(), tank.get_sgtk_module_path())


class TestGetCurrentlyRunningApiVersion(ShotgunTestBase):
    """
    Tests get_currently_running_api_version, including the importlib.metadata
    fallback used when info.yml is absent (e.g. flat pip install layout).
    """

    @mock.patch("tank.pipelineconfig_utils._get_version_from_manifest")
    def test_returns_manifest_version_when_present(self, manifest_mock):
        """
        When info.yml is present, its version is returned and the dist-metadata
        fallback is not consulted.
        """
        manifest_mock.return_value = "v1.2.3"
        with mock.patch("importlib.metadata.version") as dist_mock:
            self.assertEqual(
                pipelineconfig_utils.get_currently_running_api_version(),
                "v1.2.3",
            )
            dist_mock.assert_not_called()

    @mock.patch("tank.pipelineconfig_utils._get_version_from_manifest")
    def test_falls_back_to_dist_metadata_when_manifest_missing(self, manifest_mock):
        """
        Pip install layout: info.yml is absent so the manifest yields None,
        and the function falls back to the installed sgtk distribution version,
        re-adding the 'v' prefix that PEP 440 normalization strips.
        """
        manifest_mock.return_value = None
        with mock.patch(
            "importlib.metadata.version", return_value="0.23.8"
        ) as dist_mock:
            self.assertEqual(
                pipelineconfig_utils.get_currently_running_api_version(),
                "v0.23.8",
            )
            dist_mock.assert_called_once_with("sgtk")

    @mock.patch("tank.pipelineconfig_utils._get_version_from_manifest")
    def test_returns_unknown_when_manifest_and_dist_metadata_missing(
        self, manifest_mock
    ):
        """
        Neither info.yml nor an installed sgtk distribution available: preserve
        the original "unknown" contract instead of raising.
        """
        manifest_mock.return_value = None
        with mock.patch(
            "importlib.metadata.version",
            side_effect=importlib.metadata.PackageNotFoundError("sgtk"),
        ):
            self.assertEqual(
                pipelineconfig_utils.get_currently_running_api_version(),
                "unknown",
            )


class TestGetCoreApiVersion(ShotgunTestBase):
    """
    Tests get_core_api_version, including the distribution-metadata fallback
    used when the requested core is the currently-running one and info.yml is
    absent (e.g. flat pip install layout).
    """

    @mock.patch("tank.pipelineconfig_utils._get_version_from_manifest")
    def test_returns_manifest_version_when_present(self, manifest_mock):
        """
        When info.yml is present, its version is returned and no fallback runs.
        """
        manifest_mock.return_value = "v1.2.3"
        with mock.patch(
            "tank.pipelineconfig_utils.get_path_to_current_core"
        ) as path_mock:
            self.assertEqual(
                pipelineconfig_utils.get_core_api_version("/some/core/root"),
                "v1.2.3",
            )
            path_mock.assert_not_called()

    @mock.patch("tank.pipelineconfig_utils._get_version_from_manifest")
    def test_returns_unknown_for_other_core_when_manifest_missing(
        self, manifest_mock
    ):
        """
        When info.yml is absent and the requested core is not the currently-running
        one, distribution metadata must not leak in as the answer.
        """
        manifest_mock.return_value = None
        with mock.patch(
            "tank.pipelineconfig_utils.get_path_to_current_core",
            return_value="/different/core",
        ):
            with mock.patch("importlib.metadata.version") as dist_mock:
                self.assertEqual(
                    pipelineconfig_utils.get_core_api_version("/some/core/root"),
                    "unknown",
                )
                dist_mock.assert_not_called()

    @mock.patch("tank.pipelineconfig_utils._get_version_from_manifest")
    def test_falls_back_to_dist_metadata_for_current_core(self, manifest_mock):
        """
        Pip install layout: info.yml is absent and the requested core matches the
        currently-running one, so the function defers to dist-metadata via
        get_currently_running_api_version.
        """
        manifest_mock.return_value = None
        with mock.patch(
            "tank.pipelineconfig_utils.get_path_to_current_core",
            return_value="/some/core/root",
        ):
            with mock.patch(
                "importlib.metadata.version", return_value="0.23.8"
            ) as dist_mock:
                self.assertEqual(
                    pipelineconfig_utils.get_core_api_version("/some/core/root"),
                    "v0.23.8",
                )
                dist_mock.assert_called_once_with("sgtk")

    @mock.patch("tank.pipelineconfig_utils._get_version_from_manifest")
    def test_returns_unknown_when_current_core_resolution_fails(
        self, manifest_mock
    ):
        """
        If get_path_to_current_core raises (e.g. moved/symlinked install), the
        function preserves the "unknown" contract rather than propagating.
        """
        manifest_mock.return_value = None
        with mock.patch(
            "tank.pipelineconfig_utils.get_path_to_current_core",
            side_effect=tank.TankError("unresolvable"),
        ):
            self.assertEqual(
                pipelineconfig_utils.get_core_api_version("/some/core/root"),
                "unknown",
            )
