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

from tank_test.tank_test_base import TankTestBase
from tank_test.tank_test_base import setUpModule # noqa
from tank.errors import TankError

from mock import Mock, patch


class TestDescriptorSupport(TankTestBase):

    def setUp(self, parameters=None):

        super(TestDescriptorSupport, self).setUp()

        self.install_root = os.path.join(
            self.tk.pipeline_configuration.get_install_location(),
            "install"
        )

    def _create_info_yaml(self, path):
        """
        create a mock info.yml
        """
        sgtk.util.filesystem.ensure_folder_exists(path)
        fh = open(os.path.join(path, "info.yml"), "wt")
        fh.write("foo")
        fh.close()

    def test_app_store_descriptor_location(self):
        """
        Tests an appstore descriptor bundle path for the given bundle type and location.
        """

        location = {"type": "app_store", "version": "v0.1.2", "name": "tk-bundle"}
        path = os.path.join(self.install_root, "app_store", "tk-bundle", "v0.1.2")
        self._create_info_yaml(path)

        d = self.tk.pipeline_configuration.get_app_descriptor(location)
        self.assertEqual(d.get_path(), path)

        d = self.tk.pipeline_configuration.get_engine_descriptor(location)
        self.assertEqual(d.get_path(), path)

        d = self.tk.pipeline_configuration.get_framework_descriptor(location)
        self.assertEqual(d.get_path(), path)

    def test_manual_descriptor_location(self):
        """
        Tests a manual descriptor bundle path for the given bundle type and location.
        """

        location = {"type": "manual", "version": "v0.1.2", "name": "tk-bundle"}
        path = os.path.join(self.install_root, "manual", "tk-bundle", "v0.1.2")
        self._create_info_yaml(path)

        d = self.tk.pipeline_configuration.get_app_descriptor(location)
        self.assertEqual(d.get_path(), path)

        d = self.tk.pipeline_configuration.get_engine_descriptor(location)
        self.assertEqual(d.get_path(), path)

        d = self.tk.pipeline_configuration.get_framework_descriptor(location)
        self.assertEqual(d.get_path(), path)

    def test_dev_descriptor_location(self):
        """
        Tests a dev descriptor bundle path
        """
        path = os.path.join(self.tk.pipeline_configuration.get_path(), "bundle")
        self._create_info_yaml(path)

        d = self.tk.pipeline_configuration.get_app_descriptor({"type": "dev", "path": "{PIPELINE_CONFIG}/bundle"})
        self.assertEqual(d.get_path(), path)

        d = self.tk.pipeline_configuration.get_app_descriptor({"type": "dev", "path": path})
        self.assertEqual(d.get_path(), path)

    def _test_git_descriptor_location_with_repo(self, repo):
        """
        Tests a git descriptor bundle path for the given bundle type and location and a given
        repo.
        """
        path = os.path.join(self.install_root, "git", os.path.basename(repo), "v0.1.2")
        self._create_info_yaml(path)

        d = self.tk.pipeline_configuration.get_app_descriptor({"type": "git", "path": repo, "version": "v0.1.2"})
        self.assertEqual(d.get_path(), path)

    def test_git_descriptor_location(self):
        """
        Tests a git descriptor bundle path for the given bundle type and location for all
        supported repo naming convention.

        :param bundle_type: One of descriptor.AppDescriptor.{APP,ENGINE,FRAMEWORK}
        :param bundle_location: Location in the pipeline configuration where bundles of the given
            type get installed.
        """
        for uri in [
            "git@github.com:manneohrstrom/tk-hiero-publish.git",
            "https://github.com/manneohrstrom/tk-hiero-publish.git",
            "git://github.com/manneohrstrom/tk-hiero-publish.git",
            "/full/path/to/local/repo.git"
        ]:
            self._test_git_descriptor_location_with_repo(uri)

    def test_git_version_logic(self):
        """
        Test git descriptor version logic
        """
        desc = self.tk.pipeline_configuration.get_app_descriptor(
            {"type": "git", "path": "git@github.com:dummy/tk-multi-dummy.git", "version": "v1.2.3"}
        )

        v1 = ["v1.2.3"]
        v2 = ["v1.2.3", "v1.2.2"]
        v3 = ["v1.2.3", "v1.2.233", "v1.3.1", "v2.3.1"]
        v4 = ["v1.2.3", "v2.3.1.8", "v1.2.233", "v1.3.1", "v2.3.1", "v1.2.233.34"]
        v5 = ["v1.2.3", "v1.2.233", "v1.4.233", "v1.3.1.2.3"]

        # no input
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern([], None), None)
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern([], "vx.x.x"), None)

        # just latest version
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(v1, None), "v1.2.3")
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(v2, None), "v1.2.3")
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(v3, None), "v2.3.1")
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(v4, None), "v2.3.1.8")
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(v5, None), "v1.4.233")

        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(v1, "vx.x.x"), "v1.2.3")
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(v2, "vx.x.x"), "v1.2.3")
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(v3, "vx.x.x"), "v2.3.1")
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(v4, "vx.x.x"), "v2.3.1.8")
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(v5, "vx.x.x"), "v1.4.233")

        # absolute match
        for vv in [v1, v2, v3, v4, v5]:
            self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(vv, "v1.2.3"), "v1.2.3")

        # simple matches
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(v1, "v1.2.x"), "v1.2.3")
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(v2, "v1.2.x"), "v1.2.3")
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(v3, "v1.2.x"), "v1.2.233")
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(v4, "v1.2.x"), "v1.2.233.34")
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(v5, "v1.2.x"), "v1.2.233")

        self.assertEqual(
            desc._io_descriptor._find_latest_tag_by_pattern(["v1.2.3", "v1.2.233", "v1.3.1"], "v1.3.x"),
            "v1.3.1"
        )
        self.assertEqual(
            desc._io_descriptor._find_latest_tag_by_pattern(["v1.2.3", "v1.2.233", "v1.3.1", "v2.3.1"], "v1.x.x"),
            "v1.3.1"
        )

        # forks
        self.assertEqual(
            desc._io_descriptor._find_latest_tag_by_pattern(["v1.2.3", "v1.2.233", "v1.3.1.2.3"], "v1.3.x"),
            "v1.3.1.2.3"
        )
        self.assertEqual(
            desc._io_descriptor._find_latest_tag_by_pattern(
                ["v1.2.3", "v1.2.233", "v1.3.1.2.3", "v1.4.233"], "v1.3.1.x"
            ),
            "v1.3.1.2.3"
        )

        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(
            ["v1.2.3", "v1.2.233", "v1.5.1"], "v1.3.x"),
            None
        )
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(
            ["v1.2.3", "v1.2.233", "v1.5.1"], "v2.x.x"),
            None
        )
        self.assertEqual(desc._io_descriptor._find_latest_tag_by_pattern(
            ["v1.2.3", "v1.2.233", "v5.5.1"], "v2.x.x"),
            None
        )

        # invalids
        self.assertRaisesRegexp(TankError,
                                "Incorrect version pattern '.*'. There should be no digit after a 'x'",
                                desc._io_descriptor._find_latest_tag_by_pattern,
                                ["v1.2.3", "v1.2.233", "v1.3.1"],
                                "v1.x.2")


class SealedMock(Mock):
    """
    Sealed mock ensures that no one is accessing something we have not planned for.
    """
    def __init__(self, **kwargs):
        """
        :param kwargs: Passed down directly to the base class as kwargs. Each keys are passed to the ``spec_set``
            argument from the base class to seal the gettable and settable properties.
        """
        super(SealedMock, self).__init__(spec_set=kwargs.keys(), **kwargs)


class TestConstraintValidation(TankTestBase):
    """
    Tests for console utilities.
    """

    def setUp(self):
        """
        Ensures the Shotgun version cache is cleared between tests.
        """
        super(TestConstraintValidation, self).setUp()
        # Uncache the shotgun versions between tests.
        sgtk.descriptor.descriptor_bundle.BundleDescriptor._sg_studio_versions = {}

        self._up_to_date_sg = SealedMock(base_url="https://foo.shotgunstudio.com", server_info={"version": "6.6.6"})
        self._out_of_date_sg = SealedMock(base_url="https://foo.shotgunstudio.com", server_info={"version": "6.6.5"})

    def _create_descriptor(self, version_constraints, supported_engines):
        """
        Creates a descriptor for a fictitious app and mocks the get_manifest method
        so we can have some settings from info.yml

        :param version_constraints: Dictionary with keys min_sg, min_core and min_engine
            which are used to specify minimum version of Shotgun, Core and Engine.

        :returns: A sgtk.bootstrap.BundleDescriptor
        """
        desc = sgtk.descriptor.create_descriptor(
            self.mockgun,
            sgtk.descriptor.Descriptor.APP,
            "sgtk:descriptor:app_store?name=tk-test-app&version=v1.2.3"
        )

        # Mock the get_manifest method so it uses our fake info.yml file.
        desc._io_descriptor.get_manifest = Mock(
            return_value={
                "requires_shotgun_version": version_constraints.get("min_sg"),
                "requires_core_version": version_constraints.get("min_core"),
                "requires_engine_version": version_constraints.get("min_engine"),
                "requires_desktop_version": version_constraints.get("min_desktop"),
                "supported_engines": supported_engines
            }
        )
        return desc

    def test_min_sg_constraint_pass(self):
        """
        Ensures that having a greater or equal version of Shotgun works.
        """
        can_update, reasons = self._create_descriptor(
            version_constraints={"min_sg": "6.6.6"},
            supported_engines=None
        ).check_version_constraints(
            self._up_to_date_sg
        )

        self.assertEqual(can_update, True)
        self.assertListEqual(reasons, [])

    def test_min_sg_constraint_fail(self):
        """
        Ensures that having an older version of Shotgun fails.
        """
        can_update, reasons = self._create_descriptor(
            version_constraints={"min_sg": "6.6.6"},
            supported_engines=None
        ).check_version_constraints(
            self._out_of_date_sg
        )

        self.assertEqual(can_update, False)
        self.assertEqual(len(reasons), 1)
        self.assertRegexpMatches(reasons[0], "Requires at least Shotgun .* but currently installed version is .*\.")

    def test_min_core_constraint_pass(self):
        """
        Ensures that having a greater or equal version of core works.
        """
        can_update, reasons = self._create_descriptor(
            version_constraints={"min_core": "v6.6.6"},
            supported_engines=None
        ).check_version_constraints(self._up_to_date_sg, "v6.6.6")

        self.assertEqual(can_update, True)
        self.assertListEqual(reasons, [])

    def test_min_core_constraint_fail(self):
        """
        Ensures that having a lower version of core fails.
        """
        can_update, reasons = self._create_descriptor(
            version_constraints={"min_core": "v6.6.6"},
            supported_engines=None
        ).check_version_constraints(self._up_to_date_sg, "v6.6.5")
        self.assertEqual(can_update, False)
        self.assertEqual(len(reasons), 1)
        self.assertRegexpMatches(reasons[0], "Requires at least Core API .* but currently installed version is v6.6.5")

    @patch("tank.pipelineconfig_utils.get_currently_running_api_version", return_value="v6.6.5")
    def test_min_core_with_none_uses_fallabck(self, _):
        can_update, reasons = self._create_descriptor(
            version_constraints={"min_core": "v6.6.6"},
            supported_engines=None
        ).check_version_constraints(self._up_to_date_sg, core_version=None)
        self.assertEqual(can_update, False)
        self.assertEqual(len(reasons), 1)
        self.assertRegexpMatches(reasons[0], "Requires at least Core API .* but currently installed version is v6.6.5")

    def test_min_engine_constraint_pass(self):
        """
        Ensures that having a greater or equal version of the engine works.
        """
        can_update, reasons = self._create_descriptor(
            version_constraints={"min_engine": "v6.6.6"},
            supported_engines=None
        ).check_version_constraints(
            self._up_to_date_sg,
            parent_engine_descriptor=SealedMock(version="v6.6.6")
        )
        self.assertEqual(can_update, True)
        self.assertListEqual(reasons, [])

    def test_min_engine_constraint_fail(self):
        """
        Ensures that having a lower version of the engine fails.
        """
        can_update, reasons = self._create_descriptor(
            version_constraints={"min_engine": "v6.6.6"},
            supported_engines=None
        ).check_version_constraints(
            self._up_to_date_sg,
            parent_engine_descriptor=SealedMock(version="v6.6.5", display_name="Tk Test")
        )
        self.assertEqual(can_update, False)
        self.assertRegexpMatches(reasons[0], "Requires at least Engine .* but currently installed version is .*")

    def test_supported_engine_constraint_pass(self):
        """
        Ensures that being installed in a supported engine works.
        """
        can_update, reasons = self._create_descriptor(
            version_constraints={},
            supported_engines=["tk-test"]
        ).check_version_constraints(
            self._up_to_date_sg,
            parent_engine_descriptor=SealedMock(
                system_name="tk-test",
                display_name="Tk Test"
            )
        )
        self.assertEqual(can_update, True)
        self.assertListEqual(reasons, [])

    def test_supported_engine_constraint_fail(self):
        """
        Ensures that being installed in an unsupported engine fails.
        """
        can_update, reasons = self._create_descriptor(
            version_constraints={},
            supported_engines=["tk-test"]
        ).check_version_constraints(
            self._up_to_date_sg,
            parent_engine_descriptor=SealedMock(
                version="v6.6.5",
                system_name="tk-another-test",
                display_name="tk-test"
            )
        )
        self.assertEqual(can_update, False)
        self.assertRegexpMatches(reasons[0], "Not compatible with engine .*. Supported engines are .*")

    def test_min_desktop_constraint_pass(self):
        """
        Ensures that having a greater or equal version of Shotgun works.
        """
        can_update, reasons = self._create_descriptor(
            version_constraints={"min_desktop": "6.6.6"},
            supported_engines=None
        ).check_version_constraints(
            self._up_to_date_sg,
            desktop_version="v6.6.6"
        )

        self.assertEqual(can_update, True)
        self.assertListEqual(reasons, [])

    def test_min_desktop_constraint_fail(self):
        """
        Ensures that having an older version of Shotgun fails.
        """
        can_update, reasons = self._create_descriptor(
            version_constraints={"min_desktop": "6.6.6"},
            supported_engines=None
        ).check_version_constraints(
            self._up_to_date_sg,
            desktop_version="v6.6.5"
        )

        self.assertEqual(can_update, False)
        self.assertEqual(len(reasons), 1)
        self.assertRegexpMatches(reasons[0], "Requires at least Shotgun Desktop.* but currently installed version is .*\.")

    @patch("tank.descriptor.descriptor_bundle.BundleDescriptor._get_sg_version", return_value="6.6.5")
    @patch("tank.pipelineconfig_utils.get_currently_running_api_version", return_value="v5.5.4")
    def test_reasons_add_up(self, *_):
        """
        Ensures that having multiple failures add up.
        """
        can_update, reasons = self._create_descriptor(
            version_constraints={
                "min_core": "v5.5.5",
                "min_sg": "v6.6.6",
                "min_engine": "v4.4.4",
                "min_desktop": "v3.3.4"
            },
            supported_engines=["tk-test"]
        ).check_version_constraints(
            self._out_of_date_sg,
            parent_engine_descriptor=SealedMock(
                version="v4.4.3",
                system_name="tk-another-test",
                display_name="tk-test"
            ),
            desktop_version="v3.3.3"
        )

        self.assertEqual(can_update, False)
        self.assertEqual(len(reasons), 5)

    def test_failure_when_param_missing(self):
        can_update, reasons = self._create_descriptor(
            version_constraints={
                # No need to test for core since passing None uses the current core version instead.
                "min_sg": "v6.6.6",
                "min_engine": "v4.4.4",
                "min_desktop": "v3.3.4"
            },
            supported_engines=["tk-test"]
        ).check_version_constraints(
            connection=None,
            core_version=None,
            parent_engine_descriptor=None,
            desktop_version=None
        )

        self.assertEqual(can_update, False)
        self.assertEqual(len(reasons), 4)
