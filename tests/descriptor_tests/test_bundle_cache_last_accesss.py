# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from tank_test.tank_test_base import TankTestBase

import sgtk
from sgtk.descriptor.bundle_cache_last_access import BundleCacheLastAccess

class TestBundleCacheLastAccess(TankTestBase):
    """
    Testing the bundle cache last access & cleanup feature.
    """

    def setUp(self):
        super(TestBundleCacheLastAccess, self).setUp()
        # TODO: add setup below

    def tearDown(self):
        # TODO: add cleanup above
        super(TestBundleCacheLastAccess, self).tearDown()

    def test_db_creation(self):
        """
        Test most basic database creation when db does not exists

        Simply verify there isn't any exception
        """
        db = BundleCacheLastAccess()


