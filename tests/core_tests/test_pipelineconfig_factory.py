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
from tank_vendor import yaml
import sgtk
import tank
from tank.api import Tank
from tank.errors import TankInitError

from tank_test.tank_test_base import TankTestBase, setUpModule # noqa


class TestTankFromPath(TankTestBase):
    """
    Tests basic tank from path behavior.
    """

    def setUp(self):
        super(TestTankFromPath, self).setUp()
        self.setup_multi_root_fixtures()

    def test_primary_branch(self):
        """
        Test path from primary branch.
        """
        child_path = os.path.join(self.project_root, "child_dir")
        os.mkdir(os.path.join(self.project_root, "child_dir"))
        result = tank.tank_from_path(child_path)
        self.assertIsInstance(result, Tank)
        self.assertEquals(result.project_path, self.project_root)

    def test_alternate_branch(self):
        """
        Test path not from primary branch.
        """
        os.mkdir(os.path.join(self.alt_root_1, "child_dir"))
        child_path = os.path.join(self.alt_root_1, "child_dir")
        result = tank.tank_from_path(child_path)
        self.assertIsInstance(result, Tank)
        self.assertEquals(result.project_path, self.project_root)

    def test_bad_path(self):
        """
        Test path not in project tree.
        """
        bad_path = os.path.dirname(self.tank_temp)
        self.assertRaises(TankInitError, tank.tank_from_path, bad_path)

    def test_tank_temp(self):
        """
        Test passing in studio path.
        """
        self.assertRaises(TankInitError, tank.tank_from_path, self.tank_temp)


class TestArchivedProjects(TankTestBase):
    """
    Tests that archived projects are not visible
    """

    def setUp(self):
        super(TestArchivedProjects, self).setUp()
        self.setup_fixtures()

        # archive default project
        self.mockgun.update("Project", self.project["id"], {"archived": True})

    def test_archived(self):
        """
        Tests that archived projects are not visible
        """
        self.assertRaisesRegexp(
            TankInitError,
            "No pipeline configurations associated with Project %s" % self.project["id"],
            sgtk.sgtk_from_entity,
            "Project",
            self.project["id"]
        )

        # now unarchive it
        self.mockgun.update("Project", self.project["id"], {"archived": False})

        result = tank.tank_from_entity("Project", self.project["id"])
        self.assertIsInstance(result, Tank)
        self.assertEquals(result.project_path, self.project_root)
        self.assertEquals(result.pipeline_configuration.get_shotgun_id(), self.sg_pc_entity["id"])


class TestTankFromEntity(TankTestBase):
    """
    Tests basic tank from entity behavior.
    """

    def setUp(self):
        super(TestTankFromEntity, self).setUp()

        self.setup_fixtures()

        # in addition to the default project, set up another project
        # and shots linked to both
        self.shot = {
            "type": "Shot",
            "code": "shot_name",
            "id": 2,
            "project": self.project
        }

        self.other_project = {
            "type": "Project",
            "name": "Project with no pipeline config",
            "id": 12346,
        }

        self.other_shot = {
            "type": "Shot",
            "code": "a shot with no pipeline config",
            "id": 12345,
            "project": self.other_project
        }

        self.non_proj_entity = {
            "type": "HumanUser",
            "login": "foo.bar",
            "id": 999,
        }

        self.add_to_sg_mock_db([
            self.shot,
            self.other_project,
            self.other_shot,
            self.non_proj_entity
        ])

    def test_bad_project(self):
        """
        Test from project which does not have a pipeline configuration
        """
        self.assertRaisesRegexp(
            TankInitError,
            "No pipeline configurations associated with Project 1791284",
            sgtk.sgtk_from_entity,
            "Project",
            1791284
        )

    def test_bad_entity(self):
        """
        Test from project which does not have a pipeline configuration
        """
        self.assertRaisesRegexp(
            TankInitError,
            ".* is not associated with a project",
            sgtk.sgtk_from_entity,
            self.non_proj_entity["type"],
            self.non_proj_entity["id"]
        )

    def test_from_project(self):
        """
        Test from project
        """
        result = tank.tank_from_entity("Project", self.project["id"])
        self.assertIsInstance(result, Tank)
        self.assertEquals(result.project_path, self.project_root)
        self.assertEquals(result.pipeline_configuration.get_shotgun_id(), self.sg_pc_entity["id"])

    def test_from_shot(self):
        """
        Test from shot
        """
        result = tank.tank_from_entity("Shot", self.shot["id"])
        self.assertIsInstance(result, Tank)
        self.assertEquals(result.project_path, self.project_root)
        self.assertEquals(result.pipeline_configuration.get_shotgun_id(), self.sg_pc_entity["id"])

    def test_from_project_with_no_pipeline_config(self):
        """
        Test from project which does not have a pipeline configuration
        """
        self.assertRaisesRegexp(
            TankInitError,
            "No pipeline configurations associated with Project %s" % self.other_project["id"],
            sgtk.sgtk_from_entity,
            "Project",
            self.other_project["id"]
        )

    def test_from_shot_with_no_pipeline_config(self):
        """
        Test from shot which does not have a pipeline configuration
        """
        self.assertRaisesRegexp(
            TankInitError,
            "No pipeline configurations associated with Shot %s" % self.other_shot["id"],
            sgtk.sgtk_from_entity,
            "Shot",
            self.other_shot["id"]
        )


class TestTankFromPathDuplicatePcPaths(TankTestBase):
    """
    Test behavior and error messages when multiple pipeline
    configurations are pointing at the same location
    """

    def setUp(self):
        super(TestTankFromPathDuplicatePcPaths, self).setUp()

        # define an additional pipeline config with overlapping paths
        self.overlapping_pc = {
            "type": "PipelineConfiguration",
            "code": "Primary",
            "id": 123456,
            "project": self.project,
            "windows_path": self.pipeline_config_root,
            "mac_path": self.pipeline_config_root,
            "linux_path": self.pipeline_config_root}

        self.add_to_sg_mock_db(self.overlapping_pc)

    def test_primary_duplicates_from_path(self):
        """
        Test primary dupes
        """
        self.assertRaisesRegexp(TankInitError,
                                ".* is associated with more than one Primary pipeline configuration",
                                sgtk.sgtk_from_path,
                                self.project_root)

    def test_primary_duplicates_from_entity(self):
        """
        Test primary dupes
        """
        self.assertRaisesRegexp(TankInitError,
                                ".* is associated with more than one Primary pipeline configuration",
                                sgtk.sgtk_from_entity,
                                "Project",
                                self.project["id"])


class TestTankFromEntityWithMixedSlashes(TankTestBase):
    """
    Tests the case where a Windows local storage uses forward slashes.
    """

    def test_with_mixed_slashes(self):
        """
        Check that a sgtk init works for this path
        """
        # only run this test on windows
        if sys.platform == "win32":

            self.sg_pc_entity["windows_path"] = self.pipeline_config_root.replace("\\", "/")
            self.add_to_sg_mock_db(self.sg_pc_entity)
            self.add_to_sg_mock_db(self.project)
            self.add_to_sg_mock_db({
                "type": "Shot",
                "id": 1,
                "project": self.project
            })

            os.environ["TANK_CURRENT_PC"] = self.pipeline_config_root
            try:
                sgtk.sgtk_from_entity("Shot", 1)
            finally:
                del os.environ["TANK_CURRENT_PC"]


class TestTankFromPathWindowsNoSlash(TankTestBase):
    """
    Tests the edge case where a Windows local storage is set to be 'C:'
    """

    PROJECT_NAME = "temp"
    STORAGE_ROOT = "C:"

    def setUp(self):

        # set up a project named temp, so that it will end up in c:\temp
        super(TestTankFromPathWindowsNoSlash, self).setUp(
            parameters={"project_tank_name": self.PROJECT_NAME}
        )
        
        # set up std fixtures
        self.setup_fixtures()

        # patch primary local storage def
        self.primary_storage["windows_path"] = self.STORAGE_ROOT
        # re-add it
        self.add_to_sg_mock_db(self.primary_storage)

        # now re-write roots.yml
        roots = {"primary": {}}
        for os_name in ["windows_path", "linux_path", "mac_path"]:
            # TODO make os specific roots
            roots["primary"][os_name] = self.sg_pc_entity[os_name]
        roots_path = os.path.join(self.pipeline_config_root,
                                  "config",
                                  "core",
                                  "roots.yml")
        roots_file = open(roots_path, "w")
        roots_file.write(yaml.dump(roots))
        roots_file.close()

        # need a new pipeline config object that is
        # using the new roots def file we just created
        self.pipeline_configuration = sgtk.pipelineconfig_factory.from_path(self.pipeline_config_root)
        # push this new pipeline config into the tk api
        self.tk._Tank__pipeline_config = self.pipeline_configuration
        # force reload templates
        self.tk.reload_templates()

    def test_project_path_lookup(self):
        """
        Check that a sgtk init works for this path
        """
        # only run this test on windows
        if sys.platform == "win32":

            # probe a path inside of project
            test_path = "%s\\%s\\toolkit_test_path" % (self.STORAGE_ROOT, self.PROJECT_NAME)
            if not os.path.exists(test_path):
                os.makedirs(test_path)
            self.assertIsInstance(sgtk.sgtk_from_path(test_path), Tank)


class TestTankFromPathOverlapStorage(TankTestBase):
    """
    Tests edge case with overlapping storages

    For example, imagine the following setup:
    Storages: f:\ and f:\foo
    Project names: foo and bar
    This means we have the following project roots:
    (1) f:\foo      (storage f:\, project foo)
    (2) f:\bar      (storage f:\, project bar)
    (3) f:\foo\foo  (storage f:\foo, project foo)
    (4) f:\foo\bar  (storage f:\foo, project bar)

    The path f:\foo\bar\hello_world.ma could either belong to
    project bar (matching 4) or project foo (matching 1).

    In this case, sgtk_from_path() should succeed in case you are using a local
    tank command or API and fail if you are using a studio level command.

    """

    def setUp(self):

        # set up two storages and two projects
        super(TestTankFromPathOverlapStorage, self).setUp(
            parameters={"project_tank_name": "foo"}
        )

        # add second project
        self.project_2 = {
            "type": "Project",
            "id": 2345,
            "tank_name": "bar",
            "name": "project_name",
            "archived": False,
        }

        # define entity for pipeline configuration
        self.project_2_pc = {
            "type": "PipelineConfiguration",
            "code": "Primary",
            "id": 123456,
            "project": self.project_2,
            "windows_path": "F:\\temp\\bar_pc",
            "mac_path": "/tmp/bar_pc",
            "linux_path": "/tmp/bar_pc"
        }

        self.add_to_sg_mock_db(self.project_2)
        self.add_to_sg_mock_db(self.project_2_pc)

        # set up std fixtures
        self.setup_multi_root_fixtures()

        # patch storages
        self.alt_storage_1["windows_path"] = "C:\\temp"
        self.alt_storage_1["mac_path"] = "/tmp"
        self.alt_storage_1["linux_path"] = "/tmp"

        self.alt_storage_2["windows_path"] = "C:\\temp\\foo"
        self.alt_storage_2["mac_path"] = "/tmp/foo"
        self.alt_storage_2["linux_path"] = "/tmp/foo"

        self.add_to_sg_mock_db(self.alt_storage_1)
        self.add_to_sg_mock_db(self.alt_storage_2)

        # Write roots file
        roots = {"primary": {}, "alternate_1": {}, "alternate_2": {}}
        for os_name in ["windows_path", "linux_path", "mac_path"]:
            roots["primary"][os_name] = os.path.dirname(self.project_root)
            roots["alternate_1"][os_name] = self.alt_storage_1[os_name]
            roots["alternate_2"][os_name] = self.alt_storage_2[os_name]
        roots_path = os.path.join(self.pipeline_config_root, "config", "core", "roots.yml")
        roots_file = open(roots_path, "w")
        roots_file.write(yaml.dump(roots))
        roots_file.close()

        # need a new pipeline config object that is using the new
        # roots def file we just created
        self.pipeline_configuration = sgtk.pipelineconfig_factory.from_path(self.pipeline_config_root)
        # push this new pipeline config into the tk api
        self.tk._Tank__pipeline_config = self.pipeline_configuration
        # force reload templates
        self.tk.reload_templates()

    def test_project_path_lookup_studio_mode(self):
        """
        When running this edge case from a studio install, we expect an error:

        TankInitError: The path '/tmp/foo/bar' is potentially associated with more than one primary
        pipeline configuration. This can happen if there is ambiguity in your project setup,
        where projects store their data in an overlapping fashion. In this case, try creating
        your API instance (or tank command) directly from the pipeline configuration rather
        than via the studio level API. This will explicitly call out which project you are
        intending to use in conjunction with he path. The pipeline configuration paths
        associated with this path are:
        ['/var/folders/fq/65bs7wwx3mz7jdsh4vxm34xc0000gn/T/tankTemporaryTestData_1422967258.765262/pipeline_configuration',
        '/tmp/bar_pc']

        """

        probe_path = {}
        probe_path["win32"] = "C:\\temp\\foo\\bar\\test.ma"
        probe_path["darwin"] = "/tmp/foo/bar/test.ma"
        probe_path["linux2"] = "/tmp/foo/bar/test.ma"

        test_path = probe_path[sys.platform]
        test_path_dir = os.path.dirname(test_path)

        if not os.path.exists(test_path_dir):
            os.makedirs(test_path_dir)

        self.assertRaisesRegexp(TankInitError,
                                ".* is associated with more than one Primary pipeline configuration",
                                sgtk.sgtk_from_path,
                                test_path)

    def test_project_path_lookup_local_mode(self):
        """
        Check that a sgtk init works for this path
        """

        # By setting the TANK_CURRENT_PC, we emulate the behaviour
        # of a local API running. Push this variable
        old_tank_current_pc = None
        if "TANK_CURRENT_PC" in os.environ:
            old_tank_current_pc = os.environ["TANK_CURRENT_PC"]
        os.environ["TANK_CURRENT_PC"] = self.pipeline_config_root

        probe_path = {}
        probe_path["win32"] = "C:\\temp\\foo\\bar\\test.ma"
        probe_path["darwin"] = "/tmp/foo/bar/test.ma"
        probe_path["linux2"] = "/tmp/foo/bar/test.ma"

        test_path = probe_path[sys.platform]
        test_path_dir = os.path.dirname(test_path)

        if not os.path.exists(test_path_dir):
            os.makedirs(test_path_dir)

        self.assertIsInstance(sgtk.sgtk_from_path(test_path), Tank)

        # and pop the modification
        if old_tank_current_pc is None:
            del os.environ["TANK_CURRENT_PC"]
        else:
            os.environ["TANK_CURRENT_PC"] = old_tank_current_pc

class TestTankFromPathPCWithProjectWithoutTankName(TankTestBase):
    """
    Tests edge case where getting path for classic/installed project and another
    project exists without a tank name.
    """

    def setUp(self):

        super(TestTankFromPathPCWithProjectWithoutTankName, self).setUp()

        # a separate project record without the tank name set
        self.other_project = {
            "type": "Project",
            "name": "Project without tank_name set",
            "id": 77777,
            "archived": False,
            "tank_name": None
        }

        # define an additional pipeline config linked to the other project
        self.other_pc = {
            "type": "PipelineConfiguration",
            "code": "Other",
            "id": 123456,
            "project": self.other_project,
            "windows_path": "/foobar",
            "mac_path": "/foobar",
            "linux_path": "/foobar",
        }

        self.add_to_sg_mock_db(self.other_project)
        self.add_to_sg_mock_db(self.other_pc)

    def test_sgtk_from_path_project_no_tank_name(self):
        """
        Ensure no errors and valid Tank instance returned when a project exists
        with no tank_name
        """

        path = os.path.join(self.project_root, "child_dir")

        # this will raise if an exception occurs. prior to the associated fix
        # (#46590), if there was a project defined for the site without a
        # tank_name set, this code would fail.
        config = sgtk.pipelineconfig_factory.from_path(path)
