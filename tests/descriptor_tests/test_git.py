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
from tank_test.tank_test_base import ShotgunTestBase, skip_if_git_missing


class TestGitIODescriptor(ShotgunTestBase):
    """
    Testing the Shotgun deploy main API methods
    """

    def setUp(self):
        pass
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

    @skip_if_git_missing
    def test_latest(self):
        pass
    @skip_if_git_missing
    def test_tag(self):
        pass
    @skip_if_git_missing
    def test_branch_shorthash(self):
        pass
    @skip_if_git_missing
    def test_branch(self):
        pass
    @skip_if_git_missing
    def test_fail(self):
        pass
