# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Unit tests tank updates.
"""

from __future__ import with_statement

from tank_test.tank_test_base import TankTestBase
from tank_test.tank_test_base import setUpModule # noqa

from mock import patch, Mock

from sgtk.commands import console_utils


class SealedMock(Mock):
    """
    Sealed mock ensures that no one is accessing something we have not planned for.
    """
    def __init__(self, **kwargs):
        """
        :param kwargs: Passed down directly to the base class as kwargs. Each keys are passed to the ``spec_set`` 
            argument from the base class to seal the gettable and settable properties.
        """
        super(SealedMock, self).__init__(spec_set=kwargs.keys(), **kwargs)


class ConsoleUtilsTests(TankTestBase):
    """
    Tests for console utilities.
    """

    def setUp(self):
        """
        Ensures the Shotgun version cache is cleared between tests.
        """
        super(ConsoleUtilsTests, self).setUp()
        # Uncache the shotgun verison between tests.
        console_utils.g_sg_studio_version = None

    @patch("tank.util.shotgun.get_sg_connection", return_value=SealedMock(server_info={"version": "6.6.6"}))
    def test_min_sg_constraint_pass(self, _):
        """
        Ensures that having a greater or equal version of Shotgun works.
        """
        can_update, reasons = console_utils._check_constraints(
            SealedMock(
                version_constraints={"min_sg": "6.6.6"},
                supported_engines=None
            )
        )
        self.assertEqual(can_update, True)
        self.assertListEqual(reasons, [])

    @patch("tank.util.shotgun.get_sg_connection", return_value=SealedMock(server_info={"version": "6.6.5"}))
    def test_min_sg_constraint_fail(self, _):
        """
        Ensures that having an older version of Shotgun fails.
        """
        can_update, reasons = console_utils._check_constraints(
            SealedMock(
                version_constraints={"min_sg": "6.6.6"},
                supported_engines=None
            )
        )
        self.assertEqual(can_update, False)
        self.assertEqual(len(reasons), 1)
        self.assertRegexpMatches(reasons[0], "Requires at least Shotgun .* but currently installed version is .*\.")

    @patch("tank.pipelineconfig_utils.get_currently_running_api_version", return_value="v6.6.6")
    def test_min_core_constraint_pass(self, _):
        """
        Ensures that having a greater or equal version of core works.
        """
        can_update, reasons = console_utils._check_constraints(
            SealedMock(
                version_constraints={"min_core": "v6.6.6"},
                supported_engines=None
            )
        )
        self.assertEqual(can_update, True)
        self.assertListEqual(reasons, [])

    @patch("tank.pipelineconfig_utils.get_currently_running_api_version", return_value="v6.6.5")
    def test_min_core_constraint_fail(self, _):
        """
        Ensures that having a lower version of core fails.
        """
        can_update, reasons = console_utils._check_constraints(
            SealedMock(
                version_constraints={"min_core": "v6.6.6"},
                supported_engines=None
            )
        )
        self.assertEqual(can_update, False)
        self.assertEqual(len(reasons), 1)
        self.assertRegexpMatches(reasons[0], "Requires at least Core API .* but currently installed version is .*")

    def test_min_engine_constraint_pass(self):
        """
        Ensures that having a greater or equal version of the engine works.
        """
        can_update, reasons = console_utils._check_constraints(
            SealedMock(
                version_constraints={"min_engine": "v6.6.6"},
                supported_engines=None
            ),
            SealedMock(
                version="v6.6.6"
            )
        )
        self.assertEqual(can_update, True)
        self.assertListEqual(reasons, [])

    def test_min_engine_constraint_fail(self):
        """
        Ensures that having a lower version of the engine fails.
        """
        can_update, reasons = console_utils._check_constraints(
            SealedMock(
                version_constraints={"min_engine": "v6.6.6"},
                supported_engines=None
            ),
            SealedMock(
                version="v6.6.5",
                display_name="Tk Test"
            )
        )
        self.assertEqual(can_update, False)
        self.assertRegexpMatches(reasons[0], "Requires at least Engine .* but currently installed version is .*")

    def test_supported_engine_constraint_pass(self):
        """
        Ensures that being installed in a supported engine works.
        """
        can_update, reasons = console_utils._check_constraints(
            SealedMock(
                version_constraints={},
                supported_engines=["tk-test"]
            ),
            SealedMock(
                system_name="tk-test",
                display_name="Tk Test"
            )
        )
        self.assertEqual(can_update, True)
        self.assertListEqual(reasons, [])

    def test_supported_engine_constraint_fail(self):
        """
        Ensures that being installed in an unsupported engine fails.
        """
        can_update, reasons = console_utils._check_constraints(
            SealedMock(
                version_constraints={},
                supported_engines=["tk-test"]
            ),
            SealedMock(
                version="v6.6.5",
                system_name="tk-another-test",
                display_name="tk-test"
            )
        )
        self.assertEqual(can_update, False)
        self.assertRegexpMatches(reasons[0], "Not compatible with engine .*. Supported engines are .*")

    @patch("tank.util.shotgun.get_sg_connection", return_value=SealedMock(server_info={"version": "6.6.5"}))
    @patch("tank.pipelineconfig_utils.get_currently_running_api_version", return_value="v5.5.4")
    def test_reasons_add_up(self, *_):
        """
        Ensures that having multiple failures add up.
        """
        can_update, reasons = console_utils._check_constraints(
            SealedMock(
                version_constraints={
                    "min_core": "v5.5.5",
                    "min_sg": "v6.6.6g",
                    "min_engine": "v4.4.4"
                },
                supported_engines=["tk-test"]
            ),
            SealedMock(
                version="v4.4.3",
                system_name="tk-another-test",
                display_name="tk-test"
            )
        )

        self.assertEqual(can_update, False)
        self.assertEqual(len(reasons), 4)
