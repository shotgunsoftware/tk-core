# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Unit tests for bootstrapping.
"""

from __future__ import with_statement, print_function
import os
import sys
import tempfile
import subprocess

from unittest2 import TestCase

from sgtk.authentication import ShotgunAuthenticator
from sgtk.descriptor import Descriptor, create_descriptor

CURRENT_DIR = os.path.dirname(__file__)


class BootstrapTests(TestCase):

    LEAN_CORE_DESC = "sgtk:descriptor:path?path={0}".format(
        os.path.abspath(
            os.path.join(CURRENT_DIR, "..", "..")
        )
    )

    OLD_CORE_DESC = "sgtk:descriptor:app_store?type=app_store&version=v0.18.120&name=tk-core"

    def setUp(self):
        super(BootstrapTests, self).setUp()
        auth = ShotgunAuthenticator()
        user = auth.create_script_user(
            os.environ["TOOLKIT_INTEGRATION_TEST_API_SCRIPT"],
            os.environ["TOOLKIT_INTEGRATION_TEST_API_KEY"],
            os.environ["TOOLKIT_INTEGRATION_TEST_SITE"]
        )
        self._sg = user.create_sg_connection()

    def _launch_script(self, bootstrap_core, config_core):

        bootstrap_core_path = create_descriptor(
            self._sg,
            Descriptor.CORE,
            bootstrap_core
        ).get_path()

        try:
            subprocess.check_output(
                [
                    sys.executable,
                    # FIXME: Find how to merge the coverage from the subprocesses
                    # into our unit test coverage.
                    # os.path.join(CURRENT_DIR, "..", "python", "third_party", "coverage"),
                    # "run",
                    os.path.join(CURRENT_DIR, "boostrap_script.py"),
                    "--config-core", config_core,
                    "--config-template", "sgtk:descriptor:path?path=$TK_TEST_FIXTURES/integration_tests",
                    # "--response-file", PATH TO A LOCAL FILE THAT THE SCRIPT USES TO COMMUNICATE BACK
                    "--api-script", os.environ["TOOLKIT_INTEGRATION_TEST_API_SCRIPT"],
                    "--api-key", os.environ["TOOLKIT_INTEGRATION_TEST_API_KEY"],
                    "--site", os.environ["TOOLKIT_INTEGRATION_TEST_SITE"]
                ],
                env=dict(
                    PYTHONPATH=os.path.join(bootstrap_core_path, "python"),
                    TEMP=os.path.join(tempfile.gettempdir(), self.id()),
                    SHOTGUN_HOME="$TEMP/home",
                    TK_TEST_FIXTURES=os.environ["TK_TEST_FIXTURES"],
                    TK_DEBUG=os.environ.get("TK_DEBUG", "0")
                )
            )
        except subprocess.CalledProcessError as e:
            print("Failed executing: {0}".format(e.cmd))
            print("Output")
            print(e.output)
            raise

    def test_from_old_core_to_old_core(self):
        self._launch_script(self.OLD_CORE_DESC, self.OLD_CORE_DESC)

    def test_from_old_core_to_lean_enabled_core(self):
        self._launch_script(self.OLD_CORE_DESC, self.LEAN_CORE_DESC)

    def test_from_lean_enabled_core_to_old_core(self):
        self._launch_script(self.LEAN_CORE_DESC, self.OLD_CORE_DESC)

    def test_from_lean_enabled_core_to_lean_enabled_core(self):
        self._launch_script(self.LEAN_CORE_DESC, self.LEAN_CORE_DESC)
