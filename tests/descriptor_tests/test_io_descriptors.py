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
from mock import patch
import sys
import tempfile
import time
import uuid
import zipfile

from tank_test.tank_test_base import TankTestBase, temp_env_var
from tank_test.tank_test_base import setUpModule # noqa

import sgtk
import tank


class TestIODescriptors(TankTestBase):
    """
    Testing the Shotgun deploy main API methods
    """

    def test_version_resolve(self):
        """
        Tests the is_descriptor_version_missing method
        """
        self.assertEqual(
            sgtk.descriptor.is_descriptor_version_missing(
                {"type": "app_store", "version": "v1.1.1", "name": "tk-bundle"}
            ),
            False
        )
        self.assertEqual(
            sgtk.descriptor.is_descriptor_version_missing(
                {"type": "app_store", "name": "tk-bundle"}
            ),
            True
        )
        self.assertEqual(
            sgtk.descriptor.is_descriptor_version_missing(
                "sgtk:descriptor:app_store?version=v0.1.2&name=tk-bundle"
            ),
            False
        )
        self.assertEqual(
            sgtk.descriptor.is_descriptor_version_missing(
                "sgtk:descriptor:app_store?name=tk-bundle"
            ),
            True
        )
        self.assertEqual(
            sgtk.descriptor.is_descriptor_version_missing({"type": "dev", "path": "/tmp"}),
            False
        )
        self.assertEqual(
            sgtk.descriptor.is_descriptor_version_missing({"type": "path", "path": "/tmp"}),
            False
        )
        self.assertEqual(
            sgtk.descriptor.is_descriptor_version_missing({"type": "manual", "name": "foo"}),
            True
        )
        self.assertEqual(
            sgtk.descriptor.is_descriptor_version_missing({"type": "shotgun", "name": "foo"}),
            True
        )
        self.assertEqual(
            sgtk.descriptor.is_descriptor_version_missing({"type": "git", "path": "foo"}),
            True
        )
        self.assertEqual(
            sgtk.descriptor.is_descriptor_version_missing({"type": "git_branch", "path": "foo"}),
            True
        )

    def test_latest_cached(self):
        """
        Tests the find_latest_cached_version method
        """
        sg = self.tk.shotgun
        root = os.path.join(self.project_root, "cache_root")

        d = sgtk.descriptor.create_descriptor(
            sg,
            sgtk.descriptor.Descriptor.APP,
            {"type": "app_store", "version": "v1.1.1", "name": "tk-bundle"},
            bundle_cache_root_override=root
        )

        d2 = sgtk.descriptor.create_descriptor(
            sg,
            sgtk.descriptor.Descriptor.APP,
            {"type": "app_store", "version": "v1.2.1", "name": "tk-bundle"},
            bundle_cache_root_override=root
        )

        d3 = sgtk.descriptor.create_descriptor(
            sg,
            sgtk.descriptor.Descriptor.APP,
            {"type": "app_store", "version": "v1.3.1", "name": "tk-bundle"},
            bundle_cache_root_override=root
        )

        self.assertEqual(d.get_path(), None)
        self.assertEqual(d.find_latest_cached_version(), None)

        app_path = os.path.join(root, "app_store", "tk-bundle", "v1.1.1")
        path = os.path.join(app_path, "info.yml")

        os.makedirs(app_path)
        fh = open(path, "wt")
        fh.write("test data\n")
        fh.close()

        self.assertEqual(d.get_path(), app_path)
        self.assertEqual(d.find_latest_cached_version(), d)

        self.assertEqual(d2.get_path(), None)

        app_path = os.path.join(root, "app_store", "tk-bundle", "v1.2.1")
        path = os.path.join(app_path, "info.yml")
        os.makedirs(app_path)
        fh = open(path, "wt")
        fh.write("test data\n")
        fh.close()

        self.assertEqual(d2.get_path(), app_path)
        self.assertEqual(d.find_latest_cached_version(), d2)

        # Check to make sure we find a bundle that doesn't have an info.yml.
        app_path = os.path.join(root, "app_store", "tk-bundle", "v1.3.1")
        os.makedirs(app_path)

        self.assertEqual(d3.get_path(), app_path)
        self.assertEqual(d.find_latest_cached_version(), d3)

        # now check constraints
        self.assertEqual(d.find_latest_cached_version("v1.1.x"), d)
        self.assertEqual(d.find_latest_cached_version("v1.2.x"), d2)
        self.assertEqual(d.find_latest_cached_version("v1.x.x"), d3)
        self.assertEqual(d.find_latest_cached_version("v2.x.x"), None)

    def test_cache_locations(self):
        """
        Tests locations of caches when using fallback paths and
        the bundle cache path environment variable.
        """
        sg = self.tk.shotgun

        root_a = os.path.join(self.project_root, "cache_root_a")
        root_b = os.path.join(self.project_root, "cache_root_b")
        root_c = os.path.join(self.project_root, "cache_root_c")
        root_d = os.path.join(self.project_root, "cache_root_d")
        root_env = os.path.join(self.project_root, "cache_root_env")

        location = {"type": "app_store", "version": "v1.1.1", "name": "tk-bundle"}

        d = sgtk.descriptor.create_descriptor(
            sg,
            sgtk.descriptor.Descriptor.APP,
            location,
            bundle_cache_root_override=root_a,
            fallback_roots=[root_b, root_c, root_d]
        )

        self.assertEqual(
            d._io_descriptor._get_primary_cache_path(),
            os.path.join(root_a, "app_store", "tk-bundle", "v1.1.1")
        )

        # the bundle cache path set in the environment should
        # take precedence other cache paths.
        with temp_env_var(SHOTGUN_BUNDLE_CACHE_PATH=root_env):
            desc_env = sgtk.descriptor.create_descriptor(
                sg,
                sgtk.descriptor.Descriptor.APP,
                location,
                bundle_cache_root_override=root_a,
                fallback_roots=[root_b, root_c, root_d]
            )

            self.assertEqual(
                desc_env._io_descriptor._get_primary_cache_path(),
                os.path.join(root_env, "app_store", "tk-bundle", "v1.1.1")
            )

        self.assertEqual(
            d._io_descriptor._get_cache_paths(),
            [
                os.path.join(root_b, "app_store", "tk-bundle", "v1.1.1"),
                os.path.join(root_c, "app_store", "tk-bundle", "v1.1.1"),
                os.path.join(root_d, "app_store", "tk-bundle", "v1.1.1"),
                os.path.join(root_a, "app_store", "tk-bundle", "v1.1.1"),
                os.path.join(root_a, "apps", "app_store", "tk-bundle", "v1.1.1") # legacy path
            ]
        )

    def test_download_receipt(self):
        """
        Tests the download receipt logic
        """
        sg = self.tk.shotgun
        root = os.path.join(self.project_root, "cache_root")

        d = sgtk.descriptor.create_descriptor(
            sg,
            sgtk.descriptor.Descriptor.APP,
            {"type": "app_store", "version": "v1.1.1", "name": "tk-bundle"},
            bundle_cache_root_override=root
        )

        self.assertEqual(d.get_path(), None)
        self.assertEqual(d.find_latest_cached_version(), None)

        bundle_path = os.path.join(root, "app_store", "tk-bundle", "v1.1.1")
        info_path = os.path.join(bundle_path, "info.yml")

        os.makedirs(bundle_path)
        with open(info_path, "wt") as fh:
            fh.write("test data\n")

        self.assertEqual(d.get_path(), bundle_path)
        self.assertEqual(d.find_latest_cached_version(), d)

    def test_downloads_to_bundle_cache(self):
        """
        Tests downloads to a shared bundle cache for shotgun-related descriptors.
        """
        def _get_attachment_data(file_path):
            """
            Returns content of the file represented by `file_path`.
            :param attachment_id: The attachment id of the file to be downloaded.
            :return: Binary data of zip file associated with the file_path.
            """
            with open(file_path, "rb") as f:
                content = f.read()
            return content

        def _download_and_unpack_attachment(sg, attachment_id, target, retries=5):
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
                    bundle_content = _get_attachment_data(attachment_zip_path)
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

        def _generate_zip_file(size=10):
            """
            Generates a zip file containing a single file of `size` Megabytes.
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

        def _create_desc(location, resolve_latest=False, desc_type=sgtk.descriptor.Descriptor.CONFIG):
            """
            Helper method around create_descriptor
            """
            return sgtk.descriptor.create_descriptor(
                self.tk.shotgun,
                desc_type,
                location,
                resolve_latest=resolve_latest
            )

        def _download_app_store_bundle(target=None):
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
                    return_value=metadata
                ):
                    with patch(
                        "tank.util.shotgun.download_and_unpack_attachment",
                        side_effect=_download_and_unpack_attachment
                    ):
                        desc.download_local()

        def _download_shotgun_bundle(target=None):
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
                    desc = _create_desc(location)
            else:
                desc = _create_desc(location)
            with patch(
                    "tank.util.shotgun.download_and_unpack_attachment",
                    side_effect=_download_and_unpack_attachment):
                desc.download_local()

        processes = []
        errors = []
        attachment_zip_path = _generate_zip_file()

        metadata = {
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

        # attempt to download the app store entity directly to the bundle cache.
        _download_app_store_bundle()

        # make sure the expected local path exists.
        self.assertTrue(os.path.exists(
            os.path.join(self.tank_temp, "bundle_cache", "app_store", "tk-test-bundle2", "v1.0.0", "large_binary_file")
        ), "Failed to find the default bundle cache directory for the app store descriptor on disk.")

        # attempt to download shotgun entity directly to the bundle cache.
        _download_shotgun_bundle()

        # make sure the expected local path exists.
        self.assertTrue(os.path.exists(
            os.path.join(self.tank_temp, "bundle_cache", "sg", "unit_test_mock_sg", "PipelineConfiguration.sg_config",
                         "p123_primary", "v456", "large_binary_file")
        ), "Failed to find the default bundle cache directory for the shotgun entity descriptor on disk.")

        # skip this test on windows or py2.5 where multiprocessing isn't available
        if sys.platform == "win32" or sys.version_info < (2, 6):
            return

        # now test concurrent downloads to a shared bundle cache
        import multiprocessing

        # the shared bundle cache path to which app store data is to be downloaded.
        shared_dir = os.path.join(self.tank_temp, "shared_bundle_cache")
        try:
            # spawn 10 processes that begin downloading data to the shared path.
            for x in range(10):
                process = multiprocessing.Process(target=_download_app_store_bundle, args=(shared_dir,))
                process.start()
                processes.append(process)
        except Exception as e:
            errors.append(e)

        try:
            # spawn 10 processes that begin downloading data to the shared path.
            for x in range(10):
                process = multiprocessing.Process(target=_download_shotgun_bundle, args=(shared_dir,))
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
        self.assertEqual(len(processes), 20, "Failed to spawn the expected number of processes.")

        # make sure the expected local path exists.
        self.assertTrue(os.path.exists(
            os.path.join(self.tank_temp, "shared_bundle_cache", "app_store",
                         "tk-test-bundle2", "v1.0.0", "large_binary_file")
        ), "Failed to find the shared bundle cache directory for the app store descriptor on disk.")

        # make sure the expected local path exists.
        self.assertTrue(os.path.exists(
            os.path.join(self.tank_temp, "shared_bundle_cache", "sg", "unit_test_mock_sg",
                         "PipelineConfiguration.sg_config", "p123_primary", "v456", "large_binary_file")
        ), "Failed to find the default bundle cache directory for the shotgun entity descriptor on disk.")

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
