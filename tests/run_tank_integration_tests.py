# Copyright (c) 2015 Shotgun Software Inc.
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
import subprocess

tank_path = None


def get_test_resource_path(rel_path):
    """
    Returns the path to the test resource in the data/tank_integration_tests
    folder.

    :param rel_path: Relative file path to the test file.
    """
    return os.path.join(os.path.split(__file__)[0], "data", "tank_integration_tests", rel_path)


def test_return_value(expected_result, args):
    """
    Invokes the tank command with the arguments provided and compares the
    result with the expected value.

    e.g.

    test_return_value(9, "--login=login --password=password")

    :param expected_result: The expected integer return code for the tank process.
    :param args: String containing all the parameters for the command line.

    :raises AssertError: If the error codes differ, this exception is raised.
    """
    global tank_path
    args = [tank_path] + args.split(" ")
    print "Running %s" % " ".join(args)
    try:
        result = subprocess.check_output(args)
        output = ""
    except subprocess.CalledProcessError, e:
        result = e.returncode
        output = e.output

    if result != expected_result:
        print "Expecting %d, got %d" % (expected_result, result)
        print output
        assert(result == expected_result)


def command_line_authentication_tests():
    """
    Runs command line authentication tests.
    """

    # missing param
    test_return_value(9, "--login=test")
    test_return_value(9, "--password=1234")
    test_return_value(9, "--script=test")
    test_return_value(9, "--key=1234")
    test_return_value(9, "--auth==%s" % get_test_resource_path("authentication/missing_file"))

    # doubling param
    test_return_value(9, "--login=test --login=test --password=1234")
    test_return_value(9, "--login=test --password=1234 --password=1234")

    test_return_value(9, "--script=test --script=test --key=1234")
    test_return_value(9, "--script=test --key=1234 --key=1234")

    # mixing params
    test_return_value(9, "--login=test --script=test")
    test_return_value(9, "--login=test --key=test")
    test_return_value(9, "--login=test --auth=/var/tmp/userpass")

    test_return_value(9, "--password=test --script=test")
    test_return_value(9, "--password=test --key=test")
    test_return_value(9, "--password=test --auth=/var/tmp/userpass")

    test_return_value(9, "--script=test --auth=/var/tmp/userpass")
    test_return_value(9, "--key=test --auth=/var/tmp/userpass")

    test_return_value(9, "--auth=%s" % get_test_resource_path("authentication/mixed"))

    # invalid credentials
    test_return_value(10, "--login=test --password=1234")
    test_return_value(10, "--auth=%s" % get_test_resource_path("authentication/login_password"))


def main():
    """
    Runs all the integration tests.
    """
    if len(sys.argv) != 2:
        print "Usage: python run_tank_tests.py /path/to/your/tank.executable"
        return

    global tank_path
    tank_path = sys.argv[1]

    command_line_authentication_tests()


if __name__ == '__main__':
    main()
