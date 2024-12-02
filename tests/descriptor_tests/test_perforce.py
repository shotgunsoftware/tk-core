# Copyright (c) 2016 Shotgun Software Inc.
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
from sgtk.descriptor import Descriptor
from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import ShotgunTestBase, skip_if_p4_missing


class TestPerforceIODescriptor(ShotgunTestBase):
    """
    Testing the Shotgun deploy main API methods
    """

    def setUp(self):
        """
        Sets up the next test's environment.
        """
        ShotgunTestBase.setUp(self)

        # Depot path, Requires p4 server with a bundle path
        # and app with a changelist and a label
        self.p4_depot_uri = "//TestRepo/AppStore/tk-shotgun-pythonconsole"

        self.bundle_cache = os.path.join(self.project_root, "bundle_cache")

    def _create_desc(self, location, resolve_latest=False, desc_type=Descriptor.CONFIG):
        """
        Helper method around create_descriptor
        """
        return sgtk.descriptor.create_descriptor(
            self.mockgun,
            desc_type,
            location,
            bundle_cache_root_override=self.bundle_cache,
            resolve_latest=resolve_latest,
        )

    @skip_if_p4_missing
    def test_latest(self):

        location_dict = {
            "type": "perforce_change",
            "path": self.p4_depot_uri,
            "changelist": "100",
        }

        desc = self._create_desc(location_dict, True)
        self.assertEqual(desc.version, "100")

        location_dict = {
            "type": "perforce_label",
            "path": self.p4_depot_uri,
            "label": "v1.0.0",
        }

        desc = self._create_desc(location_dict, True)
        self.assertEqual(desc.version, "v1.0.0")

    @skip_if_p4_missing
    def test_change(self):

        location_dict = {
            "type": "perforce_change",
            "path": self.p4_depot_uri,
            "changelist": "100",
        }

        desc = self._create_desc(location_dict)

        self.assertEqual(desc.get_path(), None)

        desc.ensure_local()

        self.assertEqual(
            desc.get_path(),
            os.path.join(
                self.bundle_cache, "perforce_change", "100", "tk-shotgun-pythonconsole"
            ),
        )

        latest_desc = desc.find_latest_version()

        self.assertEqual(latest_desc.version, "100")
        self.assertEqual(latest_desc.get_path(), None)

        latest_desc.ensure_local()

        self.assertEqual(
            latest_desc.get_path(),
            os.path.join(
                self.bundle_cache, "perforce_change", "tk-shotgun-pythonconsole", "100"
            ),
        )

        # test that the copy method copies the .git folder
        copy_target = os.path.join(self.project_root, "test_copy_target")
        latest_desc.copy(copy_target)
        self.assertTrue(os.path.exists(copy_target))

    @skip_if_p4_missing
    def test_label(self):
        location_dict = {
            "type": "perforce_label",
            "path": self.p4_depot_uri,
            "label": "v1.0.0",
        }

        desc = self._create_desc(location_dict)

        self.assertEqual(desc.get_path(), None)

        desc.ensure_local()

        self.assertEqual(
            desc.get_path(),
            os.path.join(
                self.bundle_cache,
                "perforce_label",
                "tk-shotgun-pythonconsole",
                "v1.0.0",
            ),
        )

        latest_desc = desc.find_latest_version()

        self.assertEqual(latest_desc.version, "v1.0.0")
        self.assertEqual(latest_desc.get_path(), None)

        latest_desc.ensure_local()

        self.assertEqual(
            latest_desc.get_path(),
            os.path.join(
                self.bundle_cache,
                "perforce_label",
                "tk-shotgun-pythonconsole",
                "v1.0.0",
            ),
        )

        # test that the copy method copies the .git folder
        copy_target = os.path.join(self.project_root, "test_copy_target")
        latest_desc.copy(copy_target)
        self.assertTrue(os.path.exists(copy_target))
