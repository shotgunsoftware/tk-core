# Copyright (c) 2017 Shotgun Software Inc.
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
import tempfile
import atexit


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

HERE = os.path.dirname(__file__)
os.environ["TK_TEST_FIXTURES"] = os.path.join(HERE, "fixtures")

print("Fixtures will be loaded from: %s" % os.environ["TK_TEST_FIXTURES"])

import tank # noqa


tank.LogManager().initialize_base_file_handler("run_tests")

tank.LogManager().initialize_custom_handler()


#
# Create our own temporary base storage into which everything
# will be created. Having a single top-level folder will make
# complete deletion very easy.
#
new_base_tempdir = tempfile.mkdtemp(prefix="tankTemporary_")
#
# Now that we have our global test run subdir created, let's
# re-assign tempfile.temdir() value to be used a new base directory
#
# NOTE: There is no need to save the current value of 'tempfile.tempdir'
#       for later restoring. This is not changing value of default
#       temporary directory for anything else than this instance of
#       the 'tempfile' module. Overall system is not affected.
#
tempfile.tempdir = new_base_tempdir


def clean_temp(location):
    from tank.util.filesystem import safe_delete_folder

    # Note: Relying on own value rather than tempfile.tempdir
    #       being global it MIGHT be changed by anyone test
    if location and os.path.isdir(location):
        print("\nCleaning up '%s'" % (location))
        safe_delete_folder(location)


atexit.register(clean_temp, new_base_tempdir)
