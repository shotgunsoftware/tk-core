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
Provides a base class for integration tests.
"""

from __future__ import print_function

import os
import sys
import tempfile
import atexit
import subprocess
import threading
import shutil
import time
import copy

import unittest2

import sgtk
from sgtk.util.filesystem import safe_delete_folder


class SgtkIntegrationTest(unittest2.TestCase):
    """
    Base class for integration tests. Each integration test should be invoke in its own subprocess.

    The base class takes care of:
        - setting up a log file named after the test
        - creating a random temporary folder to write to or use the path pointed by SHOTGUN_TEST_TEMP
        - setting SHOTGUN_HOME to point to <temp_dir>/shotgun_home
        - creating a Shotgun connection based on the SHOTGUN_HOST, SHOTGUN_SCRIPT_NAME, SHOTGUN_SCRIPT_KEY
          environment variables
        - sets the TK_CORE_REPO_ROOT environment variable, which points to the root of this repo.
        - creating a local storage named integration_tests with an optional suffix provided by the continous
          integration provider so that multiple tests running on different CIs at the same time do not
          interact with each other
        - local storage is updated each run to point into the temporary folder.
        - cleaning up the test folder when the tests are done running.
    """

    @classmethod
    def setUpClass(cls):
        """
        Sets up the test suite.
        """

        # Set up logging
        sgtk.LogManager().initialize_base_file_handler(cls.__name__.lower())
        sgtk.LogManager().initialize_custom_handler()

        # Create a temporary directory for these tests and make sure
        # it is cleaned up.
        if "SHOTGUN_TEST_TEMP" not in os.environ:
            cls.temp_dir = tempfile.mkdtemp()
            # Do not rely on tearDown to cleanup files on disk. Use the atexit callback which is
            # much more realiable.
            atexit.register(cls._cleanup_temp_dir)
        else:
            cls.temp_dir = os.environ["SHOTGUN_TEST_TEMP"]

        # Ensure Toolkit writes to the temporary directory
        os.environ["SHOTGUN_HOME"] = os.path.join(
            cls.temp_dir, "shotgun_home"
        )

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
        cls.tk_core_repo_root = os.path.normpath(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                ".."
            )
        )
        # Set it also as an environment variable so it can be used by subprocess or a configuration.
        os.environ["TK_CORE_REPO_ROOT"] = cls.tk_core_repo_root

        # Create or update the integration_tests local storage with the current test run
        # temp folder location.
        storage_name = cls._create_unique_name("integration_tests")
        cls.local_storage = cls.sg.find_one("LocalStorage", [["code", "is", storage_name]], ["code"])
        if cls.local_storage is None:
            cls.local_storage = cls.sg.create("LocalStorage", {"code": storage_name})

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

    @classmethod
    def _cleanup_temp_dir(cls):
        """
        Called to cleanup the test folder.
        """
        # Close the file logger so that the file is not in use on Windows.
        sgtk.LogManager().uninitialize_base_file_handler()
        safe_delete_folder(cls.temp_dir)

    @classmethod
    def _create_unique_name(cls, name):
        """
        Returns a name that can be unique for the environment the test is running in.
        If SHOTGUN_TEST_ENTITY_SUFFIX environment variable is set, the suffix will be added.
        """
        if "SHOTGUN_TEST_ENTITY_SUFFIX" in os.environ:
            return "%s_%s" % (name, os.environ["SHOTGUN_TEST_ENTITY_SUFFIX"])
        else:
            return name

    @classmethod
    def create_or_find_project(cls, name, entity=None):
        """
        Creates or finds a project with a given name.

        :param str name: Name of the project to find or create.
        :param dict entity: Entity dictionary for the project if it needs to be created.

        .. note:
            The actual name of the project might be different than the name passed in if you
            are in a CI environment. As such, always use the name returned from the entity.

        :returns: Entity dictionary of the project.
        """
        entity = entity or {}

        name = cls._create_unique_name(name)

        project = cls.sg.find_one("Project", [["name", "is", name]])
        if not project:
            entity["name"] = name
            project = cls.sg.create("Project", entity)

        return project

    def run_tank_cmd(self, location, user_args=None, user_input=None, timeout=120):
        """
        Runs the tank command.

        :param str location: Folder that contains the tank command.
        :param list args: List of arguments for the command line.
        :param list user_input: List of answers to provide to provide to the tank command prompt.
            Each entry will be followed by a \n automatically.
        :param int timeout: Timeout for the subprocess in seconds.

        :raises Exception: Raised then timeout occurs or when the subprocess does not return 0.
        """
        # Take each command line arguments and make a string out of them.
        user_args = user_args or []
        user_args = [str(arg) for arg in user_args]

        # Take each input and turn it into a string with a \n at the end.
        user_input = user_input or ()
        user_input = tuple(user_input)
        user_input = ("%s\n" * len(user_input)) % user_input

        # Do not invoke the tank shell script. This causes issues when trying to timeout the subprocess
        # because killing the shell script does not terminate the python subprocess, so we want
        # to launch the python interpreter directly.

        # For this, we'll have to replicate the logic from the tank shell script.

        # Check if this is a shared core.
        core_cfg_map = {"linux2": "core_Linux.cfg", "win32": "core_Windows.cfg", "darwin": "core_Darwin.cfg"}
        core_location_file = os.path.join(location, "install", "core", core_cfg_map[sys.platform])
        if os.path.exists(core_location_file):
            with open(core_location_file, "rt") as fh:
                core_location = fh.read()
        else:
            core_location = location

        args = [
            sys.executable,
            # The tank_cmd.py is installed with the core
            os.path.join(core_location, "install", "core", "scripts", "tank_cmd.py"),
            # The script always expects as the first param the tk-core is installed
            core_location,
            # Then pass the credentials to run silently the command.
            "--script-name=%s" % os.environ["SHOTGUN_SCRIPT_NAME"],
            "--script-key=%s" % os.environ["SHOTGUN_SCRIPT_KEY"],
            # Finally pass the user requested
        ] + list(user_args)

        # If we're launching the command from a pipeline configuration that uses a shared core,
        # we need to tell the tank command which pipeline configuration it is being launched from.
        if core_location != location:
            args += ["--pc=%s" % location]

        # The following is heavily inspired from
        # http://www.ostricher.com/2015/01/python-subprocess-with-timeout/
        # Note: we're not using backported subprocess32 which supports a timeout argument
        # because it has not been validated on Windows.

        env = copy.copy(os.environ)
        # Set PYTHONPATH, just like tank_cmd shell script does
        env["PYTHONPATH"] = os.path.join(core_location, "install", "core", "python")

        proc = subprocess.Popen(
            args,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE
        )
        thread = threading.Thread(target=self._tank_cmd_thread, args=(proc, user_input))
        thread.start()
        # Wait timeout seconds before aborting the process.
        thread.join(timeout)

        # If the process hasn't finished, kill it.
        if thread.is_alive():
            print("Time out, killing process!")
            try:
                proc.kill()
            except OSError:
                # The process finished between the is_alive() and kill()
                pass
            else:
                raise Exception("Subprocess timed out!")
        # If the process did not finish with 0, return an error.
        elif proc.returncode != 0:
            raise Exception("Process completed unsuccesfully.")

    def _tank_cmd_thread(self, proc, user_input):
        """
        Clocks the time it takes to run the subprocess and prints out the return code
        and how much time it took to run.
        """
        before = time.time()
        stdout = None
        try:
            stdout, _ = proc.communicate(user_input)
        finally:
            print("tank command ran in %.2f seconds." % (time.time() - before))
            print("tank command return code", proc.returncode)
            if stdout:
                print("tank command output:")
                print(stdout)

    def remove_files(self, *files):
        """
        Removes a list of files or folders on disk if they exist.

        :param *args: List of files to delete.
        """
        for f in files:
            if os.path.exists(f):
                shutil.rmtree(f)

    def tank_setup_project(
        self,
        location,
        source_configuration,
        storage_name,
        project_id,
        tank_name,
        pipeline_root,
        force=False
    ):
        """
        Setups a Toolkit project.

        :param location: Location of the tank command.
        :param source_configuration: Location on disk where to find the configuration to use.
        :param storage_name: Name of the storage to assign to the config's root.
        :param project_id: Id of the project to setup.
        :param tank_name: Tank name for the project.
        :param pipeline_root: Location where the pipeline configuration will be written.
        :param force: If True, the project will be setup even if already configured.
        """
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
