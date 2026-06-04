# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import contextlib
import logging
import os
import shutil
import sys
import time
from io import StringIO
from queue import Empty

import tank
from tank import LogManager, folder, path_cache
from tank.util import StorageRoots
from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import (
    TankTestBase,
    mock,
    only_run_on_windows,
    temp_env_var,
)

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
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    log = logging.getLogger("sgtk.core.path_cache")
    log.setLevel(logging.DEBUG)
    log.addHandler(handler)

    # Use the path cache to look up all paths associated with this entity
    pc = path_cache.PathCache(tk)
    pc.synchronize(force_full_sync)
    pc.close()

    # No need to close the StringIO; it will be garbage collected.
    log_contents = stream.getvalue()
    log.removeHandler(handler)
    return log_contents


class TestPathCache(TankTestBase):
    """Base class for path cache tests."""

    def setUp(self):
        super().setUp()
        self.setup_multi_root_fixtures()
        self.path_cache = path_cache.PathCache(self.tk)
        self.path_cache_location = self.path_cache._get_path_cache_location()

    def tearDown(self):
        self.path_cache.close()
        super().tearDown()


class TestInit(TestPathCache):
    def test_db_exists(self):
        pass
    def test_root_map(self):
        pass
    def test_db_columns(self):
        pass
    def test_db_location(self):
        pass
class TestAddMapping(TestPathCache):
    def setUp(self):
        super().setUp()

        # entity for testing
        self.entity = {"type": "EntityType", "id": 1, "name": "EntityName"}

        # get db connection
        self.db_cursor = self.path_cache._connection.cursor()

    def test_primary_path(self):
        pass
    def test_dupe_failure(self):
        pass
    def test_is_path_in_db(self):
        pass
    def test_multi_entity_path(self):
        pass
    def test_non_primary_path(self):
        pass
    def test_add_utf_name(self):
        pass
    @only_run_on_windows
    def test_path_lookup_handles_separator_mismatch_in_shotgun_response(self):
        pass
class TestGetEntity(TestPathCache):
    """
    Tests for get_entity.
    Project and non-project entities are stored differently so tests are seperated between the two.
    """

    def setUp(self):
        super().setUp()
        self.non_project = {
            "type": "NonProjectEntity",
            "id": 999,
            "name": "NonProjectName",
        }
        # adding project roots

        proj = {
            "type": "Project",
            "id": self.project["id"],
            "name": self.project["name"],
        }
        add_item_to_cache(self.path_cache, proj, self.project_root)
        add_item_to_cache(self.path_cache, proj, self.alt_root_1)
        add_item_to_cache(self.path_cache, proj, self.alt_root_2)

    def test_non_project_primary_path(self):
        pass
    def test_non_project_alternate(self):
        pass
    def test_add_and_find_project_primary_root(self):
        pass
    def test_add_and_find_project_non_primary_root(self):
        pass
    def test_non_project_path(self):
        pass
class TestGetPaths(TestPathCache):
    def test_add_and_find_shot(self):
        pass
    def test_add_and_find_project(self):
        pass
class Test_SeperateRoots(TestPathCache):
    def test_different_case(self):
        pass
class TestShotgunSync(TankTestBase):
    def setUp(self, project_tank_name="project_code"):
        """Sets up entities in mocked shotgun database and creates Mock objects
        to pass in as callbacks to Schema.create_folders. The mock objects are
        then queried to see what paths the code attempted to create.
        """
        super().setUp(
            parameters={"project_tank_name": project_tank_name}
        )
        self.setup_fixtures()

        self.seq = {
            "type": "Sequence",
            "id": 2,
            "code": "seq_code",
            "project": self.project,
        }
        self.shot = {
            "type": "Shot",
            "id": 1,
            "code": "shot_code",
            "sg_sequence": self.seq,
            "project": self.project,
        }
        self.step = {
            "type": "Step",
            "id": 3,
            "code": "step_code",
            "entity_type": "Shot",
            "short_name": "step_short_name",
        }
        self.task = {
            "type": "Task",
            "id": 4,
            "entity": self.shot,
            "step": self.step,
            "project": self.project,
        }

        entities = [self.shot, self.seq, self.step, self.project, self.task]

        # Add these to mocked shotgun
        self.add_to_sg_mock_db(entities)

        self.schema_location = os.path.join(
            self.pipeline_config_root, "config", "core", "schema"
        )

    def _get_path_cache(self):
        path_cache = tank.path_cache.PathCache(self.tk)
        c = path_cache._connection.cursor()
        cache = list(c.execute("select * from path_cache"))
        c.close()
        path_cache.close()
        return cache

    def test_shot(self):
        pass
    def test_no_new_folders_created(self):
        pass
    def test_incremental_sync(self):
        pass
    def test_missing_roots_mapping(self):
        pass
    def test_truncated_eventlog(self):
        pass
    def test_multiple_projects_eventlog(self):
        pass
class TestConcurrentShotgunSync(TankTestBase):
    """
    Tests that the path cache can gracefully handle multiple
    clients cocurrently synchronizing with it
    """

    def setUp(self, project_tank_name="project_code"):
        """Sets up entities in mocked shotgun database and creates Mock objects
        to pass in as callbacks to Schema.create_folders. The mock objects are
        then queried to see what paths the code attempted to create.
        """
        super().setUp(project_tank_name)
        self.setup_fixtures()

        self.seq = {
            "type": "Sequence",
            "id": 2,
            "code": "seq_code",
            "project": self.project,
        }
        self.shot = {
            "type": "Shot",
            "id": 1,
            "code": "shot_code",
            "sg_sequence": self.seq,
            "project": self.project,
        }
        self.step = {
            "type": "Step",
            "id": 3,
            "code": "step_code",
            "entity_type": "Shot",
            "short_name": "step_short_name",
        }
        self.task = {
            "type": "Task",
            "id": 4,
            "entity": self.shot,
            "step": self.step,
            "project": self.project,
        }

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
        except Exception as e:
            print("Exception from concurrent full sync process: %s" % e)
            self._multiprocess_fail = True

    def _test_concurrent_full_sync(self):
        """
        test multiple processes doing a full sync of the path cache at the same time
        """

        import multiprocessing

        folder.process_filesystem_structure(
            self.tk, self.task["type"], self.task["id"], preview=False, engine=None
        )

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
            all_processes_finished = all(not (p.is_alive()) for p in processes)

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
                except Empty:
                    pass
                self.tk.synchronize_filesystem_structure()
        except Exception as e:
            print("Exception from concurrent sync process: %s" % e)
            self._multiprocess_fail = True

    def _test_concurrent(self):
        """
        Test multi process incremental sync as records are being inserted.
        """

        import multiprocessing

        folder.process_filesystem_structure(
            self.tk, self.task["type"], self.task["id"], preview=False, engine=None
        )

        self.tk.synchronize_filesystem_structure(True)

        processes = []
        queues = []

        self._multiprocess_fail = False

        for x in range(20):
            queue = multiprocessing.Queue()
            proc = multiprocessing.Process(
                target=self.concurrent_payload, args=(queue,)
            )
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
                "project": self.project,
            }

            sg_folder = {
                "id": filesystem_location_id,
                "type": "FilesystemLocation",
                "project": self.project,
                "code": sg_shot["code"],
                "linked_entity_type": "Shot",
                "linked_entity_id": shot_id,
                "path": None,
                "configuration_metadata": "",
                "is_primary": True,
                "pipeline_configuration": {"type": "PipelineConfiguration", "id": 123},
                "created_by": None,
                "entity": sg_shot,
            }

            sg_event_log_entry = {
                "id": event_log_id,
                "type": "EventLogEntry",
                "project": self.project,
                "event_type": "Toolkit_Folders_Create",
                "meta": {
                    "core_api_version": "HEAD",
                    "sg_folder_ids": [filesystem_location_id],
                },
            }

            self.add_to_sg_mock_db([sg_shot, sg_folder, sg_event_log_entry])

            if all(not (p.is_alive()) for p in processes):
                # all procs finished
                break

            # now update the mockgun in all other processes
            for queue in queues:
                try:
                    queue.put(self.tk.shotgun._db, block=False)
                except IOError:
                    pass

        self.assertFalse(self._multiprocess_fail)


class TestPathCacheGetLocationsFullSync(TankTestBase):
    """
    Tests that Getting FilesystemLocations in a full sync only returns ones belonging to the current project.
    """

    def setUp(self):
        super().setUp()

        # Create a new project, we will assign a new Filesystemlocation entity to this
        self._project_entity_b = self.mockgun.create("Project", {"name": "Project_B"})

        # create a new FilesystemLocation entity and attach it to the default project 1 that generated by TankTestBase
        # We hope to retrieve this entity in our test
        self._asset_entity = self.mockgun.create(
            "FilesystemLocation",
            {"code": "MyAsset_A", "project": {"type": "Project", "id": 1}},
        )

        # create a new FilesystemLocation entity and associate it with the new project we created
        # we hope not to retrieve this entity in our test
        self._asset_entity = self.mockgun.create(
            "FilesystemLocation",
            {"code": "MyAsset_B", "project": self._project_entity_b},
        )

        self._pc = path_cache.PathCache(self.tk)

    def tearDown(self):
        self._pc.close()
        super().tearDown()

    def test_get_entities(self):
        pass
class TestPathCacheDelete(TankTestBase):
    """
    Tests various scenarios where path cache entries are deleted and we incrementally sync these changes.
    """

    def setUp(self):
        """
        Creates a bunch of entities in Mockgun and adds an entry to the FilesystemLocation.
        """
        super().setUp()

        # Create a bunch of entities for unit testing.
        self._project_link = self.mockgun.create("Project", {"name": "MyProject"})

        self._shot_entity = self.mockgun.create(
            "Shot", {"code": "MyShot", "project": self._project_link}
        )
        self._shot_entity["name"] = "MyShot"
        self._shot_full_path = os.path.join(self.project_root, "shot")

        self._asset_entity = self.mockgun.create(
            "Asset", {"code": "MyAsset", "project": self._project_link}
        )
        self._asset_entity["name"] = "MyAsset"
        self._asset_full_path = os.path.join(self.project_root, "asset")

        self._pc = path_cache.PathCache(self.tk)

        # Register the asset. This will be our sentinel to make sure we are not deleting too much stuff during
        # the tests.
        add_item_to_cache(self._pc, self._asset_entity, self._asset_full_path)

        # Wrap some methods in a mock so we can track their usage.
        self._pc._do_full_sync = mock.Mock(wraps=self._pc._do_full_sync)
        self._pc._import_filesystem_location_entry = mock.Mock(
            wraps=self._pc._import_filesystem_location_entry
        )
        self._pc._remove_filesystem_location_entities = mock.Mock(
            wraps=self._pc._remove_filesystem_location_entities
        )

    def tearDown(self):
        """
        Ensures our sentinel is still present.
        """
        try:
            # Ensure nothing has messed with our asset.
            paths = self._pc.get_paths(
                self._asset_entity["type"], self._asset_entity["id"], primary_only=True
            )
            self.assertEqual(len(paths), 1)

            # Ensure no full sync has happened. We're testing incremental syncs here!
            self.assertEqual(self._pc._do_full_sync.called, False)
        finally:
            self._pc.close()
            super().tearDown()

    @contextlib.contextmanager
    def mock_remote_path_cache(self):
        """
        Mocks a remote path cache that can be updated.
        """
        # Override the SHOTGUN_HOME so that path cache is read from another location.
        with temp_env_var(
            SHOTGUN_HOME=os.path.join(self.tank_temp, "other_path_cache_root")
        ):
            pc = path_cache.PathCache(self.tk)
            pc.synchronize()
            try:
                yield pc
            finally:
                pc.close()

    def test_simple_delete_by_paths(self):
        pass
    def test_reregister_under_new_name(self):
        pass
    def test_sync_entity_that_no_longer_has_an_entry(self):
        pass
    def test_sync_remote_path_cache_with_multiple_invalid_paths(self):
        pass
    def test_unregister_multiple_folders(self):
        pass
    def _remove_filesystem_locations_by_paths(self, paths, pc=None):
        """
        Removes the FilesystemLocations entities from Shotgun associated with a given set of paths.

        :param list paths: Paths that need to be unregistered.
        :param pc: Path cache to sync with. If None, the one initialized during setUp will be used.
        """
        pc = pc or self._pc
        path_ids = [pc.get_shotgun_id_from_path(p) for p in paths]
        pc.remove_filesystem_location_entries(self.tk, path_ids)


class TestPathCacheBatchOperation(TankTestBase):
    """
    Tests the deletion of 2000+ filesystem locations (#44931)
    """

    def setUp(self):
        super().setUp()
        self._pc = path_cache.PathCache(self.tk)

        # dial down batch sizes for these tests
        self._prev_batch_size = self._pc.SHOTGUN_ENTITY_QUERY_BATCH_SIZE
        self._pc.SHOTGUN_ENTITY_QUERY_BATCH_SIZE = 11

    def tearDown(self):
        self._pc.close()
        self._pc.SHOTGUN_ENTITY_QUERY_BATCH_SIZE = self._prev_batch_size
        super().tearDown()

    def test_high_volume_batch_deletion(self):
        pass
    @mock.patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    def test_full_shotgun_retrieval(self, find_mock):
        pass
    @mock.patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    def test_batched_shotgun_retrieval(self, find_mock):
        pass
