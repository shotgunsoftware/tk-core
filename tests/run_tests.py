# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from __future__ import print_function

import sys
import os
import glob
import platform
import tempfile
import time

from optparse import OptionParser


# Let the user know which Python is picked up to run the tests.
print()
print("Using Python version \"%s\" at \"%s\"" % (".".join(
    str(i) for i in sys.version_info[0:3]
), sys.executable))

# prepend tank_vendor location to PYTHONPATH to make sure we are running
# the tests against the vendor libs, not local libs on the machine
core_python_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "python"))
print("")
print("Adding tank location to python_path: %s" % core_python_path)
sys.path = [core_python_path] + sys.path

# prepend tank_vendor location to PYTHONPATH to make sure we are running
# the tests against the vendor libs, not local libs on the machine
test_python_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "python"))
print("Adding tests/python location to python_path: %s" % test_python_path)
sys.path = [test_python_path] + sys.path

test_python_path = os.path.join(test_python_path, "third_party")
print("Adding tests/python/third_party location to python_path: %s" % test_python_path)
sys.path = [test_python_path] + sys.path

import unittest2 as unittest

# Requires the extra sys paths added above
import tank_test.misc_test_utils as utils


class TankTestRunner(object):

    def __init__(self, test_root=None):

        curr_dir = os.path.dirname(os.path.abspath(__file__))

        if test_root is None:
            self.test_path = curr_dir
        else:
            self.test_path = test_root

        print("Tests will be loaded from: %s" % self.test_path)

        # the fixtures are always located relative to the test location
        # so store away the fixtures location in an environment vartiable
        # for later use
        os.environ["TK_TEST_FIXTURES"] = os.path.join(self.test_path, "fixtures")
        print("Fixtures will be loaded from: %s" % os.environ["TK_TEST_FIXTURES"])

        # set up the path to the core API
        self.packages_path = os.path.join(os.path.dirname(curr_dir), "python")

        # add to pythonpath
        sys.path.append(self.packages_path)
        sys.path.append(self.test_path)
        self.suite = None

    def setup_suite(self, test_names):
        # args used to specify specific module.TestCase.test
        if test_names:
            test_names_iterator = self._massage_test_names(test_names)
            self.suite = unittest.loader.TestLoader().loadTestsFromNames(test_names_iterator)
        else:
            self.suite = unittest.loader.TestLoader().discover(self.test_path)

    def run_tests(self, test_names):
        self.setup_suite(test_names)
        return unittest.TextTestRunner(verbosity=2).run(self.suite)

    def _massage_test_names(self, test_names):
        """
        Massages the text input by the user in order to convert all input into proper
        python modules path.

        For example::
            core_tests/test_api.py -> [core_tests.test_api]
            authentication_tests -> [all test_*.py files]

        :param test_names: List of file names and/or module paths.
        """
        for test_name in test_names:
            # If the user used tab completion there will be an extra path separator at
            # the end, so remove it.
            if test_name[-1] == os.path.sep:
                test_name = test_name[:-1]

            # If a test name looks like a file name, turn the slashes into . and remove the
            # extension.
            test_name = test_name.replace("/", ".").replace(".py", "")

            # If we have a simple module name, no sub-module, then, run all the tests in that
            # module.
            if "." not in test_name:
                # Grab all the python files named after test_*.py
                for filename in self._massage_test_names(
                    # Generate clean module/submodule.py files without the fully qualified path.
                    # Skip the extra /
                    os.path.abspath(filename).replace(self.test_path, "")[1:]
                    for filename in glob.iglob(os.path.join(self.test_path, test_name, "test_*.py"))
                ):
                    yield filename
            else:
                yield test_name


def _initialize_coverage(test_root):
    """
    Starts covering the code inside the tank module.

    :returns: The coverage instance.
    """
    import coverage

    if test_root:
        coveragerc_location = os.path.abspath(
            os.path.join(
                test_root, # <root>/tests
                "..", # <root>
                ".coveragerc") # <root>/.coveragerc
        )
    else:
        run_tests_py_location = __file__
        coveragerc_location = os.path.abspath(
            os.path.join(
                os.path.dirname(run_tests_py_location), # <root>/tests
                "..", # <root>
                ".coveragerc") # <root>/.coveragerc
        )
    cov = coverage.coverage(config_file=coveragerc_location)
    cov.start()
    return cov


def _finalize_coverage(cov):
    """
    Stops covering code and writes out reports.
    """
    cov.stop()
    cov.report()

    try:
        # seems to be some CI issues with html coverage so
        # failing gracefully with a warning in case it doesn't work.
        cov.html_report(directory="coverage_html_report")
    except Exception as e:
        print("WARNING: Html coverage report could not be written: %s" % e)
    else:
        print("Note: Full html coverage report can be found in the coverage_html_report folder.")


def _initialize_logging(log_to_console):
    """
    Sets up a log file for the unit tests and optionally logs everything to the console.

    :param log_to_console: If True, all Toolkit logging will go to the console.
    """
    import tank
    tank.LogManager().initialize_base_file_handler("run_tests")

    if options.log_to_console:
        tank.LogManager().initialize_custom_handler()


def _run_tests(test_root, test_names):
    """
    Runs the tests.

    :param test_root: Folder where unit tests can be found.
    :param test_name: Name of the unit test to run. If None, all tests are run.
    """
    if test_root:
        # resolve path
        test_root = os.path.expanduser(os.path.expandvars(test_root))
        test_root = os.path.abspath(test_root)
        tank_test_runner = TankTestRunner(test_root)
    else:
        tank_test_runner = TankTestRunner()

    return tank_test_runner.run_tests(test_names)


def _parse_command_line():
    """
    Parses the command line.

    :returns: The options and the name of the unit test specified on the command line, if any.
    """
    parser = OptionParser()
    parser.add_option("--with-coverage",
                      action="store_true",
                      dest="coverage",
                      help="run with coverage (requires coverage is installed)")
    parser.add_option("--interactive",
                      action="store_true",
                      dest="interactive",
                      help="run tests that have been decorated with the interactive decorator")
    parser.add_option("--test-root",
                      action="store",
                      dest="test_root",
                      help="Specify a folder where to look for tests.")
    parser.add_option("--log-to-console", "-l",
                      action="store_true",
                      help="run tests and redirect logging output to the console.")

    (options, args) = parser.parse_args()

    test_names = args or []

    return options, test_names


def test_leaked_files_after_date(test_start_time):
    """
    Heuristically try to determine whether any of the tests leaked some resource files
    :param test_start_time: double unix timestamp
    :return: integer 1 on failure else returns 0
    """

    know_tank_filemasks = [
        "tankTemporaryTestData",
        "_tank_source",
        "_tank_content"
    ]

    temp_dir = tempfile.gettempdir()
    all_files_and_folders = os.listdir(temp_dir)

    possibly_leaking_resources = []
    leaking_resources = []
    for f in all_files_and_folders:
        try:
            full_path = os.path.join(temp_dir, f)
            d = utils.creation_date(full_path)
            if d >= test_start_time:
                basename = os.path.basename(full_path)
                if any(fm in basename for fm in know_tank_filemasks):
                    leaking_resources.append(full_path)
                else:
                    possibly_leaking_resources.append(full_path)

        except Exception as e:
            print("Exception: %s" % (str(e)))

    #
    # Prints out 'possible' resource leaks
    #
    print("")
    for f in possibly_leaking_resources:
        print("WARNING: Possible resource leak: %s" % str(f))

    #
    # Prints out known resource leaks
    #
    if not leaking_resources:
        return 0

    print("")
    total_leaked_bytes = 0
    for f in leaking_resources:
        entry_size = utils.get_size(f)
        #entry_size = get_total_size(f)
        total_leaked_bytes = total_leaked_bytes + entry_size
        print("ERROR: %s leaked, Test resource leak: %s" % (utils.format_value(entry_size), str(f)))

    if total_leaked_bytes:
        print("ERROR: %s total leaked" % utils.format_value(total_leaked_bytes))

    return 1


if __name__ == "__main__":

    options, test_names = _parse_command_line()

    # Create a time marker
    test_start_time = time.time()

    # Do not import Toolkit before coverage or it will tank (pun intended) our coverage
    # score. We'll do this test even when we're not running code coverage to make sure
    # we don't introduce unintended regressions.
    if "tank" in sys.modules or "sgtk" in sys.modules:
        raise RuntimeError(
            "tank or sgtk was imported before the coverage module. Please fix run_tests.py."
        )

    if options.coverage:
        cov = _initialize_coverage(options.test_root)

    _initialize_logging(options.log_to_console)

    # If we have a custom test root, add its python folder, if it exists, so the user doesn't need
    # to set it up themselves.
    if options.test_root:
        python_test_root = os.path.join(options.test_root, "python")
        if os.path.exists(python_test_root):
            sys.path.insert(0, python_test_root)

    ret_val = _run_tests(options.test_root, test_names)

    if options.coverage:
        _finalize_coverage(cov)

    # Exit value determined by failures and errors
    exit_val = test_leaked_files_after_date(test_start_time)

    if ret_val.errors or ret_val.failures:
        exit_val = 1
    sys.exit(exit_val)
