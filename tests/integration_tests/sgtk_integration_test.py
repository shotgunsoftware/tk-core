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
import shutil

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

        # Advertise the temporary directory and root of the tk-core repo
        cls.temp_dir = temp_dir
        cls.tk_core_repo_root = TK_CORE_REPO_ROOT
        # Set it also as an environment variable so it can be used by subprocess or a configuration.
        os.environ["TK_CORE_REPO_ROOT"] = TK_CORE_REPO_ROOT

        # Create or update the integration_tests local storage with the current test run
        # temp folder location.
        cls.local_storage = cls.sg.find_one("LocalStorage", [["code", "is", "integration_tests"]], ["code"])
        if cls.local_storage is None:
            cls.local_storage = cls.sg.create("LocalStorage", {"code": "integration_tests"})

        # Use platform agnostic token to facilitate tests.
        cls.local_storage["path"] = os.path.join(cls.temp_dir, "storage")
        cls.sg.update(
            "LocalStorage", cls.local_storage["id"],
            # This means that a test suite can only run one at a time again a given site per
            # platform. This is reasonable limitation, as our CI runs on only one
            # node at a time.
            {sgtk.util.ShotgunPath.get_shotgun_storage_key(): cls.local_storage["path"]}
        )

        # Ensure the local storage folder exists on disk.
        if not os.path.exists(cls.local_storage["path"]):
            os.makedirs(cls.local_storage["path"])

    def run_tank_cmd(self, location, args=None, user_input=None, timeout=30):
        """
        Runs the tank command.

        :param str location: Folder that contains the tank command.
        """
        proc_dict = {}

        # Take each command line arguments and make a string out of them.
        args = args or ()
        args = [str(arg) for arg in args]

        # Take each input and turn it into a string with a \n at the end.
        user_input = user_input or tuple()
        user_input = ("%s\n" * len(user_input)) % user_input

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
            proc.stdin.write(user_input)
            if proc.wait() == 0:
                print(proc.stdout.read())
            else:
                print(proc.stdout.read())

        thread = threading.Thread(target=tank_cmd_thread, args=(proc_dict,))
        thread.start()
        thread.join(timeout)

        if proc_dict["handle"].poll() is None:
            print("Time out, killing process!")
            proc_dict["handle"].kill()
            raise Exception("Subprocess timed out!")
        elif proc_dict["handle"].poll() != 0:
            raise Exception("Process completed unsuccesfully.")

    def remove_files(self, *files):
        for f in files:
            if os.path.exists(f):
                shutil.rmtree(f)

    def setup_project(
        self,
        location,
        source_configuration,
        storage_name,
        project_id,
        tank_name,
        pipeline_root,
        force=False
    ):
        if os.path.exists(pipeline_root):
            shutil.rmtree(pipeline_root)

        pipeline_root = sgtk.util.ShotgunPath.from_current_os_path(pipeline_root)

        self.run_tank_cmd(
            location,
            ("setup_project", "--force" if force else ""),
            user_input=(
                # >> Which configuration would you like to associate with this project?
                source_configuration,
                # >> For each storage root, enter the name of the local storage
                storage_name,
                # >> Please type in the id of the project to connect to or ENTER
                project_id,
                # >> Please enter a folder name
                tank_name,
                # >> Paths look valid. Continue?
                "yes",
                # >> Now it is time to decide where the configuration for this project should go.
                # >> Typically, this is in a software install area where you keep
                # >> all your Toolkit code and configuration. We will suggest defaults
                # >> based on your current install.
                pipeline_root.linux or "",
                pipeline_root.windows or "",
                pipeline_root.macosx or "",
                # >> Continue with project setup?
                "yes"
            )
        )
