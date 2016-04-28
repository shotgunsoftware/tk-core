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
import sgtk

from tank_test.tank_test_base import *
from tank.errors import TankError

class TestLegacyDescriptorSupport(TankTestBase):

    def setUp(self, parameters=None):

        super(TestLegacyDescriptorSupport, self).setUp()

        self.install_root = os.path.join(
            self.tk.pipeline_configuration.get_install_location(),
            "install"
        )

    def _create_info_yaml(self, path):
        """
        create a mock info.yml
        """
        sgtk.util.filesystem.ensure_folder_exists(path)
        fh = open(os.path.join(path, "info.yml"), "wt")
        fh.write("foo")
        fh.close()

    def test_get_from_location_and_paths(self):
        """
        Tests legacy method get_from_location_and_paths
        """

        location = {"type": "app_store", "version": "v0.1.2", "name": "tk-bundle"}
        path = os.path.join(self.install_root, "app_store", "tk-bundle", "v0.1.2")
        self._create_info_yaml(path)

        from sgtk.deploy import descriptor

        d = descriptor.get_from_location_and_paths(
            descriptor.AppDescriptor.APP,
            "dummy_value",
            self.install_root,
            location,
        )

        self.assertEqual(d.get_path(), path)
        self.assertEqual(d.__class__, sgtk.descriptor.AppDescriptor)


