# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import itertools
import os
import sys
import sgtk
from sgtk.util import ShotgunPath

from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import (
    mock,
    TankTestBase,
)
from tank.bootstrap import constants


class TestResolverBase(TankTestBase):
    """
    Base class for resolver tests
    """

    def setUp(self):
        pass
    def _create_info_yaml(self, path):
        """
        create a mock info.yml
        """
        sgtk.util.filesystem.ensure_folder_exists(path)
        with open(os.path.join(path, "info.yml"), "wt") as fh:
            fh.write("foo")

    def _create_pc(
        self,
        code,
        project=None,
        path=None,
        users=None,
        plugin_ids=None,
        descriptor=None,
        uploaded_config_dict=None,
    ):
        """
        Creates a pipeline configuration.

        :param code: Name of the pipeline configuration.
        :param project: Project of the pipeline configuration.
        :param path: mac_path, windows_path and linux_path will be set to this.
        :param users: List of users who should be able to use this pipeline.
        :param plugin_ids: Plugin ids for the pipeline configuration.
        :param descriptor: Descriptor for the pipeline configuration
        :param uploaded_config_dict: Full attachment dictionary to represent an uploaded config
        :returns: Dictionary with keys entity_type and entity_id.
        """

        return self.mockgun.create(
            "PipelineConfiguration",
            dict(
                code=code,
                project=project,
                users=users or [],
                windows_path=path,
                mac_path=path,
                linux_path=path,
                plugin_ids=plugin_ids,
                descriptor=descriptor,
                uploaded_config=uploaded_config_dict,
            ),
        )


class TestUserRestriction(TestResolverBase):
    """
    Testing the logic around user restrictions
    """

    def setUp(self):
        pass
    def test_find_user_sandbox(self):
        pass
    def test_find_shared_sandbox(self):
        pass
class TestPluginMatching(TestResolverBase):
    """
    Tests the matching of plugin ids
    """

    def test_plugin_id_matching(self):
        pass
    @mock.patch("os.path.isdir", return_value=True)
    def test_single_matching_id(self, _):
        pass
    def test_no_plugin_id_matching(self):
        pass
class TestFallbackHandling(TestResolverBase):
    """
    Tests the logic for when to communicate with shotgun
    """

    def setUp(self):
        pass
    @mock.patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    def test_resolve_base_config(self, find_mock):
        pass
    @mock.patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.find")
    def test_resolve_latest_base_config(self, find_mock):
        pass
class TestAutoUpdate(TestResolverBase):
    """
    A test class for the config resolved when
    the PTR desktop app is launched to startup the tk-desktop
    engine on a site or Project context.
    """
    def setUp(self):
        pass
class TestResolverPriority(TestResolverBase):
    """
    This test ensures that the following priority is respected when multiple pipeline configurations
    are found.

    1. Pipeline configuration sandbox for a project
    2. Pipeline configuration for a project
    3. Pipeline configuration sandbox for site
    4. Pipeline configuration for site.
    """

    PROJECT_PC_PATH = "project_pc_path"

    def _create_project_pc(self):
        """
        Creates a pipeline configuration for the TestCases's project. The paths will be set
        to PROJECT_PC_PATH.
        """
        return self._create_pc(
            "Primary", self._project, self.PROJECT_PC_PATH, [], plugin_ids="foo.*"
        )

    PROJECT_SANDBOX_PC_PATH = "project_sandbox_pc_path"

    def _create_project_sandbox_pc(self):
        """
        Creates a pipeline configuration for the TestCases's project and it's user. The paths will be set
        to PROJECT_SANDBOX_PC_PATH.
        """
        return self._create_pc(
            "Development",
            self._project,
            self.PROJECT_SANDBOX_PC_PATH,
            [self._john_smith],
            plugin_ids="foo.*",
        )

    SITE_PC_PATH = "site_pc_path"

    def _create_site_pc(self):
        """
        Creates a pipeline configuration with no project. The paths will be set
        to SITE_PC_PATH.
        """
        return self._create_pc(
            "Primary", None, self.SITE_PC_PATH, [], plugin_ids="foo.*"
        )

    SITE_SANDBOX_PC_PATH = "site_sandbox_pc_path"

    def _create_site_sandbox_pc(self):
        """
        Creates a pipeline configuration with no project for the TestCases's user. The paths will be set
        to SITE_PC_PATH.
        """
        return self._create_pc(
            "Development",
            None,
            self.SITE_SANDBOX_PC_PATH,
            [self._john_smith],
            plugin_ids="foo.*",
        )

    def _create_project_centralized_pc(self):
        """
        Creates a non-plugin-based pipeline configuration for a project. The paths will
        be set to PROJECT_PC_PATH
        """
        return self._create_pc("Primary", self._project, self.PROJECT_PC_PATH)

    def _create_project_centralized_sandbox_pc(self):
        """
        Creates a non-plugin-based pipeline configuration sandbox for a project and a user.
        The paths will be set to PROJECT_PC_PATH
        """
        return self._create_pc(
            "Development",
            self._project,
            self.PROJECT_SANDBOX_PC_PATH,
            [self._john_smith],
        )

    def _test_priority(self, expected_path):
        """
        Resolves a pipeline configuration and ensures it's the expected one by comparing the
        path.

        :param str expected_path: Expected value for the current platform's path.
        """
        with mock.patch("os.path.isdir", return_value=True):
            config = self.resolver.resolve_shotgun_configuration(
                pipeline_config_identifier=None,
                fallback_config_descriptor=self.config_1,
                sg_connection=self.mockgun,
                current_login="john.smith",
            )
        self.assertEqual(config._path.current_os, expected_path)

    def test_site_overrides_fallback(self):
        pass
    def test_site_sandbox_overrides_site(self):
        pass
    def test_project_overrides_any_site(self):
        pass
    def test_project_sandbox_overrides_everything(self):
        pass
    def test_resolve_one_config(self):
        pass
    def test_project_primary_overrides_site_primary(self):
        pass
    def test_centralized_primary_overrides_all_other_primaries(self):
        pass
    @mock.patch("os.path.isdir", return_value=True)
    def test_more_recent_pipeline_is_shadowed(self, _):
        pass
    def test_primary_ordering(self):
        pass
    def test_pipeline_configuration_ordering(self):
        pass
class TestPipelineLocationFieldPriority(TestResolverBase):
    """
    Tests the field priority between descriptor, xxx_path and uploaded_config
    """

    @mock.patch("os.path.isdir", return_value=True)
    def test_path_override(self, _):
        pass
    def test_pc_descriptor(self):
        pass
    def test_pc_uploaded(self):
        pass
    def test_pipeline_without_location(self):
        pass
    def test_pipeline_without_current_os_path(self):
        pass
    def test_descriptor_without_plugin(self):
        pass
class TestResolverSiteConfig(TestResolverBase):
    """
    All Test Resolver tests, just with the site config instead of a project config
    """

    def setUp(self):
        pass
    @mock.patch("os.path.isdir", return_value=True)
    def test_resolve_installed_from_sg(self, _):
        pass
    def test_resolve_cached_from_sg(self):
        pass
class TestResolvedConfiguration(TankTestBase):
    """
    Ensures that resolving a descriptor returns the right Configuration object.
    """

    def setUp(self):
        pass
    def test_resolve_installed_configuration(self):
        pass
    def test_resolve_baked_configuration(self):
        pass
    def test_resolve_cached_configuration(self):
        pass
class TestResolvedLatestConfiguration(TankTestBase):
    """
    Ensures that resolving a descriptor with no version specified returns the right Configuration object.
    """

    def setUp(self):
        pass
    def test_resolve_latest_cached_configuration(self):
        pass
class TestResolveWithFilter(TestResolverBase):
    @mock.patch("os.path.isdir", return_value=True)
    def test_existing_pc_ic(self, _):
        pass
    @mock.patch("os.path.isdir", return_value=True)
    def test_non_existing_pc_ic(self, _):
        pass
    @mock.patch("os.path.isdir", return_value=True)
    def test_resolve_by_name(self, _):
        pass
class TestErrorHandling(TestResolverBase):
    def test_installed_configuration_not_on_disk(self):
        pass
    def test_invalid_descriptors_without_plugin_id_cant_break_enumeration(self):
        pass
    def test_configuration_not_found_on_disk(self):
        pass
