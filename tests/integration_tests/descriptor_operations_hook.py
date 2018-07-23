# Copyright (c) 2018 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
This test makes sure that various tank command operations do not fail.
"""

from __future__ import print_function

import os
import tempfile

import unittest2
from sgtk_integration_test import SgtkIntegrationTest
import sgtk

logger = sgtk.LogManager.get_logger(__name__)


class DescriptorOperationsHooks(SgtkIntegrationTest):
    """
    Tests that it is possible to invoke a hook during bootstrap that will download the
    core, engine, app and frameworks.
    """

    @classmethod
    def _zip_bundle(cls, location):
        # Create a tempoprary zip file.
        temp_zip_fd, temp_zip_location = tempfile.mkstemp(os.path.basename(location))

        # Write to it.
        sgtk.util.zip.zip_file(location, temp_zip_location)

        # Close it
        os.close(temp_zip_fd)

        return temp_zip_location

    @classmethod
    def _upload_bundle_at(cls, location, descriptor):
        """
        Uploads a bundle from a given location with the given code.

        :param descriptor: URI of the descriptor we're uploading.
        :param location: Path on disk where the bundle is located.
        """
        # First create a temporary zip file for that bundle.
        temp_zipfile = cls._zip_bundle(location)

        # Then look for a recod in Shotgun that can hold it.
        item = cls._find_bundle_in_sg(descriptor)

        # If we didn't find the record, create it. We're being fault tolerant here and assuming that
        # maybe a run might have created the record but failed at uploading the bundle.
        if not item:
            item = cls.sg.create("CustomNonProjectEntity01", {"code": descriptor})

        # Upload the bundle to Shotgun.
        cls.sg.upload("CustomNonProjectEntity01", item["id"], temp_zipfile, "sg_uploaded_bundle")

    @classmethod
    def _find_bundle_in_sg(cls, descriptor):
        """
        Finds for a bundle in Shotgun.
        """
        return cls.sg.find_one("CustomNonProjectEntity01", [["code", "is", descriptor]], ["sg_uploaded_bundle"])

    @classmethod
    def _is_bundle_uploaded(cls, descriptor):
        """
        Checks if a bundle has been uploaded in Shotgun.
        """
        item = cls._find_bundle_in_sg(descriptor)
        # We're being fault tolerant here and assuming that maybe a test run might have created the record but
        # failed at uploading.
        return item is not None and item.get("sg_uploaded_bundle") is not None

    @classmethod
    def _upload_bundle_if_missing(cls, location, descriptor):
        """
        Uploads a bundle if it is missing from Shotgun.
        """
        if cls._is_bundle_uploaded(descriptor):
            return
        cls._upload_bundle_at(os.path.join(cls.fixtures_root, "config", "bundles"), descriptor)

    @classmethod
    def _upload_core_if_missing(cls, descriptor):
        """
        Uploads the core if it is missing from Shotgun.
        """
        if cls._is_bundle_uploaded(descriptor):
            return
        cls._upload_bundle_at(cls.tk_core_repo_root, descriptor)

    @classmethod
    def _ensure_entity_fields_ready(cls):
        """
        Ensures the sg_uploaded_bundle field exists in Shotgun.
        """
        try:
            cls.sg.schema_field_read("CustomNonProjectEntity01", "sg_uploaded_bundle")
        except Exception as e:
            if "sg_uploaded_bundle doesn't exist" not in str(e):
                raise
            # If the field doesn't exist, create it.
            cls.sg.schema_field_create("CustomNonProjectEntity01", "url", "Uploaded Bundle")

    @classmethod
    def setUpClass(cls):
        super(DescriptorOperationsHooks, cls).setUpClass()

        cls._ensure_entity_fields_ready()

        # Upload all our test data.
        cls._upload_bundle_if_missing(
            "test_engine",
            "sgtk:descriptor:app_store?name=test_engine&version=v1.2.3"
        )
        cls._upload_bundle_if_missing(
            "test_app",
            "sgtk:descriptor:app_store?name=test_engine&version=v4.5.6"
        )
        cls._upload_bundle_if_missing(
            "test_framework_v1",
            "sgtk:descriptor:app_store?name=test_engine&version=v7.8.9"
        )
        cls._upload_core_if_missing("sgtk:descriptor:app_store?name=tk-core&version=v10.11.12")

        cls.project = cls.create_or_find_project("Descriptor Operations Hooks")
        # Create a descriptor-based pipeline configuration we will be using to bootstrap.
        cls.pipeline_configuration = cls.ensure_pipeline_configuration_exists(
            "descriptor_hooks_configuration",
            {
                "plugin_ids": "basic.*",
                "descriptor": "sgtk:descriptor:path?%s" % (
                    os.path.join(cls.fixtures_root, "descriptor_tests", "with_create_descriptor_hook")
                ),
                "project": cls.project
            }
        )

    def test_bootstrap_with_descriptor_hooks(self):
        """
        This test will bootstrap using the descriptor hooks. If the descriptor doesn't properly do its job,
        the test won't be able to cache the bundles from the hook and will connect to the app store,
        which will fail since we don't have bundles with the required names.
        """
        manager = sgtk.bootstrap.ToolkitManager(self.user)
        manager.pipeline_configuration = self.pipeline_configuration["id"]
        manager.bootstrap_engine("test_engine", self.project)


if __name__ == "__main__":
    ret_val = unittest2.main(failfast=True, verbosity=2)
