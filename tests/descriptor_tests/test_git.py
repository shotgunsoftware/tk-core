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
import multiprocessing
import time

import sgtk
from sgtk.descriptor import Descriptor
from tank_test.tank_test_base import *

from tank_test.tank_test_base import TankTestBase, skip_if_git_missing, temp_env_var

class TestGitIODescriptor(TankTestBase):
    """
    Testing the Shotgun deploy main API methods
    """

    def setUp(self):
        """
        Sets up the next test's environment.
        """
        TankTestBase.setUp(self)

        # bare repo cloned from our official default config
        # multiple branches and tags
        self.git_repo_uri = os.path.join(self.fixtures_root, "misc", "tk-config-default.git")

        # Bare-minimum repo with both annotated and lightweight tags
        self.git_tag_repo_uri = os.path.join(self.fixtures_root, "misc", "tag-test-repo.git")

        self.bundle_cache = os.path.join(self.project_root, "bundle_cache")

    def _create_desc(self, location, resolve_latest=False, desc_type=Descriptor.CONFIG):
        """
        Helper method around create_descriptor
        """
        return sgtk.descriptor.create_descriptor(
            self.tk.shotgun,
            desc_type,
            location,
            bundle_cache_root_override=self.bundle_cache,
            resolve_latest=resolve_latest)

    @skip_if_git_missing
    def test_latest(self):

        location_dict = {
            "type": "git_branch",
            "path": self.git_repo_uri,
            "branch": "master"
        }

        desc = self._create_desc(location_dict, True)
        self.assertEqual(desc.version, "30c293f29a50b1e58d2580522656695825523dba")

        location_dict = {
            "type": "git",
            "path": self.git_repo_uri,
        }

        desc = self._create_desc(location_dict, True)
        self.assertEqual(desc.version, "v0.16.1")

    @skip_if_git_missing
    def test_tag(self):

        location_dict = {
            "type": "git",
            "path": self.git_repo_uri,
            "version": "v0.16.0"
        }

        desc = self._create_desc(location_dict)

        self.assertEqual(desc.version, "v0.16.0")
        self.assertEqual(desc.get_path(), None)

        desc.ensure_local()

        self.assertEqual(
            desc.get_path(),
            os.path.join(self.bundle_cache, "git", "tk-config-default.git", "v0.16.0")
        )

        latest_desc = desc.find_latest_version()

        self.assertEqual(latest_desc.version, "v0.16.1")
        self.assertEqual(latest_desc.get_path(), None)

        latest_desc.ensure_local()

        self.assertEqual(
            latest_desc.get_path(),
            os.path.join(self.bundle_cache, "git", "tk-config-default.git", "v0.16.1")
        )

        latest_desc = desc.find_latest_version("v0.15.x")

        self.assertEqual(latest_desc.version, "v0.15.11")
        self.assertEqual(latest_desc.get_path(), None)

        latest_desc.ensure_local()

        self.assertEqual(
            latest_desc.get_path(),
            os.path.join(self.bundle_cache, "git", "tk-config-default.git", "v0.15.11")
        )

        # test that the copy method copies the .git folder
        copy_target = os.path.join(self.project_root, "test_copy_target")
        latest_desc.copy(copy_target)
        self.assertTrue(os.path.exists(os.path.join(copy_target, ".git")))


    @skip_if_git_missing
    def test_branch_shorthash(self):

        location_dict = {
            "type": "git_branch",
            "path": self.git_repo_uri,
            "branch": "master",
            "version": "3e6a681"
        }

        desc = self._create_desc(location_dict)

        self.assertEqual(desc.get_path(), None)

        desc.ensure_local()

        self.assertEqual(
            desc.get_path(),
            os.path.join(self.bundle_cache, "gitbranch", "tk-config-default.git", "3e6a681")
        )


    @skip_if_git_missing
    def test_branch(self):

        location_dict = {
            "type": "git_branch",
            "path": self.git_repo_uri,
            "branch": "master",
            "version": "3e6a681234a02237e8bf35861b6439e7df73e05d"
        }

        desc = self._create_desc(location_dict)

        self.assertEqual(desc.get_path(), None)

        desc.ensure_local()

        self.assertEqual(
            desc.get_path(),
            os.path.join(self.bundle_cache, "gitbranch", "tk-config-default.git", "3e6a681")
        )

        latest_desc = desc.find_latest_version()

        self.assertEqual(latest_desc.version, "30c293f29a50b1e58d2580522656695825523dba")
        self.assertEqual(latest_desc.get_path(), None)

        latest_desc.ensure_local()

        self.assertEqual(
            latest_desc.get_path(),
            os.path.join(self.bundle_cache, "gitbranch", "tk-config-default.git", "30c293f")
        )

        location_dict = {
            "type": "git_branch",
            "path": self.git_repo_uri,
            "branch": "018_test",
            "version": "9035355e4e578dd874536ba333fedda0177d97a3"
        }

        desc = self._create_desc(location_dict)

        self.assertEqual(desc.get_path(), None)

        desc.ensure_local()

        self.assertEqual(
            desc.get_path(),
            os.path.join(self.bundle_cache, "gitbranch", "tk-config-default.git", "9035355")
        )

        latest_desc = desc.find_latest_version()

        self.assertEqual(latest_desc.version, "7fa75a749c1dfdbd9ad93ee3497c7eaa8e1a488d")
        self.assertEqual(latest_desc.get_path(), None)

        latest_desc.ensure_local()

        self.assertEqual(
            latest_desc.get_path(),
            os.path.join(self.bundle_cache, "gitbranch", "tk-config-default.git", "7fa75a7")
        )

        # test that the copy method copies the .git folder
        copy_target = os.path.join(self.project_root, "test_copy_target")
        latest_desc.copy(copy_target)
        self.assertTrue(os.path.exists(os.path.join(copy_target, ".git")))

    @skip_if_git_missing
    def test_downloads_to_bundle_cache(self):
        """
        Tests local downloads to the bundle cache for git descriptors.
        """
        def _download_bundles(target=None):
            """
            :param target: The path to which the bundle is to be downloaded.
            """
            location_dict_tag = {
                "type": "git",
                "path": self.git_repo_uri,
                "version": "v0.16.0"
            }
            location_dict_short_version = {
                "type": "git_branch",
                "path": self.git_repo_uri,
                "branch": "master",
                "version": "3e6a681"
            }
            location_dict_version = {
                "type": "git_branch",
                "path": self.git_repo_uri,
                "branch": "018_test",
                "version": "9035355e4e578dd874536ba333fedda0177d97a3"
            }
            location_dict_branch = {
                "type": "git_branch",
                "path": self.git_repo_uri,
                "branch": "master"
            }
            if target:
                with temp_env_var(SHOTGUN_BUNDLE_CACHE_PATH=target):
                    desc_git_tag = self._create_desc(location_dict_tag)
                    desc_git_short_version = self._create_desc(location_dict_short_version)
                    desc_git_version = self._create_desc(location_dict_version)
                    desc_git_branch = self._create_desc(location_dict_branch, True)
            else:
                desc_git_tag = self._create_desc(location_dict_tag)
                desc_git_short_version = self._create_desc(location_dict_short_version)
                desc_git_version = self._create_desc(location_dict_version)
                desc_git_branch = self._create_desc(location_dict_branch, True)
            desc_git_tag.download_local()
            desc_git_short_version.download_local()
            desc_git_version.download_local()
            desc_git_branch.download_local()

        processes = []
        errors = []

        # test concurrent downloads to a shared bundle cache by multiple processes.

        # the shared bundle cache path to which git data is to be downloaded.
        shared_dir = os.path.join(self.tank_temp, "shared_bundle_cache")
        try:
            # spawn 10 processes that begin downloading data to the shared path.
            for x in range(10):
                process = multiprocessing.Process(target=_download_bundles, args=(shared_dir,))
                process.start()
                processes.append(process)
        except Exception as e:
            errors.append(e)

        # wait until all processes have finished
        all_processes_finished = False
        while not all_processes_finished:
            time.sleep(0.1)
            all_processes_finished = all(not (process.is_alive()) for process in processes)

        # Make sure the number of processes forked are as expected.
        self.assertEqual(len(processes), 10, "Failed to spawn the expected number of processes.")

        # bit-wise OR the exit codes of all processes.
        all_processes_exit_code = reduce(
            lambda x, y: x | y,
            [proc.exitcode for proc in processes]
        )

        # Make sure none of the child processes had non-zero exit statuses.
        self.assertEqual(
            all_processes_exit_code,
            0,
            "Failed to write concurrently to shared bundle cache: %s" % ",".join(errors)
        )
