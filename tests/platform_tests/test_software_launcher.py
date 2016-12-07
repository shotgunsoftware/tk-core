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
import shutil

from tank_test.tank_test_base import *
import tank

from tank.platform import create_engine_launcher
from tank.platform import SoftwareLauncher
from tank.platform import SoftwareVersion
from tank.platform import LaunchInformation

from tank.errors import TankEngineInitError

class TestEngineLauncher(TankTestBase):
    def setUp(self):
        super(TestEngineLauncher, self).setUp()
        self.setup_fixtures()

        # setup shot
        seq = {"type":"Sequence", "name":"seq_name", "id":3}
        seq_path = os.path.join(self.project_root, "sequences/Seq")
        self.add_production_path(seq_path, seq)

        shot = {"type":"Shot", "name": "shot_name", "id":2,
                "project": self.project}
        shot_path = os.path.join(seq_path, "shot_code")
        self.add_production_path(shot_path, shot)

        step = {"type":"Step", "name":"step_name", "id":4}
        self.shot_step_path = os.path.join(shot_path, "step_name")
        self.add_production_path(self.shot_step_path, step)

        self.context = self.tk.context_from_path(self.shot_step_path)
        self.engine_name = "test_engine"

    def test_create_launcher(self):
        """
        Makes sure a valid SoftwareLauncher instance gets created
        by the platform public factory method create_engine_launcher()
        """
        # Verify the create method raises TankEngineInitError for 
        # engines that cannot be found
        self.assertRaises(
            TankEngineInitError,
            create_engine_launcher,
            self.tk, self.context, "not an engine",
        )

        # Verify that engines without startup.py files will return None
        startup_plugin = os.path.join(
            self.pipeline_config_root, "config", "bundles", "test_engine", "startup.py"
        )
        if os.path.exists(startup_plugin):
            os.remove(startup_plugin)
        launcher = create_engine_launcher(self.tk, self.context, self.engine_name)
        self.assertEqual(launcher, None)

        # Verify valid input results in a valid SoftwareLauncher
        expected_disk_location = os.path.join(
            self.pipeline_config_root, "config", "bundles", "test_engine"
        )
        startup_copy = os.path.join(
            self.pipeline_config_root, "config", "bundles", "test_engine", "startup_copy.py"
        )
        
        shutil.copy(startup_copy, startup_plugin)
        launcher = create_engine_launcher(self.tk, self.context, self.engine_name)
        self.assertIsInstance(launcher, SoftwareLauncher)
        self.assertEqual(self.engine_name, launcher.engine_name)
        self.assertEqual(self.tk, launcher.sgtk)
        self.assertEqual(self.context, launcher.context)
        self.assertEqual("%s Startup" % self.engine_name, launcher.display_name)
        self.assertEqual(expected_disk_location, launcher.disk_location)


    def test_launcher_scan_software(self):
        launcher = create_engine_launcher(self.tk, self.context, self.engine_name)
        sw_versions = launcher.scan_software()
        self.assertEqual(sw_versions, [])

        scan_versions = [str(v) for v in range(10, 100, 20)]
        scan_display = "UT Display Name"
        scan_icon = "/some/path/to/a/ut/icon.png"
        sw_versions = launcher.scan_software(
            scan_versions, scan_display, scan_icon
        )
        self.assertIsInstance(sw_versions, list)
        for i, swv in enumerate(sw_versions):
            self.assertIsInstance(swv, SoftwareVersion)
            self.assertEqual(swv.version, scan_versions[i])
            self.assertEqual(swv.display_name, scan_display)
            self.assertEqual(swv.icon, scan_icon)


    def test_launcher_prepare_launch(self):
        prep_path = "/some/path/to/an/executable"
        prep_args = "-t 1-20 --show_all -v --select parts"
        open_file = "open_this_file.ext"
        startup_path = os.path.join(
            self.pipeline_config_root, "config", "bundles", "test_engine", "startup"
        )

        launcher = create_engine_launcher(self.tk, self.context, self.engine_name)
        launch_info = launcher.prepare_launch(prep_path, prep_args)
        self.assertIsInstance(launch_info, LaunchInformation)
        self.assertEqual(prep_path, launch_info.path)
        self.assertEqual(prep_args, launch_info.args)
        self.assertTrue("PYTHONPATH" in launch_info.environment)
        self.assertTrue(startup_path in launch_info.environment["PYTHONPATH"])
        self.assertFalse("FILE_TO_OPEN" in launch_info.environment)

        launch_info = launcher.prepare_launch(prep_path, prep_args, open_file)
        self.assertTrue("FILE_TO_OPEN" in launch_info.environment)
        self.assertTrue(open_file in launch_info.environment["FILE_TO_OPEN"])


class TestSoftwareVersion(TankTestBase):
    def setUp(self):
        super(TestSoftwareVersion, self).setUp()

        self._version = "v293.49.2.dev"
        self._display_name = "My Custom App {version}"
        self._path = "/my/path/to/app/{version}/my_custom_app"
        self._icon = "%s/icon.png" % self._path

    def test_init_software_version(self):
        sw_version = SoftwareVersion(
            self._version,
            self._display_name,
            self._path,
            self._icon,
        )

        self.assertEqual(self._version, sw_version.version)
        self.assertEqual(self._display_name, sw_version.display_name)
        self.assertEqual(self._path, sw_version.path)
        self.assertEqual(self._icon, sw_version.icon)


class TestLaunchInformation(TankTestBase):
    def setUp(self):
        super(TestLaunchInformation, self).setUp()

        self._path = "/my/path/to/app/{version}/my_custom_app"
        self._args = "-t 1-30 --show_all -v --select ship"
        self._environment = {
            "ENV_STR_KEY": "custom enviorment string value",
            "ENV_INT_KEY": 1001,
            "ENV_FLT_KEY": 3.1415,
        }

    def test_init_launch_information(self):
        launch_info = LaunchInformation(
            self._path,
            self._args,
            self._environment
        )

        self.assertEqual(self._path, launch_info.path)
        self.assertEqual(self._args, launch_info.args)
        self.assertEqual(self._environment, launch_info.environment)
