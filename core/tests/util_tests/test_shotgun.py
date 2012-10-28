"""
Copyright (c) 2012 Shotgun Software, Inc
"""
import os
import datetime

from mock import Mock, patch

import tank
from tank import context
from tank import TankError
from tank_test.tank_test_base import *
from tank.template import TemplatePath
from tank.templatekey import SequenceKey


class TestShotgunFindPublish(TankTestBase):
    
    def setUp(self):
        """Sets up entities in mocked shotgun database and creates Mock objects
        to pass in as callbacks to Schema.create_folders. The mock objects are
        then queried to see what paths the code attempted to create.
        """
        super(TestShotgunFindPublish, self).setUp()
        
        #self.setup_fixtures()
        self.setup_multi_root_fixtures()

        self.storage_1 = {"type": "LocalStorage", "id": 1, "code": "Tank"}
        self.storage_2 = {"type": "LocalStorage", "id": 43, "code": "alternate_1"}
        
        project_name = os.path.basename(self.project_root)
        # older publish to test we get the latest
        self.pub_1 = {"type": "TankPublishedFile",
                    "id": 1,
                    "code": "hello",
                    "path_cache": "%s/foo/bar" % project_name,
                    "created_at": datetime.datetime(2012, 10, 12, 12, 1),
                    "path_cache_storage": {"type": "LocalStorage", "id": 1, "code": "Tank"}}

        # publish matching older publish
        self.pub_2 = {"type": "TankPublishedFile",
                    "id": 2,
                    "code": "more recent",
                    "path_cache": "%s/foo/bar" % project_name,
                    "created_at": datetime.datetime(2012, 10, 13, 12, 1),
                    "path_cache_storage": {"type": "LocalStorage", "id": 1, "code": "Tank"}}
        
        self.pub_3 = {"type": "TankPublishedFile",
                    "id": 3,
                    "code": "world",
                    "path_cache": "%s/foo/baz" % project_name,
                    "created_at": datetime.datetime(2012, 10, 13, 12, 2),
                    "path_cache_storage": {"type": "LocalStorage", "id": 1, "code": "Tank"}}

        # sequence publish
        self.pub_4 = {"type": "TankPublishedFile",
                    "id": 4,
                    "code": "sequence_file",
                    "path_cache": "%s/foo/seq_%%03d.ext" % project_name,
                    "created_at": datetime.datetime(2012, 10, 13, 12, 2),
                    "path_cache_storage": {"type": "LocalStorage", "id": 1, "code": "Tank"}}


        self.pub_5 = {"type": "TankPublishedFile",
                    "id": 5,
                    "code": "other storage",
                    "path_cache": "foo/bar",
                    "created_at": datetime.datetime(2012, 10, 12, 12, 1),
                    "path_cache_storage": {"type": "LocalStorage", "id": 43, "code": "alternate_1"}}

        # Add these to mocked shotgun
        self.add_to_sg_mock_db([self.storage_1, self.storage_2, 
                                self.pub_1, self.pub_2, self.pub_3, self.pub_4, self.pub_5])
        self.tk = tank.Tank(self.project_root)
        self.tk._tank__sg = self.sg_mock

    def test_find(self):        
        paths = [os.path.join(self.project_root, "foo", "bar")]
        d = tank.util.find_publish(self.tk, paths)
        self.assertEqual(len(d), 1)
        self.assertEqual(d.keys(), paths)
        # make sure we got the latest matching publish
        sg_data = d.get(paths[0])
        self.assertEqual(sg_data["id"], self.pub_2["id"])
        # make sure we are only getting the ID back.
        self.assertEqual(sg_data.keys(), ["id"])

    def test_most_recent_path(self):
        # check that dupes return the more recent record        
        paths = [os.path.join(self.project_root, "foo", "bar")]
        d = tank.util.find_publish(self.tk, paths, fields=["code"])
        self.assertEqual(len(d), 1)
        sg_data = d.get(paths[0])
        self.assertEqual(sg_data["code"], "more recent")

    def test_missing_paths(self):
        paths = [os.path.join(self.project_root, "foo", "bar"),
                 os.path.join("tmp", "foo")]
        d = tank.util.find_publish(self.tk, paths)
        self.assertEqual(len(d), 1)
        self.assertEqual(d.keys(), [ paths[0] ])

    def test_sequence_path(self):
        # make sequence template matching sequence publish
        keys = {"seq": SequenceKey("seq", format_spec="03")}
        template = TemplatePath("foo/seq_{seq}.ext", keys, self.project_root)
        self.tk.templates["sequence_test"] = template
        paths = [os.path.join(self.project_root, "foo", "seq_002.ext")]
        d = tank.util.find_publish(self.tk, paths)
        self.assertEqual(len(d), 1)
        self.assertEqual(d.keys(), [ paths[0] ])
        sg_data = d.get(paths[0])
        self.assertEqual(sg_data["id"], self.pub_4["id"])

    def test_abstracted_sequence_path(self):
        # make sequence template matching sequence publish
        keys = {"seq": SequenceKey("seq", format_spec="03")}
        template = TemplatePath("foo/seq_{seq}.ext", keys, self.project_root)
        self.tk.templates["sequence_test"] = template
        paths = [os.path.join(self.project_root, "foo", "seq_%03d.ext")]
        d = tank.util.find_publish(self.tk, paths)
        self.assertEqual(len(d), 1)
        self.assertEqual(d.keys(), [ paths[0] ])
        sg_data = d.get(paths[0])
        self.assertEqual(sg_data["id"], self.pub_4["id"])

#    def test_multi_root(self):        
#        paths = [os.path.join(self.alt_root_1, "foo", "bar")]
#        d = tank.util.find_publish(self.tk, paths)
#        print "find publish returned: %s" % d
#        self.assertEqual(len(d), 1)
#        self.assertEqual(d.keys(), paths)
#        # make sure we got the latest matching publish
#        sg_data = d.get(paths[0])
#        self.assertEqual(sg_data["id"], self.pub_5["id"])
#        # make sure we are only getting the ID back.
#        self.assertEqual(sg_data.keys(), ["id"])



class TestShotgunRegisterPublish(TankTestBase):
    def setUp(self):
        """Sets up entities in mocked shotgun database and creates Mock objects
        to pass in as callbacks to Schema.create_folders. The mock objects are
        then queried to see what paths the code attempted to create.
        """
        super(TestShotgunRegisterPublish, self).setUp()
        
        self.setup_fixtures()

        self.storage = {"type": "LocalStorage", "id": 1, "code": "Tank"}

        self.tank_type_1 = {"type": "TankType",
            "id": 1,
            "code": "Maya Scene"
        }

        # Add these to mocked shotgun
        self.add_to_sg_mock_db([self.storage, self.tank_type_1])
        self.tk = tank.Tank(self.project_root)
        self.tk.__tank_sg = self.sg_mock

        self.shot = {"type": "Shot",
                    "name": "shot_name",
                    "id": 2,
                    "project": self.project}
        self.step = {"type": "Step", "name": "step_name", "id": 4}

        context_data = {
            "tk": self.tk,
            "project": self.project,
            "entity": self.shot,
            "step": self.step,
        }

        self.context = context.Context(**context_data)
        self.path = os.path.join(self.project_root, "foo", "bar")
        self.name = "Test Publish"
        self.version = 1

    def test_register_publish_with_missing_tank_type(self):
        self.assertRaises(
            TankError, 
            tank.util.register_publish, 
            self.tk, 
            self.context, 
            self.path, 
            self.name, 
            self.version, 
            tank_type="Missing Type"
        )

    def test_sequence_abstracted_path(self):
        """Test that if path supplied represents a sequence, the abstract version of that
        sequence is used."""
        tk = tank.Tank(self.project_root)
        # mock shotgun
        tk._tank__sg = Mock()

        # make sequence key
        keys = { "seq": tank.templatekey.SequenceKey("seq", format_spec="03")}
        # make sequence template
        seq_template = tank.template.TemplatePath("/folder/name_{seq}.ext", keys, self.project_root)
        tk.templates["sequence_template"] = seq_template

        seq_path = os.path.join(self.project_root, "folder", "name_001.ext")

        # mock sg.create, check it for path value
        tank.util.register_publish(tk, self.context, seq_path, self.name, self.version)

        # check that path is modified before sent to shotgun
        expected_path = os.path.join(self.project_root, "folder", "name_%03d.ext")
        project_name = os.path.basename(self.project_root)
        expected_path_cache = "%s/%s/%s" % (project_name, "folder", "name_%03d.ext")

        # look at values sent to the Mocked shotgun.create
        actual_path = tk.shotgun.create.call_args[0][1]["path"]["local_path"]
        actual_path_cache = tk.shotgun.create.call_args[0][1]["path_cache"]

        self.assertEqual(expected_path, actual_path)
        self.assertEqual(expected_path_cache, actual_path_cache)



class TestCalcPathCache(TankTestBase):
    @patch("tank.root.get_project_roots")
    def test_case_difference(self, get_project_roots):
        """
        Case that root case is different between input path and that in roots file.
        Bug Ticket #18116
        """
        get_project_roots.return_value = {"primary" : self.project_root}
        relative_path = os.path.join("Some","Path")
        wrong_case_root = self.project_root.swapcase()
        expected = os.path.join(os.path.basename(wrong_case_root), relative_path).replace(os.sep, "/")

        input_path = os.path.join(wrong_case_root, relative_path)
        root_name, path_cache = tank.util.shotgun._calc_path_cache(self.project_root, input_path)
        self.assertEqual("primary", root_name)
        self.assertEqual(expected, path_cache)


