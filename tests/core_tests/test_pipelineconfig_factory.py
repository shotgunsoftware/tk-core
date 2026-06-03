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
        pass
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
        pass
    def test_archived(self):
        pass
class TestTankFromEntity(TankTestBase):
    """
    Tests basic tank from entity behavior.
    """

    def setUp(self):
        pass
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
        pass
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
        pass
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
        pass
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
        pass
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
        pass
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
        pass
    def test_sgtk_from_path_project_no_tank_name(self):
        pass
