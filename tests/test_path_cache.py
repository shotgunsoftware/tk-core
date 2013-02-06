"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------
"""
import os
import sqlite3

from tank_test.tank_test_base import *

from tank import path_cache
from tank.platform import constants

class TestPathCache(TankTestBase):
    """Base class for path cache tests."""
    def setUp(self):
        super(TestPathCache, self).setUp()
        self.setup_multi_root_fixtures()
        self.path_cache = path_cache.PathCache(self.project_root)

    def tearDown(self):
        self.path_cache.close()
        super(TestPathCache, self).tearDown()

class TestInit(TestPathCache):
    def test_db_exists(self):
        db_path = constants.get_cache_db_location(self.project_root)
        if os.path.exists(db_path):
            self.path_cache.close()
            os.remove(db_path)
        self.assertFalse(os.path.exists(db_path))
        pc = path_cache.PathCache(self.project_root)
        pc.close()
        self.assertTrue(os.path.exists(db_path))

    def test_root_map(self):
        """Test that mapping of project root locations is created"""
        # More specific testing of loading roots happens in test_root
        self.assertIn("primary", self.path_cache.roots)
        self.assertEquals(self.project_root, self.path_cache.roots["primary"])
        

    def test_pass_in_root_mapping(self):
        """Test that if a mapping of project root locations is passed in, it is used."""
        mapping = {'root_name':'root_path'}
        pc_obj = path_cache.PathCache(self.project_root, roots=mapping)
        for root_name, root_path in mapping.items():
            self.assertEquals(root_path, pc_obj.roots[root_name])

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
        self.path_cache.add_mapping(self.entity["type"], self.entity["id"], self.entity["name"], full_path)

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
        self.path_cache.add_mapping(self.entity["type"], self.entity["id"], self.entity["name"], full_path)
        
        # and a second time - this should be fine as the mapping is the same
        self.path_cache.add_mapping(self.entity["type"], self.entity["id"], self.entity["name"], full_path)

        # and a third time - this should be fine as the id and type is the same
        self.path_cache.add_mapping(self.entity["type"], self.entity["id"], "foo", full_path)

        # and a fourth time - this should be bad because id is not matching
        self.assertRaises(tank.TankError, self.path_cache.add_mapping, self.entity["type"], self.entity["id"]+1, "foo", full_path)         

        # finally, make sure that there is exactly a single record in the db representing the path
        res = self.db_cursor.execute("SELECT path, root FROM path_cache WHERE entity_type = ? AND entity_id = ?", (self.entity["type"], self.entity["id"]))
        self.assertEqual( len(res.fetchall()), 1)
        


    def test_multi_entity_path(self):
        """
        Tests that secondary paths can be inserted.
        """
        relative_path = "shot"
        full_path = os.path.join(self.project_root, relative_path)
        self.path_cache.add_mapping(self.entity["type"], self.entity["id"], self.entity["name"], full_path)
        self.path_cache.add_mapping(self.entity["type"], self.entity["id"]+1, self.entity["name"], full_path, primary=False)
        self.path_cache.add_mapping(self.entity["type"], self.entity["id"]+2, self.entity["name"], full_path, primary=False)
        self.path_cache.add_mapping(self.entity["type"], self.entity["id"]+3, self.entity["name"], full_path, primary=False)
        
        # adding the same thing over and over should be fine (but not actually insert anything into the db)
        self.path_cache.add_mapping(self.entity["type"], self.entity["id"]+3, self.entity["name"], full_path, primary=False)
        self.path_cache.add_mapping(self.entity["type"], self.entity["id"]+3, self.entity["name"], full_path, primary=False)
        self.path_cache.add_mapping(self.entity["type"], self.entity["id"]+3, self.entity["name"], full_path, primary=False)
        self.path_cache.add_mapping(self.entity["type"], self.entity["id"]+3, self.entity["name"], full_path, primary=False)

        # get path should return the primary record
        self.assertEquals( self.path_cache.get_entity(full_path), {'type': 'EntityType', 'id': 1, 'name': 'EntityName'} )
        
        # check lookup from other direction
        paths = self.path_cache.get_paths(self.entity["type"], self.entity["id"])
        self.assertEquals( len(paths), 1)
        self.assertEquals( paths[0], full_path)

        paths = self.path_cache.get_paths(self.entity["type"], self.entity["id"]+1)
        self.assertEquals( len(paths), 1)
        self.assertEquals( paths[0], full_path)

        paths = self.path_cache.get_paths(self.entity["type"], self.entity["id"]+2)
        self.assertEquals( len(paths), 1)
        self.assertEquals( paths[0], full_path)

        paths = self.path_cache.get_paths(self.entity["type"], self.entity["id"]+3)
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
        self.path_cache.add_mapping(self.entity["type"], self.entity["id"], self.entity["name"], full_path)

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
        self.path_cache.add_mapping(entity_type, entity_id, entity_name, full_path)

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
        self.path_cache.add_mapping("Project", self.project["id"], self.project["name"], self.project_root)
        self.path_cache.add_mapping("Project", self.project["id"], self.project["name"], self.alt_root_1)
        self.path_cache.add_mapping("Project", self.project["id"], self.project["name"], self.alt_root_2)

    def test_non_project_primary_path(self):
        """Test finding a non-project entity whose path includes the primary project root."""
        shot_path = os.path.join(self.project_root, "seq", "shot_name")
        self.path_cache.add_mapping(self.non_project["type"],
                                    self.non_project["id"],
                                    self.non_project["name"],
                                    shot_path)
        result = self.path_cache.get_entity(shot_path)
        self.assertIsNotNone(result)
        self.assertEquals(self.non_project["type"], result["type"])
        self.assertEquals(self.non_project["id"], result["id"])
        self.assertEquals(self.non_project["name"], result["name"])

    def test_non_project_alternate(self):
        """Test finding a non-project entity whose path includes a non-primary root"""
        shot_path = os.path.join(self.alt_root_1, "seq", "shot_name")
        self.path_cache.add_mapping(self.non_project["type"],
                                    self.non_project["id"],
                                    self.non_project["name"],
                                    shot_path)
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
        self.path_cache.add_mapping("Shot", shot_id, shot_name, primary_shot_path)
        self.path_cache.add_mapping("Shot", shot_id, shot_name, alt_shot_path)
        result = self.path_cache.get_paths("Shot", shot_id)
        self.assertIsNotNone(result)
        self.assertIn(primary_shot_path, result)
        self.assertIn(alt_shot_path, result)

    def test_add_and_find_project(self):
        self.path_cache.add_mapping("Project", self.project["id"], self.project["name"], self.project_root)
        self.path_cache.add_mapping("Project", self.project["id"], self.project["name"], self.alt_root_1)
        result = self.path_cache.get_paths("Project", self.project["id"])
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

        root_name, relative_result = self.path_cache._seperate_root(full_path)
        self.assertEquals("primary", root_name)
        # returns relative path starting with seperator
        self.assertEquals(os.sep + relative_path, relative_result)

