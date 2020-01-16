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
import time
import copy
import random

import unittest2

import sgtk
from sgtk.util import sgre as re
from sgtk.util.filesystem import safe_delete_folder, safe_delete_file
from tank_vendor import six
from tank_vendor.shotgun_api3.lib import sgsix
from tank_vendor import yaml


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
        sgtk.LogManager().initialize_base_file_handler(
            cls._camel_to_snake(cls.__name__)
        )
        sgtk.LogManager().initialize_custom_handler()

        # Create a temporary directory for these tests and make sure
        # it is cleaned up.
        if "SHOTGUN_TEST_TEMP" not in os.environ:
            cls.temp_dir = tempfile.mkdtemp()
            # Only clean up the temp dir when not retrieving coverage for the tests,
            # or we won't be able ot merge the reports from all runs.
            if "SHOTGUN_TEST_COVERAGE" not in os.environ:
                # Do not rely on tearDown to cleanup files on disk. Use the atexit callback which is
                # much more realiable.
                atexit.register(cls._cleanup_temp_dir)
        else:
            cls.temp_dir = os.environ["SHOTGUN_TEST_TEMP"]

        # Ensures calls to the tempfile module generate paths under the unit test temp folder.
        tempfile.tempdir = cls.temp_dir

        # Ensure Toolkit writes to the temporary directory
        os.environ["SHOTGUN_HOME"] = os.path.join(cls.temp_dir, "shotgun_home")

        # Create a user and connection to Shotgun.
        sa = sgtk.authentication.ShotgunAuthenticator()
        user = sa.create_script_user(
            os.environ["SHOTGUN_SCRIPT_NAME"],
            os.environ["SHOTGUN_SCRIPT_KEY"],
            os.environ["SHOTGUN_HOST"],
        )
        cls.user = user
        cls.sg = user.create_sg_connection()

        # Write the credentials to disk instead of passing them as arguments
        # on the command line to avoid them being printed on screen in CI. Let's not
        # trust the filtering on those.
        cls.shotgun_credentials_file = os.path.join(cls.temp_dir, "sg_credentials.txt")
        with open(cls.shotgun_credentials_file, "wt") as fh:
            yaml.safe_dump(
                {
                    "script-name": os.environ["SHOTGUN_SCRIPT_NAME"],
                    "script-key": os.environ["SHOTGUN_SCRIPT_KEY"],
                },
                fh,
            )
        atexit.register(cls._clean_credentials)

        # Advertise the temporary directory and root of the tk-core repo
        cls.tk_core_repo_root = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "..")
        )
        # Set it also as an environment variable so it can be used by subprocess or a configuration.
        os.environ["TK_CORE_REPO_ROOT"] = cls.tk_core_repo_root
        cls.fixtures_root = os.path.join(cls.tk_core_repo_root, "tests", "fixtures")

        # Create or update the integration_tests local storage with the current test run
        # temp folder location.
        storage_name = cls._create_unique_name("integration_tests")
        cls.local_storage = cls.sg.find_one(
            "LocalStorage", [["code", "is", storage_name]], ["code"]
        )
        if cls.local_storage is None:
            cls.local_storage = cls.sg.create("LocalStorage", {"code": storage_name})

        # Use platform agnostic token to facilitate tests.
        cls.local_storage["path"] = os.path.join(cls.temp_dir, "storage")
        cls.sg.update(
            "LocalStorage",
            cls.local_storage["id"],
            # This means that a test suite can only run one at a time again a given site per
            # platform. This is reasonable limitation, as our CI runs on only one
            # node at a time.
            {
                sgtk.util.ShotgunPath.get_shotgun_storage_key(): cls.local_storage[
                    "path"
                ]
            },
        )

        # Ensure the local storage folder exists on disk.
        if not os.path.exists(cls.local_storage["path"]):
            os.makedirs(cls.local_storage["path"])

    @staticmethod
    def _camel_to_snake(text):
        """
        Converts a string from CamelCase to snake_case.
        """
        str1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", text)
        return re.sub("([a-z0-9])([A-Z])", r"\1_\2", str1).lower()

    @classmethod
    def _cleanup_temp_dir(cls):
        """
        Called to cleanup the test folder.
        """
        # Close the file logger so that the file is not in use on Windows.
        sgtk.LogManager().uninitialize_base_file_handler()
        safe_delete_folder(cls.temp_dir)

    @classmethod
    def _clean_credentials(cls):
        """
        Called to remove the shotgun credentials file.
        """
        # This file might have already been deleted if _cleanup_temp_dir
        # has already run.
        #
        # One reason for cleanup temp dir to not have been called is if
        # test coverage was turned on.
        if os.path.exists(cls.shotgun_credentials_file):
            safe_delete_file(cls.shotgun_credentials_file)

    @classmethod
    def _create_unique_name(cls, name):
        """
        Returns a name that can be unique for the environment the test is running in.
        If SHOTGUN_TEST_ENTITY_SUFFIX environment variable is set, the suffix will be added.
        """
        if "SHOTGUN_TEST_ENTITY_SUFFIX" in os.environ:
            return "%s - %s" % (name, os.environ["SHOTGUN_TEST_ENTITY_SUFFIX"])
        else:
            return name

    @classmethod
    def create_or_update_project(cls, name, entity=None):
        """
        Creates or finds a project with a given name.

        :param str name: Name of the project to find or create.
        :param dict entity: Entity dictionary for the project if it needs to be created.

        .. note:
            The actual name of the project will be different than the name passed in. As such,
            always use the name returned from the entity.

        :returns: Entity dictionary of the project.
        """
        # Ensures only the requested fields are set so we don't confuse the roots
        # configuration detection.
        complete_project_data = {"tank_name": None}
        complete_project_data.update(entity or {})
        name = cls._create_unique_name("tk-core CI - %s" % name)
        return cls.create_or_update_entity("Project", name, complete_project_data)

    @classmethod
    def create_or_update_entity(cls, entity_type, name, entity_fields=None):
        """
        Creates of finds an entity with a given name

        :param str name: Name of the project to find or create.
        :param dict entity: Entity dictionary for the project if it needs to be created.

        .. note:
            The actual name of the entity might be different than the name passed in if you
            are in a CI environment. As such, always use the name returned from the entity.

        :returns: Entity dictionary of the project.
        """
        entity_fields = entity_fields or {}

        entity_name_field = sgtk.util.get_sg_entity_name_field(entity_type)

        filters = [[entity_name_field, "is", name]]

        # Filter by project, as not doing so can mean retrieving an asset with the
        # same name from another project.
        if "project" in entity_fields:
            filters.append(["project", "is", entity_fields["project"]])

        # Find the entity by this name in Shotgun for the specified project, if any.
        entity = cls.sg.find_one(entity_type, filters)
        # If it doesn't exist, create it!
        if not entity:
            entity_fields[entity_name_field] = name
            entity = cls.sg.create(entity_type, entity_fields)
        else:
            # But if it does, make sure it has the right data on it.
            cls.sg.update(entity_type, entity["id"], entity_fields)

        return entity

    @classmethod
    def create_or_update_pipeline_configuration(cls, name, entity_data):
        """
        Ensures a pipeline configuration with the given name exists.

        :param name: Name of the configuration to look for.
        :param entity_data: Data for the pipeline configuration that will be
            created or updated.
        """

        # Ensures only the requested fields are set so we don't confuse the bootstrap
        # process
        complete_pc_data = {
            "mac_path": "",
            "windows_path": "",
            "linux_path": "",
            "descriptor": "",
            "plugin_ids": "",
            # Turn on the associated feature pref if this field is giving out errors.
            "uploaded_config": None,
            "project": None,
        }
        complete_pc_data.update(entity_data)

        return cls.create_or_update_entity("PipelineConfiguration", name, entity_data)

    def run_tank_cmd(
        self,
        location,
        cmd_name,
        context=None,
        extra_cmd_line_arguments=None,
        user_input=None,
        timeout=120,
    ):
        """
        Runs the tank command.

        :param str location: Folder that contains the tank command.
        :param str cmd_name: Name of the Toolkit command. Can be ``None``.
        :param dict context: Shotgun entity dictionary with keys ``type`` and ``id``.
        :param list(str) extra_cmd_line_arguments: List of extra command line arguments. Empty by default.
        :param list user_input: List of answers to provide to provide to the tank command prompt. Empty by default.
            Each entry will be followed by a \n automatically.
        :param int timeout: Timeout for the subprocess in seconds. Defaults to 120 seconds.

        :raises Exception: Raised then timeout occurs or when the subprocess does not return 0.

        The command line argument will be generated as:

            tank [context["type"] context["id"]] [cmd_name] [extra_cmd_line_arguments]
        """
        # The tank command line accepts argument in the following order:
        # tank <optional entity type> <optional entity id> <optional command name> <optional arguments>
        # For example: tank Asset Alice folders
        #
        # We'll build the command line arguments for the tank command backwards.
        # First, add the tailing arguments to the list of arguments.
        if extra_cmd_line_arguments is not None:
            cmd_line_arguments = list(extra_cmd_line_arguments)
        else:
            cmd_line_arguments = []

        # If a command name was specified, we'll add it.
        if cmd_name is not None:
            cmd_line_arguments = [cmd_name] + cmd_line_arguments

        # If a context was specified, add it.
        if context is not None:
            cmd_line_arguments = [context["type"], context["id"]] + cmd_line_arguments

        # Turn every command line arguments to strings.
        cmd_line_arguments = [str(arg) for arg in cmd_line_arguments]

        # Take each input and turn it into a string with a \n at the end.
        user_input = tuple(user_input) if user_input else tuple()
        user_input = ("%s\n" * len(user_input)) % user_input

        # Do not invoke the tank shell (tank.bat or tank.sh) script directly. This causes
        # issues when trying to timeout the subprocess because killing the shell script
        # does not terminate the python subprocess.
        #
        # Therefore, we'll have to replicate the logic from the tank shell script.

        # Check if this is a shared core and figure out the core location.
        core_cfg_map = {
            "linux2": "core_Linux.cfg",
            "win32": "core_Windows.cfg",
            "darwin": "core_Darwin.cfg",
        }
        core_location_file = os.path.join(
            location, "install", "core", core_cfg_map[sgsix.platform]
        )
        if os.path.exists(core_location_file):
            with open(core_location_file, "rt") as fh:
                core_location = fh.read()
        else:
            core_location = location

        # If we want test coverage, invoke the coverage module in parallel-mode instead of simply
        # invoking the script.
        if "SHOTGUN_TEST_COVERAGE" in os.environ:
            launcher = [sys.executable, "-m", "coverage", "run", "--parallel-mode"]
        else:
            launcher = [sys.executable]

        args = (
            launcher
            + [
                # The tank_cmd.py is installed with the core
                os.path.join(
                    core_location, "install", "core", "scripts", "tank_cmd.py"
                ),
                # The script always expects as the first param the tk-core is installed
                core_location,
                # Then pass the credentials to run silently the command.
                "--credentials-file=%s" % self.shotgun_credentials_file,
                # Finally pass the user requested
            ]
            + list(cmd_line_arguments)
        )

        # If we're launching the command from a pipeline configuration that uses a shared core,
        # we need to tell the tank command which pipeline configuration it is being launched from.
        if core_location != location:
            args += ["--pc=%s" % location]

        args += ["--no-line-wrapping"]

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
            stdin=subprocess.PIPE,
        )
        self._stdout = ""
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
        return self._stdout

    def _tank_cmd_thread(self, proc, user_input):
        """
        Clocks the time it takes to run the subprocess and prints out the return code
        and how much time it took to run.

        The output of the method will be stored in self._stdout.
        """
        before = time.time()
        try:
            self._stdout, _ = proc.communicate(six.ensure_binary(user_input))
            if self._stdout:
                self._stdout = six.ensure_str(self._stdout)
        finally:
            print("tank command ran in %.2f seconds." % (time.time() - before))
            print("tank command return code", proc.returncode)
            if self._stdout:
                print("tank command output:")
                print(self._stdout)

    def remove_files(self, *files):
        """
        Removes a list of files or folders on disk if they exist.

        :param *args: List of files to delete.
        """
        for f in files:
            if os.path.isdir(f):
                safe_delete_folder(f)
            else:
                safe_delete_file(f)

    def tank_setup_project(
        self,
        location,
        source_configuration,
        storage_name,
        project_id,
        tank_name,
        pipeline_root,
        force=False,
    ):
        """
        Setups a Toolkit project using the tank command.

        :param location: Location of the tank command.
        :param source_configuration: Location on disk where to find the configuration to use.
        :param storage_name: Name of the storage to assign to the config's root.
        :param project_id: Id of the project to setup.
        :param tank_name: Tank name for the project.
        :param pipeline_root: Location where the pipeline configuration will be written.
        :param force: If True, the project will be setup even if already configured.
        """
        if os.path.exists(pipeline_root):
            self.remove_files(pipeline_root)

        pipeline_root = sgtk.util.ShotgunPath.from_current_os_path(pipeline_root)

        # >> Which configuration would you like to associate with this project?
        user_input = (source_configuration,)

        # >> For each storage root, enter the name of the local storage
        # This will be asked only if storage roots are used in the config.
        if storage_name is not None:
            user_input += (storage_name,)

        user_input += (
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
            "yes",
        )

        self.run_tank_cmd(
            location,
            "setup_project",
            extra_cmd_line_arguments=["--force"] if force else None,
            user_input=user_input,
            timeout=240,
        )
