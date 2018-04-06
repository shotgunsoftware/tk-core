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

import os
import tempfile
import atexit

import unittest2

import sgtk
from sgtk.util.filesystem import safe_delete_folder

# Create a temporary directory for these tests and make sure
# it is cleaned up.
temp_dir = tempfile.mkdtemp()
atexit.register(lambda: safe_delete_folder(temp_dir))

# Ensure Toolkit writes to the temporary directory/
os.environ["SHOTGUN_HOME"] = os.path.join(
    temp_dir, "shotgun_home"
)


class SgtkIntegrationTest(unittest2.TestCase):

    @classmethod
    def setUpClass(cls):
        """
        Sets up the test suite.
        """

        # Create a user and connection to Shotgun.
        sa = sgtk.authentication.ShotgunAuthenticator()
        user = sa.create_script_user(
            os.environ["SHOTGUN_SCRIPT_NAME"],
            os.environ["SHOTGUN_SCRIPT_KEY"],
            os.environ["SHOTGUN_HOST"]
        )
        cls.user = user
        cls.sg = user.create_sg_connection()

        cls.temp_dir = temp_dir
