# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import sys
import os
import shutil
import tempfile

from tank_test.tank_test_base import *
import tank
from tank.errors import TankError
from tank.platform import application
from tank.platform import constants
from tank.template import Template
from tank.deploy import descriptor


class TestApplication(TankTestBase):
    def setUp(self):
        super(TestApplication, self).setUp()
        self.setup_fixtures()
        
        # setup shot
        seq = {"type":"Sequence", "code": "seq_name", "id":3 }
        seq_path = os.path.join(self.project_root, "sequences/Seq/seq_name")
        self.add_production_path(seq_path, seq)
        
        shot = {"type":"Shot", "code": "shot_name", "id":2, "sg_sequence": seq, "project": self.project}
        shot_path = os.path.join(seq_path, "shot_name")
        self.add_production_path(shot_path, shot)
        
        step = {"type":"Step", "code": "step_name", "id":4 }
        self.shot_step_path = os.path.join(shot_path, "step_name")
        self.add_production_path(self.shot_step_path, step)

        self.test_resource = os.path.join(self.project_root, "tank", "config", "foo", "bar.png")
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


class TestGetApplication(TestApplication):
    def test_bad_app_path(self):
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
        app_path = os.path.join(self.project_config, "test_app")
        # make a dev location and create descriptor
        app_desc = descriptor.get_from_location(descriptor.AppDescriptor.APP, 
                                                self.tk.pipeline_configuration, 
                                                {"type": "dev", "path": app_path})
        result = application.get_application(self.engine, app_path, app_desc, {}, "instance_name", None)
        self.assertIsInstance(result, application.Application)
        

class TestGetSetting(TestApplication):
    def setUp(self):
        super(TestGetSetting, self).setUp()
        self.app = self.engine.apps["test_app"]
        
    def test_get_setting(self):
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

class TestExecuteHook(TestApplication):
    
    def test_standard_format(self):
        app = self.engine.apps["test_app"]
        self.assertTrue(app.execute_hook("test_hook_std", dummy_param=True))

    def test_custom_method(self):
        app = self.engine.apps["test_app"]
        self.assertTrue(app.execute_hook_method("test_hook_std", "second_method", another_dummy_param=True))

    def test_self_format(self):
        app = self.engine.apps["test_app"]
        self.assertTrue(app.execute_hook("test_hook_self", dummy_param=True))

    def test_config_format(self):
        app = self.engine.apps["test_app"]
        self.assertTrue(app.execute_hook("test_hook_config", dummy_param=True))

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
        self.assertTrue(len(tank.hook._HOOKS_CACHE) == 0)
        app = self.engine.apps["test_app"]
        self.assertTrue(app.execute_hook("test_hook_std", dummy_param=True))
        self.assertTrue(len(tank.hook._HOOKS_CACHE) == 1)
        self.engine.destroy()
        self.assertTrue(len(tank.hook._HOOKS_CACHE) == 0)




class TestProperties(TestApplication):


    def test_properties(self):
        """
        test engine properties
        """
        app = self.engine.apps["test_app"]
        self.assertEqual(app.name, "test_app")
        self.assertEqual(app.display_name, "Test App")
        self.assertEqual(app.version, "Undefined")
        self.assertEqual(app.documentation_url, None)
        

