# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Integration tests for core.
"""

from __future__ import print_function

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
    return os.path.join(os.path.split(__file__)[0], "fixtures", "integration_tests", rel_path)


def _test_return_value(expected_result, args):
    """
    Invokes the tank command compares the result with the expected value.

    e.g.

    test_return_value(9, "--login=login --password=password")

    :param expected_result: The expected integer return code for the tank process.
    :param args: String containing all the parameters for the command line.

    :raises AssertError: If the error codes differ, this exception is raised.
    """
    args = [tank_path] + args.split(" ")
    print("Running %s" % " ".join(args))
    try:
        output = subprocess.check_output(args, stdin=None)
        result = 0
    except subprocess.CalledProcessError as e:
        result = e.returncode
        output = e.output

    if result != expected_result:
        print("Expecting %s, got %s" % (expected_result, result))
        print(output)
        assert(result == expected_result)


def test_return_value(expected_result, args):
    """
    Invokes the tank command with the arguments provided with and without a core
    command and compares the result with the expected value.

    :param expected_result: The expected integer return code for the tank process.
    :param args: String containing all the parameters for the command line.

    :raises AssertError: If the error codes differ, this exception is raised.
    """
    _test_return_value(expected_result, args)
    _test_return_value(expected_result, args + " shell")


def command_line_authentication_tests():
    """
    Runs command line authentication tests.
    """
    # missing param
    test_return_value(9, "--script-name=test")
    test_return_value(9, "--script-key=1234")
    test_return_value(9, "--credentials-file=%s" % get_test_resource_path("authentication/missing_file"))

    test_return_value(9, "--script-name=test --script-name=test --script-key=1234")
    test_return_value(9, "--script-name=test --script-key=1234 --script-key=1234")

    # mixing params
    test_return_value(9, "--script-name=test --credentials-file=/var/tmp/script_credentials.yml")
    test_return_value(9, "--script-key=test --credentials-file=/var/tmp/script_credentials.yml")

    # Bad credentials
    test_return_value(7, "--script-name=test --script-key=1234")
    test_return_value(7, "--credentials-file=%s" % get_test_resource_path("authentication/bad_credentials"))


def main():
    """
    Runs all the integration tests.
    """
    if len(sys.argv) != 2:
        print("Usage: python run_tank_tests.py /path/to/your/tank.executable")
        return

    global tank_path
    tank_path = sys.argv[1]

    command_line_authentication_tests()


if __name__ == '__main__':
    main()
