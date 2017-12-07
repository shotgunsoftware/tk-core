# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from __future__ import with_statement

import contextlib
import os
import sys

from tank_test.tank_test_base import setUpModule # noqa
from tank_test.tank_test_base import TankTestBase

import sgtk
from sgtk.bootstrap.configuration_writer import ConfigurationWriter
from sgtk.util import ShotgunPath
from tank_vendor import yaml
from mock import patch


class TestConfigurationWriterBase(TankTestBase):

    def _write_mock_config(self, shotgun_yml_data=None):
        """
        Creates a fake config with the provided shotgun.yml data.
        """
        mock_config_root = os.path.join(self.tank_temp, "template", self.id())
        # Make sure the bundle "exists" on disk.
        os.makedirs(mock_config_root)

        if shotgun_yml_data:
            self.create_file(
                os.path.join(mock_config_root, "core", "shotgun.yml"),
                yaml.dump(shotgun_yml_data)
            )

        return sgtk.descriptor.create_descriptor(
            self.mockgun,
            sgtk.descriptor.Descriptor.CONFIG,
            dict(type="dev", path=mock_config_root)
        )

    def _create_configuration_writer(self):
        """
        Creates a configuration writer that will write to a unique folder for this test.
        """
        new_config_root = os.path.join(self.tank_temp, "new_configuration", self.id())
        shotgun_yml_root = os.path.join(new_config_root, "config", "core")
        # Ensures the location for the shotgun.yml exists.
        os.makedirs(shotgun_yml_root)

        writer = ConfigurationWriter(
            ShotgunPath.from_current_os_path(new_config_root),
            self.mockgun
        )
        writer.ensure_project_scaffold()
        return writer


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
        shotgun_yml_path = os.path.join(cw.path.current_os, "config", "core", "shotgun.yml")
        self.assertTrue(os.path.exists(shotgun_yml_path))
        with open(shotgun_yml_path, "rb") as fh:
            return yaml.load(fh)

    def test_no_template_generate_new_file(self):
        """
        Ensures that writing out a configuration without a shotgun.yml yields
        the default shotgun.yml file.
        """
        descriptor = self._write_mock_config(None)
        cw = self._create_configuration_writer()
        cw.write_shotgun_file(descriptor)
        self.assertEqual(
            self._get_shotgun_yml_content(cw),
            {
                "host": self.mockgun.base_url
            }
        )

    def test_with_template_transfers_metadata(self):
        """
        Ensures that any setting found in the config's shotgun.yml will be
        carried over to the new file.
        """
        shotgun_yml_template = {
            "app_store_http_proxy": "1.2.3.4",
            "some_unknown_information": "1234"
        }
        descriptor = self._write_mock_config(shotgun_yml_template)
        cw = self._create_configuration_writer()
        cw.write_shotgun_file(descriptor)

        shotgun_yml_actual = self._get_shotgun_yml_content(cw)

        # Ensures host has been added.
        self.assertEqual(len(shotgun_yml_template) + 1, len(shotgun_yml_actual))
        self.assertIn("host", shotgun_yml_actual)
        self.assertEqual(shotgun_yml_actual["host"], self.mockgun.base_url)

        # Remove the host which was added and compare the rest with the template.
        # Everything else should be in there intact.
        del shotgun_yml_actual["host"]
        self.assertDictEqual(shotgun_yml_template, shotgun_yml_actual)


class TestInterpreterFilesWriter(TestConfigurationWriterBase):
    """
    Ensures interpreter files are written out correctly.
    """

    def setUp(self):
        # Makes sure every unit test run in its own sandbox.
        super(TestInterpreterFilesWriter, self).setUp()
        self._root = os.path.join(self.tank_temp, self.id())
        os.makedirs(self._root)
        self._cw = ConfigurationWriter(
            ShotgunPath.from_current_os_path(self._root),
            self.mockgun
        )

    def _get_default_intepreters(self):
        """
        Gets the default interpreter values for the Shotgun Desktop.
        """
        return ShotgunPath(
            r"C:\Program Files\Shotgun\Python\python.exe",
            "/opt/Shotgun/Python/bin/python",
            "/Applications/Shotgun.app/Contents/Resources/Python/bin/python"
        )

    def test_existing_files_not_overwritten(self):
        """
        Ensures that if there were already interpreter files present in the config that they won't be overwritten.
        """
        descriptor = self._write_mock_config()

        interpreter_yml_path = ShotgunPath.get_file_name_from_template(
            os.path.join(descriptor.get_path(), "core", "interpreter_%s.cfg")
        )
        # Do not write sys.executable in this file, otherwise we won't know if we're reading our value
        # or the default value. This means however that we'll have to present the file exists when
        # os.path.exists is called.
        os.makedirs(os.path.dirname(interpreter_yml_path))
        path = os.path.join("a", "b", "c")
        with open(interpreter_yml_path, "w") as fh:
            fh.write(path)

        # We're going to pretend the interpreter location exists
        with patch("os.path.exists", return_value=True):
            # Check that our descriptors sees the value we just wrote to disk
            self.assertEqual(
                descriptor.python_interpreter,
                path
            )
        # Copy the descriptor to its location.
        descriptor.copy(os.path.join(self._cw.path.current_os, "config"))

        # have the interpreter files be written out by the writer. The interpreter file we just
        # wrote should have been left alone.
        self.assertEqual(
            self._write_interpreter_file().current_os, path
        )

    def test_desktop_interpreter(self):
        """
        Checks that if we're running in the Shotgun Desktop we're writing the correct interpreter.
        """
        expected_interpreters = self._get_default_intepreters()
        if sys.platform == "win32":
            sys_prefix = r"C:\Program Files\Shotgun.v1.4.3\Python"
            sys_executable = r"C:\Program Files\Shotgun_v1.4.3\Shotgun.exe"
            python_exe = os.path.join(sys_prefix, "python.exe")
        elif sys.platform == "darwin":
            sys_prefix = "/Applications/Shotgun.v1.4.3.app/Contents/Resources/Python"
            sys_executable = "/Applications/Shotgun.v1.4.3.app/Contents/MacOS/Shotgun"
            python_exe = os.path.join(sys_prefix, "bin", "python")
        else:
            sys_prefix = "/opt/Shotgun.v.1.4.3/Python"
            sys_executable = "/opt/Shotgun.v.1.4.3/Shotgun"
            python_exe = os.path.join(sys_prefix, "bin", "python")

        expected_interpreters.current_os = python_exe

        interpreters = self._write_interpreter_file(sys_executable, sys_prefix)

        self.assertEqual(interpreters, expected_interpreters)

    def test_python_interpreter(self):
        """
        Checks that if we're running inside a real interpreter we reuse it.
        """
        expected_interpreters = self._get_default_intepreters()
        expected_interpreters.current_os = sys.executable

        interpreters = self._write_interpreter_file(sys.executable, sys.prefix)
        self.assertEqual(interpreters, expected_interpreters)

    def test_unknown_interpreter(self):
        """
        Checks that we default to the default desktop locations when we can't guess the interpreter location.
        """
        interpreters = self._write_interpreter_file(r"C:\Program Files\Autodesk\Maya2017\bin\maya.exe", r"C:\whatever")
        self.assertEqual(interpreters, self._get_default_intepreters())

    def _write_interpreter_file(self, executable=sys.executable, prefix=sys.prefix):
        """
        Writes the interpreter file to disk based on an executable and prefix.

        :returns: Path that was written in each interpreter file.
        :rtype: sgtk.util.ShotgunPath
        """
        core_folder = os.path.join(self._root, "config", "core")
        if not os.path.exists(core_folder):
            os.makedirs(core_folder)
        os.makedirs(os.path.join(self._root, "install", "core", "setup", "root_binaries"))

        self._cw.create_tank_command(executable, prefix)

        interpreters = []
        for platform in ["Windows", "Linux", "Darwin"]:
            file_name = os.path.join(self._root, "config", "core", "interpreter_%s.cfg" % platform)

            with open(file_name, "r") as w:
                interpreters.append(w.read())

        return ShotgunPath(*interpreters)


class TestWritePipelineConfigFile(TankTestBase):

    FALLBACK_PATHS = ["/bundle/cache", "/fallback/paths"]

    def _create_test_data(self, create_project):
        """
        Creates test data, including
            - __pipeline_configuration, a shotgun entity dict.
            - optional __project entity dict, linked from the pipeline configuration
            - __descriptor, a sgtk.descriptor.Descriptor refering to a config on disk.
            - __cw, a ConfigurationWriter
        """

        if create_project:
            self.__project = self.mockgun.create(
                "Project",
                {
                    "code": "TestWritePipelineConfigFile",
                    "tank_name": "pc_tank_name"
                }
            )
        else:
            self.__project = None

        self.__pipeline_configuration = self.mockgun.create(
            "PipelineConfiguration",
            {
                "code": "PC_TestWritePipelineConfigFile",
                "project": self.__project
            }
        )

        self.__descriptor = sgtk.descriptor.create_descriptor(
            self.mockgun,
            sgtk.descriptor.Descriptor.CONFIG,
            dict(type="dev", path="/a/b/c")
        )

        config_root = os.path.join(self.tank_temp, self.id())

        self.__cw = ConfigurationWriter(
            ShotgunPath.from_current_os_path(config_root),
            self.mockgun
        )
        os.makedirs(
            os.path.join(
                config_root,
                "config",
                "core"
            )
        )

    def test_write_site_config(self):
        """
        Expects site configurations are written out properly.
        """
        self._create_test_data(create_project=False)

        path = self.__cw.write_pipeline_config_file(
            None,
            None,
            "basic.plugin",
            self.FALLBACK_PATHS,
            self.__descriptor
        )

        with open(path, "r") as fh:
            config_info = yaml.safe_load(fh)

        self.assertDictEqual(
            config_info,
            {
                "pc_id": None,
                "pc_name": "Unmanaged",
                "project_id": None,
                "project_name": "Site",
                "plugin_id": "basic.plugin",
                "published_file_entity_type": "PublishedFile",
                "use_bundle_cache": True,
                "bundle_cache_fallback_roots": self.FALLBACK_PATHS,
                "use_shotgun_path_cache": True,
                "source_descriptor": self.__descriptor.get_dict()
            }
        )

    def test_write_site_sandbox_config(self):
        """
        Expects site configuration sanboxes are written out properly.
        """
        self._create_test_data(create_project=False)

        with self._fixme_find_one():
            path = self.__cw.write_pipeline_config_file(
                self.__pipeline_configuration["id"],
                None,
                "basic.plugin",
                self.FALLBACK_PATHS,
                self.__descriptor
            )

        with open(path, "r") as fh:
            config_info = yaml.safe_load(fh)

        self.assertDictEqual(
            config_info,
            {
                "pc_id": self.__pipeline_configuration["id"],
                "pc_name": self.__pipeline_configuration["code"],
                "project_id": None,
                "project_name": "unnamed",
                "plugin_id": "basic.plugin",
                "published_file_entity_type": "PublishedFile",
                "use_bundle_cache": True,
                "bundle_cache_fallback_roots": self.FALLBACK_PATHS,
                "use_shotgun_path_cache": True,
                "source_descriptor": self.__descriptor.get_dict()
            }
        )

    def test_write_project_config(self):
        """
        Expects project configurations are written out properly.
        """
        self._create_test_data(create_project=True)

        path = self.__cw.write_pipeline_config_file(
            None,
            self.__project["id"],
            "basic.plugin",
            self.FALLBACK_PATHS,
            self.__descriptor
        )

        with open(path, "r") as fh:
            config_info = yaml.safe_load(fh)

        self.assertDictEqual(
            config_info,
            {
                "pc_id": None,
                "pc_name": "Unmanaged",
                "project_id": self.__project["id"],
                "project_name": "pc_tank_name",
                "plugin_id": "basic.plugin",
                "published_file_entity_type": "PublishedFile",
                "use_bundle_cache": True,
                "bundle_cache_fallback_roots": self.FALLBACK_PATHS,
                "use_shotgun_path_cache": True,
                "source_descriptor": self.__descriptor.get_dict()
            }
        )

    @contextlib.contextmanager
    def _fixme_find_one(self):
        """
        Workaround for a bug in Mockgun.
        """
        # FIXME: There's a bug in Mockgun when a linked field is set to None. A client fixed this
        # bug, we're only waiting for the PR to be merged.
        with patch("tank_vendor.shotgun_api3.lib.mockgun.mockgun.Shotgun.find_one") as p:
            def mocked_find_one(entity_type, filters, *args):
                # Make sure we're being queried for the pipeline configuration we are expecting.
                self.assertEqual(entity_type, "PipelineConfiguration")
                self.assertEqual(
                    filters, [["id", "is", self.__pipeline_configuration["id"]]]
                )
                # Make sure we are mocking the call for the project which is None.
                self.assertIsNone(self.__pipeline_configuration["project"])
                result = {
                    "project.Project.tank_name": None
                }
                result.update(self.__pipeline_configuration)
                return result

            p.side_effect = mocked_find_one
            yield

    def test_write_project_sandbox_config(self):
        """
        Expects project configuration sandboxes are written out properly.
        """
        self._create_test_data(create_project=True)
        path = self.__cw.write_pipeline_config_file(
            self.__pipeline_configuration["id"],
            self.__project["id"],
            "basic.plugin",
            self.FALLBACK_PATHS,
            self.__descriptor
        )

        with open(path, "r") as fh:
            config_info = yaml.safe_load(fh)

        self.assertDictEqual(
            config_info,
            {
                "pc_id": self.__pipeline_configuration["id"],
                "pc_name": self.__pipeline_configuration["code"],
                "project_id": self.__project["id"],
                "project_name": self.__project["tank_name"],
                "plugin_id": "basic.plugin",
                "published_file_entity_type": "PublishedFile",
                "use_bundle_cache": True,
                "bundle_cache_fallback_roots": self.FALLBACK_PATHS,
                "use_shotgun_path_cache": True,
                "source_descriptor": self.__descriptor.get_dict()
            }
        )


class TestTransaction(TankTestBase):

    def test_transactions(self):
        """
        Ensures the transaction flags are properly handled for a config.
        """
        new_config_root = os.path.join(self.tank_temp, self.id())

        writer = ConfigurationWriter(
            ShotgunPath.from_current_os_path(new_config_root),
            self.mockgun
        )

        # Test standard transaction flow.
        # Non pending -> Pending -> Non pending
        self.assertEqual(False, writer.is_transaction_pending())
        writer.start_transaction()
        self.assertEqual(True, writer.is_transaction_pending())
        writer.end_transaction()
        self.assertEqual(False, writer.is_transaction_pending())

        # Remove the transaction folder
        writer._delete_state_file(writer._TRANSACTION_START_FILE)
        writer._delete_state_file(writer._TRANSACTION_END_FILE)
        # Even if the marker is missing, the API should report no pending transactions since the
        # transaction folder doesn't even exist, which will happen for configurations written
        # with a previous version of core.
        self.assertEqual(False, writer.is_transaction_pending())

        # We've deleted both the transaction files and now we're writing the end transaction file.
        # If we're in that state, we'll assume something is broken and say its pending since the
        # config was tinkered with.
        writer.end_transaction()
        self.assertEqual(True, writer.is_transaction_pending())
