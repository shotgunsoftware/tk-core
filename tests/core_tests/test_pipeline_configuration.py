# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.


from tank_test.tank_test_base import TankTestBase, setUpModule

import tank


class TestPipelineConfig(TankTestBase):
    """
    Tests for the pipeline configuration.
    """

    def test_update_metadata(self):
        """
        Tests if updating the pipeline to site config actually updates it.
        """
        self.assertFalse(self.tk.pipeline_configuration.is_site_configuration())

        # Make sure the project has been concerted to a site config.
        self.tk.pipeline_configuration.convert_to_site_config()
        self.assertTrue(self.tk.pipeline_configuration.is_site_configuration())

        # Make sure that the setting was correctly written to disk by recreating
        # another instance of the pipeline configuration object so that it reloads
        # it from disk.
        tk2 = tank.sgtk_from_path(self.tk.pipeline_configuration.get_path())
        self.assertTrue(tk2.pipeline_configuration.is_site_configuration())

    def test_default_pipeline_in_unittest(self):
        """
        Make sure that we are using the default pipeline configuration from
        the unit tests.
        """
        self.assertEqual(
            self.tk.pipeline_configuration.get_published_file_entity_type(),
            "PublishedFile"
        )

    def test_fixture_pipeline_reloaded(self):
        """
        Makes sure we are using the pipeline configuration form the fixture
        """
        self.setup_fixtures(name="fixture_tests")
        self.assertEqual(
            self.tk.pipeline_configuration.get_shotgun_id(),
            42
        )
        self.assertEqual(
            self.tk.pipeline_configuration.get_project_id(),
            42
        )
        self.assertEqual(
            self.tk.pipeline_configuration.get_project_disk_name(),
            "abc"
        )
        self.assertEqual(
            self.tk.pipeline_configuration.get_name(),
            "Firstary"
        )
