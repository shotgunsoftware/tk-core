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
import shutil
import subprocess
import tempfile
import unittest.mock

import sgtk
from tank_test.tank_test_base import (
    ShotgunTestBase,
    _is_git_lfs_missing,
    _is_git_missing,
    setUpModule,  # noqa
    skip_if_git_lfs_missing,
    skip_if_git_missing,
)

LFS_FILE_NAME = "sample.dat"
LFS_FILE_CONTENT = "hello lfs content for tk-core tests\n"


@skip_if_git_missing
@skip_if_git_lfs_missing
class TestGitLFSIODescriptor(ShotgunTestBase):
    """
    Testing the Git LFS validation performed by IODescriptorGit.
    """

    @classmethod
    def setUpClass(cls):
        """
        Builds, once for the whole test class, a small local git repo with a
        single file tracked via Git LFS. This repo is used as a read-only
        clone source by every test - no need to check in a repo fixture,
        it's trivial and fast to (re)build on demand.
        """
        super().setUpClass()

        cls.git_lfs_repo_uri = None
        if _is_git_missing() or _is_git_lfs_missing():
            # tests are skipped in this case, no need to build the repo
            return

        cls.git_lfs_repo_uri = tempfile.mkdtemp(prefix="tk_test_lfs_repo_")
        env = dict(
            os.environ,
            GIT_AUTHOR_NAME="tk-core tests",
            GIT_AUTHOR_EMAIL="tk-core-tests@example.com",
            GIT_COMMITTER_NAME="tk-core tests",
            GIT_COMMITTER_EMAIL="tk-core-tests@example.com",
        )

        def _run(*args):
            subprocess.check_call(args, cwd=cls.git_lfs_repo_uri, env=env)

        _run("git", "init", "-q", "-b", "master")
        _run("git", "lfs", "install", "--local")
        with open(os.path.join(cls.git_lfs_repo_uri, LFS_FILE_NAME), "w") as fh:
            fh.write(LFS_FILE_CONTENT)
        _run("git", "lfs", "track", LFS_FILE_NAME)
        _run("git", "add", ".gitattributes", LFS_FILE_NAME)
        _run("git", "commit", "-q", "-m", "initial commit with an lfs file")

    @classmethod
    def tearDownClass(cls):
        if cls.git_lfs_repo_uri:
            shutil.rmtree(cls.git_lfs_repo_uri, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        """
        Sets up the next test's environment.
        """
        ShotgunTestBase.setUp(self)

        # each test gets its own bundle cache so a download in one test can't
        # be mistaken for an already-resolved download in another
        self.bundle_cache = os.path.join(
            self.project_root, "bundle_cache_%s" % self._testMethodName
        )

    def _create_desc(
        self,
        location,
        resolve_latest=False,
        desc_type=sgtk.descriptor.Descriptor.CONFIG,
    ):
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

        lfs_file_path = os.path.join(desc.get_path(), LFS_FILE_NAME)
        with open(lfs_file_path, "r") as fh:
            self.assertEqual(fh.read(), LFS_FILE_CONTENT)

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

        with unittest.mock.patch.dict(os.environ, {"GIT_LFS_SKIP_SMUDGE": "1"}):
            with self.assertRaises(sgtk.descriptor.errors.TankDescriptorError):
                desc.ensure_local()
