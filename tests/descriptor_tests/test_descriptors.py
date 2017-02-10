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
from tank.descriptor import CheckVersionConstraintsError

from mock import Mock, patch

from tank_vendor.shotgun_api3.lib.mockgun import Shotgun as Mockgun


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
        # Set the server info on the Mockgun object.
        self._up_to_date_sg = Mockgun("https://foo.shotgunstudio.com")
        self._up_to_date_sg.server_info = {"version": (6, 6, 6)}
        self._out_of_date_sg = Mockgun("https://foo.shotgunstudio.com")
        self._out_of_date_sg.server_info = {"version": (6, 6, 5)}

    def _create_descriptor(self, version_constraints, supported_engines, sg_connection=None):
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
        self._create_descriptor(
            version_constraints={"min_sg": "6.6.6"},
            supported_engines=None
        ).check_version_constraints()

    def test_min_sg_constraint_fail(self):
        """
        Ensures that having an older version of Shotgun fails.
        """

        with self.assertRaises(CheckVersionConstraintsError) as ctx:
            self._create_descriptor(
                version_constraints={"min_sg": "6.6.6"},
                supported_engines=None,
                sg_connection=self._out_of_date_sg
            ).check_version_constraints()

        self.assertEqual(len(ctx.exception.reasons), 1)
        self.assertRegexpMatches(
            ctx.exception.reasons[0], "Requires at least Shotgun .* but currently installed version is .*\."
        )

    def test_min_core_constraint_pass(self):
        """
        Ensures that having a greater or equal version of core works.
        """
        self._create_descriptor(
            version_constraints={"min_core": "v6.6.6"},
            supported_engines=None
        ).check_version_constraints("v6.6.6")

    def test_min_core_constraint_fail(self):
        """
        Ensures that having a lower version of core fails.
        """
        with self.assertRaises(CheckVersionConstraintsError) as ctx:
            self._create_descriptor(
                version_constraints={"min_core": "v6.6.6"},
                supported_engines=None
            ).check_version_constraints("v6.6.5")

        self.assertEqual(len(ctx.exception.reasons), 1)
        self.assertRegexpMatches(
            ctx.exception.reasons[0], "Requires at least Core API .* but currently installed version is v6.6.5"
        )

    @patch("tank.pipelineconfig_utils.get_currently_running_api_version", return_value="v6.6.5")
    def test_min_core_with_none_uses_fallabck(self, _):
        with self.assertRaises(CheckVersionConstraintsError) as ctx:
            self._create_descriptor(
                version_constraints={"min_core": "v6.6.6"},
                supported_engines=None
            ).check_version_constraints(core_version=None)

        self.assertEqual(len(ctx.exception.reasons), 1)
        self.assertRegexpMatches(
            ctx.exception.reasons[0], "Requires at least Core API .* but currently installed version is v6.6.5"
        )

    def test_min_engine_constraint_pass(self):
        """
        Ensures that having a greater or equal version of the engine works.
        """
        self._create_descriptor(
            version_constraints={"min_engine": "v6.6.6"},
            supported_engines=None
        ).check_version_constraints(
            engine_descriptor=SealedMock(version="v6.6.6")
        )

    def test_min_engine_constraint_fail(self):
        """
        Ensures that having a lower version of the engine fails.
        """
        with self.assertRaises(CheckVersionConstraintsError) as ctx:
            self._create_descriptor(
                version_constraints={"min_engine": "v6.6.6"},
                supported_engines=None
            ).check_version_constraints(
                engine_descriptor=SealedMock(version="v6.6.5", display_name="Tk Test")
            )

        self.assertRegexpMatches(
            ctx.exception.reasons[0],
            "Requires at least Engine .* but currently installed version is .*"
        )

    def test_supported_engine_constraint_pass(self):
        """
        Ensures that being installed in a supported engine works.
        """
        self._create_descriptor(
            version_constraints={},
            supported_engines=["tk-test"]
        ).check_version_constraints(
            engine_descriptor=SealedMock(
                system_name="tk-test",
                display_name="Tk Test"
            )
        )

    def test_supported_engine_constraint_fail(self):
        """
        Ensures that being installed in an unsupported engine fails.
        """
        with self.assertRaises(CheckVersionConstraintsError) as ctx:
            self._create_descriptor(
                version_constraints={},
                supported_engines=["tk-test"]
            ).check_version_constraints(
                engine_descriptor=SealedMock(
                    version="v6.6.5",
                    system_name="tk-another-test",
                    display_name="tk-test"
                )
            )

        self.assertRegexpMatches(
            ctx.exception.reasons[0], "Not compatible with engine .*. Supported engines are .*"
        )

    def test_min_desktop_constraint_pass(self):
        """
        Ensures that having a greater or equal version of Shotgun works.
        """
        self._create_descriptor(
            version_constraints={"min_desktop": "6.6.6"},
            supported_engines=None
        ).check_version_constraints(
            desktop_version="v6.6.6"
        )

    def test_min_desktop_constraint_fail(self):
        """
        Ensures that having an older version of Shotgun fails.
        """
        with self.assertRaises(CheckVersionConstraintsError) as ctx:
            self._create_descriptor(
                version_constraints={"min_desktop": "6.6.6"},
                supported_engines=None
            ).check_version_constraints(
                desktop_version="v6.6.5"
            )

        self.assertEqual(len(ctx.exception.reasons), 1)
        self.assertRegexpMatches(
            ctx.exception.reasons[0],
            "Requires at least Shotgun Desktop.* but currently installed version is .*\."
        )

    @patch("tank.descriptor.descriptor_bundle.BundleDescriptor._get_sg_version", return_value="6.6.5")
    @patch("tank.pipelineconfig_utils.get_currently_running_api_version", return_value="v5.5.4")
    def test_reasons_add_up(self, *_):
        """
        Ensures that having multiple failures add up.
        """
        with self.assertRaises(CheckVersionConstraintsError) as ctx:
            self._create_descriptor(
                version_constraints={
                    "min_core": "v5.5.5",
                    "min_sg": "v6.6.6",
                    "min_engine": "v4.4.4",
                    "min_desktop": "v3.3.4"
                },
                supported_engines=["tk-test"]
            ).check_version_constraints(
                engine_descriptor=SealedMock(
                    version="v4.4.3",
                    system_name="tk-another-test",
                    display_name="tk-test"
                ),
                desktop_version="v3.3.3"
            )

        self.assertEqual(len(ctx.exception.reasons), 5)

    def test_failure_when_param_missing(self):
        """
        Ensures that when the user is not passing any information that the
        """
        with self.assertRaises(CheckVersionConstraintsError) as ctx:
            self._create_descriptor(
                version_constraints={
                    # No need to test for core or Shotgun since passing None uses the current core
                    # and Shotgun version instead.
                    "min_engine": "v4.4.4",
                    "min_desktop": "v3.3.4"
                },
                supported_engines=["tk-test"]
            ).check_version_constraints()

        self.assertEqual(len(ctx.exception.reasons), 3)
        self.assertRegexpMatches(
            ctx.exception.reasons[0],
            "Requires a minimal engine version but no engine was specified"
        )
        self.assertRegexpMatches(
            ctx.exception.reasons[1], "Bundle is compatible with a subset of engines but no engine was specified"
        )
        self.assertRegexpMatches(
            ctx.exception.reasons[2], "Requires at least Shotgun Desktop v3.3.4 but no version was specified"
        )
