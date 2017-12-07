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
import uuid
import os

from tank_test.tank_test_base import TankTestBase, setUpModule, temp_env_var


class TestDecorators(TankTestBase):
    """
    Basic environment tests
    """

    def test_temp_env_var_that_didnt_exist(self):
        """
        Check if temp_env_var sets and restores the variable
        """
        # Create a unique env var and make sure it doesn't currectly exist.
        env_var_name = "ENV_VAR_" + uuid.uuid4().hex
        self.assertFalse(env_var_name in os.environ)

        # Temporarily set the env var.
        with temp_env_var(**{env_var_name: "test_value"}):
            self.assertTrue(env_var_name in os.environ)
            self.assertEquals(os.environ[env_var_name], "test_value")

        # Make sure it is gone.
        self.assertFalse(env_var_name in os.environ)

    def test_temp_env_var_that_already_exist(self):
        """
        Check if temp_env_var sets and restores the variable
        """
        # Create a unique env var and make sure it doesn't currectly exist.
        env_var_name = "ENV_VAR_" + uuid.uuid4().hex
        self.assertFalse(env_var_name in os.environ)

        # Temporarily set the env var.
        with temp_env_var(**{env_var_name: "test_value"}):

            # Make sure it is set.
            self.assertTrue(env_var_name in os.environ)
            self.assertEquals(os.environ[env_var_name], "test_value")

            # Override the existing variable with a new one
            with temp_env_var(**{env_var_name: "test_value_2"}):

                # Make sure it was overriden
                self.assertTrue(env_var_name in os.environ)
                self.assertEquals(os.environ[env_var_name], "test_value_2")

            # Make sure the original one was restore.
            self.assertTrue(env_var_name in os.environ)
            self.assertEquals(os.environ[env_var_name], "test_value")

        # Make sure it is gone.
        self.assertFalse(env_var_name in os.environ)
