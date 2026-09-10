# Copyright (c) 2026 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
from unittest import mock

import sgtk
from sgtk.descriptor import Descriptor
from tank_test.tank_test_base import (
    ShotgunTestBase,
    setUpModule,  # noqa
    skip_if_git_lfs_missing,
    skip_if_git_missing,
)


class TestGitLFSIODescriptor(ShotgunTestBase):
    """
    Testing the Git LFS validation performed by IODescriptorGit.
    """

    def setUp(self):
        """
        Sets up the next test's environment.
        """
        ShotgunTestBase.setUp(self)

        # bare repo with a single file tracked via Git LFS
        self.git_lfs_repo_uri = os.path.join(
            self.fixtures_root, "misc", "lfs-test-repo.git"
        )

        # each test gets its own bundle cache so a download in one test can't
        # be mistaken for an already-resolved download in another
        self.bundle_cache = os.path.join(
            self.project_root, "bundle_cache_%s" % self._testMethodName
        )

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
    @skip_if_git_lfs_missing
    def test_lfs_content_resolved(self):
        """
        A repo whose Git LFS content resolves normally should check out fine.
        """
        location_dict = {
            "type": "git_branch",
            "path": self.git_lfs_repo_uri,
            "branch": "master",
        }

        desc = self._create_desc(location_dict, True)
        desc.ensure_local()

        lfs_file_path = os.path.join(desc.get_path(), "sample.dat")
        with open(lfs_file_path, "r") as fh:
            self.assertEqual(fh.read(), "hello lfs content for tk-core tests\n")

    @skip_if_git_missing
    @skip_if_git_lfs_missing
    def test_lfs_content_unresolved(self):
        """
        If Git LFS content is checked out as unresolved pointer text (e.g.
        git-lfs wasn't registered on the machine that did the clone), Toolkit
        should raise rather than silently use the pointer file as-is.
        """
        location_dict = {
            "type": "git_branch",
            "path": self.git_lfs_repo_uri,
            "branch": "master",
        }

        desc = self._create_desc(location_dict, True)

        with mock.patch.dict(os.environ, {"GIT_LFS_SKIP_SMUDGE": "1"}):
            with self.assertRaises(sgtk.descriptor.errors.TankDescriptorError):
                desc.ensure_local()
