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
        with temp_env_var(SHOTGUN_ENTITY_TYPE="Shot", SHOTGUN_ENTITY_ID="123"):
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
