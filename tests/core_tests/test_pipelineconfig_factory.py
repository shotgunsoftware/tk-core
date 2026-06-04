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
import pickle
import sys
from tank_vendor import yaml
import sgtk
import tank
from tank.api import Tank
from tank.util import is_windows
from tank.errors import TankInitError
from sgtk.util import ShotgunPath
from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import (
    mock,
    ShotgunTestBase,
    TankTestBase,
)


class TestTankFromPath(TankTestBase):
    """
    Tests basic tank from path behavior.
    """

    def setUp(self):
        super().setUp()
        self.setup_multi_root_fixtures()

    def test_primary_branch(self):
        pass
    def test_alternate_branch(self):
        pass
    def test_bad_path(self):
        pass
    def test_tank_temp(self):
        pass
class TestArchivedProjects(TankTestBase):
    """
    Tests that archived projects are not visible
    """

    def setUp(self):
        super().setUp()
        self.setup_fixtures()

        # archive default project
        self.mockgun.update("Project", self.project["id"], {"archived": True})

    def test_archived(self):
        pass
class TestTankFromEntity(TankTestBase):
    """
    Tests basic tank from entity behavior.
    """

    def setUp(self):
        super().setUp()

        self.setup_fixtures()

        # in addition to the default project, set up another project
        # and shots linked to both
        self.shot = {
            "type": "Shot",
            "code": "shot_name",
            "id": 2,
            "project": self.project,
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
            "project": self.other_project,
        }

        self.non_proj_entity = {"type": "HumanUser", "login": "foo.bar", "id": 999}

        self.add_to_sg_mock_db(
            [self.shot, self.other_project, self.other_shot, self.non_proj_entity]
        )

    def test_bad_project(self):
        pass
    def test_bad_entity(self):
        pass
    def test_from_project(self):
        pass
    def test_from_shot(self):
        pass
    def test_from_project_with_no_pipeline_config(self):
        pass
    def test_from_shot_with_no_pipeline_config(self):
        pass
class TestTankFromPathDuplicatePcPaths(TankTestBase):
    """
    Test behavior and error messages when multiple pipeline
    configurations are pointing at the same location
    """

    def setUp(self):
        super().setUp()

        # define an additional pipeline config with overlapping paths
        self.overlapping_pc = {
            "type": "PipelineConfiguration",
            "code": "Primary",
            "id": 123456,
            "project": self.project,
            ShotgunPath.get_shotgun_storage_key(): self.project_root,
        }

        self.add_to_sg_mock_db(self.overlapping_pc)

    def test_primary_duplicates_from_path(self):
        pass
    def test_primary_duplicates_from_entity(self):
        pass
class TestSharedCoreWithSiteWideConfigs(TankTestBase):
    def test_multiple_primaries(self):
        pass
    def test_no_primary(self):
        pass
    def test_no_path(self):
        pass
class TestPipelineConfigurationEnumeration(ShotgunTestBase):
    """
    Tests pipeline configuration enumeration.
    """

    def setUp(self):
        super().setUp()

        # Clean Mockgun of existing project and pipeline configurations. We want a clean slate.
        self.mockgun.delete("PipelineConfiguration", self.sg_pc_entity["id"])
        self.mockgun.delete("Project", self.project["id"])

        # Create two projects with different tank names.
        self.project_with_tank_name = self.mockgun.create(
            "Project",
            {"name": "WithTankName", "tank_name": "with_tank_name", "archived": False},
        )
        self.project_with_another_tank_name = self.mockgun.create(
            "Project",
            {
                "name": "WithAnotherTankName",
                "tank_name": "with_another_tank_name",
                "archived": False,
            },
        )

        # Create four different kinds of pipeline configurations, 2 site wide ones and 2 project specific ones.
        self.site_wide_path = self.mockgun.create(
            "PipelineConfiguration",
            {
                "code": "SiteWidePath",
                "windows_path": os.path.join(self.tank_temp, "site_wide_path"),
                "linux_path": os.path.join(self.tank_temp, "site_wide_path"),
                "mac_path": os.path.join(self.tank_temp, "site_wide_path"),
                "project": None,
            },
        )

        self.site_wide_desc = self.mockgun.create(
            "PipelineConfiguration",
            {
                "code": "SiteWideDescriptor",
                "descriptor": "sgtk:descriptor:path?path="
                + os.path.join(self.tank_temp, "site_wide_descriptor"),
                "plugin_ids": "basic.*",
                "project": None,
                "windows_path": None,
                "linux_path": None,
                "mac_path": None,
            },
        )
        # Remove some values from the resulting dict, this will make validation easier in the tests.
        self.site_wide_desc = self._remove_items(
            self.site_wide_desc, ["plugin_ids", "descriptor"]
        )

        self.proj_spec_path = self.mockgun.create(
            "PipelineConfiguration",
            {
                "code": "ProjectSpecificPath",
                "windows_path": os.path.join(self.tank_temp, "site_wide_path"),
                "linux_path": os.path.join(self.tank_temp, "site_wide_path"),
                "mac_path": os.path.join(self.tank_temp, "site_wide_path"),
                "project": self.project_with_tank_name,
            },
        )

        self.proj_spec_desc = self.mockgun.create(
            "PipelineConfiguration",
            {
                "code": "ProjectSpecificDescriptor",
                "descriptor": "sgtk:descriptor:path?path="
                + os.path.join(self.tank_temp, "project_specific_descriptor"),
                "plugin_ids": "basic.*",
                "project": self.project_with_tank_name,
                "windows_path": None,
                "linux_path": None,
                "mac_path": None,
            },
        )
        # Remove some values from the resulting dict, this will make validation easier in the tests.
        self.proj_spec_desc = self._remove_items(
            self.proj_spec_desc, ["plugin_ids", "descriptor"]
        )

        self.project_with_tank_name = self._remove_items(
            self.project_with_tank_name, ["archived"]
        )
        self.project_with_another_tank_name = self._remove_items(
            self.project_with_another_tank_name, ["archived"]
        )

        # Retrieve all the pipeline configuration info.
        self._sg_data = sgtk.pipelineconfig_factory._get_pipeline_configs(True)

        self.maxDiff = None

    def test_get_pipeline_configs(self):
        pass
    def test_get_pipeline_configs_from_path(self):
        pass
    def test_get_pipeline_configs_for_project(self):
        pass
    def _remove_items(self, dictionary, keys_to_remove):
        """
        Creates a new dictionary with a given set of keys removed.

        :param dictionary: Dictionary to clean.
        :param keys_to_remove: List of keys to remove.

        :returns: A new dictionary without the keys specified.
        """
        return dict((k, v) for k, v in dictionary.items() if k not in keys_to_remove)


class TestLookupCache(ShotgunTestBase):
    def test_cache_lookup_for_pipeline_configs(self):
        pass
class TestTankFromWithSiteConfig(TankTestBase):
    """
    Tests tank.tank_from_* with site configurations.
    """

    def setUp(self):
        super().setUp()
        # Turn the config into a site configuration.
        self.mockgun.update(
            "PipelineConfiguration",
            self.sg_pc_entity["id"],
            {
                "windows_path": None,
                "linux_path": None,
                "mac_path": None,
                "project": None,
            },
        )

        self.mockgun.create(
            "PipelineConfiguration", {"code": "NoPath", "project": self.project}
        )

    def test_from_path(self):
        pass
    def test_from_entity(self):
        pass
    def _invalidate_pipeline_configuration_yml(self):
        """
        Updates pipeline_configuration.yml to point to a pipeline configuration id
        that doesn't match.
        """
        pc_yml = os.path.join(
            self.pipeline_config_root, "config", "core", "pipeline_configuration.yml"
        )
        pc_yml_data = (
            "{ project_name: %s, use_shotgun_path_cache: true, pc_id: %d, "
            "project_id: %d, pc_name: %s}\n\n"
            % (
                self.project["tank_name"],
                9595,
                self.project["id"],
                self.sg_pc_entity["code"],
            )
        )
        self.create_file(pc_yml, pc_yml_data)


class TestTankFromEntityWithMixedSlashes(TankTestBase):
    """
    Tests the case where a Windows local storage uses forward slashes.
    """

    def test_with_mixed_slashes(self):
        pass
class TestTankFromPathWindowsNoSlash(TankTestBase):
    """
    Tests the edge case where a Windows local storage is set to be 'C:'
    """

    PROJECT_NAME = "temp"
    STORAGE_ROOT = "C:"

    def setUp(self):

        # set up a project named temp, so that it will end up in c:\temp
        super().setUp(
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
        roots_path = os.path.join(
            self.pipeline_config_root, "config", "core", "roots.yml"
        )
        roots_file = open(roots_path, "w")
        roots_file.write(yaml.dump(roots))
        roots_file.close()

        # need a new pipeline config object that is
        # using the new roots def file we just created
        self.pipeline_configuration = sgtk.pipelineconfig_factory.from_path(
            self.pipeline_config_root
        )
        # push this new pipeline config into the tk api
        self.tk._Tank__pipeline_config = self.pipeline_configuration
        # force reload templates
        self.tk.reload_templates()

    def test_project_path_lookup(self):
        pass
class TestTankFromPathOverlapStorage(TankTestBase):
    r"""
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
        super().setUp(
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
            "linux_path": "/tmp/bar_pc",
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
        roots_path = os.path.join(
            self.pipeline_config_root, "config", "core", "roots.yml"
        )
        roots_file = open(roots_path, "w")
        roots_file.write(yaml.dump(roots))
        roots_file.close()

        # need a new pipeline config object that is using the new
        # roots def file we just created
        self.pipeline_configuration = sgtk.pipelineconfig_factory.from_path(
            self.pipeline_config_root
        )
        # push this new pipeline config into the tk api
        self.tk._Tank__pipeline_config = self.pipeline_configuration
        # force reload templates
        self.tk.reload_templates()

    def test_project_path_lookup_studio_mode(self):
        pass
    def test_project_path_lookup_local_mode(self):
        pass
class TestTankFromPathPCWithProjectWithoutTankName(TankTestBase):
    """
    Tests edge case where getting path for centralized project and another
    project exists without a tank name.
    """

    def setUp(self):

        super().setUp()

        # a separate project record without the tank name set
        self.other_project = {
            "type": "Project",
            "name": "Project without tank_name set",
            "id": 77777,
            "archived": False,
            "tank_name": None,
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
        pass
