# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from functools import reduce
import multiprocessing
import os
from mock import patch
import sys
import tempfile
import time
import uuid
import zipfile

from tank_test.tank_test_base import TankTestBase, skip_if_git_missing, temp_env_var
from tank_test.tank_test_base import setUpModule # noqa

import sgtk
import tank


class TestDownloadableIODescriptors(TankTestBase):
    """
    Tests the ability of the descriptor to download to a path on disk.
    """
    ###############################################################################################
    # Helper methods

    def _setup_shotgun_data(self):
        """
        Sets up instance fields required for testing shotgun-related descriptor downloads.
        """
        # the path of the generated zip file that acts as a placeholder for a desciptor's zip package
        # in shotgun.
        self._attachment_zip_path = self._generate_zip_file()

        # the metadata identifying the descriptor's payload in shotgun.
        self._metadata = {
            'sg_version_data':
                {
                    'sg_payload':
                        {
                            'name': 'attachment-17922.zip',
                            'content_type': 'application/zip',
                            'type': 'Attachment',
                            'id': 17922,
                            'link_type': 'upload',
                        }
                },
            'sg_bundle_data': {},
        }

    def _setup_git_data(self):
        """
        Sets up instance fields required for testing git descriptor downloads.
        """
        # bare repo cloned from our official default config
        # multiple branches and tags
        self.git_repo_uri = os.path.join(self.fixtures_root, "misc", "tk-config-default.git")

        # Bare-minimum repo with both annotated and lightweight tags
        self.git_tag_repo_uri = os.path.join(self.fixtures_root, "misc", "tag-test-repo.git")

        self.bundle_cache = os.path.join(self.project_root, "bundle_cache")

    def _get_attachment_data(self, file_path):
        """
        Returns content of the file represented by `file_path`.
        :param file_path: The attachment id of the file to be downloaded.
        :return: Binary data of the file associated with the `file_path`.
        """
        with open(file_path, "rb") as f:
            content = f.read()
        return content

    def _download_and_unpack_attachment(self, sg, attachment_id, target, retries=5):
        """
        Mock implementation of the tank.util.shotgun.download_and_unpack_attachment() that
        reads a pre-generated zip file and unpacks it to the target.

        :param sg: Mocked Shotgun API instance
        :param attachment_id: Attachment ID to download
        :param target: Folder to unpack zip to. if not created, the method will
                       try to create it.
        :param retries: Number of times to retry before giving up
        """
        attempt = 0
        done = False

        while not done and attempt < retries:

            zip_tmp = os.path.join(tempfile.gettempdir(), "%s_tank.zip" % uuid.uuid4().hex)
            try:
                bundle_content = self._get_attachment_data(self._attachment_zip_path)
                with open(zip_tmp, "wb") as fh:
                    fh.write(bundle_content)

                tank.util.filesystem.ensure_folder_exists(target)
                tank.util.zip.unzip_file(zip_tmp, target)
            except Exception as e:
                print("Attempt %s: Attachment download failed: %s" % (attempt, e))
                attempt += 1
                # sleep 500ms before we retry
                time.sleep(0.5)
            else:
                done = True
            finally:
                # remove zip file
                tank.util.filesystem.safe_delete_file(zip_tmp)
        if not done:
            # we were not successful
            raise Exception("Failed to download after %s retries." % (retries))

    def _generate_zip_file(self, size=10):
        """
        Generates a zip file containing a single binary file of `size` Megabytes.
        :return: The path of the zip file
        """
        text_file_path = os.path.join(tempfile.gettempdir(), "%s_tank_content" % uuid.uuid4().hex)
        # write 10 MB of data into the text file
        with open(text_file_path, "wb") as f:
            f.seek((1024 * 1024 * size) - 1)
            f.write("\0")

        zip_file_path = os.path.join(tempfile.gettempdir(), "%s_tank_source.zip" % uuid.uuid4().hex)
        try:
            zf = zipfile.ZipFile(zip_file_path, "w")
            zf.write(text_file_path, arcname="large_binary_file")
        except Exception as e:
            print("Failed to create the temporary zip package at %s." % zip_file_path)
            raise e
        finally:
            zf.close()
        return zip_file_path

    def _create_desc(self, location, resolve_latest=False, desc_type=sgtk.descriptor.Descriptor.CONFIG):
        """
        Helper method around create_descriptor.
        """
        return sgtk.descriptor.create_descriptor(
            self.tk.shotgun,
            desc_type,
            location,
            resolve_latest=resolve_latest
        )

    def _download_app_store_bundle(self, target=None):
        """
        Creates an app store descriptor and attempts to download it locally.
        :param target: The path to which the bundle is to be downloaded.
        """
        if target:
            with temp_env_var(SHOTGUN_BUNDLE_CACHE_PATH=target):
                desc = sgtk.descriptor.create_descriptor(
                    None,
                    sgtk.descriptor.Descriptor.FRAMEWORK,
                    {"name": "tk-test-bundle2", "version": "v1.0.0", "type": "app_store"}
                )
        else:
            desc = sgtk.descriptor.create_descriptor(
                None,
                sgtk.descriptor.Descriptor.FRAMEWORK,
                {"name": "tk-test-bundle2", "version": "v1.0.0", "type": "app_store"}
            )
        io_descriptor_app_store = "tank.descriptor.io_descriptor.appstore.IODescriptorAppStore"
        with patch(
            "%s._IODescriptorAppStore__create_sg_app_store_connection" % io_descriptor_app_store,
            return_value=(self.mockgun, None)
        ):
            with patch(
                "%s._IODescriptorAppStore__refresh_metadata" % io_descriptor_app_store,
                return_value=self._metadata
            ):
                with patch(
                    "tank.util.shotgun.download_and_unpack_attachment",
                    side_effect=self._download_and_unpack_attachment
                ):
                    desc.download_local()

    def _download_shotgun_bundle(self, target=None):
        """
        Creates a shotgun entity descriptor and attempts to download it locally.
        :param target: The path to which the bundle is to be downloaded
        """
        location = {
            "type": "shotgun",
            "entity_type": "PipelineConfiguration",
            "name": "primary",
            "project_id": 123,
            "field": "sg_config",
            "version": 456
        }
        if target:
            with temp_env_var(SHOTGUN_BUNDLE_CACHE_PATH=target):
                desc = self._create_desc(location)
        else:
            desc = self._create_desc(location)
        with patch(
                "tank.util.shotgun.download_and_unpack_attachment",
                side_effect=self._download_and_unpack_attachment):
            desc.download_local()

    def _download_git_branch_bundle(self, target=None):
        """
        Downloads the data given by the git descriptors to disk.
        :param target: The path to which the bundle is to be downloaded.
        """
        location_dict_branch = {
            "type": "git_branch",
            "path": self.git_repo_uri,
            "branch": "33014_nuke_studio"
        }
        if target:
            with temp_env_var(SHOTGUN_BUNDLE_CACHE_PATH=target):
                desc_git_branch = self._create_desc(location_dict_branch, True)
        else:
            desc_git_branch = self._create_desc(location_dict_branch, True)
        desc_git_branch.download_local()

    def _download_git_tag_bundle(self, target=None):
        """
        Downloads the data given by the git descriptors to disk.
        :param target: The path to which the bundle is to be downloaded.
        """
        location_dict_tag = {
            "type": "git",
            "path": self.git_repo_uri,
            "version": "v0.15.0"
        }
        if target:
            with temp_env_var(SHOTGUN_BUNDLE_CACHE_PATH=target):
                desc_git_tag = self._create_desc(location_dict_tag)
        else:
            desc_git_tag = self._create_desc(location_dict_tag)
        desc_git_tag.download_local()

    def _test_multiprocess_download_to_shared_bundle_cache(self, func, shared_dir, expected_path):
        """
        Spawns 10 processes and attempts to run the download function simultaneously. It verifies
        that the process completes without errors, and the expected path of download exists.

        :param func: Function that downloads a descriptor
        :param expected_path: The expected path of the descriptor once it is downloaded locally.
        :param shared_dir: Optional shared directory to which the descriptor has to be downloaded to.
        """
        # skip this test on windows or py2.5 where multiprocessing isn't available
        # TODO: Test with subprocess instead of multiprocessing.
        if sys.platform == "win32" or sys.version_info < (2, 6):
            return

        processes = []
        errors = []

        try:
            # spawn 10 processes that begin downloading data to the shared path.
            for x in range(10):
                process = multiprocessing.Process(target=func, args=(shared_dir,))
                process.start()
                processes.append(process)
        except Exception as e:
            errors.append(e)

        # wait until all processes have finished
        all_processes_finished = False
        while not all_processes_finished:
            time.sleep(0.1)
            sys.stderr.write(".")
            all_processes_finished = all(not (process.is_alive()) for process in processes)

        # Make sure the number of processes forked are as expected.
        self.assertEqual(len(processes), 10, "Failed to spawn the expected number of processes.")

        # make sure the expected local path exists.
        self.assertTrue(
            os.path.exists(expected_path),
            "Failed to find the shared bundle cache directory for the descriptor on disk."
        )

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

    def _raise_exception(self, placeholder_a="default_a", placeholder_b="default_b"):
        """
        Generic mock function to raise an OSError.

        :param placeholder_a: Placeholder first argument
        :param placeholder_b: Placeholder second argument
        :raises: OSError
        """
        raise OSError("An unknown OSError occurred")

    ###############################################################################################

    def test_appstore_downloads(self):
        """
        Tests app store descriptor downloads to a bundle cache.
        """
        # setup shotgun test data
        self._setup_shotgun_data()

        # attempt to download the app store entity directly to the bundle cache.
        self._download_app_store_bundle()

        # make sure the expected local path exists.
        self.assertTrue(os.path.exists(
            os.path.join(self.tank_temp, "bundle_cache", "app_store", "tk-test-bundle2", "v1.0.0", "large_binary_file")
        ), "Failed to find the default bundle cache directory for the app store descriptor on disk.")

        # now test concurrent downloads to a shared bundle cache
        self._test_multiprocess_download_to_shared_bundle_cache(
            self._download_app_store_bundle,
            os.path.join(self.tank_temp, "shared_bundle_cache"),
            os.path.join(self.tank_temp, "shared_bundle_cache", "app_store",
                         "tk-test-bundle2", "v1.0.0", "large_binary_file")
        )

    def test_shotgun_entity_downloads(self):
        """
        Tests shotgun entity downloads to the bundle cache.
        """
        # setup shotgun test data.
        self._setup_shotgun_data()

        # attempt to download shotgun entity directly to the bundle cache.
        self._download_shotgun_bundle()

        # make sure the expected local path exists.
        self.assertTrue(os.path.exists(
            os.path.join(self.tank_temp, "bundle_cache", "sg", "unit_test_mock_sg", "PipelineConfiguration.sg_config",
                         "p123_primary", "v456", "large_binary_file")
        ), "Failed to find the default bundle cache directory for the shotgun entity descriptor on disk.")

        # now test concurrent downloads to a shared bundle cache
        self._test_multiprocess_download_to_shared_bundle_cache(
            self._download_shotgun_bundle,
            os.path.join(self.tank_temp, "shared_bundle_cache"),
            os.path.join(self.tank_temp, "shared_bundle_cache", "sg", "unit_test_mock_sg",
                         "PipelineConfiguration.sg_config", "p123_primary", "v456", "large_binary_file")
        )

    @skip_if_git_missing
    def test_git_tag_downloads(self):
        """
        Tests git tag descriptor downloads to the bundle cache.
        """
        # setup git test data
        self._setup_git_data()

        self._download_git_tag_bundle()

        # make sure the expected local path exists.
        self.assertTrue(os.path.exists(
            os.path.join(self.tank_temp, "bundle_cache", "git", "tk-config-default.git", "v0.15.0")
        ), "Failed to find the default bundle cache directory for the app store descriptor on disk.")

        # now test concurrent downloads to a shared bundle cache
        self._test_multiprocess_download_to_shared_bundle_cache(
            self._download_git_tag_bundle,
            os.path.join(self.tank_temp, "shared_bundle_cache"),
            os.path.join(self.tank_temp, "shared_bundle_cache", "git",
                         "tk-config-default.git", "v0.15.0")
        )

    @skip_if_git_missing
    def test_git_branch_downloads(self):
        """
        Tests git branch descriptor downloads to the bundle cache.
        """
        # setup git test data
        self._setup_git_data()

        self._download_git_branch_bundle()

        # make sure the expected local path exists.
        self.assertTrue(os.path.exists(
            os.path.join(self.tank_temp, "bundle_cache", "gitbranch", "tk-config-default.git", "e1c03fa")
        ), "Failed to find the default bundle cache directory for the app store descriptor on disk.")

        # now test concurrent downloads to a shared bundle cache
        self._test_multiprocess_download_to_shared_bundle_cache(
            self._download_git_branch_bundle,
            os.path.join(self.tank_temp, "shared_bundle_cache"),
            os.path.join(self.tank_temp, "shared_bundle_cache", "gitbranch",
                         "tk-config-default.git", "e1c03fa")
        )

    def test_descriptor_download_error_throws_exception(self):
        """
        Tests that an error during a descriptor download throws the required exception.
        """
        # setup shotgun test data
        self._setup_git_data()

        # ensure that an exception raised while downloading the descriptor to a
        # temporary folder will raise a TankDescriptorError
        with patch(
                "tank.descriptor.io_descriptor.git_branch.IODescriptorGitBranch._download_local",
                side_effect=self._raise_exception
        ):
            with self.assertRaises(tank.descriptor.errors.TankDescriptorError):
                self._download_git_branch_bundle()

        # ensure that an exception raised while renaming the temporary folder
        # to the target path will raise a TankError if the target does not exist.
        with patch(
                "os.rename",
                side_effect=self._raise_exception
        ):
            with self.assertRaises(tank.errors.TankError):
                self._download_git_branch_bundle()
