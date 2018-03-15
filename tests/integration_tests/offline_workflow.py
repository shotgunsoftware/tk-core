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
This test ensures that the offline workflow using local bundle cached inside an uploaded
zipped config can be bootstrap into without requiring to download anything from Shotgun.
"""

from __future__ import print_function

import unittest2
import os
import sys
import atexit
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "python"))

import sgtk
from sgtk.util.filesystem import safe_delete_folder

# Create a temporary directory for these tests and make sure
# it is cleaned up.
temp_dir = tempfile.mkdtemp()
atexit.register(lambda: safe_delete_folder(temp_dir))

# Set up logging
sgtk.LogManager().initialize_base_file_handler("offline_workflow")
sgtk.LogManager().initialize_custom_handler()

# Ensure Toolkit writes to the temporary directory/
os.environ["SHOTGUN_HOME"] = os.path.join(
    temp_dir, "shotgun_home"
)


class OfflineWorkflow(unittest2.TestCase):

    OFFLINE_WORKFLOW_TEST = "offline_workflow_test"

    @classmethod
    def setUpClass(cls):
        """
        Sets up the test suite.
        """

        # Create a user and connection to Shotgun.
        sa = sgtk.authentication.ShotgunAuthenticator()
        user = sa.create_script_user(
            os.environ["SHOTGUN_TEST_API_SCRIPT"],
            os.environ["SHOTGUN_TEST_API_KEY"],
            os.environ["SHOTGUN_TEST_SITE_URL"]
        )
        cls.user = user
        cls.sg = user.create_sg_connection()

        # Points to where the config will be cached to.
        cls.config_dir = os.path.join(temp_dir, "config")

    def test_01_copy_config_to_test_folder(self):
        """
        Takes the configuration from integration_tests/data/offline_workflow
        and copies it into {tempdir}
        """
        desc = sgtk.descriptor.create_descriptor(
            self.sg,
            sgtk.descriptor.Descriptor.CONFIG,
            {
                "type": "path",
                "path": os.path.join(
                    os.path.dirname(__file__),
                    "data",
                    "offline_workflow_config"
                )
            }
        )
        os.makedirs(self.config_dir)
        desc.copy(self.config_dir)

    def test_02_generate_zipped_config(self):
        """
        Generates the zipped configuration file containing the configuration and bundles.
        """
        repo_root = os.path.join(
            os.path.dirname(__file__),
            "..", ".."
        )
        try:
            sgtk.util.process.subprocess_check_output([
                sys.executable,
                os.path.join(repo_root, "developer", "populate_bundle_cache.py"),
                "--shotgun-host", self.sg.base_url,
                "--shotgun-script-name", self.sg.config.script_name,
                "--shotgun-script-key", self.sg.config.api_key,
                "sgtk:descriptor:path?path={0}".format(self.config_dir),
                self.config_dir
            ])
        except sgtk.util.process.SubprocessCalledProcessError as e:
            print(e.output)
            raise

        sgtk.util.zip.zip_file(
            self.config_dir,
            "{temp_dir}/config.zip".format(temp_dir=temp_dir),
        )

    def test_03_upload_to_pipeline_configuration(self):
        """
        Ensures the project and pipeline configuration we want to use are ready in Shotgun. This
        includes uploading the pipeline configuration to Shotgun.
        """

        # Ensure the project exists.
        projects = self.sg.find("Project", [["name", "is", self.OFFLINE_WORKFLOW_TEST]])
        self.assertLessEqual(len(projects), 1)
        if not projects:
            project = self.sg.create(
                "Project",
                {"name": self.OFFLINE_WORKFLOW_TEST, "tank_name": self.OFFLINE_WORKFLOW_TEST}
            )
        else:
            project = projects[0]

        # Ensure the pipeline configuration exists.
        pcs = self.sg.find("PipelineConfiguration", [["code", "is", "Primary"], ["project", "is", project]])
        self.assertLessEqual(len(pcs), 1)
        if not pcs:
            pc = self.sg.create(
                "PipelineConfiguration",
                {"code": "Primary", "project": project, "plugin_ids": "basic.*"}
            )
        else:
            pc = pcs[0]

        # Upload the zip file to Shotgun.
        self.sg.upload(
            "PipelineConfiguration", pc["id"],
            "{temp_dir}/config.zip".format(temp_dir=temp_dir),
            "sg_uploaded_config",
            "Uploaded by tk-core integration tests."
        )

    def test_04_bootstrap(self):
        """
        Ensures we can bootstrap into the uploaded configuration and that no bundles are downloaded from
        the app store.
        """

        # Change the Toolkit sandbox so we don't reuse the previous cache.
        os.environ["SHOTGUN_HOME"] = os.path.join(
            temp_dir, "new_shotgun_home"
        )
        self.assertFalse(os.path.exists(os.environ["SHOTGUN_HOME"]))

        # Find the project and pipeline configuration in Shotgun.
        project = self.sg.find_one("Project", [["name", "is", self.OFFLINE_WORKFLOW_TEST]])
        pc = self.sg.find_one("PipelineConfiguration", [["code", "is", "Primary"], ["project", "is", project]])

        # Bootstrap into the tk-shell engine.
        manager = sgtk.bootstrap.ToolkitManager(self.user)
        manager.pipeline_configuration = pc["id"]
        engine = manager.bootstrap_engine("tk-shell", project)
        engine.destroy_engine()

        # Make sure we only have a sg descriptor cache.
        self.assertEqual(
            sorted(
                os.listdir(
                    os.path.join(os.environ["SHOTGUN_HOME"], "bundle_cache")
                )
            ),
            ["sg", "tmp"]
        )


if __name__ == "__main__":
    ret_val = unittest2.main(failfast=True, verbosity=2)
