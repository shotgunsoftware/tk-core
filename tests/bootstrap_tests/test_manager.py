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
from tank_test.tank_test_base import TankTestBase, temp_env_var


class TestErrorHandling(TankTestBase):

    def test_get_pipeline_configurations_by_id(self):
        """
        Ensure that the resolver detects when an installed configuration has not been set for the
        current platform.
        """
        def find_mock_impl(*args, **kwargs):
            mgr = ToolkitManager()
            mgr.pipeline_configuration = 1
            with self.assertRaisesRegexp(
                sgtk.bootstrap.TankBootstrapError,
                "Can't enumerate pipeline configurations matching a specific id."
            ):
                mgr.get_pipeline_configurations(None)


class TestFunctionality(TankTestBase):

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
