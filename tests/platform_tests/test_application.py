"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------
"""
import sys
import os

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
        seq = {"type":"Sequence", "name":"seq_name", "id":3}
        seq_path = os.path.join(self.project_root, "sequences/Seq")
        self.add_production_path(seq_path, seq)
        shot = {"type":"Shot",
                "name": "shot_name",
                "id":2,
                "project": self.project}
        shot_path = os.path.join(seq_path, "shot_code")
        self.add_production_path(shot_path, shot)
        step = {"type":"Step", "name":"step_name", "id":4}
        self.shot_step_path = os.path.join(shot_path, "step_name")
        self.add_production_path(self.shot_step_path, step)
        
        tk = tank.Tank(self.project_root)
        context = tk.context_from_path(self.shot_step_path)
        self.engine = tank.platform.start_engine("test_engine", tk, context)
        
    def tearDown(self):
        # engine is held as global, so must be destroyed.
        cur_engine = tank.platform.current_engine()
        if cur_engine:
            cur_engine.destroy()


class TestGetApplication(TestApplication):
    def test_bad_app_path(self):
        bogus_path = os.path.join(self.tank_temp, "bogus_path")
        
        self.assertRaises(TankError,
                          application.get_application,
                          self.engine, bogus_path, "bogus_app", {})
        
        try:
            application.get_application(self.engine, bogus_path, "bogus_app", {})
        except TankError, cm:
            expected_msg = "Failed to load plugin"
            self.assertTrue(cm.message.startswith(expected_msg))
        
    def test_good_path(self):
        app_path = os.path.join(self.project_config, "test_app")
        # make a dev location and create descriptor
        app_desc = descriptor.get_from_location(descriptor.AppDescriptor.APP, 
                                                self.project_root, 
                                                {"type": "dev", "path": app_path})
        result = application.get_application(self.engine, app_path, app_desc, {})
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
    def test_call_hook(self):
        app = self.engine.apps["test_app"]
        self.assertTrue(app.execute_hook("test_hook", dummy_param=True))

    def test_request_folder(self):
        app = self.engine.apps["test_app"]
        
        path = "/tmp/tank_unit_test_test_request_folder"
    
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
        self.assertTrue(app.execute_hook("test_hook", dummy_param=True))
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
        

