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

import sgtk

from tank import pipelineconfig_utils
from tank import (
    TankError,
    TankInvalidInterpreterLocationError,
    TankFileDoesNotExistError,
    TankInvalidCoreLocationError,
    TankNotPipelineConfigurationError
)

from tank_test.tank_test_base import TankTestBase
from tank_test.tank_test_base import setUpModule # noqa


class TestPipelineConfigUtils(TankTestBase):
    """
    Tests pipeline configuration utilities.
    """

    def _get_current_platform_file_suffix(self):
        """
        Find the suffix for the current platform's configuration file.

        :returns: Suffix for the current platform's configuration file.
        :rtype: str
        """
        # Now find out the appropriate python interpreter file to search for
        if sys.platform == "darwin":
            return "Darwin"
        elif sys.platform == "win32":
            return "Windows"
        elif sys.platform.startswith("linux"):
            return "Linux"
        else:
            raise TankError("Unknown platform: %s." % sys.platform)

    def _create_interpreter_file(self, config_root, path):
        """
        Creates an interpreter file in a configuration.

        :param str config_root_name: Path to the configuration root.
        :param str path: Path to write in the interpreter file.
        """
        self.create_file(
            os.path.join(
                config_root, "config", "core",
                "interpreter_%s.cfg" % self._get_current_platform_file_suffix()
            ),
            path
        )

    def _create_core_file(self, config_root, path):
        """
        Creates a core file in a configuration.

        :param str config_root_name: Path to the configuration root.
        :param str path: Path to write in the interpreter file.
        """
        self.create_file(
            os.path.join(
                config_root, "install", "core",
                "core_%s.cfg" % self._get_current_platform_file_suffix()
            ),
            path
        )

    def _create_core(self, core_root):
        self.create_file(
            os.path.join(core_root, "install", "core", "_core_upgrader.py"),
            "" # Content is unimportant.
        )
        return core_root

    def _create_studio_core(self, core_name):
        core_root = os.path.join(self.tank_temp, core_name)
        return self._create_core(core_root)

    def _create_unlocalized_pipeline_configuration(self, config_name):
        config_root = os.path.join(self.tank_temp, config_name)
        self.create_file(
            os.path.join(config_root, "config", "core", "roots.yml"),
            "{}" # We don't care for the content of that file
        )
        return config_root

    def _create_pipeline_configuration(self, config_name, core_location=None):
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
        self._create_interpreter_file(config_root_with_bad_interpreter, "/path/to/non/existing/python")

        # Test when the interpreter file is present and has a valid python interpreter.
        self.assertEqual(
            pipelineconfig_utils.get_python_interpreter_for_config(config_root), sys.executable
        )

        # Test when the interpreter file is present but the interpreter path is bad.
        with self.assertRaises(TankInvalidInterpreterLocationError):
            pipelineconfig_utils.get_python_interpreter_for_config(config_root_with_bad_interpreter)

        # Test when the interpreter file is missing
        with self.assertRaisesRegexp(TankFileDoesNotExistError, "No interpreter file for"):
            pipelineconfig_utils.get_python_interpreter_for_config(config_root_without_interpreter_file)

    def test_core_location_retrieval(self):

        config_root = self._create_pipeline_configuration(
            "localized_core"
        )

        self.assertEqual(
            pipelineconfig_utils.get_core_python_path_for_config(config_root),
            os.path.join(config_root, "install", "core", "python")
        )

        self.assertEqual(
            pipelineconfig_utils.get_core_path_for_config(config_root),
            config_root
        )

        unlocalized_core_root = self._create_studio_core("unlocalized_core")

        config_root = self._create_pipeline_configuration(
            "config_without_core",
            core_location=unlocalized_core_root
        )

        self.assertEqual(
            pipelineconfig_utils.get_core_python_path_for_config(config_root),
            os.path.join(unlocalized_core_root, "install", "core", "python")
        )

        self.assertEqual(
            pipelineconfig_utils.get_core_path_for_config(config_root),
            unlocalized_core_root
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
                    "config_with_valid_studio_core",
                    core_location=valid_studio_core
                )
            ),
            sys.executable
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
                    core_location=studio_core_with_bad_interpreter_location
                )
            )

        # Test shared config with missing interpreter file.
        studio_core_with_missing_interpreter_file_location = self._create_studio_core(
            "studio_core_with_missing_interpreter_file"
        )
        with self.assertRaisesRegexp(TankFileDoesNotExistError, "No interpreter file for"):
            pipelineconfig_utils.get_python_interpreter_for_config(
                self._create_pipeline_configuration(
                    "config_using_studio_core_with_missing_interpreter_file",
                    core_location=studio_core_with_missing_interpreter_file_location
                )
            )

        # Test with a core location that is invalid.
        config_with_invalid_core_location = self._create_unlocalized_pipeline_configuration(
            "config_with_invalid_core"
        )

        self._create_core_file(config_with_invalid_core_location, "/path/to/missing/core")

        with self.assertRaises(TankInvalidCoreLocationError):
            pipelineconfig_utils.get_python_interpreter_for_config(config_with_invalid_core_location)

        # Test when the core file is missing.
        config_with_no_core_file_location = self._create_unlocalized_pipeline_configuration(
            "config_with_no_core_file"
        )

        with self.assertRaisesRegexp(TankFileDoesNotExistError, "is missing a core location file"):
            pipelineconfig_utils.get_python_interpreter_for_config(config_with_no_core_file_location)
