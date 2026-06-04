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
import sys
import tempfile
import time
import uuid
import shutil
import zipfile
import contextlib
import pytest

from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import (
    mock,
    ShotgunTestBase,
    skip_if_git_missing,
    temp_env_var,
)

import sgtk
import tank
from tank.util import is_windows


def _raise_exception(placeholder_a="default_a", placeholder_b="default_b"):
    """
    Generic mock function to raise an OSError.

    :param placeholder_a: Placeholder first argument
    :param placeholder_b: Placeholder second argument
    :raises: OSError
    """
    raise OSError("An unknown OSError occurred")


class TestDownloadableIODescriptors(ShotgunTestBase):
    """
    Tests the ability of the descriptor to download to a path on disk.
    """

    # In Python 3.8+, the TestCase class cannot be serialized due to a regression.
    # It appears an argument parser is reachable from the TestCase instance. The
    # multiprocessing module serializes both the test method and the instance
    # associated to it (which makes sense, since we need the test data on the
    # instance!). This becomes an issue, because ArgumentParser is not picklable
    # in Python 3.8 (due to a regression it seems). The cleanest way to avoid
    # this serialization issue without mucking around with the TestCase internals
    # and that generates the smallest diff is to create a new Implementation
    # class defined below that reimplements the necessary interface from
    # ShotgunTestBase and have the TestDownloadableIODescriptors call the test
    # methods on that new clean instance that is serializable.
    def setUp(self):
        """
        Instantiate the actual test class that is are pickle-able by multiprocessing
        and pass any information required for the test to function.
        """
        super().setUp()
        self.imp = Implementation(
            self.tank_temp, self.project_root, self.mockgun, self.fixtures_root
        )

    def test_appstore_downloads(self):
        pass
    def test_shotgun_entity_downloads(self):
        pass
    @skip_if_git_missing
    def test_git_tag_downloads(self):
        pass
    @skip_if_git_missing
    def test_git_branch_downloads(self):
        pass
    def test_descriptor_download_error_throws_exception(self):
        pass
    def test_descriptor_rename_error_fallbacks(self):
        pass
    def test_descriptor_rename_fallback_failure(self):
        pass
    def test_partial_download_handling(self):
        pass
class Implementation(object):
    """
    Class that actually contains the test and its data.
    """

    def __init__(self, tank_temp, project_root, mockgun, fixtures_root):
        """
        :param str tank_temp: Temporary folder where the test will write its files.
        :param str project_root: Root of the project
        :param mockgun: Mockgun instance with the test data.
        :param fixtures_root: Absolute path to the tests/fixtures folder.
        """
        self.tank_temp = tank_temp
        self.project_root = project_root
        self.mockgun = mockgun
        self.fixtures_root = fixtures_root

    # Implements some methods from TestCase, which will avoid
    # us having to modify the tests below and keep the history clean.
    def assertTrue(self, test, msg=""):
        assert not not test, msg

    def assertFalse(self, test, msg=""):
        assert not test, msg

    def assertEqual(self, lhs, rhs, msg=""):
        assert lhs == rhs, msg

    def assertNotEqual(self, lhs, rhs, msg=""):
        assert lhs != rhs, msg

    @contextlib.contextmanager
    def assertRaises(self, exception_type):
        with pytest.raises(exception_type):
            yield

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
            "sg_version_data": {
                "sg_payload": {
                    "name": "attachment-17922.zip",
                    "content_type": "application/zip",
                    "type": "Attachment",
                    "id": 17922,
                    "link_type": "upload",
                }
            },
            "sg_bundle_data": {},
        }

    def _setup_git_data(self):
        """
        Sets up instance fields required for testing git descriptor downloads.
        """
        # bare repo cloned from our official default config
        # multiple branches and tags
        self.git_repo_uri = os.path.join(
            self.fixtures_root, "misc", "tk-config-default.git"
        )

        # Bare-minimum repo with both annotated and lightweight tags
        self.git_tag_repo_uri = os.path.join(
            self.fixtures_root, "misc", "tag-test-repo.git"
        )

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

    def _download_and_unpack_attachment(
        self, sg, attachment_id, target, retries=5, auto_detect_bundle=False
    ):
        """
        Mock implementation of the tank.util.shotgun.download_and_unpack_attachment() that
        reads a pre-generated zip file and unpacks it to the target.

        :param sg: Mocked Shotgun API instance
        :param attachment_id: Attachment ID to download
        :param target: Folder to unpack zip to. if not created, the method will
                       try to create it.
        :param retries: Number of times to retry before giving up
        :param auto_detect_bundle: Hints that the attachment contains a toolkit bundle
            (config, app, engine, framework) and that this should be attempted to be
            detected and unpacked intelligently. For example, if the zip file contains
            the bundle in a subfolder, this should be correctly unfolded.
        """
        attempt = 0
        done = False

        while not done and attempt < retries:

            zip_tmp = os.path.join(
                tempfile.gettempdir(), "%s_tank.zip" % uuid.uuid4().hex
            )
            try:
                bundle_content = self._get_attachment_data(self._attachment_zip_path)
                with open(zip_tmp, "wb") as fh:
                    fh.write(bundle_content)

                tank.util.filesystem.ensure_folder_exists(target)
                tank.util.zip.unzip_file(zip_tmp, target, auto_detect_bundle)
            except Exception as e:
                print(("Attempt %s: Attachment download failed: %s" % (attempt, e)))
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
        text_file_path = os.path.join(
            tempfile.gettempdir(), "%s_tank_content" % uuid.uuid4().hex
        )
        # write 10 MB of data into the text file
        with open(text_file_path, "wb") as f:
            f.seek((1024 * 1024 * size) - 1)
            f.write(b"\0")

        zip_file_path = os.path.join(
            tempfile.gettempdir(), "%s_tank_source.zip" % uuid.uuid4().hex
        )
        try:
            zf = zipfile.ZipFile(zip_file_path, "w")
            zf.write(text_file_path, arcname="large_binary_file")
        except Exception as e:
            print(("Failed to create the temporary zip package at %s." % zip_file_path))
            raise e
        finally:
            zf.close()
        return zip_file_path

    def _create_desc(
        self,
        location,
        resolve_latest=False,
        desc_type=sgtk.descriptor.Descriptor.CONFIG,
    ):
        """
        Helper method around create_descriptor.
        """
        return sgtk.descriptor.create_descriptor(
            self.mockgun, desc_type, location, resolve_latest=resolve_latest
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
                    {
                        "name": "tk-test-bundle2",
                        "version": "v1.0.0",
                        "type": "app_store",
                    },
                )
        else:
            desc = sgtk.descriptor.create_descriptor(
                None,
                sgtk.descriptor.Descriptor.FRAMEWORK,
                {"name": "tk-test-bundle2", "version": "v1.0.0", "type": "app_store"},
            )
        io_descriptor_app_store = (
            "tank.descriptor.io_descriptor.appstore.IODescriptorAppStore"
        )
        with mock.patch(
            "%s._IODescriptorAppStore__create_sg_app_store_connection"
            % io_descriptor_app_store,
            return_value=(self.mockgun, None),
        ):
            with mock.patch(
                "%s._IODescriptorAppStore__refresh_metadata" % io_descriptor_app_store,
                return_value=self._metadata,
            ):
                with mock.patch(
                    "tank.util.shotgun.download_and_unpack_attachment",
                    side_effect=self._download_and_unpack_attachment,
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
            "version": 456,
        }
        if target:
            with temp_env_var(SHOTGUN_BUNDLE_CACHE_PATH=target):
                desc = self._create_desc(location)
        else:
            desc = self._create_desc(location)
        with mock.patch(
            "tank.util.shotgun.download_and_unpack_attachment",
            side_effect=self._download_and_unpack_attachment,
        ):
            desc.download_local()

    def _download_git_branch_bundle(self, target=None):
        """
        Downloads the data given by the git descriptors to disk.
        :param target: The path to which the bundle is to be downloaded.
        :returns: a descriptor instance
        """
        location_dict_branch = {
            "type": "git_branch",
            "path": self.git_repo_uri,
            "branch": "33014_nuke_studio",
        }
        if target:
            with temp_env_var(SHOTGUN_BUNDLE_CACHE_PATH=target):
                desc_git_branch = self._create_desc(location_dict_branch, True)
        else:
            desc_git_branch = self._create_desc(location_dict_branch, True)
        desc_git_branch.download_local()

        return desc_git_branch

    def _download_git_tag_bundle(self, target=None):
        """
        Downloads the data given by the git descriptors to disk.
        :param target: The path to which the bundle is to be downloaded.
        """
        location_dict_tag = {
            "type": "git",
            "path": self.git_repo_uri,
            "version": "v0.15.0",
        }
        if target:
            with temp_env_var(SHOTGUN_BUNDLE_CACHE_PATH=target):
                desc_git_tag = self._create_desc(location_dict_tag)
        else:
            desc_git_tag = self._create_desc(location_dict_tag)
        desc_git_tag.download_local()

    def _test_multiprocess_download_to_shared_bundle_cache(
        self, func, shared_dir, expected_path
    ):
        """
        Spawns 10 processes and attempts to run the download function simultaneously. It verifies
        that the process completes without errors, and the expected path of download exists.

        :param func: Function that downloads a descriptor
        :param expected_path: The expected path of the descriptor once it is downloaded locally.
        :param shared_dir: Optional shared directory to which the descriptor has to be downloaded to.
        """

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
            all_processes_finished = all(
                not (process.is_alive()) for process in processes
            )

        # Make sure the number of processes forked are as expected.
        self.assertEqual(
            len(processes), 10, "Failed to spawn the expected number of processes."
        )

        # make sure the expected local path exists.
        self.assertTrue(
            os.path.exists(expected_path),
            "Failed to find the shared bundle cache directory for the descriptor on disk.",
        )

        # bit-wise OR the exit codes of all processes.
        all_processes_exit_code = reduce(
            lambda x, y: x | y, [proc.exitcode for proc in processes]
        )

        # Make sure none of the child processes had non-zero exit statuses.
        self.assertEqual(
            all_processes_exit_code,
            0,
            "Failed to write concurrently to shared bundle cache: %s"
            % ",".join(errors),
        )

    ###############################################################################################

    def test_appstore_downloads(self):
        pass
    def test_shotgun_entity_downloads(self):
        pass
    @skip_if_git_missing
    def test_git_tag_downloads(self):
        pass
    @skip_if_git_missing
    def test_git_branch_downloads(self):
        pass
    def test_descriptor_download_error_throws_exception(self):
        pass
    @mock.patch("os.rename", side_effect=_raise_exception)
    def test_descriptor_rename_error_fallbacks(self, *_):
        pass
    @mock.patch("tank.util.filesystem.move_folder")
    @mock.patch("os.rename", side_effect=_raise_exception)
    def test_descriptor_rename_fallback_failure(self, rename_mock, move_mock):
        pass
    def test_partial_download_handling(self):
        pass
