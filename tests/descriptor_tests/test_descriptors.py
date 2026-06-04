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
import sgtk

import unittest

from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import (
    mock,
    SealedMock,
    ShotgunTestBase,
    TankTestBase,
)


from tank.errors import TankError
from tank.descriptor import (
    CheckVersionConstraintsError,
    TankDescriptorError,
    create_descriptor,
    Descriptor,
    TankMissingManifestError,
    ConfigDescriptor,
    CoreDescriptor,
)
from tank.descriptor.descriptor_installed_config import InstalledConfigDescriptor

from tank_vendor.shotgun_api3.lib.mockgun import Shotgun as Mockgun
from tank_vendor import yaml
from tank_vendor.shotgun_api3.lib import httplib2


class TestCachedConfigDescriptor(ShotgunTestBase):
    def test_core_descriptor_features(self):
        pass
    def test_self_contained_config_core_descriptor(self):
        pass
    def test_cached_config_associated_core_descriptor(self):
        pass
    def test_cached_config_manifest(self):
        pass
class TestConfigDescriptor(TankTestBase):
    def test_core_descriptor(self):
        pass
    def test_legacy_configs(self):
        pass
    def test_cant_copy_installed_config(self):
        pass
    def test_mutability(self):
        pass
    def test_installed_config_associated_core_descriptor(self):
        pass
    def test_installed_config_manifest(self):
        pass
    def test_empty_manifest(self):
        pass
    def test_readme_content(self):
        pass
    def test_missing_readme_file(self):
        pass
    def test_required_storages(self):
        pass
    def test_missing_roots_yml(self):
        pass
class TestDescriptorSupport(TankTestBase):
    def setUp(self, parameters=None):

        super().setUp()

        self.install_root = os.path.join(
            self.tk.pipeline_configuration.get_install_location(), "install"
        )

    def _create_info_yaml(self, path):
        """
        create a mock info.yml
        """
        sgtk.util.filesystem.ensure_folder_exists(path)
        fh = open(os.path.join(path, "info.yml"), "wt")
        fh.write("foo")
        fh.close()

    def test_shotgun_descriptor_location(self):
        pass
    def test_app_store_descriptor_location(self):
        pass
    def test_manual_descriptor_location(self):
        pass
    def test_dev_descriptor_location(self):
        pass
    def _test_git_descriptor_location_with_repo(self, repo):
        """
        Tests a git descriptor bundle path for the given bundle type and location and a given
        repo.
        """
        path = os.path.join(self.install_root, "git", os.path.basename(repo), "v0.1.2")
        self._create_info_yaml(path)

        d = self.tk.pipeline_configuration.get_app_descriptor(
            {"type": "git", "path": repo, "version": "v0.1.2"}
        )
        self.assertEqual(d.get_path(), path)

    def test_git_descriptor_location(self):
        pass
    def test_bad_app_store_credentials(self):
        pass
    def test_ssl_error(self):
        pass
    def test_git_version_logic(self):
        pass
    def test_git_branch_descriptor_commands(self):
        pass
class TestConstraintValidation(unittest.TestCase):
    """
    Tests for console utilities.
    """

    def setUp(self):
        """
        Ensures the Shotgun version cache is cleared between tests.
        """
        super().setUp()
        # Set the server info on the Mockgun object.
        self._up_to_date_sg = Mockgun("https://foo.shotgunstudio.com")
        self._up_to_date_sg.server_info = {"version": (6, 6, 6)}
        self._out_of_date_sg = Mockgun("https://foo.shotgunstudio.com")
        self._out_of_date_sg.server_info = {"version": (6, 6, 5)}

    def _create_descriptor(
        self, version_constraints, supported_engines, sg_connection=None
    ):
        """
        Creates a descriptor for a fictitious app and mocks the get_manifest method
        so we can have some settings from info.yml

        :param version_constraints: Dictionary with keys min_sg, min_core and min_engine
            which are used to specify minimum version of Shotgun, Core and Engine.
        :param supported_engines: List of engines that are supported by this descriptor.
        :param sg_connection: Connection to the current Shotgun site. This will be used
            for comparing the version of Shotgun with the descriptor. If None, a
            Shotgun connection to a site using version 6.6.6 will be used.

        :returns: A sgtk.bootstrap.BundleDescriptor
        """
        desc = sgtk.descriptor.create_descriptor(
            sg_connection if sg_connection else self._up_to_date_sg,
            sgtk.descriptor.Descriptor.APP,
            "sgtk:descriptor:app_store?name=tk-test-app&version=v1.2.3",
        )

        # Mock the get_manifest method so it uses our fake info.yml file.
        desc._io_descriptor.get_manifest = mock.Mock(
            return_value={
                "requires_shotgun_version": version_constraints.get("min_sg"),
                "requires_core_version": version_constraints.get("min_core"),
                "requires_engine_version": version_constraints.get("min_engine"),
                "requires_desktop_version": version_constraints.get("min_desktop"),
                "supported_engines": supported_engines,
            }
        )
        return desc

    def test_min_sg_constraint_pass(self):
        pass
    def test_min_sg_constraint_fail(self):
        pass
    def test_min_core_constraint_pass(self):
        pass
    def test_min_core_constraint_fail(self):
        pass
    @mock.patch(
        "tank.pipelineconfig_utils.get_currently_running_api_version",
        return_value="v6.6.5",
    )
    def test_min_core_with_none_uses_fallabck(self, _):
        pass
    def test_min_engine_constraint_pass(self):
        pass
    def test_min_engine_constraint_fail(self):
        pass
    def test_supported_engine_constraint_pass(self):
        pass
    def test_supported_engine_constraint_fail(self):
        pass
    def test_min_desktop_constraint_pass(self):
        pass
    def test_min_desktop_constraint_fail(self):
        pass
    @mock.patch(
        "tank.descriptor.descriptor_bundle.BundleDescriptor._get_sg_version",
        return_value="6.6.5",
    )
    @mock.patch(
        "tank.pipelineconfig_utils.get_currently_running_api_version",
        return_value="v5.5.4",
    )
    def test_reasons_add_up(self, *_):
        pass
    def test_failure_when_param_missing(self):
        pass
class TestFeaturesApi(unittest.TestCase):
    def _create_core_desc(self, io_descriptor):
        """
        Helper method which creates an io_descriptor
        """
        sg_connection = mock.Mock()
        bundle_cache_root_override = None
        fallback_roots = None
        return sgtk.descriptor.CoreDescriptor(
            sg_connection, io_descriptor, bundle_cache_root_override, fallback_roots
        )

    def test_missing_manifest(self):
        pass
    def test_missing_features_section(self):
        pass
    def test_missing_feature(self):
        pass
    def test_available_feature(self):
        pass
    def test_core_features(self):
        pass
