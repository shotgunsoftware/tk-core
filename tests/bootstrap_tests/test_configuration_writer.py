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

import os

from mock import patch, Mock

from tank_test.tank_test_base import setUpModule # noqa
from tank_test.tank_test_base import TankTestBase

import sgtk
from sgtk.bootstrap.configuration_writer import ConfigurationWriter
from sgtk.util import ShotgunPath
from tank_vendor import yaml


class TestShotgunYmlWriting(TankTestBase):
    """
    Makes sure zero-config based pipelines end up with a valid shotgun.yml file.
    """

    def _write_mock_config(self, shotgun_yml_data):
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

        return ConfigurationWriter(
            ShotgunPath.from_current_os_path(new_config_root),
            self.mockgun
        )

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
