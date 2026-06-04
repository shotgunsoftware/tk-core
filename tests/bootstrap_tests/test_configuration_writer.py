# Copyright (c) 2017 Shotgun Software Inc.
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

from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import (
    mock,
    ShotgunTestBase,
)

import sgtk
from sgtk.bootstrap.configuration_writer import ConfigurationWriter
from sgtk.util import ShotgunPath
from tank.util import is_macos, is_windows
from tank_vendor import yaml


class TestConfigurationWriterBase(ShotgunTestBase):
    def _write_mock_config(self, shotgun_yml_data=None):
        """
        Creates a fake config with the provided shotgun.yml data.
        """
        # Make the file name not too long or we'll run into file length issues on Windows.
        mock_config_root = os.path.join(
            self.tank_temp, "template", "%s" % self.short_test_name
        )
        # Make sure the bundle "exists" on disk.
        os.makedirs(mock_config_root)

        if shotgun_yml_data:
            self.create_file(
                os.path.join(mock_config_root, "core", "shotgun.yml"),
                yaml.dump(shotgun_yml_data),
            )

        return sgtk.descriptor.create_descriptor(
            self.mockgun,
            sgtk.descriptor.Descriptor.CONFIG,
            dict(type="dev", path=mock_config_root),
        )

    def _create_configuration_writer(self):
        """
        Creates a configuration writer that will write to a unique folder for this test.
        """
        new_config_root = os.path.join(
            self.tank_temp, "new_configuration", self.short_test_name
        )
        shotgun_yml_root = os.path.join(new_config_root, "config", "core")
        # Ensures the location for the shotgun.yml exists.
        os.makedirs(shotgun_yml_root)

        writer = ConfigurationWriter(
            ShotgunPath.from_current_os_path(new_config_root), self.mockgun
        )
        writer.ensure_project_scaffold()
        return writer


class TestCoreInstallation(TestConfigurationWriterBase):
    def test_core_install_with_skip_list(self):
        pass
class TestShotgunYmlWriting(TestConfigurationWriterBase):
    """
    Makes sure zero-config based pipelines end up with a valid shotgun.yml file.
    """

    def _get_shotgun_yml_content(self, cw):
        """
        Retrieves the content of the shotgun.yml file based on the configuration writer passed in.

        :param cw: Configuration writer used to write the shotgun.yml file.

        :returns: Path to the Shotgun file.
        """
        shotgun_yml_path = os.path.join(
            cw.path.current_os, "config", "core", "shotgun.yml"
        )
        self.assertTrue(os.path.exists(shotgun_yml_path))
        with open(shotgun_yml_path, "rb") as fh:
            return yaml.load(fh, Loader=yaml.FullLoader)

    def test_no_template_generate_new_file(self):
        pass
    def test_with_template_transfers_metadata(self):
        pass
class TestInterpreterFilesWriter(TestConfigurationWriterBase):
    """
    Ensures interpreter files are written out correctly.
    """

    def setUp(self):
        # Makes sure every unit test run in its own sandbox.
        super().setUp()
        self._root = os.path.join(self.tank_temp, self.short_test_name)
        os.makedirs(self._root)
        self._cw = ConfigurationWriter(
            ShotgunPath.from_current_os_path(self._root), self.mockgun
        )

    def _get_default_intepreters(self):
        """
        Gets the default interpreter values for the Shotgun Desktop.
        """
        return ShotgunPath(
            r"C:\Program Files\Shotgun\Python\python.exe",
            "/opt/Shotgun/Python/bin/python",
            "/Applications/Shotgun.app/Contents/Resources/Python/bin/python",
        )

    def test_existing_files_not_overwritten(self):
        pass
    def test_desktop_interpreter(self):
        pass
    def test_python_interpreter(self):
        pass
    def test_unknown_interpreter(self):
        pass
    def _write_interpreter_file(self, executable=sys.executable, prefix=sys.prefix):
        """
        Writes the interpreter file to disk based on an executable and prefix.

        :returns: Path that was written in each interpreter file.
        :rtype: sgtk.util.ShotgunPath
        """
        core_folder = os.path.join(self._root, "config", "core")
        if not os.path.exists(core_folder):
            os.makedirs(core_folder)
        os.makedirs(
            os.path.join(self._root, "install", "core", "setup", "root_binaries")
        )

        self._cw.create_tank_command(executable, prefix)

        interpreters = []
        for platform in ["Windows", "Linux", "Darwin"]:
            file_name = os.path.join(
                self._root, "config", "core", "interpreter_%s.cfg" % platform
            )

            with open(file_name, "r") as w:
                interpreters.append(w.read())

        return ShotgunPath(*interpreters)


class TestWritePipelineConfigFile(ShotgunTestBase):

    FALLBACK_PATHS = ["/bundle/cache", "/fallback/paths"]

    def _create_test_data(self, create_project):
        """
        Creates test data, including
            - __site_configuration, a shotgun entity dict.
            - optional __project entity dict, linked from the pipeline configuration
            - __descriptor, a sgtk.descriptor.Descriptor refering to a config on disk.
            - __cw, a ConfigurationWriter
        """

        if create_project:
            self.__project = self.mockgun.create(
                "Project",
                {"name": "TestWritePipelineConfigFile", "tank_name": "pc_tank_name"},
            )
        else:
            self.__project = None

        self.__site_configuration = self.mockgun.create(
            "PipelineConfiguration",
            {"code": "PC_TestWritePipelineConfigFile", "project": None},
        )

        self.__project_configuration = self.mockgun.create(
            "PipelineConfiguration",
            {"code": "PC_TestWritePipelineConfigFile", "project": self.__project},
        )

        self.__descriptor = sgtk.descriptor.create_descriptor(
            self.mockgun,
            sgtk.descriptor.Descriptor.CONFIG,
            dict(type="dev", path="/a/b/c"),
        )

        config_root = os.path.join(self.tank_temp, self.short_test_name)

        self.__cw = ConfigurationWriter(
            ShotgunPath.from_current_os_path(config_root), self.mockgun
        )
        os.makedirs(os.path.join(config_root, "config", "core"))

    def test_write_site_config(self):
        pass
    def test_write_site_sandbox_config(self):
        pass
    def test_write_site_sandbox_config_using_project(self):
        pass
    def test_write_project_config(self):
        pass
    def test_write_project_sandbox_config(self):
        pass
class TestInstallationLocationFile(ShotgunTestBase):
    def test_character_escaping(self):
        pass
class TestTransaction(ShotgunTestBase):
    def test_transactions(self):
        pass
