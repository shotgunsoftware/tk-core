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

import sys
import os
import StringIO
import shutil
import logging
import tempfile
import mock

from tank_test.tank_test_base import *
import tank
from tank.errors import TankError, TankHookMethodDoesNotExistError
from tank.platform import application, constants, validation
from tank.template import Template
from tank.deploy import descriptor


class TestApplication(TankTestBase):
    """
    Base class for Application tests
    """

    def setUp(self):
        super(TestApplication, self).setUp()
        self.setup_fixtures()
        
        # setup shot
        seq = {"type":"Sequence", "code": "seq_name", "id":3 }
        seq_path = os.path.join(self.project_root, "sequences", "seq_name")
        self.add_production_path(seq_path, seq)
        
        shot = {"type":"Shot", "code": "shot_name", "id":2, "sg_sequence": seq, "project": self.project}
        shot_path = os.path.join(seq_path, "shot_name")
        self.add_production_path(shot_path, shot)
        
        step = {"type":"Step", "code": "step_name", "id":4 }
        self.shot_step_path = os.path.join(shot_path, "step_name")
        self.add_production_path(self.shot_step_path, step)

        self.test_resource = os.path.join(self.pipeline_config_root, "config", "foo", "bar.png")
        os.makedirs(os.path.dirname(self.test_resource))
        fh = open(self.test_resource, "wt")
        fh.write("test")
        fh.close()
        
        context = self.tk.context_from_path(self.shot_step_path)
        self.engine = tank.platform.start_engine("test_engine", self.tk, context)

        
    def tearDown(self):
        # engine is held as global, so must be destroyed.
        cur_engine = tank.platform.current_engine()
        if cur_engine:
            cur_engine.destroy()
        os.remove(self.test_resource)

        # important to call base class so it can clean up memory
        super(TestApplication, self).tearDown()


class TestAppFrameworks(TestApplication):
    """
    Tests for framework related operations
    """

    def test_minimum_version(self):
        """
        Tests the min required frameworks for an app
        """
        app = self.engine.apps["test_app"]
        previous_mins = dict()
        frameworks = app.descriptor.required_frameworks

        for fw in frameworks:
            previous_mins[fw["name"]] = fw.get("minimum_version")
            fw["minimum_version"] = "v999.999.999"

        try:
            # We should get an error here due to the too-high
            # minumum required version for the frameworks.
            self.assertRaises(
                TankError,
                validation.validate_and_return_frameworks,
                app.descriptor,
                self.engine.get_env(),
            )

            for fw in frameworks:
                fw["minimum_version"] = "v0.0.0"

            # We should get back a list of framework objects that
            # is the same length as the number of required frameworks
            # we have.
            self.assertEqual(
                len(validation.validate_and_return_frameworks(
                    app.descriptor,
                    self.engine.get_env(),
                )),
                len(frameworks),
            )
        finally:
            # In case any future tests need to make use of the minimum
            # version requirements in the frameworks, we'll put them
            # back to what they were before.
            for fw in frameworks:
                if previous_mins[fw["name"]]:
                    fw["minimum_version"] = previous_mins[fw["name"]]
                else:
                    del fw["minimum_version"]


class TestGetApplication(TestApplication):
    """
    Tests the application.get_application method
    """
    def test_bad_app_path(self):
        """
        Tests a get_application invalid path
        """
        bogus_path = os.path.join(self.tank_temp, "bogus_path")
        
        self.assertRaises(TankError,
                          application.get_application,
                          self.engine, bogus_path, "bogus_app", {}, "instance_name", None)
        
        try:
            application.get_application(self.engine, bogus_path, "bogus_app", {}, "instance_name", None)
        except TankError, cm:
            expected_msg = "Failed to load plugin"
            self.assertTrue(cm.message.startswith(expected_msg))
        
    def test_good_path(self):
        """
        Tests a get_application valid path
        """
        app_path = os.path.join(self.project_config, "bundles", "test_app")
        # make a dev location and create descriptor
        app_desc = self.tk.pipeline_configuration.get_app_descriptor({"type": "dev", "path": app_path})
        result = application.get_application(self.engine, app_path, app_desc, {}, "instance_name", None)
        self.assertIsInstance(result, application.Application)
        

class TestGetSetting(TestApplication):
    """
    Tests settings retrieval
    """

    def setUp(self):
        super(TestGetSetting, self).setUp()
        self.app = self.engine.apps["test_app"]
        
    def test_get_setting(self):
        """
        Tests application.get_setting()
        """
        # Test that app is able to locate a template based on the template name
        tmpl = self.app.get_template("test_template")
        self.assertEqual("maya_publish_name", tmpl.name)
        self.assertIsInstance(tmpl, Template)
        
        # test resource
        self.assertEqual(self.test_resource, self.app.get_setting("test_icon"))

        # Test a simple list
        test_list = self.app.get_setting("test_simple_list")
        self.assertEqual(4, len(test_list))
        self.assertEqual("a", test_list[0])
        
        # Test a complex list
        test_list = self.app.get_setting("test_complex_list")
        test_item = test_list[0]
        
        self.assertEqual(2, len(test_list))
        self.assertEqual("a", test_item["test_str"])
        self.assertEqual(1, test_item["test_int"])
        self.assertEqual(1.1, test_item["test_float"])
        self.assertEqual(True, test_item["test_bool"])
        self.assertEqual("extra", test_item["test_extra"])

        # sparse tests. these values do not exists in the environment, only
        # as default values in the manifest. the results should be the same
        self.assertEqual("a", self.app.get_setting("test_str_sparse"))
        self.assertEqual(1, self.app.get_setting("test_int_sparse"))
        self.assertEqual(1.1, self.app.get_setting("test_float_sparse"))
        self.assertEqual(True, self.app.get_setting("test_bool_sparse"))
        self.assertEqual("", self.app.get_setting("test_empty_str_sparse"))

        tmpl_sparse = self.app.get_template("test_template_sparse")
        self.assertEqual("maya_publish_name", tmpl.name)
        self.assertIsInstance(tmpl_sparse, Template)

        # test legacy case where a setting has no schema
        self.assertEqual(1234.5678, self.app.get_setting("test_no_schema"))

        # test allow empty types with no default
        self.assertEqual([], self.app.get_setting("test_allow_empty_list"))
        self.assertEqual({}, self.app.get_setting("test_allow_empty_dict"))

        # test the default values of sparse hooks
        self.assertEqual(
            "{config}/config_test_hook.py",
            self.app.get_setting("test_hook_std_sparse")
        )

        self.assertEqual(
            "{self}/test_hook.py",
            self.app.get_setting("test_hook_default_sparse")
        )

        self.assertEqual(
            "{$TEST_ENV_VAR}/test_env_var_hook.py",
            self.app.get_setting("test_hook_env_var_sparse")
        )

        self.assertEqual(
            "{self}/test_hook.py",
            self.app.get_setting("test_hook_self_sparse")
        )

        self.assertEqual(
            "{self}/test_hook-test_engine.py",
            self.app.get_setting("test_hook_new_style_config_old_style_engine_specific_hook_sparse")
        )

        self.assertEqual(
            "{self}/test_hook-test_engine.py",
            self.app.get_setting("test_default_syntax_with_new_style_engine_specific_hook_sparse")
        )

class TestExecuteHookByName(TestApplication):
    """
    Tests execute_hook_by_name
    """

    def test_legacy_format_old_method(self):
        app = self.engine.apps["test_app"]
        self.assertEqual(app.execute_hook_by_name("named_hook", dummy_param=True), "named_hook_1")

    def test_legacy_format(self):
        app = self.engine.apps["test_app"]
        self.assertEqual(app.execute_hook_expression("named_hook", "execute", dummy_param=True), "named_hook_1")

    def test_legacy_format_2(self):
        app = self.engine.apps["test_app"]
        self.assertEqual(app.execute_hook_expression("named_hook", "second_method", another_dummy_param=True), 
                         "named_hook_2")

    def test_config(self):
        app = self.engine.apps["test_app"]
        self.assertEqual(app.execute_hook_expression("{config}/named_hook.py", "execute", dummy_param=True), 
                         "named_hook_1")

    def test_engine(self):
        app = self.engine.apps["test_app"]
        self.assertEqual(app.execute_hook_expression("{engine}/named_hook.py", "execute", dummy_param=True),
                         "named_hook_1")

    def test_self(self):
        app = self.engine.apps["test_app"]
        self.assertTrue(app.execute_hook_expression("{self}/test_hook.py", "execute", dummy_param=True), 
                        "named_hook_1")

    # calling `execute_hook_method` for a method that does not exist in the hook
    # should raise the TankHookMethodDoesNotExistError exception
    def test_no_method(self):
        app = self.engine.apps["test_app"]
        self.assertRaises(
            TankHookMethodDoesNotExistError,
            app.execute_hook_method,
            "test_hook_std",
            "foobar"
        )


class TestExecuteHook(TestApplication):
    """
    Tests the app.execute_hook method
    """

    def test_standard_format(self):
        app = self.engine.apps["test_app"]
        self.assertTrue(app.execute_hook("test_hook_std", dummy_param=True))

    def test_custom_method(self):
        app = self.engine.apps["test_app"]
        self.assertTrue(app.execute_hook_method("test_hook_std", "second_method", another_dummy_param=True))

    def test_create_instance(self):
        """
        tests the built-in get_instance() method
        """
        app = self.engine.apps["test_app"]
        hook_expression = app.get_setting("test_hook_std")
        instance_1 = app.create_hook_instance(hook_expression)
        self.assertEquals(instance_1.second_method(another_dummy_param=True), True)
        instance_2 = app.create_hook_instance(hook_expression)
        self.assertNotEquals(instance_1, instance_2)

    def test_parent(self):
        """
        Tests hook.parent for applications
        """
        app = self.engine.apps["test_app"]
        hook_expression = app.get_setting("test_hook_std")
        hook_instance = app.create_hook_instance(hook_expression)
        self.assertEquals(hook_instance.parent, app)

    def test_sgtk(self):
        """
        Tests hook.sgtk accessor for applications
        """
        app = self.engine.apps["test_app"]
        hook_expression = app.get_setting("test_hook_std")
        hook_instance = app.create_hook_instance(hook_expression)
        self.assertEquals(hook_instance.sgtk, app.sgtk)

    def test_logger(self):
        """
        tests the logger property for application hooks
        """
        # capture sync log to string
        stream = StringIO.StringIO()
        handler = logging.StreamHandler(stream)

        app = self.engine.apps["test_app"]
        hook_logger_name = "%s.hook.config_test_hook" % app.logger.name

        log = logging.getLogger(hook_logger_name)
        log.setLevel(logging.DEBUG)
        log.addHandler(handler)

        # run hook method that logs something via self.logger
        app.execute_hook_method("test_hook_std", "logging_method")

        log_contents = stream.getvalue()
        stream.close()
        log.removeHandler(handler)

        self.assertEquals(log_contents, "hello toolkitty\n")

    def test_disk_location(self):
        """
        tests the hook.disk_location property
        """
        app = self.engine.apps["test_app"]
        disk_location = app.execute_hook_method("test_hook_std", "test_disk_location")
        self.assertEquals(
            disk_location,
            os.path.join(self.pipeline_config_root, "config", "hooks", "toolkitty.png")
        )

    def test_inheritance_disk_location(self):
        """
        tests the hook.disk_location property in a multi inheritance scenarios
        """
        app = self.engine.apps["test_app"]

        hook = app.create_hook_instance(
            "{config}/config_test_hook.py:{config}/more_hooks/config_test_hook.py"
        )

        (disk_location_1, disk_location_2) = hook.test_inheritance_disk_location()

        self.assertEquals(
            disk_location_1,
            os.path.join(
                self.pipeline_config_root,
                "config",
                "hooks",
                "toolkitty.png"
            )
        )
        self.assertEquals(
            disk_location_2,
            os.path.join(
                self.pipeline_config_root,
                "config",
                "hooks",
                "more_hooks",
                "toolkitty.png"
            )
        )

        # edge case: also make sure that if we call the method externally,
        # we get the location of self
        self.assertEquals(
            hook.disk_location,
            os.path.join(
                self.pipeline_config_root,
                "config",
                "hooks",
                "more_hooks"
            )
        )

    def test_self_format(self):
        app = self.engine.apps["test_app"]
        self.assertTrue(app.execute_hook("test_hook_self", dummy_param=True))

    def test_config_format(self):
        app = self.engine.apps["test_app"]
        self.assertTrue(app.execute_hook("test_hook_config", dummy_param=True))

    def test_engine_format(self):
        app = self.engine.apps["test_app"]
        self.assertTrue(app.execute_hook("test_hook_engine", dummy_param=True))

    def test_default_format(self):
        app = self.engine.apps["test_app"]
        self.assertTrue(app.execute_hook("test_hook_default", dummy_param=True))

    def test_env_var_format(self):
        app = self.engine.apps["test_app"]
        shutil.copy( os.path.join(app.disk_location, "hooks", "test_hook.py"), 
                     os.path.join(self.project_root, "test_env_var_hook.py"))
        os.environ["TEST_ENV_VAR"] = self.project_root

        self.assertTrue(app.execute_hook("test_hook_env_var", dummy_param=True))

    def test_inheritance(self):
        app = self.engine.apps["test_app"]
        self.assertEqual(app.execute_hook_method("test_hook_inheritance_1", "foo", bar=True), "base class")

    def test_inheritance_2(self):
        app = self.engine.apps["test_app"]
        self.assertEqual(app.execute_hook_method("test_hook_inheritance_2", "foo2", bar=True), "custom class base class")

    def test_inheritance_3(self):
        app = self.engine.apps["test_app"]
        self.assertEqual(app.execute_hook_method("test_hook_inheritance_3", "foo2", bar=True), "custom class base class")

    def test_inheritance_old_style(self):
        """
        Test that a hook that contains multiple levels of derivation works as long as there is only one leaf
        level class
        """
        app = self.engine.apps["test_app"]
        self.assertEqual(app.execute_hook("test_hook_inheritance_old_style", dummy_param=True), "doubly derived class")

    def test_inheritance_old_style_fails(self):
        """
        Test that a hook file that contains multiple levels of derivation raises a TankError when there
        are multiple leaf level classes derived from 'Hook'
        """
        app = self.engine.apps["test_app"]
        self.assertRaises(TankError,
                         app.execute_hook,
                         "test_hook_inheritance_old_style_fails", dummy_param=True)

    def test_new_style_config_old_style_hook(self):
        app = self.engine.apps["test_app"]
        self.assertTrue(app.execute_hook("test_hook_new_style_config_old_style_hook", dummy_param=True))
        self.assertTrue(app.execute_hook("test_hook_new_style_config_old_style_engine_specific_hook", dummy_param=True))

    def test_default_syntax_with_new_style_hook(self):
        app = self.engine.apps["test_app"]
        self.assertTrue(app.execute_hook("test_default_syntax_with_new_style_hook", dummy_param=True))
        self.assertTrue(app.execute_hook("test_default_syntax_with_new_style_engine_specific_hook", dummy_param=True))

    def test_default_syntax_missing_implementation(self):
        """
        Test the case when the default hook defined in the manifest is missing.
        This is common when using the {engine_name} token and a user is trying
        to create a hook which supports an engine which the app does not yet support.
        """
        app = self.engine.apps["test_app"]
        self.assertEqual(app.execute_hook_method("test_default_syntax_missing_implementation", "test_method"), "hello")

    # sparse tests

    def test_hooks_sparse(self):
        app = self.engine.apps["test_app"]

        self.assertTrue(app.execute_hook("test_hook_std_sparse", dummy_param=True))
        self.assertTrue(app.execute_hook_method("test_hook_std_sparse", "second_method", another_dummy_param=True))
        self.assertTrue(app.execute_hook("test_hook_default_sparse", dummy_param=True))
        self.assertTrue(app.execute_hook("test_hook_self_sparse", dummy_param=True))

        shutil.copy( os.path.join(app.disk_location, "hooks", "test_hook.py"),
                     os.path.join(self.project_root, "test_env_var_hook.py"))
        os.environ["TEST_ENV_VAR"] = self.project_root
        self.assertTrue(app.execute_hook("test_hook_env_var_sparse", dummy_param=True))

        self.assertTrue(app.execute_hook("test_hook_new_style_config_old_style_engine_specific_hook_sparse", dummy_param=True))
        self.assertTrue(app.execute_hook("test_default_syntax_with_new_style_engine_specific_hook_sparse", dummy_param=True))

    def test_default_values(self):
        app = self.engine.apps["test_app"]

        self.assertEqual(app.get_setting("test_engine_specific_default"), "foobar")
        self.assertEqual(app.get_setting("test_engine_specific_multi"), "foobar")
        self.assertEqual(app.get_setting("test_engine_specific_default_only"), "foobar")
        self.assertEqual(app.get_setting("test_engine_specific_default_wrong"), None)

class TestRequestFolder(TestApplication):
    
    def test_request_folder(self):
        app = self.engine.apps["test_app"]
        
        path = os.path.join( tempfile.gettempdir(), "tank_unit_test_test_request_folder")
    
        self.assertFalse(os.path.exists(path))
        app.ensure_folder_exists(path)
        self.assertTrue(os.path.exists(path))
        os.rmdir(path)

class TestHookCache(TestApplication):
    """
    Check that the hooks cache is cleared when an engine is restarted.
    """
    def test_call_hook(self):

        tank.hook.clear_hooks_cache()
        self.assertTrue(len(tank.hook._hooks_cache) == 0)
        app = self.engine.apps["test_app"]
        self.assertTrue(app.execute_hook("test_hook_std", dummy_param=True))
        self.assertTrue(len(tank.hook._hooks_cache) == 1)

        with mock.patch("tank.hook._hooks_cache.clear", wraps=tank.hook._hooks_cache.clear) as clear_mock:
            self.engine.destroy()
            self.assertEqual(clear_mock.call_count, 1)


class TestProperties(TestApplication):


    def test_properties(self):
        """
        test engine properties
        """
        app = self.engine.apps["test_app"]
        expected_doc_url = "https://support.shotgunsoftware.com/hc/en-us/articles/115000068574-User-Guide"
        self.assertEqual(app.name, "test_app")
        self.assertEqual(app.display_name, "Test App")
        self.assertEqual(app.version, "Undefined")
        self.assertEqual(app.documentation_url, expected_doc_url)
        

