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
Ensures the bootstrap hook can be used to download bundles in lieu of the
default implementation.
"""

from __future__ import print_function

import os
import tempfile

import unittest2
from sgtk_integration_test import SgtkIntegrationTest
import sgtk

logger = sgtk.LogManager.get_logger(__name__)


class BootstrapHookTests(SgtkIntegrationTest):
    """
    Tests that it is possible to invoke a hook during bootstrap that will download the
    core, engine, app and frameworks.

    Note that for performance reason, we only upload the bundles once to the Shotgun
    site. However, the core is uploaded every single time since a bugfix could
    have been introduced to the core.
    """

    @classmethod
    def _zip_bundle(cls, location):
        # Create a temporary zip file.
        temp_zip_location = os.path.join(
            cls._bundle_upload_folder, "%s.zip" % os.path.basename(location)
        )

        # Write to it.
        sgtk.util.zip.zip_file(location, temp_zip_location)

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
            item = cls.sg.create(
                "CustomNonProjectEntity01", {"sg_descriptor": descriptor}
            )

        for _ in range(5):
            try:
                # Upload the bundle to Shotgun.
                cls.sg.upload(
                    "CustomNonProjectEntity01", item["id"], temp_zipfile, "sg_content"
                )
            except Exception:
                logger.exception(
                    "An unexpected exception was raised using the upload of the configuration:"
                )
            else:
                return
        else:
            raise RuntimeError("Failed uploading media after 5 retries.")

    @classmethod
    def _find_bundle_in_sg(cls, descriptor):
        """
        Finds for a bundle in Shotgun.
        """
        return cls.sg.find_one(
            "CustomNonProjectEntity01",
            [["sg_descriptor", "is", descriptor]],
            ["sg_content"],
        )

    @classmethod
    def _upload_bundle(cls, bundle_name, descriptor):
        """
        Uploads a bundle to Shotgun.
        """
        cls._upload_bundle_at(
            os.path.join(cls.fixtures_root, "config", "bundles", bundle_name),
            descriptor,
        )

    @classmethod
    def _upload_core(cls, descriptor):
        """
        Uploads the core to Shotgun.
        """
        # Create a temp folder into which we'll create a leaner tk-core distribution.

        # Unfortunately, our zipping method takes a folder as is and doesn't take a skip list,
        # so we'll have to streamline the core ourselves.
        core_temp_folder = os.path.join(cls._bundle_upload_folder, "tk-core")
        os.makedirs(core_temp_folder)
        sgtk.util.filesystem.copy_folder(
            cls.tk_core_repo_root,
            core_temp_folder,
            skip_list=[
                # Make the core leaner to speed up the test.
                "docs",
                "tests",
                ".git",
            ],
        )

        cls._upload_bundle_at(core_temp_folder, descriptor)

    @classmethod
    def _ensure_entity_fields_ready(cls):
        """
        Ensures the sg_uploaded_bundle field exists in Shotgun.
        """
        try:
            cls.sg.schema_field_read("CustomNonProjectEntity01", "sg_descriptor")
        except Exception as e:
            if "sg_descriptor doesn't exist" not in str(e):
                raise
            # If the field doesn't exist, create it.
            cls.sg.schema_field_create("CustomNonProjectEntity01", "text", "Descriptor")
        try:
            cls.sg.schema_field_read("CustomNonProjectEntity01", "sg_content")
        except Exception as e:
            if "sg_content doesn't exist" not in str(e):
                raise
            # If the field doesn't exist, create it.
            cls.sg.schema_field_create("CustomNonProjectEntity01", "url", "Content")

    @classmethod
    def setUpClass(cls):
        super(BootstrapHookTests, cls).setUpClass()

        cls._ensure_entity_fields_ready()

        # Create a leaner version of tk-core.
        cls._bundle_upload_folder = tempfile.mkdtemp()

        # Upload all our test data.
        cls._upload_bundle(
            "test_engine", "sgtk:descriptor:app_store?name=test_engine&version=v1.2.3"
        )
        cls._upload_bundle(
            "test_app", "sgtk:descriptor:app_store?name=test_app&version=v4.5.6"
        )
        cls._upload_bundle(
            "test_framework_v1",
            "sgtk:descriptor:app_store?name=test_framework&version=v7.8.9",
        )
        cls._upload_core("sgtk:descriptor:app_store?name=tk-core&version=v10.11.12")

        cls.project = cls.create_or_update_project("Descriptor Operations Hooks")
        # Create a descriptor-based pipeline configuration we will be using to bootstrap.
        cls.pipeline_configuration = cls.create_or_update_pipeline_configuration(
            "Primary",
            {
                "plugin_ids": "basic.*",
                "descriptor": "sgtk:descriptor:path?path=%s"
                % (
                    os.path.join(
                        cls.fixtures_root, "descriptor_tests", "with_bootstrap_hook"
                    )
                ),
                "project": cls.project,
            },
        )
        cls.asset = cls.create_or_update_entity(
            "Asset", "TestAsset", {"project": cls.project}
        )

    def test_bootstrap_with_descriptor_hooks(self):
        """
        This test will bootstrap using the descriptor hooks. If the descriptor doesn't properly do its job,
        the test won't be able to cache the bundles from the hook and will connect to the app store,
        which will fail since we don't have bundles with the required names.
        """
        manager = sgtk.bootstrap.ToolkitManager(self.user)
        manager.plugin_id = "basic.test"
        manager.pipeline_configuration = self.pipeline_configuration["id"]
        manager.bootstrap_engine("test_engine", self.asset)


if __name__ == "__main__":
    ret_val = unittest2.main(failfast=True, verbosity=2)
