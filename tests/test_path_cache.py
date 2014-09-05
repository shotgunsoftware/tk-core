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
import sqlite3
import shutil

from tank_test.tank_test_base import *

from tank import path_cache
from tank import folder
from tank.platform import constants

def add_item_to_cache(path_cache, entity, path, primary = True):
    
    data = [{"entity": entity, "path": path, "primary": primary, "metadata": {} }]    
    path_cache.add_mappings(data, None, [])    
    

def sync_path_cache(tk, force_full_sync=False):
    """
    Synchronizes the path cache with Shotgun.
    
    :param force_full_sync: Force a full sync. 
    """
    # Use the path cache to look up all paths associated with this entity
    pc = path_cache.PathCache(tk)
    pc.synchronize(log=None, force=force_full_sync)
    pc.close()


class TestPathCache(TankTestBase):
    """Base class for path cache tests."""
    def setUp(self):
        super(TestPathCache, self).setUp()
        self.setup_multi_root_fixtures()
        self.path_cache = path_cache.PathCache(self.tk)

    def tearDown(self):
        self.path_cache.close()
        super(TestPathCache, self).tearDown()

class TestInit(TestPathCache):
    def test_db_exists(self):
        pc = tank.pipelineconfig.from_path(self.project_root)
        db_path = self.tk.get_path_cache_location()
        if os.path.exists(db_path):
            self.path_cache.close()
            os.remove(db_path)
        self.assertFalse(os.path.exists(db_path))
        pc = path_cache.PathCache(self.tk)
        pc.close()
        self.assertTrue(os.path.exists(db_path))

    def test_root_map(self):
        """Test that mapping of project root locations is created"""
        # More specific testing of loading roots happens in test_root
        self.assertIn("primary", self.path_cache._roots)
        self.assertEquals(self.project_root, self.path_cache._roots["primary"])
        
    def test_db_columns(self):
        """Test that expected columns are created in db"""
        expected = ["entity_type", "entity_id", "entity_name", "root", "path", "primary_entity"]
        self.db_cursor = self.path_cache._connection.cursor()
        ret = self.db_cursor.execute("PRAGMA table_info(path_cache)")
        column_names = [x[1] for x in ret.fetchall()]
        self.assertEquals(expected, column_names)



class TestAddMapping(TestPathCache):
    def setUp(self):
        super(TestAddMapping, self).setUp()

        # entity for testing
        self.entity = {"type":"EntityType",
                       "id":1,
                       "name":"EntityName"}

        # get db connection
        self.db_cursor = self.path_cache._connection.cursor()

    def test_primary_path(self):
        """
        Case path to add has primary project as root.
        """
        relative_path = "shot"
        full_path = os.path.join(self.project_root, relative_path)
        add_item_to_cache(self.path_cache, self.entity, full_path)

        res = self.db_cursor.execute("SELECT path, root FROM path_cache WHERE entity_type = ? AND entity_id = ?", (self.entity["type"], self.entity["id"]))
        entry = res.fetchall()[0]
        self.assertEquals("/shot", entry[0])
        self.assertEquals("primary", entry[1])

    def test_dupe_failure(self):
        """
        Test that the system fails if two paths are inserted.
        """
        relative_path = "shot"
        full_path = os.path.join(self.project_root, relative_path)
        add_item_to_cache(self.path_cache, self.entity, full_path)
        
        # and a second time - this should be fine as the mapping is the same
        add_item_to_cache(self.path_cache, self.entity, full_path)

        # and a third time - this should be fine as the id and type is the same
        ne = {"type": self.entity["type"], "id": self.entity["id"], "name": "foo"}
        add_item_to_cache(self.path_cache, ne, full_path)

        # and a fourth time - this should be bad because id is not matching
        ne2 = {"type": self.entity["type"], "id": self.entity["id"]+1, "name": "foo"}
        self.assertRaises(tank.TankError, add_item_to_cache, self.path_cache, ne2, full_path)         

        # finally, make sure that there is exactly a single record in the db representing the path
        res = self.db_cursor.execute("SELECT path, root FROM path_cache WHERE entity_type = ? AND entity_id = ?", (self.entity["type"], self.entity["id"]))
        self.assertEqual( len(res.fetchall()), 1)
        


    def test_multi_entity_path(self):
        """
        Tests that secondary paths can be inserted.
        """
        relative_path = "shot"
        full_path = os.path.join(self.project_root, relative_path)
        
        et = self.entity["type"]
        eid = self.entity["id"]
        en = self.entity["name"] 
        
        add_item_to_cache(self.path_cache, {"type": et, "id": eid, "name": en}, full_path)
        add_item_to_cache(self.path_cache, {"type": et, "id": eid+1, "name": en}, full_path, primary=False)
        add_item_to_cache(self.path_cache, {"type": et, "id": eid+2, "name": en}, full_path, primary=False)
        add_item_to_cache(self.path_cache, {"type": et, "id": eid+3, "name": en}, full_path, primary=False)
        
        # adding the same thing over and over should be fine (but not actually insert anything into the db)
        add_item_to_cache(self.path_cache, {"type": et, "id": eid+3, "name": en}, full_path, primary=False)
        add_item_to_cache(self.path_cache, {"type": et, "id": eid+3, "name": en}, full_path, primary=False)
        add_item_to_cache(self.path_cache, {"type": et, "id": eid+3, "name": en}, full_path, primary=False)
        add_item_to_cache(self.path_cache, {"type": et, "id": eid+3, "name": en}, full_path, primary=False)
        add_item_to_cache(self.path_cache, {"type": et, "id": eid+3, "name": en}, full_path, primary=False)
        
        # get path should return the primary record
        self.assertEquals( self.path_cache.get_entity(full_path), {'type': 'EntityType', 'id': 1, 'name': 'EntityName'} )
        
        # check lookup from other direction
        paths = self.path_cache.get_paths(self.entity["type"], self.entity["id"], primary_only=True)
        self.assertEquals( len(paths), 1)
        self.assertEquals( paths[0], full_path)

        paths = self.path_cache.get_paths(self.entity["type"], self.entity["id"]+1, primary_only=True)
        self.assertEquals( len(paths), 0)

        paths = self.path_cache.get_paths(self.entity["type"], self.entity["id"]+1, primary_only=False)
        self.assertEquals( len(paths), 1)
        self.assertEquals( paths[0], full_path)

        paths = self.path_cache.get_paths(self.entity["type"], self.entity["id"]+2, primary_only=False)
        self.assertEquals( len(paths), 1)
        self.assertEquals( paths[0], full_path)

        paths = self.path_cache.get_paths(self.entity["type"], self.entity["id"]+3, primary_only=False)
        self.assertEquals( len(paths), 1)
        self.assertEquals( paths[0], full_path)

        # finally, make sure that there no dupe records
        res = self.db_cursor.execute("SELECT path, root FROM path_cache WHERE entity_type = ? AND entity_id = ?", (self.entity["type"], self.entity["id"]+3))
        self.assertEqual( len(res.fetchall()), 1)



    def test_non_primary_path(self):
        """
        Case path to add has alternate (non-primary) project as root.
        """
        relative_path = "shot"
        full_path = os.path.join(self.alt_root_1, relative_path)
        add_item_to_cache(self.path_cache, self.entity, full_path)

        res = self.db_cursor.execute("SELECT path, root FROM path_cache WHERE entity_type = ? AND entity_id = ?", (self.entity["type"], self.entity["id"]))
        entry = res.fetchall()[0]
        self.assertEquals("/shot", entry[0])
        self.assertEquals("alternate_1", entry[1])

    def test_add_utf_name(self):
        """
        utf-8 characters in name. As per Bug #18289.
        """
        relative_path = "shot_1"
        full_path = os.path.join(self.project_root, relative_path)
        entity_type = "Shot"
        entity_id = 12
        entity_name = "someunicode\xe8"
        add_item_to_cache(self.path_cache, {"name":entity_name, "id":entity_id, "type":entity_type}, full_path)

        res = self.db_cursor.execute("SELECT entity_name FROM path_cache WHERE entity_type = ? AND entity_id = ?", (entity_type, entity_id))
        entry = res.fetchall()[0]
        self.assertEquals(entity_name, entry[0])


class TestGetEntity(TestPathCache):
    """
    Tests for get_entity. 
    Project and non-project entities are stored differently so tests are seperated between the two.
    """
    def setUp(self):
        super(TestGetEntity, self).setUp()
        self.non_project = {"type":"NonProjectEntity",
                            "id":999,
                            "name":"NonProjectName"}
        # adding project roots
        
        proj = {"type": "Project", "id": self.project["id"], "name": self.project["name"] }
        add_item_to_cache(self.path_cache, proj, self.project_root)
        add_item_to_cache(self.path_cache, proj, self.alt_root_1)
        add_item_to_cache(self.path_cache, proj, self.alt_root_2)        

    def test_non_project_primary_path(self):
        """Test finding a non-project entity whose path includes the primary project root."""
        shot_path = os.path.join(self.project_root, "seq", "shot_name")
        
        non_proj = {"type": self.non_project["type"], "id": self.non_project["id"], "name": self.non_project["name"] }
        add_item_to_cache(self.path_cache, non_proj, shot_path)        
        
        result = self.path_cache.get_entity(shot_path)
        self.assertIsNotNone(result)
        self.assertEquals(self.non_project["type"], result["type"])
        self.assertEquals(self.non_project["id"], result["id"])
        self.assertEquals(self.non_project["name"], result["name"])

    def test_non_project_alternate(self):
        """Test finding a non-project entity whose path includes a non-primary root"""
        shot_path = os.path.join(self.alt_root_1, "seq", "shot_name")
        
        non_proj = {"type": self.non_project["type"], "id": self.non_project["id"], "name": self.non_project["name"] }
        add_item_to_cache(self.path_cache, non_proj, shot_path)        
                
        result = self.path_cache.get_entity(shot_path)
        self.assertIsNotNone(result)
        self.assertEquals(self.non_project["type"], result["type"])
        self.assertEquals(self.non_project["id"], result["id"])
        self.assertEquals(self.non_project["name"], result["name"])

    def test_add_and_find_project_primary_root(self):
        result = self.path_cache.get_entity(self.project_root)
        self.assertIsNotNone(result)
        self.assertEquals("Project", result["type"])
        self.assertEquals(self.project["id"], result["id"])

    def test_add_and_find_project_non_primary_root(self):
        result = self.path_cache.get_entity(self.alt_root_1)
        self.assertIsNotNone(result)
        self.assertEquals("Project", result["type"])
        self.assertEquals(self.project["id"], result["id"])

    def test_non_project_path(self):
        non_project_path = os.path.join("path", "not", "in", "project")
        result = self.path_cache.get_entity(non_project_path)
        self.assertIsNone(result)


class TestGetPaths(TestPathCache):
    def test_add_and_find_shot(self):
        # add two paths to cache for a shot
        shot_id = 999
        shot_name = "shot_name"
        primary_shot_path = os.path.join(self.project_root, "seq", shot_name)
        alt_shot_path = os.path.join(self.alt_root_1, "seq", shot_name)
        
        e = {"type": "Shot", "id": shot_id, "name": shot_name }
        
        add_item_to_cache(self.path_cache, e, primary_shot_path)
        add_item_to_cache(self.path_cache, e, alt_shot_path)
                
        result = self.path_cache.get_paths("Shot", shot_id, primary_only=True)
        self.assertIsNotNone(result)
        self.assertIn(primary_shot_path, result)
        self.assertIn(alt_shot_path, result)

    def test_add_and_find_project(self):
        
        e = {"type": "Project", "id": self.project["id"], "name": self.project["name"] }
        add_item_to_cache(self.path_cache, e, self.project_root)
        add_item_to_cache(self.path_cache, e, self.alt_root_1)
        
        result = self.path_cache.get_paths("Project", self.project["id"], primary_only=True)
        self.assertIsNotNone(result)
        self.assertIn(self.project_root, result)
        self.assertIn(self.alt_root_1, result)

class Test_SeperateRoots(TestPathCache):
    def test_different_case(self):
        """
        Case that input path uses different case than roots.
        """
        relative_path = os.path.join("Some", "Path")
        full_path = os.path.join(self.project_root.swapcase(), relative_path)

        root_name, relative_result = self.path_cache._separate_root(full_path)
        self.assertEquals("primary", root_name)
        # returns relative path starting with seperator
        self.assertEquals(os.sep + relative_path, relative_result)


class TestShotgunSync(TankTestBase):
    
    def setUp(self, project_tank_name = "project_code"):
        """Sets up entities in mocked shotgun database and creates Mock objects
        to pass in as callbacks to Schema.create_folders. The mock objects are
        then queried to see what paths the code attempted to create.
        """
        super(TestShotgunSync, self).setUp(project_tank_name)
        self.setup_fixtures()
        
        self.seq = {"type": "Sequence",
                    "id": 2,
                    "code": "seq_code",
                    "project": self.project}
        self.shot = {"type": "Shot",
                     "id": 1,
                     "code": "shot_code",
                     "sg_sequence": self.seq,
                     "project": self.project}
        self.step = {"type": "Step",
                     "id": 3,
                     "code": "step_code",
                     "entity_type": "Shot",
                     "short_name": "step_short_name"}
        self.task = {"type": "Task",
                     "id": 4,
                     "entity": self.shot,
                     "step": self.step,
                     "project": self.project}

        entities = [self.shot, self.seq, self.step, self.project, self.task]

        # Add these to mocked shotgun
        self.add_to_sg_mock_db(entities)

        self.schema_location = os.path.join(self.project_root, "tank", "config", "core", "schema")

    def _get_path_cache(self):
        path_cache = tank.path_cache.PathCache(self.tk)
        c = path_cache._connection.cursor()
        cache = list(c.execute("select * from path_cache" ))
        c.close()
        path_cache.close()
        return cache


    def test_shot(self):
        """Test full and incremental path cache sync."""
        
        self.assertEqual(len(self.tk.shotgun.find(tank.path_cache.SHOTGUN_ENTITY, [])), 1)        
        self.assertEqual( len(self._get_path_cache()), 1)
        
        
        folder.process_filesystem_structure(self.tk, 
                                            self.seq["type"], 
                                            self.seq["id"], 
                                            preview=False,
                                            engine=None)        
        
        # now have project / seq 
        self.assertEqual(len(self.tk.shotgun.find(tank.path_cache.SHOTGUN_ENTITY, [])), 2)
        self.assertEqual( len(self._get_path_cache()), 2)
                
        # nothing should happen
        sync_path_cache(self.tk)
        self.assertEqual(len(self.tk.shotgun.find(tank.path_cache.SHOTGUN_ENTITY, [])), 2)
        self.assertEqual( len(self._get_path_cache()), 2)

        # make a copy of the path cache at this point
        pcl = self.tk.get_path_cache_location()
        shutil.copy(pcl, "%s.snap1" % pcl) 

        # now insert a new path in Shotgun
        folder.process_filesystem_structure(self.tk, 
                                            self.task["type"], 
                                            self.task["id"], 
                                            preview=False,
                                            engine=None)        
        
        # now have project / seq / shot / step 
        self.assertEqual(len(self.tk.shotgun.find(tank.path_cache.SHOTGUN_ENTITY, [])), 4)
        self.assertEqual( len(self._get_path_cache()), 4)
        path_cache_contents_1 = self._get_path_cache()
        
        # now replace our path cache with snap1
        shutil.copy(pcl, "%s.snap2" % pcl) 
        shutil.copy("%s.snap1" % pcl, pcl)
        
        # now path cache has not been synchronized but shotgun has an entry
        self.assertEqual(len(self.tk.shotgun.find(tank.path_cache.SHOTGUN_ENTITY, [])), 4)
        self.assertEqual( len(self._get_path_cache()), 2)
        sync_path_cache(self.tk)
        
        # check that the sync happend
        self.assertEqual(len(self.tk.shotgun.find(tank.path_cache.SHOTGUN_ENTITY, [])), 4)
        self.assertEqual( len(self._get_path_cache()), 4)
        
        # and that the content is the same
        path_cache_contents_2 = self._get_path_cache()
        self.assertEqual(path_cache_contents_2, path_cache_contents_1)
        
        # now clear the path cache completely. This should trigger a full flush
        os.remove(pcl)
        sync_path_cache(self.tk)
        
        # check that the sync happend
        self.assertEqual(len(self.tk.shotgun.find(tank.path_cache.SHOTGUN_ENTITY, [])), 4)
        self.assertEqual( len(self._get_path_cache()), 4)
        
        # and that the content is the same
        path_cache_contents_3 = self._get_path_cache()
        self.assertEqual(path_cache_contents_3, path_cache_contents_1)
        
        
        
        
class TestShotgunSync013AutoPush(TankTestBase):
    
    def setUp(self, project_tank_name = "project_code"):

        super(TestShotgunSync013AutoPush, self).setUp(project_tank_name)
        self.setup_fixtures()
        
        self.seq = {"type": "Sequence",
                    "id": 2,
                    "code": "seq_code",
                    "project": self.project}
        self.shot = {"type": "Shot",
                     "id": 1,
                     "code": "shot_code",
                     "sg_sequence": self.seq,
                     "project": self.project}
        self.step = {"type": "Step",
                     "id": 3,
                     "code": "step_code",
                     "entity_type": "Shot",
                     "short_name": "step_short_name"}
        self.task = {"type": "Task",
                     "id": 4,
                     "entity": self.shot,
                     "step": self.step,
                     "project": self.project}

        entities = [self.shot, self.seq, self.step, self.project, self.task]

        # Add these to mocked shotgun
        self.add_to_sg_mock_db(entities)

        self.schema_location = os.path.join(self.project_root, "tank", "config", "core", "schema")

    def _get_path_cache(self):
        path_cache = tank.path_cache.PathCache(self.tk)
        c = path_cache._connection.cursor()
        cache = list(c.execute("select * from path_cache" ))
        c.close()
        path_cache.close()
        return cache

    def _get_status_table(self):
        path_cache = tank.path_cache.PathCache(self.tk)
        c = path_cache._connection.cursor()
        cache = list(c.execute("select * from shotgun_status" ))
        c.close()
        path_cache.close()
        return cache


    def test_shot(self):
        """Test full and incremental path cache sync."""
        
        self.assertEqual(len(self.tk.shotgun.find(tank.path_cache.SHOTGUN_ENTITY, [])), 1)        
        self.assertEqual( len(self._get_path_cache()), 1)
        
        
        folder.process_filesystem_structure(self.tk, 
                                            self.task["type"], 
                                            self.task["id"], 
                                            preview=False,
                                            engine=None)        
        
        # now have project / seq / shot / step 
        self.assertEqual(len(self.tk.shotgun.find(tank.path_cache.SHOTGUN_ENTITY, [])), 4)
        self.assertEqual( len(self._get_path_cache()), 4)
        self.assertEqual( len(self._get_status_table()), 4)
                
        # now remove items from the pc sync table to simulate a 0.13 entry
        path_cache = tank.path_cache.PathCache(self.tk)
        c = path_cache._connection.cursor()
        c.execute("delete from shotgun_status" )
        path_cache._connection.commit()
        c.close()
        path_cache.close()
                
        # synchronize should trigger a push to sg
        # and introduce duplicated on the shotgun side
        # but not in the path cache
        sync_path_cache(self.tk)
        self.assertEqual(len(self.tk.shotgun.find(tank.path_cache.SHOTGUN_ENTITY, [])), 8)
        self.assertEqual( len(self._get_path_cache()), 4)
        
        # further syncs should not affect the setup
        sync_path_cache(self.tk)
        self.assertEqual(len(self.tk.shotgun.find(tank.path_cache.SHOTGUN_ENTITY, [])), 8)
        self.assertEqual( len(self._get_path_cache()), 4)

        # full sync should be consistent
        sync_path_cache(self.tk, force_full_sync=True)
        self.assertEqual(len(self.tk.shotgun.find(tank.path_cache.SHOTGUN_ENTITY, [])), 8)
        self.assertEqual( len(self._get_path_cache()), 4)
        

        
        
        
        
        
        
        
        

        
        
