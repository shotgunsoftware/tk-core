# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import sys
import os
from optparse import OptionParser

print
print "Using Python version \"%s\"" % (".".join(
    str(i) for i in sys.version_info[0:3]
),)

# prepend tank_vendor location to PYTHONPATH to make sure we are running
# the tests against the vendor libs, not local libs on the machine
core_python_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "python"))
print ""
print "Adding tank location to python_path: %s" % core_python_path
sys.path = [core_python_path] + sys.path

# prepend tank_vendor location to PYTHONPATH to make sure we are running
# the tests against the vendor libs, not local libs on the machine
test_python_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "python"))
print "Adding tests/python location to python_path: %s" % test_python_path
sys.path = [test_python_path] + sys.path

import unittest2 as unittest


class TankTestRunner(object):

    def __init__(self, test_root=None):

        curr_dir = os.path.dirname(os.path.abspath(__file__))

        if test_root is None:
            self.test_path = curr_dir
        else:
            self.test_path = test_root

        print "Tests will be loaded from: %s" % self.test_path

        # the fixtures are always located relative to the test location
        # so store away the fixtures location in an environment vartiable
        # for later use
        os.environ["TK_TEST_FIXTURES"] = os.path.join(self.test_path, "fixtures")
        print "Fixtures will be loaded from: %s" % os.environ["TK_TEST_FIXTURES"]

        # set up the path to the core API
        self.packages_path = os.path.join(os.path.dirname(curr_dir), "python")

        # add to pythonpath
        sys.path.append(self.packages_path)
        sys.path.append(self.test_path)
        self.suite = None

    def setup_suite(self, test_name):
        # args used to specify specific module.TestCase.test
        if test_name:
            self.suite = unittest.loader.TestLoader().loadTestsFromName(test_name)
        else:
            self.suite = unittest.loader.TestLoader().discover(self.test_path)

    def run_tests(self, test_name):
        self.setup_suite(test_name)
        return unittest.TextTestRunner(verbosity=2).run(self.suite)


if __name__ == "__main__":
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

    test_name = None
    if args:
        test_name = args[0]

    # Do not import Toolkit before coverage or it will tank (pun intended) our coverage
    # score.
    if "tank" in sys.modules or "sgtk" in sys.modules:
        raise RuntimeError(
            "tank or sgtk was imported before the coverage module. Please fix run_tests.py."
        )

    if options.coverage:
        import coverage
        shotgun_path = os.path.join(core_python_path, "tank_vendor", "*")
        cov = coverage.coverage(source=["tank"], omit=shotgun_path)
        cov.start()

    import tank
    tank.LogManager().initialize_base_file_handler("run_tests")

    if options.log_to_console:
        tank.LogManager().initialize_custom_handler()

    if options.test_root:
        # resolve path
        test_root = os.path.expanduser(os.path.expandvars(options.test_root))
        test_root = os.path.abspath(test_root)
        tank_test_runner = TankTestRunner(test_root)
    else:
        tank_test_runner = TankTestRunner()

    ret_val = tank_test_runner.run_tests(test_name)

    if options.coverage:
        cov.stop()
        cov.report()
        cov.xml_report(outfile="coverage.xml")

    # Exit value determined by failures and errors
    exit_val = 0
    if ret_val.errors or ret_val.failures:
        exit_val = 1
    sys.exit(exit_val)
