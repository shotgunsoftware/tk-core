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
import sys
import time
import Queue
import StringIO
import shutil
import contextlib
import logging

from mock import Mock

from tank_test.tank_test_base import TankTestBase, temp_env_var
from tank_test.tank_test_base import setUpModule # noqa

from tank import path_cache
from tank import folder
from tank import constants
from tank import LogManager
import tank

log = LogManager.get_logger(__name__)


def add_item_to_cache(path_cache, entity, path, primary=True):
    data = [{"entity": entity, "path": path, "primary": primary, "metadata": {}}]
    # Last two parameters are only used for debug logging, they can be empty.
    path_cache.add_mappings(data, None, [])


def sync_path_cache(tk, force_full_sync=False):
    """
    Synchronizes the path cache with Shotgun.
    
    :param force_full_sync: Force a full sync.
    :returns: log output in a variable 
    """
    
    # capture sync log to string
    stream = StringIO.StringIO()
    handler = logging.StreamHandler(stream)
    log = logging.getLogger("sgtk.core.path_cache")
    log.setLevel(logging.DEBUG)
    log.addHandler(handler)
    
    # Use the path cache to look up all paths associated with this entity
    pc = path_cache.PathCache(tk)
    pc.synchronize(force_full_sync)
    pc.close()

    log_contents = stream.getvalue()
    stream.close()
    log.removeHandler(handler)
    return log_contents


class TestPathCache(TankTestBase):
    """Base class for path cache tests."""
    def setUp(self):
        super(TestPathCache, self).setUp()
        self.setup_multi_root_fixtures()
        self.path_cache = path_cache.PathCache(self.tk)
        self.path_cache_location = self.path_cache._get_path_cache_location()

    def tearDown(self):
        self.path_cache.close()
        super(TestPathCache, self).tearDown()

class TestInit(TestPathCache):
    
    def test_db_exists(self):
        
        if os.path.exists(self.path_cache_location):
            self.path_cache.close()
            os.remove(self.path_cache_location)
        self.assertFalse(os.path.exists(self.path_cache_location))
        pc = path_cache.PathCache(self.tk)
        pc.close()
        self.assertTrue(os.path.exists(self.path_cache_location))

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

        self.schema_location = os.path.join(self.pipeline_config_root, "config", "core", "schema")

    def _get_path_cache(self):
        path_cache = tank.path_cache.PathCache(self.tk)
        c = path_cache._connection.cursor()
        cache = list(c.execute("select * from path_cache" ))
        c.close()
        path_cache.close()
        return cache


    def test_shot(self):
        """Test full and incremental path cache sync."""
        
        path_cache = tank.path_cache.PathCache(self.tk)
        pcl = path_cache._get_path_cache_location()
        path_cache.close()
        
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
        log = sync_path_cache(self.tk)
        self.assertTrue("Performing a complete Shotgun folder sync" in log)
        
        # check that the sync happend
        self.assertEqual(len(self.tk.shotgun.find(tank.path_cache.SHOTGUN_ENTITY, [])), 4)
        self.assertEqual( len(self._get_path_cache()), 4)
        
        # and that the content is the same
        path_cache_contents_3 = self._get_path_cache()
        self.assertEqual(path_cache_contents_3, path_cache_contents_1)
        
        
        
        
        
        
    def test_no_new_folders_created(self):
        """
        Test the case when folder creation is running for an already existing path 
        """        
        
        # we should have one Toolkit_Folders_Create record in the path cache,
        # coming from the project setup
        folder_events = self.tk.shotgun.find("EventLogEntry", [["event_type", "is", "Toolkit_Folders_Create"]])
        self.assertEqual(len(folder_events), 1)
        
        folder.process_filesystem_structure(self.tk,
                                            self.seq["type"], 
                                            self.seq["id"],
                                            preview=False,
                                            engine=None)        
        
        # a seq should have been added to the path cache and we should have two events
        folder_events = self.tk.shotgun.find("EventLogEntry", [["event_type", "is", "Toolkit_Folders_Create"]])
        self.assertEqual(len(folder_events), 2)

        # running this again, no folders should be created and no events should be generated
        folder.process_filesystem_structure(self.tk,
                                            self.seq["type"], 
                                            self.seq["id"],
                                            preview=False,
                                            engine=None)        

        folder_events = self.tk.shotgun.find("EventLogEntry", [["event_type", "is", "Toolkit_Folders_Create"]])
        self.assertEqual(len(folder_events), 2)
        




    def test_incremental_sync(self):
        """Tests that the incremental sync kicks in when possible."""

        # get the location of the pc
        path_cache = tank.path_cache.PathCache(self.tk)
        pcl = path_cache._get_path_cache_location()
        path_cache.close()
        
        # now process the sequence level folder creation
        folder.process_filesystem_structure(self.tk, 
                                            self.seq["type"], 
                                            self.seq["id"], 
                                            preview=False,
                                            engine=None)        
        
        # now have project and sequence in the path cache 
        self.assertEqual(len(self.tk.shotgun.find(tank.path_cache.SHOTGUN_ENTITY, [])), 2)
        self.assertEqual( len(self._get_path_cache()), 2)
                
        # make a copy of the path cache at this point
        shutil.copy(pcl, "%s.snap1" % pcl) 

        # now create folders down to task level 
        folder.process_filesystem_structure(self.tk, 
                                            self.task["type"], 
                                            self.task["id"], 
                                            preview=False,
                                            engine=None)        
        
        # now have project / seq / shot / step 
        self.assertEqual(len(self.tk.shotgun.find(tank.path_cache.SHOTGUN_ENTITY, [])), 4)
        self.assertEqual( len(self._get_path_cache()), 4)
        
        # now replace our path cache file with with snap1
        # so that we have a not-yet-up to date path cache file. 
        shutil.copy("%s.snap1" % pcl, pcl)
        self.assertEqual( len(self._get_path_cache()), 2)
        
        # now we run the sync - and this sync should be incremental 
        log = sync_path_cache(self.tk)
        # make sure the log mentions an incremental sync
        self.assertTrue( "Doing an incremental sync" in log )
        # and make sure the sync generated new records
        self.assertEqual( len(self._get_path_cache()), 4)


    def test_missing_roots_mapping(self):
        """
        Tests that invalid roots.yml lookups result in ignored records 
        """        
        
        # create folders 
        folder.process_filesystem_structure(self.tk, 
                                            self.task["type"], 
                                            self.task["id"], 
                                            preview=False,
                                            engine=None)  
        
        self.assertEqual(len(self.tk.shotgun.find(tank.path_cache.SHOTGUN_ENTITY, [])), 4)
        self.assertEqual( len(self._get_path_cache()), 4)
        
        roots_yml = os.path.join(self.pipeline_config_root, 
                                 "config", 
                                 "core", 
                                 constants.STORAGE_ROOTS_FILE)
        
        # construct an invalid roots.yml that is out of sync with the records coming from
        current_roots = self.pipeline_configuration._roots
        invalid_roots = {
            "primary": tank.util.ShotgunPath.from_shotgun_dict(
                {"linux_path": "/invalid",
                 "mac_path": "/invalid",
                 "windows_path": "X:\\invalid"
                 }
            )
        }
        
        self.pipeline_configuration._roots = invalid_roots
        
        # perform a full sync
        log = sync_path_cache(self.tk, force_full_sync=True)
        self.assertTrue("Could not resolve storages - skipping" in log)
        self.assertEqual( len(self._get_path_cache()), 0)
        
        # and set roots back again and check 
        self.pipeline_configuration._roots = current_roots
        # perform a full sync
        log = sync_path_cache(self.tk, force_full_sync=True)
        self.assertTrue("Could not resolve storages - skipping" not in log)
        self.assertEqual( len(self._get_path_cache()), 4)


    def test_truncated_eventlog(self):
        """Tests that a full sync happens if the event log is truncated."""

        
        # now create folders down to task level 
        folder.process_filesystem_structure(self.tk, 
                                            self.task["type"], 
                                            self.task["id"], 
                                            preview=False,
                                            engine=None)        

        # truncate the event log
        self.tk.shotgun._db["EventLogEntry"] = {}
        
        # now have FilesystemLocations but no EventLogEntries
        self.assertEqual(len(self.tk.shotgun.find(tank.path_cache.SHOTGUN_ENTITY, [])), 4)
        self.assertEqual(len(self.tk.shotgun.find("EventLogEntry", [])), 0)

        # check that this triggers a full sync        
        log = sync_path_cache(self.tk)
        self.assertTrue("Performing a complete Shotgun folder sync" in log)



    def test_multiple_projects_eventlog(self):
        """
        Tests that projects don't get their path caches mixed up.

        This tests that the path cache for a project isn't influenced
        or affected by filesystem locations and event logs created
        by other projects.
        """

        # now create folders down to task level
        folder.process_filesystem_structure(self.tk,
                                            self.task["type"],
                                            self.task["id"],
                                            preview=False,
                                            engine=None)

        # simulate event from other project inserted
        sg_proj = self.tk.shotgun.create("Project", {"name": "other_project"})
        sg_data = {
            'description': 'Toolkit HEAD: Created folders on disk for Tasks with id: 888',
            'entity': {'id': 666, 'type': 'PipelineConfiguration'},
            'event_type': 'Toolkit_Folders_Create',
            'meta': {'core_api_version': 'HEAD', 'sg_folder_ids': [768]},
            'project': sg_proj
        }
        for x in range(100):
            self.tk.shotgun.create("EventLogEntry", sg_data)

        # now delete our path cache so that next time, a full sync is done
        path_cache = tank.path_cache.PathCache(self.tk)
        path_cache_location = path_cache._get_path_cache_location()
        path_cache.close()
        os.remove(path_cache_location)

        # now because we deleted our path cache, we will do a full sync
        log = sync_path_cache(self.tk)
        self.assertTrue("Performing a complete Shotgun folder sync" in log)

        # now if we sync again, this should be incremental and the sync
        # should detect that there are no new entries for this project,
        # even though there are new entries for other projects.
        log = sync_path_cache(self.tk)
        self.assertTrue("Path cache syncing not necessary" in log)



class TestConcurrentShotgunSync(TankTestBase):
    """
    Tests that the path cache can gracefully handle multiple
    clients cocurrently synchronizing with it
    """

    def setUp(self, project_tank_name = "project_code"):
        """Sets up entities in mocked shotgun database and creates Mock objects
        to pass in as callbacks to Schema.create_folders. The mock objects are
        then queried to see what paths the code attempted to create.
        """
        super(TestConcurrentShotgunSync, self).setUp(project_tank_name)
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

        self._multiprocess_fail = False

    def concurrent_full_sync(self):
        """
        Run full sync 20 times
        """
        try:
            for x in range(20):
                self.tk.synchronize_filesystem_structure(True)
        except Exception, e:
            print "Exception from concurrent full sync process: %s" % e
            self._multiprocess_fail = True


    def test_concurrent_full_sync(self):
        """
        test multiple processes doing a full sync of the path cache at the same time
        """

        # skip this test on windows or py2.5 where multiprocessing isn't available
        if sys.platform == "win32" or sys.version_info < (2,6):
            return

        import multiprocessing

        folder.process_filesystem_structure(self.tk,
                                            self.task["type"],
                                            self.task["id"],
                                            preview=False,
                                            engine=None)

        self.tk.synchronize_filesystem_structure(True)
        self._multiprocess_fail = False

        processes = []

        for x in range(50):
            p = multiprocessing.Process(target=self.concurrent_full_sync)
            p.start()
            processes.append(p)

        all_processes_finished = False
        while not all_processes_finished:
            time.sleep(0.1)
            sys.stderr.write(".")
            all_processes_finished = all([not(p.is_alive()) for p in processes])

        self.assertFalse(self._multiprocess_fail)

    def concurrent_payload(self, queue):
        """
        Run incremental sync 20 times
        """
        try:
            for x in range(80):
                time.sleep(0.05)
                # update the local mockgun db that we have in memory
                try:
                    self.tk.shotgun._db = queue.get_nowait()
                except Queue.Empty:
                    pass
                self.tk.synchronize_filesystem_structure()
        except Exception, e:
            print "Exception from concurrent sync process: %s" % e
            self._multiprocess_fail = True

    def test_concurrent(self):
        """
        Test multi process incremental sync as records are being inserted.
        """

        # skip this test on windows or py2.5 where multiprocessing isn't available
        if sys.platform == "win32" or sys.version_info < (2,6):
            return

        import multiprocessing

        folder.process_filesystem_structure(self.tk,
                                            self.task["type"],
                                            self.task["id"],
                                            preview=False,
                                            engine=None)

        self.tk.synchronize_filesystem_structure(True)

        processes = []
        queues = []

        self._multiprocess_fail = False

        for x in range(20):
            queue = multiprocessing.Queue()
            proc = multiprocessing.Process(target=self.concurrent_payload, args=(queue,))
            processes.append(proc)
            queues.append(queue)
            proc.start()

        shot_id = 5000
        filesystem_location_id = 6000
        event_log_id = 7000

        while True:

            time.sleep(0.1)
            sys.stderr.write(".")

            shot_id += 1
            filesystem_location_id += 1
            event_log_id += 1

            # create a new shot in shotgun
            sg_shot = {
                "type": "Shot",
                "id": shot_id,
                "code": "shot_code_%s" % shot_id,
                "sg_sequence": self.seq,
                "project": self.project
            }

            sg_folder = {
                'id': filesystem_location_id,
                'type': 'FilesystemLocation',
                'project': self.project,
                'code': sg_shot["code"],
                'linked_entity_type': 'Shot',
                'linked_entity_id': shot_id,
                'path': None,
                'configuration_metadata': '',
                'is_primary': True,
                'pipeline_configuration': {'type': 'PipelineConfiguration', 'id': 123},
                'created_by': None,
                'entity': sg_shot
             }

            sg_event_log_entry = {
                'id': event_log_id,
                'type': 'EventLogEntry',
                'project': self.project,
                'event_type': "Toolkit_Folders_Create",
                'meta': {
                    'core_api_version': 'HEAD',
                    'sg_folder_ids': [filesystem_location_id]
                }
             }

            self.add_to_sg_mock_db([sg_shot, sg_folder, sg_event_log_entry])

            if all([not(p.is_alive()) for p in processes]):
                # all procs finished
                break

            # now update the mockgun in all other processes
            for queue in queues:
                try:
                    queue.put(self.tk.shotgun._db, block=False)
                except IOError:
                    pass

        self.assertFalse(self._multiprocess_fail)


class TestPathCacheDelete(TestPathCache):

    def setUp(self):
        super(TestPathCacheDelete, self).setUp()

        # Create a bunch of entities for unit testing.
        self._project_link = self.mockgun.create("Project", {"name": "MyProject"})

        self._shot_entity = self.mockgun.create("Shot", {"code": "MyShot", "project": self._project_link})
        self._shot_entity["name"] = "MyShot"
        self._shot_full_path = os.path.join(self.project_root, "shot")

        self._asset_entity = self.mockgun.create("Asset", {"code": "MyAsset", "project": self._project_link})
        self._asset_entity["name"] = "MyAsset"
        self._asset_full_path = os.path.join(self.project_root, "asset")

        # Prevent logging to the console during unit tests.
        self._unregister_folder_command = self.tk.get_command("unregister_folders")
        self._unregister_folder_command.set_logger(log)

        # Register the asset. This will be our sentinel to make sure we are not deleting too much stuff during
        # the tests.
        add_item_to_cache(self.path_cache, self._asset_entity, self._asset_full_path)

    def tearDown(self):
        # Ensure nothing has messed with our asset.
        paths = self.path_cache.get_paths(self._asset_entity["type"], self._asset_entity["id"], primary_only=True)
        self.assertEqual(len(paths), 1)
        super(TestPathCacheDelete, self).tearDown()

    def test_simple_delete_by_paths(self):
        """
        Register and then unregister a folder for a shot.
        """
        add_item_to_cache(self.path_cache, self._shot_entity, self._shot_full_path)
        paths = self.path_cache.get_paths(self._shot_entity["type"], self._shot_entity["id"], primary_only=True)
        self.assertEqual(len(paths), 1)

        self._remove_filesystem_locations_by_paths(paths)

        self.path_cache.synchronize()
        paths = self.path_cache.get_paths(self._shot_entity["type"], self._shot_entity["id"], primary_only=True)
        self.assertEqual(len(paths), 0)

    @contextlib.contextmanager
    def other_path_cache_instance(self):
        with temp_env_var(SHOTGUN_HOME=os.path.join(self.tank_temp, "other_path_cache_root")):
            yield path_cache.PathCache(self.tk)

    def test_create_then_delete_then_recreate(self):

        add_item_to_cache(self.path_cache, self._shot_entity, self._shot_full_path)
        paths = self.path_cache.get_paths(self._shot_entity["type"], self._shot_entity["id"], primary_only=True)
        self.assertEqual(len(paths), 1)

        # Remove these paths from Shotgun.
        self._remove_filesystem_locations_by_paths(paths)

        new_shot_path = os.path.join(self.project_root, "new_shot")

        # Update Shotgun with new entries.
        with self.other_path_cache_instance() as pc:
            add_item_to_cache(pc, self._shot_entity, new_shot_path)

        self.path_cache.synchronize()

        paths = self.path_cache.get_paths(self._shot_entity["type"], self._shot_entity["id"], primary_only=True)
        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0], new_shot_path)

    def _remove_filesystem_locations_by_paths(self, paths):
        """
        Removes the given paths from the path cache.
        """
        path_ids = [self.path_cache.get_shotgun_id_from_path(p) for p in paths]
        self.path_cache.remove_filesystem_location_entries(self.tk, path_ids)
