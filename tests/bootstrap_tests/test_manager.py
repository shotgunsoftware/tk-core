# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from __future__ import with_statement
import os

import sgtk
from mock import patch, Mock

from sgtk.bootstrap import ToolkitManager

from tank_test.tank_test_base import setUpModule # noqa
from tank_test.tank_test_base import ShotgunTestBase, temp_env_var
from tank_test.tank_test_base import TankTestBase


class TestErrorHandling(ShotgunTestBase):

    def test_get_pipeline_configurations_by_id(self):
        """
        Ensure that the resolver detects when an installed configuration has not been set for the
        current platform.
        """
        def find_mock_impl(*args, **kwargs):
            mgr = ToolkitManager()
            mgr.pipeline_configuration = 1
            with self.assertRaisesRegex(
                sgtk.bootstrap.TankBootstrapError,
                "Can't enumerate pipeline configurations matching a specific id."
            ):
                mgr.get_pipeline_configurations(None)


class TestFunctionality(ShotgunTestBase):

    @patch("tank.authentication.ShotgunAuthenticator.get_user", return_value=Mock())
    def test_pipeline_config_id_env_var(self, _):
        """
        Tests the SHOTGUN_PIPELINE_CONFIGURATION_ID being picked up at init
        """
        mgr = ToolkitManager()
        self.assertEqual(mgr.pipeline_configuration, None)

        with temp_env_var(SHOTGUN_PIPELINE_CONFIGURATION_ID="123"):
            mgr = ToolkitManager()
            self.assertEqual(mgr.pipeline_configuration, 123)

        with temp_env_var(SHOTGUN_PIPELINE_CONFIGURATION_ID="invalid"):
            mgr = ToolkitManager()
            self.assertEqual(mgr.pipeline_configuration, None)

    @patch("tank.authentication.ShotgunAuthenticator.get_user", return_value=Mock())
    def test_get_entity_from_environment(self, _):
        """
        Ensure the ToolkitManager can extract the entities from the environment
        """

        # no env set
        mgr = ToolkitManager()
        self.assertEqual(mgr.get_entity_from_environment(), None)

        # std case
        with temp_env_var(
            SHOTGUN_ENTITY_TYPE="Shot",
            SHOTGUN_ENTITY_ID="123"
        ):
            self.assertEqual(
                mgr.get_entity_from_environment(),
                {"type": "Shot", "id": 123}
            )
        # site mismatch
        with temp_env_var(
            SHOTGUN_SITE="https://some.other.site",
            SHOTGUN_ENTITY_TYPE="Shot",
            SHOTGUN_ENTITY_ID="123"
        ):
            self.assertEqual(
                mgr.get_entity_from_environment(),
                None
            )

        # invalid data case
        with temp_env_var(
            SHOTGUN_ENTITY_TYPE="Shot",
            SHOTGUN_ENTITY_ID="invalid"
        ):
            self.assertEqual(
                mgr.get_entity_from_environment(),
                None
            )

    @patch("tank.authentication.ShotgunAuthenticator.get_user", return_value=Mock())
    def test_shotgun_bundle_cache(self, _):
        """
        Ensures ToolkitManager deals property with bundle cache from the user and from
        environment variables.
        """

        # Ensure the list is empty by default.
        mgr = ToolkitManager()
        self.assertEqual(mgr._get_bundle_cache_fallback_paths(), [])

        # If the user bundle cache is set, we should see it in the results.
        mgr.bundle_cache_fallback_paths = ["/a/b/c", "/d/e/f"]
        self.assertEqual(
            set(mgr._get_bundle_cache_fallback_paths()), set(["/a/b/c", "/d/e/f"]))

        # Reset the user bundle cache.
        mgr.bundle_cache_fallback_paths = []
        self.assertEqual(mgr._get_bundle_cache_fallback_paths(), [])

        # Set the environment variable which allows to inherit paths from another process.
        with temp_env_var(
            SHOTGUN_BUNDLE_CACHE_FALLBACK_PATHS=os.pathsep.join(["/g/h/i", "/j/k/l", "/a/b/c"])
        ):
            # Should see the content from the environment variable.
            self.assertEqual(
                set(mgr._get_bundle_cache_fallback_paths()), set(["/g/h/i", "/j/k/l", "/a/b/c"]))

            # Add a few user specified folders.
            mgr.bundle_cache_fallback_paths = ["/a/b/c", "/d/e/f"]

            self.assertEqual(
                set(mgr._get_bundle_cache_fallback_paths()),
                set(["/a/b/c", "/d/e/f", "/g/h/i", "/j/k/l"])
            )

        # Now that the env var is not set anymore we should see its bundle caches.
        self.assertEqual(
            set(mgr._get_bundle_cache_fallback_paths()), set(["/a/b/c", "/d/e/f"])
        )

    @patch("tank.authentication.ShotgunAuthenticator.get_user", return_value=Mock())
    def test_serialization(self, _):
        """
        Ensures we're serializing the manager properly.
        """
        # Make sure nobody has added new parameters that need to be serialized.
        class_attrs = set(dir(ToolkitManager))
        instance_attrs = set(dir(ToolkitManager()))
        unserializable_attrs = set(
            ["_sg_connection", "_sg_user", "_pre_engine_start_callback", "_progress_cb"]
        )
        # Through this operation, we're taking all the symbols that are defined from an instance,
        # we then remove everything that is defined also in the class, which means we're left
        # with what was added during __init__, and then we remove the parameters we know can't
        # be serialized. We're left with a small list of values that can be serialized.
        instance_data_members = instance_attrs - class_attrs - unserializable_attrs
        self.assertEqual(len(instance_data_members), 7)

        # Create a manager that hasn't been updated yet.
        clean_mgr = ToolkitManager()
        clean_settings = clean_mgr.extract_settings()

        # Now create one where we modify everything.
        modified_mgr = ToolkitManager()
        modified_mgr.bundle_cache_fallback_paths = ["/a/b/c"]
        modified_mgr.caching_policy = ToolkitManager.CACHE_FULL
        modified_mgr.pipeline_configuration = "Primary"
        modified_mgr.base_configuration = "sgtk:descriptor:app_store?"\
            "version=v0.18.91&name=tk-config-basic"
        modified_mgr.do_shotgun_config_lookup = False
        modified_mgr.plugin_id = "basic.default"
        modified_mgr.allow_config_overrides = False

        # Extract settings and make sure the implementation still stores dictionaries.
        modified_settings = modified_mgr.extract_settings()
        self.assertIsInstance(modified_settings, dict)

        # Make sure the unit test properly changes all the settings from their default values.
        for k, v in modified_settings.iteritems():
            self.assertNotEqual(v, clean_settings[k])

        # Restore the settings from the manager.
        restored_mgr = ToolkitManager()
        restored_mgr.restore_settings(modified_settings)

        # Extract the settings back from the restored manager to make sure everything was written
        # back correctly.
        self.assertEqual(restored_mgr.extract_settings(), modified_settings)


class _MockedShotgunUser(object):
    """
    A fake shotgun user object that we can pass to the manager.
    """
    def __init__(self, mockgun, login):
        self._mockgun = mockgun
        self._login = login

    @property
    def login(self):
        """
        Current User Login
        """
        return self._login

    def create_sg_connection(self):
        """
        Returns the associated mockgun connection
        """
        return self._mockgun


class TestPrepareEngine(ShotgunTestBase):

    def setUp(self):
        super(TestPrepareEngine, self).setUp({"primary_root_name": "primary"})

    def test_prepare_engine(self):
        """
        Makes sure that prepare engine works.
        """
        mgr = ToolkitManager(_MockedShotgunUser(self.mockgun, "larry"))
        mgr.do_shotgun_config_lookup = False
        mgr.base_configuration = {
            "type": "path",
            "path": os.path.join(
                self.fixtures_root, "bootstrap_tests", "config"
            )
        }

        def progress_cb(progress_value, message):
            self.assertLess(progress_cb.previous_progress, progress_value)
            progress_cb.previous_progress = progress_value
            if message.startswith("Checking"):
                progress_cb.nb_exists_locally += 1

        progress_cb.nb_exists_locally = 0
        progress_cb.previous_progress = -1

        mgr.progress_callback = progress_cb
        path, desc = mgr.prepare_engine("test_engine", self.project)
        self.assertEqual(desc.get_dict(), mgr.base_configuration)
        self.assertEqual(path, os.path.join(self.tank_temp, "unit_test_mock_sg", "p1", "cfg"))
        self.assertEqual(progress_cb.nb_exists_locally, 3)


class TestGetPipelineConfigs(TankTestBase):

    def setUp(self):
        super(TestGetPipelineConfigs, self).setUp()

        self._john_doe = self.mockgun.create("HumanUser", {"login": "john.doe"})
        self._john_smith = self.mockgun.create("HumanUser", {"login": "john.smith"})
        self._project = self.mockgun.create("Project", {"name": "my_project"})
        self._mocked_sg_user = _MockedShotgunUser(self.mockgun, "john.doe")

    def test_basic_execution(self):
        """
        Test basic execution and return value structure
        """
        cc = self.mockgun.create(
            "PipelineConfiguration",
            dict(
                code="Primary",
                project=self._project,
                users=[],
                windows_path=None,
                mac_path=None,
                linux_path=None,
                plugin_ids="basic.*",
                descriptor="sgtk:descriptor:app_store?name=tk-config-basic&version=v1.2.3",
                uploaded_config=None,
            )
        )

        mgr = ToolkitManager(self._mocked_sg_user)
        mgr.plugin_id = "basic.test"
        configs = mgr.get_pipeline_configurations(self._project)

        expected_fields = [
            "descriptor_source_uri",
            "name",
            "project",
            "descriptor",
            "type",
            "id"
        ]

        self.assertEqual(len(configs), 1)
        config = configs[0]
        self.assertEqual(sorted(expected_fields), sorted(config.keys()))
        self.assertEqual(config["id"], cc["id"])
        self.assertEqual(config["type"], "PipelineConfiguration")
        self.assertEqual(config["name"], "Primary")
        self.assertEqual(config["project"], self._project)
        self.assertEqual(config["descriptor"].get_uri(), "sgtk:descriptor:app_store?name=tk-config-basic&version=v1.2.3")
        self.assertEqual(config["descriptor_source_uri"], "sgtk:descriptor:app_store?name=tk-config-basic&version=v1.2.3")

        # with a different plugin id we won't get anything
        mgr.plugin_id = "something.else"
        configs = mgr.get_pipeline_configurations(self._project)
        self.assertEqual(len(configs), 0)

    def test_user_filters(self):
        """
        Test user based sandboxes
        """
        self.mockgun.create(
            "PipelineConfiguration",
            dict(
                code="Doe Dev",
                project=self._project,
                users=[self._john_doe],
                windows_path=None,
                mac_path=None,
                linux_path=None,
                plugin_ids="basic.*",
                descriptor="sgtk:descriptor:app_store?name=tk-config-basic&version=v1.2.3",
                uploaded_config=None,
            )
        )

        self.mockgun.create(
            "PipelineConfiguration",
            dict(
                code="Smith Dev",
                project=self._project,
                users=[self._john_smith],
                windows_path=None,
                mac_path=None,
                linux_path=None,
                plugin_ids="basic.*",
                descriptor="sgtk:descriptor:app_store?name=tk-config-basic&version=v1.2.3",
                uploaded_config=None,
            )
        )

        mgr = ToolkitManager(self._mocked_sg_user)
        mgr.plugin_id = "basic.test"
        configs = mgr.get_pipeline_configurations(self._project)

        self.assertEqual(len(configs), 1)
        config = configs[0]
        self.assertEqual(config["name"], "Doe Dev")

    @patch("tank.bootstrap.resolver.ConfigurationResolver._create_config_descriptor", return_value=Mock())
    def test_latest_tracking_descriptor(self, _):
        """
        Test descriptors tracking latest
        """
        self.mockgun.create(
            "PipelineConfiguration",
            dict(
                code="Primary",
                project=self._project,
                users=[],
                windows_path=None,
                mac_path=None,
                linux_path=None,
                plugin_ids="basic.*",
                descriptor="sgtk:descriptor:app_store?name=tk-config-basic",
                uploaded_config=None,
            )
        )

        mgr = ToolkitManager(self._mocked_sg_user)
        mgr.plugin_id = "basic.test"
        configs = mgr.get_pipeline_configurations(self._project)

        config = configs[0]
        self.assertTrue(isinstance(config["descriptor"], Mock))
        self.assertEqual(config["descriptor_source_uri"], "sgtk:descriptor:app_store?name=tk-config-basic")

    def test_override_logic(self):
        """
        Tests that paths override descriptors
        """

        self.mockgun.create(
            "PipelineConfiguration",
            dict(
                code="Primary",
                project=self._project,
                users=[],
                windows_path="/path",
                mac_path="/path",
                linux_path="/path",
                plugin_ids="basic.*",
                descriptor="sgtk:descriptor:app_store?name=tk-config-basic&version=v1.2.3",
                uploaded_config=None,
            )
        )

        mgr = ToolkitManager(self._mocked_sg_user)
        mgr.plugin_id = "basic.test"
        configs = mgr.get_pipeline_configurations(self._project)

        config = configs[0]
        self.assertEqual(
            config["descriptor"].get_uri(),
            "sgtk:descriptor:path?linux_path=/path&mac_path=/path&windows_path=\\path"
        )
        self.assertEqual(config["descriptor_source_uri"], None)
