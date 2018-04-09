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

from sgtk_integration_test import SgtkIntegrationTest

import sgtk


class OfflineWorkflow(SgtkIntegrationTest):

    OFFLINE_WORKFLOW_TEST = "offline_workflow_test"

    @classmethod
    def setUpClass(cls):
        """
        Sets up the test suite.
        """
        super(OfflineWorkflow, cls).setUpClass()
        # Points to where the config will be cached to.
        cls.config_dir = os.path.join(cls.temp_dir, "config")

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
                    "simple_config"
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
                # Run the script through coverage so we get stats from the subprocess.
                os.path.join(repo_root, "tests", "python", "third_party", "coverage"),
                "run", "-a",
                os.path.join(repo_root, "developer", "populate_bundle_cache.py"),
                "sgtk:descriptor:path?path={0}".format(self.config_dir),
                self.config_dir
            ])
        except sgtk.util.process.SubprocessCalledProcessError as e:
            print(e.output)
            raise

        sgtk.util.zip.zip_file(
            self.config_dir,
            "{temp_dir}/config.zip".format(temp_dir=self.temp_dir),
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
            "{temp_dir}/config.zip".format(temp_dir=self.temp_dir),
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
            self.temp_dir, "new_shotgun_home"
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
