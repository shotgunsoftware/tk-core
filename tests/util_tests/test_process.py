# Copyright (c) 2019 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import sys
from unittest import TestCase

from tank.util import process


class TestProcess(TestCase):
    def _run_python_cmd(self, exit_code):
        return process.subprocess_check_output(
            [
                sys.executable,
                "-c",
                "import sys;"
                # Flush each write so they are guaranteed to be in the right order
                # when captured.
                "sys.stdout.write('Hello world from stdout'); sys.stdout.flush();"
                "sys.stderr.write('Hello world from stderr'); sys.stderr.flush();"
                "sys.exit({0});".format(exit_code),
            ]
        )

    def test_successful_run(self):
        pass
    def test_failed_run(self):
        pass
