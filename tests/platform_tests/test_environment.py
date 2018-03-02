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

from tank.errors import TankError
from tank_test.tank_test_base import setUpModule # noqa
from tank_test.tank_test_base import TankTestBase
from tank_vendor import yaml

import copy

class TestEnvironment(TankTestBase):
    """
    Basic environment tests
    """

    def setUp(self):
        super(TestEnvironment, self).setUp()
        self.setup_fixtures()

        self.test_env = "test"
        self.test_engine = "test_engine"

        # create env object
        self.env = self.tk.pipeline_configuration.get_environment(self.test_env)

        # get raw environment
        env_file = os.path.join(self.project_config, "env", "test.yml")
        fh = open(env_file)
        self.raw_env_data = yaml.load(fh)
        fh.close()

        # get raw app metadata
        app_md = os.path.join(self.project_config, "bundles", "test_app", "info.yml")
        fh = open(app_md)
        self.raw_app_metadata = yaml.load(fh)
        fh.close()

        # get raw engine metadata
        eng_md = os.path.join(self.project_config, "bundles", "test_engine", "info.yml")
        fh = open(eng_md)
        self.raw_engine_metadata = yaml.load(fh)
        fh.close()

    def test_basic_properties(self):
        self.assertEqual(self.env.name, "test")
        # disabled engine should be skipped
        self.assertEqual(self.env.get_engines(), ["test_included_engine", "incomplete_engine", "test_engine"])
        # disabled app should be skipped
        self.assertEqual(self.env.get_apps("test_engine"), ["test_app"])

    def test_engine_settings(self):

        self.assertRaises(TankError, self.env.get_engine_settings, "no-exist")

        eng_env = copy.deepcopy(self.raw_env_data["engines"]["test_engine"])
        eng_env.pop("location")
        eng_env.pop("apps")
        self.assertEqual(self.env.get_engine_settings("test_engine"), eng_env)

    def test_app_settings(self):

        self.assertRaises(TankError, self.env.get_app_settings, "test_engine", "bad_app")
        self.assertRaises(TankError, self.env.get_app_settings, "bad_engine", "bad_app")
        self.assertRaises(TankError, self.env.get_app_settings, "bad_engine", "test_app")

        app_env = copy.deepcopy(self.raw_env_data["engines"]["test_engine"]["apps"]["test_app"])
        app_env.pop("location")
        self.assertEqual(self.env.get_app_settings("test_engine", "test_app"), app_env)

    def test_engine_meta(self):

        self.assertRaises(TankError, self.env.get_engine_descriptor, "bad_engine")
        self.assertEqual(self.env.get_engine_descriptor("test_engine").configuration_schema,
                         self.raw_engine_metadata["configuration"])

    def test_app_meta(self):

        self.assertRaises(TankError, self.env.get_app_descriptor, "test_engine", "bad_engine")
        self.assertEqual(self.env.get_app_descriptor("test_engine", "test_app").configuration_schema,
                         self.raw_app_metadata["configuration"])


class TestDumpEnvironment(TankTestBase):

    def setUp(self):
        super(TestDumpEnvironment, self).setUp()
        # This test will write to the configuration folder, so copy it.
        self.setup_fixtures(parameters={"installed_config": True})

        # create env object
        self.env = self.tk.pipeline_configuration.get_environment("test_dump", writable=True)

    def test_dump(self):

        env_name = "test_dump_unmodified"

        # dump to a temp file
        temp_path = os.path.join(self.project_config, "env", env_name + ".yml")
        fh = open(temp_path, "w")
        self.env.dump(fh, self.env.NONE)  # no transform
        fh.close()

        self.assertTrue(os.path.exists(temp_path))

        # make sure the env can be loaded
        dumped_env = self.tk.pipeline_configuration.get_environment(env_name)

        # make sure engines are there
        self.assertEquals(dumped_env.get_engines(), ["test_engine"])

        # make sure apps are there
        self.assertEquals(dumped_env.get_apps("test_engine"), ["test_app"])

        # because we didn't transform, it should not have any of the sparse
        # config values. try a couple to be sure
        app_settings = dumped_env.get_app_settings("test_engine", "test_app")
        self.assertTrue("test_str_sparse" not in app_settings)
        self.assertTrue("test_empty_str_sparse" not in app_settings)
        self.assertTrue("test_template_sparse" not in app_settings)
        self.assertTrue("test_hook_std_sparse" not in app_settings)

    def test_dump_full(self):

        env_name = "test_dump_full"

        # dump to a temp file
        temp_path = os.path.join(self.project_config, "env", env_name + ".yml")
        fh = open(temp_path, "w")
        self.env.dump(fh, self.env.INCLUDE_DEFAULTS)
        fh.close()

        self.assertTrue(os.path.exists(temp_path))

        # make sure the env can be loaded
        dumped_env = self.tk.pipeline_configuration.get_environment(env_name)

        # make sure engines are there
        self.assertEquals(dumped_env.get_engines(), ["test_engine"])

        # make sure apps are there
        self.assertEquals(dumped_env.get_apps("test_engine"), ["test_app"])

        # it should have the sparse config values. try a couple to be sure
        app_settings = dumped_env.get_app_settings("test_engine", "test_app")
        self.assertTrue("test_str_sparse" in app_settings)
        self.assertTrue("test_empty_str_sparse" in app_settings)
        self.assertTrue("test_template_sparse" in app_settings)
        self.assertTrue("test_hook_std_sparse" in app_settings)

    def test_dump_sparse(self):

        env_name = "test_dump_sparse"

        # dump to a temp file
        temp_path = os.path.join(self.project_config, "env", env_name + ".yml")
        fh = open(temp_path, "w")
        self.env.dump(fh, self.env.STRIP_DEFAULTS)
        fh.close()

        self.assertTrue(os.path.exists(temp_path))

        # make sure the env can be loaded
        dumped_env = self.tk.pipeline_configuration.get_environment(env_name)

        # make sure engines are there
        self.assertEquals(dumped_env.get_engines(), ["test_engine"])

        # make sure apps are there
        self.assertEquals(dumped_env.get_apps("test_engine"), ["test_app"])

        # because we dumped sparse, it should not have any of the sparse
        # config values. try a couple to be sure
        app_settings = dumped_env.get_app_settings("test_engine", "test_app")
        self.assertTrue("test_str_sparse" not in app_settings)
        self.assertTrue("test_empty_str_sparse" not in app_settings)
        self.assertTrue("test_template_sparse" not in app_settings)
        self.assertTrue("test_hook_std_sparse" not in app_settings)


class TestUpdateEnvironment(TankTestBase):
    """
    Tests yaml environment updates
    """

    def setUp(self):
        super(TestUpdateEnvironment, self).setUp()
        # The following tests are going to update the configuration.
        self.setup_fixtures(parameters={"installed_config": True})

        self.test_env = "test"
        self.test_engine = "test_engine"

        # create env object
        self.env = self.tk.pipeline_configuration.get_environment(self.test_env, writable=True)

    def test_add_engine(self):

        self.assertRaises(TankError, self.env.create_engine_settings, "test_engine")

        # get raw environment before
        env_file = os.path.join(self.project_config, "env", "test.yml")
        fh = open(env_file)
        env_before = yaml.load(fh)
        fh.close()

        self.env.create_engine_settings("new_engine")

        # get raw environment after
        env_file = os.path.join(self.project_config, "env", "test.yml")
        fh = open(env_file)
        env_after = yaml.load(fh)
        fh.close()

        # ensure that disk was updated
        self.assertNotEqual(env_after, env_before)
        env_before["engines"]["new_engine"] = {}
        env_before["engines"]["new_engine"]["location"] = {}
        env_before["engines"]["new_engine"]["apps"] = {}
        self.assertEqual(env_after, env_before)

        # ensure memory was updated
        cfg_after = self.env.get_engine_settings("new_engine")
        self.assertEqual(cfg_after, {})

    def test_add_app(self):

        self.assertRaises(TankError, self.env.create_app_settings, "test_engine", "test_app")
        self.assertRaises(TankError, self.env.create_app_settings, "unknown_engine", "test_app")

        # get raw environment before
        env_file = os.path.join(self.project_config, "env", "test.yml")
        with open(env_file) as fh:
            env_before = yaml.load(fh)

        self.env.create_app_settings("test_engine", "new_app")

        # get raw environment after
        env_file = os.path.join(self.project_config, "env", "test.yml")
        with open(env_file) as fh:
            env_after = yaml.load(fh)

        # ensure that disk was updated
        self.assertNotEqual(env_after, env_before)
        env_before["engines"]["test_engine"]["apps"]["new_app"] = {}
        env_before["engines"]["test_engine"]["apps"]["new_app"]["location"] = {}
        self.assertEqual(env_after, env_before)

        # ensure memory was updated
        cfg_after = self.env.get_app_settings("test_engine", "new_app")
        self.assertEqual(cfg_after, {})

    def test_find_included_engine_location(self):
        # In the case where we use the protected method to access the
        # absolute location of the engine's descriptor, we'll end up
        # with the path to the engine_location.yml file, which is being
        # included into test.yml.
        tokens, yml_file = self.env._find_location_for_engine(
            "test_included_engine",
            absolute_location=True,
        )
        self.assertEqual(os.path.basename(yml_file), "engine_location.yml")

        # In the default case, we end up with test.yml, which is where
        # the test_included_engine instance is defined.
        tokens, yml_file = self.env.find_location_for_engine(
            "test_included_engine"
        )
        self.assertEqual(os.path.basename(yml_file), "test.yml")


    def test_update_engine_settings(self):

        self.assertRaises(TankError, self.env.update_engine_settings, "bad_engine", {}, {})

        # get raw environment before
        env_file = os.path.join(self.project_config, "env", "test.yml")
        fh = open(env_file)
        env_before = yaml.load(fh)
        fh.close()
        prev_settings = self.env.get_engine_settings("test_engine")

        self.env.update_engine_settings("test_engine",
                                        {"foo": u"bar"},
                                        {"type": "dev", "path": "foo"})

        # get raw environment after
        env_file = os.path.join(self.project_config, "env", "test.yml")
        fh = open(env_file)
        env_after = yaml.load(fh)
        fh.close()

        # ensure that disk was updated
        self.assertNotEqual(env_after, env_before)
        env_before["engines"]["test_engine"]["foo"] = "bar"
        env_before["engines"]["test_engine"]["location"] = {"type":"dev", "path":"foo"}
        self.assertEqual(env_after, env_before)

        # #31315 - make sure the u"bar" unicode was converted to str
        self.assertEqual(type(env_after["engines"]["test_engine"]["foo"]), str)

        # ensure memory was updated
        new_settings = self.env.get_engine_settings("test_engine")
        prev_settings.update({"foo":"bar"})
        self.assertEqual(new_settings, prev_settings)

        desc_after = self.env.get_engine_descriptor("test_engine")
        self.assertEqual(desc_after.get_dict(), {"type":"dev", "path":"foo"})



    def test_update_app_settings(self):

        self.assertRaises(TankError, self.env.update_app_settings, "bad_engine", "bad_app", {}, {})

        new_location = {"type":"dev", "path":"foo1"}
        new_settings = {
                        "foo":"bar",
                        "test_simple_dictionary":{"foo":"bar"},
                        "test_complex_dictionary":{"test_list": {"foo":"bar"}},
                        "test_complex_list":{"foo":"bar"},
                        "test_very_complex_list":{"test_list":{"foo":"bar"}},
                        }


        # get raw environment before
        env_file = os.path.join(self.project_config, "env", "test.yml")
        fh = open(env_file)
        env_before = yaml.load(fh)
        fh.close()
        settings_before = self.env.get_app_settings("test_engine", "test_app")

        # update settings:
        self.env.update_app_settings("test_engine", "test_app", new_settings, new_location)

        # get raw environment after
        env_file = os.path.join(self.project_config, "env", "test.yml")
        fh = open(env_file)
        env_after = yaml.load(fh)
        fh.close()

        # ensure that disk was updated
        self.assertNotEqual(env_after, env_before)

        env_app_settings = env_before["engines"]["test_engine"]["apps"]["test_app"]
        env_app_settings["location"] = new_location
        env_app_settings["foo"] = "bar"
        env_app_settings["test_simple_dictionary"]["foo"] = "bar"
        for item in env_app_settings["test_complex_dictionary"]["test_list"]:
            item["foo"] = "bar"
        for item in env_app_settings["test_complex_list"]:
            item["foo"] = "bar"
        for item in env_app_settings["test_very_complex_list"]:
            for sub_item in item["test_list"]:
                sub_item["foo"] = "bar"

        self.assertEqual(env_after, env_before)

        # ensure memory was updated
        settings_after = self.env.get_app_settings("test_engine", "test_app")

        settings_before["foo"] = "bar"
        settings_before["test_simple_dictionary"]["foo"] = "bar"
        for item in settings_before["test_complex_dictionary"]["test_list"]:
            item["foo"] = "bar"
        for item in settings_before["test_complex_list"]:
            item["foo"] = "bar"
        for item in settings_before["test_very_complex_list"]:
            for sub_item in item["test_list"]:
                sub_item["foo"] = "bar"

        self.assertEqual(settings_after, settings_before)

        desc_after = self.env.get_app_descriptor("test_engine", "test_app")
        self.assertEqual(desc_after.get_dict(), new_location)



class TestUpdateEnvironmentRuamelYaml(TestUpdateEnvironment):
    """
    Runs the standard environment Update tests with the
    ruamel parser enabled.
    """

    def setUp(self):
        super(TestUpdateEnvironmentRuamelYaml, self).setUp()
        self.env.set_yaml_preserve_mode(True)





class TestRuamelParser(TankTestBase):
    """
    Tests writing yaml files using the ruamel parser
    """


    def setUp(self):
        super(TestRuamelParser, self).setUp()
        self.setup_fixtures(parameters={"installed_config": True})

    def test_yaml(self):

        # create env object
        env = self.tk.pipeline_configuration.get_environment("test", writable=True)

        env.create_engine_settings("new_engine")

        # get environment content before
        env_file = os.path.join(self.project_config, "env", "test.yml")
        with open(env_file) as fh:
            updated_env = fh.readlines()

        # get raw environment after
        # ruamel parser only used in py2.6+
        if sys.version_info < (2, 6):
            env_file = os.path.join(self.project_config, "env", "post_update", "test_post_update_old_parser.yml")
        else:
            env_file = os.path.join(self.project_config, "env", "post_update", "test_post_update_new_parser.yml")

        with open(env_file) as fh:
            expected_env = fh.readlines()

        # because floats are rendered differently on different versions of
        # python, replace the FLOAT_VALUE keyword in the expected fixture
        # with whatever the current version of python is expecting
        expected_env = [l.replace("FLOAT_VALUE", repr(1.1)) for l in expected_env]
        self.assertEqual(updated_env, expected_env)



class TestPyYamlParser(TankTestBase):
    """
    Tests writing yaml files using the old pyyaml parser
    """

    def setUp(self):
        super(TestPyYamlParser, self).setUp()
        self.setup_fixtures(parameters={"installed_config": True})

    def test_yaml(self):

        # create env object
        env = self.tk.pipeline_configuration.get_environment("test", writable=True)
        env.set_yaml_preserve_mode(False)

        env.create_engine_settings("new_engine")

        # get environment content before
        env_file = os.path.join(self.project_config, "env", "test.yml")
        fh = open(env_file)
        updated_env = fh.readlines()
        fh.close()

        # get raw environment after
        env_file = os.path.join(self.project_config, "env", "post_update", "test_post_update_old_parser.yml")
        fh = open(env_file)
        expected_env = fh.readlines()
        fh.close()

        # because floats are rendered differently on different versions of
        # python, replace the FLOAT_VALUE keyword in the expected fixture
        # with whatever the current version of python is expecting
        expected_env = [l.replace("FLOAT_VALUE", repr(1.1)) for l in expected_env]
        self.assertEqual(updated_env, expected_env)
