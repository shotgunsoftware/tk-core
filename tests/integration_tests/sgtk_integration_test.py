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
import sys
import tempfile
import atexit
import subprocess
import threading

import unittest2

import sgtk
from sgtk.util.filesystem import safe_delete_folder

TK_CORE_REPO_ROOT = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        ".."
    )
)

os.environ["TK_CORE_REPO_ROOT"] = TK_CORE_REPO_ROOT

# Create a temporary directory for these tests and make sure
# it is cleaned up.

if "SHOTGUN_TEST_TEMP" not in os.environ:
    temp_dir = tempfile.mkdtemp()
    atexit.register(lambda: safe_delete_folder(temp_dir))
else:
    temp_dir = os.environ["SHOTGUN_TEST_TEMP"]

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

        cls.tk_core_repo_root = TK_CORE_REPO_ROOT

    def run_tank_cmd(self, location, args, input=None, timeout=30):
        proc_dict = {}

        def tank_cmd_thread(proc_dict):
            proc = subprocess.Popen(
                [
                    os.path.join(location, "tank.bat" if sys.platform == "win32" else "tank"),
                    "--script-name=%s" % os.environ["SHOTGUN_SCRIPT_NAME"],
                    "--script-key=%s" % os.environ["SHOTGUN_SCRIPT_KEY"],
                ] + list(args),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE
            )
            proc_dict["handle"] = proc
            proc.stdin.write(input)
            if proc.wait() == 0:
                print(proc.stdout.read())

        thread = threading.Thread(target=tank_cmd_thread, args=(proc_dict,))
        thread.start()
        thread.join(timeout)

        if proc_dict["handle"].poll() is None:
            print("Time out, killing process!")
            proc_dict["handle"].kill()
            raise Exception("Subprocess timed out!")
