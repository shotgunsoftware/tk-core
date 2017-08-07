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

from tank_test.tank_test_base import TankTestBase
from tank_test.tank_test_base import setUpModule # noqa

import sgtk


class TestIODescriptors(TankTestBase):
    """
    Testing the Shotgun deploy main API methods
    """

    def test_branch_descriptor_cache(self):
        """
        Tests branch descriptors through caching
        """
        sg = self.tk.shotgun
        root = os.path.join(self.project_root, "cache_root")
        releases = []
        # Create a succession of releases, for each release number:
        # - A release with no branch information
        # - A release with an explicit "master" branch information
        # - A release with for a "topic" branch
        for release in ["v1.1.1", "v1.1.2", "v2.1.1", "v2.1.2"]:
            # Create release with no branch information
            releases.append(
                sgtk.descriptor.create_descriptor(
                    sg,
                    sgtk.descriptor.Descriptor.APP, {
                        "type": "app_store",
                        "version": release,
                        "name": "tk-bundle"
                    },
                    bundle_cache_root_override=root,
                )
            )
            # check the uri, we shouldn't have any label param in it
            # sgtk:descriptor:app_store?version=v2.1.2&name=tk-bundle
            self.assertFalse("label" in releases[-1].get_uri())
            # Create a master release, where master is explicit
            releases.append(
                sgtk.descriptor.create_descriptor(
                    sg,
                    sgtk.descriptor.Descriptor.APP, {
                        "type": "app_store",
                        "version": "%s-master" % release,
                        "label": "master",
                        "name": "tk-bundle"
                    },
                    bundle_cache_root_override=root,
                )
            )
            self.assertTrue("&label=master" in releases[-1].get_uri())
            # Create a branch release
            releases.append(
                sgtk.descriptor.create_descriptor(
                    sg,
                    sgtk.descriptor.Descriptor.APP, {
                        "type": "app_store",
                        "version": "%s-topic" % release,
                        "label": "topic",
                        "name": "tk-bundle"
                    },
                    bundle_cache_root_override=root,
                )
            )
            # check the uri, we should have label=topic in it
            # e.g. sgtk:descriptor:app_store?version=v2.1.2.topic&name=tk-bundle&label=topic
            self.assertTrue("&label=topic" in releases[-1].get_uri())

        sg_bundle_data = {
            "id": 666,
            "sg_system_name": "tk-bundle",
            "sg_status_list": "ip",
            "sg_deprecation_message": "",
        }
        # Create dummy app payload
        for i, release in enumerate(releases):
            app_path = os.path.join(root, "app_store", "tk-bundle", release.version)
            path = os.path.join(app_path, "info.yml")
            if not os.path.exists(app_path):
                os.makedirs(app_path)
            fh = open(path, "wt")
            fh.write("test data\n")
            fh.close()

            # Generate cached meta data
            sg_data_for_version = {
                "id": i,
                "code": release.version,
                "sg_status_list": "alpha",
                "description": "",
                "tag_list": [None, ["master"], ["topic"]][i%3],
                "sg_detailed_release_notes": "",
                "sg_documentation": "",
                "sg_branch": [None, "master", "topic"][i%3],
            }
            # Need to access the private method directly, otherwise we get the error:
            # AttributeError: 'IODescriptorAppStore' object has no attribute '_TestIODescriptors__refresh_metadata'
            release._io_descriptor._IODescriptorAppStore__refresh_metadata(
                release.get_path(),
                sg_bundle_data,
                sg_data_for_version
            )

        # Check internal methods, this is mostly useful to get some debug information
        # if something goes wrong in other tests below.
        all_versions = releases[-1]._io_descriptor._get_locally_cached_versions()
        ignored = []
        for v, p in all_versions.iteritems():
            metadata = releases[-1]._io_descriptor._IODescriptorAppStore__load_cached_app_store_metadata(
                p,
            )
            if releases[-1]._io_descriptor._IODescriptorAppStore__match_label(
                metadata["sg_version_data"]["tag_list"]
                ):
                break
            else:
                ignored.append(metadata["sg_version_data"])
        else:
            raise ValueError("Couldn't find label %s from %s" % (
                releases[-1]._io_descriptor._label,
                ignored
            ))

        # Check various release constraint patterns, for releases with a label
        latest = releases[-1].find_latest_cached_version("vx.x.x")
        self.assertEqual(
            latest.version,
            releases[-1].version
        )
        # Check the label is preserved in the descriptor
        self.assertTrue("&label=topic" in latest.get_uri())
        latest = releases[-2].find_latest_cached_version("vx.x.x")
        self.assertEqual(
            latest.version,
            releases[-2].version
        )
        # Check the label is preserved in the descriptor
        self.assertTrue("&label=master" in latest.get_uri())
        # With no tag we see all versions, so latest version for the version with
        # no tag will be the latest topic release
        latest = releases[-3].find_latest_cached_version("vx.x.x")
        self.assertEqual(
            latest.version,
            releases[-1].version
        )
        # Even if we picked a "topic" release, it shouldn't have a label set in its
        # descriptor, otherwise we will not see all versions anymore when the next
        # time we will be updating to latest.
        self.assertFalse("label" in latest.get_uri())

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
        self.assertEqual(d.find_latest_cached_version("vx.x.x"), d3)
        self.assertEqual(d.find_latest_cached_version("v2.x.x"), None)

    def test_cache_locations(self):
        """
        Tests locations of caches when using fallback paths.
        """
        sg = self.tk.shotgun

        root_a = os.path.join(self.project_root, "cache_root_a")
        root_b = os.path.join(self.project_root, "cache_root_b")
        root_c = os.path.join(self.project_root, "cache_root_c")
        root_d = os.path.join(self.project_root, "cache_root_d")

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

        # create metadata folder
        metadata_dir = os.path.join(bundle_path, "appstore-metadata")
        os.makedirs(metadata_dir)

        # because download receipt is missing, nothing is detected
        self.assertEqual(d.get_path(), None)
        self.assertEqual(d.find_latest_cached_version(), None)

        # add download receipt and re-check
        path = os.path.join(metadata_dir, "download_complete")
        with open(path, "wt") as fh:
            fh.write("test data\n")

        self.assertEqual(d.get_path(), bundle_path)
        self.assertEqual(d.find_latest_cached_version(), d)
