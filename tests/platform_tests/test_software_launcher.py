# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import logging
import os

from tank_test.tank_test_base import *
from mock import PropertyMock, patch
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
        seq = {"type": "Sequence", "name": "seq_name", "id": 3}
        seq_path = os.path.join(self.project_root, "sequences/Seq")
        self.add_production_path(seq_path, seq)

        self.shot = {"type": "Shot", "name": "shot_name", "id": 2, "project": self.project}
        shot_path = os.path.join(seq_path, "shot_code")
        self.add_production_path(shot_path, self.shot)

        self.step = {"type": "Step", "name": "step_name", "id": 4}
        self.shot_step_path = os.path.join(shot_path, "step_name")
        self.add_production_path(self.shot_step_path, self.step)

        self.context = self.tk.context_from_path(self.shot_step_path)
        self.engine_name = "test_engine"

        self.task = {"type": "Task",
                     "id": 23,
                     "entity": self.shot,
                     "step": self.step,
                     "project": self.project}

        entities = [self.task]

        # Add these to mocked shotgun
        self.add_to_sg_mock_db(entities)


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
        startup_copy = startup_plugin.replace("startup.py", "startup_copy.py")
        os.rename(startup_plugin, startup_copy)
        launcher = create_engine_launcher(self.tk, self.context, self.engine_name)
        self.assertEqual(launcher, None)

        # Verify valid input results in a valid SoftwareLauncher
        expected_disk_location = os.path.join(
            self.pipeline_config_root, "config", "bundles", "test_engine"
        )
        os.rename(startup_copy, startup_plugin)

        versions_list =[1, 2, 3, 4]
        products_list =["A", "B", "C"]

        launcher = create_engine_launcher(
            self.tk,
            self.context,
            self.engine_name,
            versions=versions_list,
            products=products_list
        )
        self.assertIsInstance(launcher, SoftwareLauncher)
        self.assertIsInstance(launcher.logger, logging.Logger)
        self.assertEqual(self.engine_name, launcher.engine_name)
        self.assertEqual(self.tk, launcher.sgtk)
        self.assertEqual(self.context, launcher.context)
        self.assertEqual(versions_list, launcher.versions)
        self.assertEqual(products_list, launcher.products)
        self.assertEqual("%s Startup" % self.engine_name, launcher.display_name)
        self.assertEqual(expected_disk_location, launcher.disk_location)

    def test_launcher_scan_software(self):

        # test engine launcher hardcoded to return 10 paths
        launcher = create_engine_launcher(self.tk, self.context, self.engine_name)
        sw_versions = launcher._scan_software()
        self.assertEqual(len(sw_versions), 10)

        launcher = create_engine_launcher(self.tk, self.context, self.engine_name)
        sw_versions = launcher._scan_software()
        self.assertIsInstance(sw_versions, list)
        for i, swv in enumerate(sw_versions):
            self.assertIsInstance(swv, SoftwareVersion)

    def test_get_standard_plugin_environment(self):

        for entity in [self.shot, self.project, self.task]:

            ctx = self.tk.context_from_entity(entity["type"], entity["id"])
            launcher = create_engine_launcher(self.tk, ctx, self.engine_name)
            env = launcher.get_standard_plugin_environment()
            self.assertEqual(env["SHOTGUN_PIPELINE_CONFIGURATION_ID"], "123")
            self.assertEqual(env["SHOTGUN_SITE"], "http://unit_test_mock_sg")
            self.assertEqual(env["SHOTGUN_ENTITY_TYPE"], entity["type"])
            self.assertEqual(env["SHOTGUN_ENTITY_ID"], str(entity["id"]))

    def test_get_standard_plugin_environment_empty(self):

        ctx = self.tk.context_empty()
        launcher = create_engine_launcher(self.tk, ctx, self.engine_name)
        env = launcher.get_standard_plugin_environment()
        self.assertEqual(env["SHOTGUN_PIPELINE_CONFIGURATION_ID"], "123")
        self.assertEqual(env["SHOTGUN_SITE"], "http://unit_test_mock_sg")
        self.assertTrue("SHOTGUN_ENTITY_TYPE" not in env)
        self.assertTrue("SHOTGUN_ENTITY_ID" not in env)

    def test_minimum_version(self):

        launcher = create_engine_launcher(self.tk, self.context, self.engine_name)

        # if no version has been set, anything goes
        self.assertEqual(launcher._is_version_supported("foo"), True)
        self.assertEqual(launcher._is_version_supported("v1204"), True)

        self.assertEqual(launcher.minimum_supported_version, None)

        # mock the property
        min_version_method = "sgtk.platform.software_launcher.SoftwareLauncher.minimum_supported_version"
        with patch(min_version_method, new_callable=PropertyMock) as min_version_mock:

            min_version_mock.return_value = "2017.2"

            self.assertEqual(launcher.minimum_supported_version, "2017.2")
            self.assertEqual(launcher._is_version_supported("2017"), False)
            self.assertEqual(launcher._is_version_supported("2017.2"), True)
            self.assertEqual(launcher._is_version_supported("2017.2.sp1"), True)
            self.assertEqual(launcher._is_version_supported("2017.2sp1"), True)
            self.assertEqual(launcher._is_version_supported("2017.3"), True)
            self.assertEqual(launcher._is_version_supported("2018"), True)
            self.assertEqual(launcher._is_version_supported("2018.1"), True)

            min_version_mock.return_value = "2017.2sp1"

            self.assertEqual(launcher.minimum_supported_version, "2017.2sp1")
            self.assertEqual(launcher._is_version_supported("2017"), False)
            self.assertEqual(launcher._is_version_supported("2017.2"), False)
            self.assertEqual(launcher._is_version_supported("2017.2sp1"), True)
            self.assertEqual(launcher._is_version_supported("2017.3"), True)
            self.assertEqual(launcher._is_version_supported("2018"), True)
            self.assertEqual(launcher._is_version_supported("2018.1"), True)

    def test_version_supported(self):

        launcher = create_engine_launcher(self.tk, self.context, self.engine_name)

        # all should pass since no version constraint
        self.assertEqual(launcher._is_version_supported("2017"), True)
        self.assertEqual(launcher._is_version_supported("2018"), True)
        self.assertEqual(launcher._is_version_supported("2019"), True)
        self.assertEqual(launcher._is_version_supported("2019v0"), True)
        self.assertEqual(launcher._is_version_supported("2019v0.1"), True)
        self.assertEqual(launcher._is_version_supported("2020.1"), True)
        self.assertEqual(launcher._is_version_supported("2020"), True)
        self.assertEqual(launcher._is_version_supported("v0.1.2"), True)
        self.assertEqual(launcher._is_version_supported("v0.1"), True)

        versions_list = [
            "2018",
            "2019v0.1",
            "2020.1",
            "v0.1.2"
        ]

        launcher = create_engine_launcher(self.tk, self.context, self.engine_name, versions=versions_list)

        min_version_method = "sgtk.platform.software_launcher.SoftwareLauncher.minimum_supported_version"
        with patch(min_version_method, new_callable=PropertyMock) as min_version_mock:

            min_version_mock.return_value = "2019"

            self.assertEqual(launcher._is_version_supported("2017"), False) # should fail min version
            self.assertEqual(launcher._is_version_supported("2018"), False) # should fail min version
            self.assertEqual(launcher._is_version_supported("2019"), False) # not in version list
            self.assertEqual(launcher._is_version_supported("2019v0"), False) # not in version list
            self.assertEqual(launcher._is_version_supported("2019v0.1"), True) # in version list
            self.assertEqual(launcher._is_version_supported("2020.1"), True) # in version list
            self.assertEqual(launcher._is_version_supported("2020"), False) # not in version list
            self.assertEqual(launcher._is_version_supported("v0.1.2"), False) # fails min version
            self.assertEqual(launcher._is_version_supported("v0.1"), False) # fails min version and not in list

    def test_product_supported(self):

        launcher = create_engine_launcher(self.tk, self.context, self.engine_name)

        # all should pass since no product constraing
        self.assertEqual(launcher._is_product_supported("asfasdfakj"), True)
        self.assertEqual(launcher._is_product_supported("asfa sdfakj"), True)
        self.assertEqual(launcher._is_product_supported("asfa sdf akj"), True)
        self.assertEqual(launcher._is_product_supported("asfas1 124 1231 dfakj"), True)
        self.assertEqual(launcher._is_product_supported("111 1 1asfasdfakj"), True)

        products_list = [
            "A B C",
            "DEF",
            "G HI",
        ]

        launcher = create_engine_launcher(self.tk, self.context, self.engine_name, products=products_list)

        self.assertEqual(launcher._is_product_supported("A B C"), True)
        self.assertEqual(launcher._is_product_supported("ABC"), False)
        self.assertEqual(launcher._is_product_supported("DEF"), True)
        self.assertEqual(launcher._is_product_supported("D E F"), False)
        self.assertEqual(launcher._is_product_supported("G HI"), True)
        self.assertEqual(launcher._is_product_supported(" G HI "), False)

    def test_is_supported(self):

        # versions returned are range(0, 10)
        versions_list = [2, 3, 4]

        launcher = create_engine_launcher(
            self.tk,
            self.context,
            self.engine_name,
            versions=versions_list,
        )
        sw_versions = launcher._scan_software()
        for sw_version in sw_versions:
            (supported, reason) = launcher._is_supported(sw_version)
            if sw_version.version in [2, 3, 4]:
                self.assertEqual(supported, True)
                self.assertEqual(reason, "")
            else:
                self.assertEqual(supported, False)
                self.assertIsInstance(reason, basestring)



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
        self._product = "My Custom App"
        self._path = "/my/path/to/app/{version}/my_custom_app"
        self._icon = "%s/icon.png" % self._path
        self._arguments = ["--42"]

    def test_init_software_version(self):
        sw_version = SoftwareVersion(
            self._version,
            self._product,
            self._path,
            self._icon,
            self._arguments
        )

        self.assertEqual(self._version, sw_version.version)
        self.assertEqual(self._product, sw_version.product)
        self.assertEqual("%s %s" % (self._product, self._version), sw_version.display_name)
        self.assertEqual(self._path, sw_version.path)
        self.assertEqual(self._icon, sw_version.icon)
        self.assertEqual(self._arguments, sw_version.arguments)


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
