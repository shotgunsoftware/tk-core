# Copyright (c) 2018 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import ShotgunTestBase
import sgtk


class TestVersionCompare(ShotgunTestBase):
    def setUp(self):
        super(TestVersionCompare, self).setUp()

    def test_is_git_commit(self):
        from tank.util.version import _is_git_commit

        valid_commit = "b2cbcb9cefea668eb4ccf071e51cc650ebb27504"
        short_commit = valid_commit[0:7]
        assert len(short_commit) == 7

        too_short_commit = short_commit[:-1]
        assert len(too_short_commit) == 6

        # The regex accepts any letters between A-F upper/lower case
        # and numbers, from 7 to 40 characters.
        assert _is_git_commit(valid_commit) is True
        assert _is_git_commit(valid_commit.upper()) is True
        assert _is_git_commit(short_commit) is True

        # Invalid character at the beginning
        assert _is_git_commit("x" + short_commit) is False
        # Invalid character at the end
        assert _is_git_commit(short_commit + "x") is False
        # Too long
        assert _is_git_commit(valid_commit + "a") is False
        # Too short
        assert _is_git_commit(too_short_commit) is False

    def test_is_version_newer(self):

        from tank.util.version import is_version_newer

        self.assertTrue(is_version_newer("1.2.3", "1.0.0"))
        self.assertTrue(is_version_newer("v1.2.3", "v1.0.0"))
        self.assertTrue(is_version_newer("v1.2.3", "1.0.0"))

        self.assertTrue(is_version_newer("v1.200.3", "v1.12.345"))

        self.assertTrue(is_version_newer("HEaD", "v1.12.345"))
        self.assertTrue(is_version_newer("MAsTER", "v1.12.345"))

        self.assertTrue(is_version_newer("HEaD", "1.12.345"))
        self.assertTrue(is_version_newer("MAsTER", "1.12.345"))

        self.assertFalse(is_version_newer("v0.12.3", "HEaD"))
        self.assertFalse(is_version_newer("v0.12.3", "MAsTER"))

        self.assertFalse(is_version_newer("0.12.3", "HEaD"))
        self.assertFalse(is_version_newer("0.12.3", "MAsTER"))

        self.assertFalse(is_version_newer("v0.12.3", "1.2.3"))
        self.assertFalse(is_version_newer("v0.12.3", "0.12.4"))

        self.assertFalse(is_version_newer("1.0.0", "1.0.0"))

        self.assertTrue(is_version_newer("1.2.3", "1.0.0"))

        # Git hashes are always considered more recent that a version string.
        self.assertFalse(
            is_version_newer("1.2.3", "b2cbcb9cefea668eb4ccf071e51cc650ebb27504")
        )
        self.assertTrue(
            is_version_newer("b2cbcb9cefea668eb4ccf071e51cc650ebb27504", "1.2.3")
        )

        # Commits are the same.
        self.assertFalse(
            is_version_newer(
                "b2cbcb9cefea668eb4ccf071e51cc650ebb27504",
                "b2cbcb9cefea668eb4ccf071e51cc650ebb27504",
            )
        )

        with self.assertRaises(sgtk.TankError):
            is_version_newer("b2cbcb9cefea668eb4", "a2cbcb9cefea668eb4")

    def test_is_version_older(self):

        from tank.util.version import is_version_older

        self.assertFalse(is_version_older("1.2.3", "1.0.0"))
        self.assertFalse(is_version_older("v1.2.3", "v1.0.0"))
        self.assertFalse(is_version_older("v1.2.3", "1.0.0"))

        self.assertFalse(is_version_older("v1.200.3", "v1.12.345"))

        self.assertFalse(is_version_older("HEaD", "v1.12.345"))
        self.assertFalse(is_version_older("MAsTER", "v1.12.345"))

        self.assertFalse(is_version_older("HEaD", "1.12.345"))
        self.assertFalse(is_version_older("MAsTER", "1.12.345"))

        self.assertTrue(is_version_older("v0.12.3", "HEaD"))
        self.assertTrue(is_version_older("v0.12.3", "MAsTER"))

        self.assertTrue(is_version_older("0.12.3", "HEaD"))
        self.assertTrue(is_version_older("0.12.3", "MAsTER"))

        self.assertTrue(is_version_older("v0.12.3", "1.2.3"))
        self.assertTrue(is_version_older("v0.12.3", "0.12.4"))

        self.assertFalse(is_version_older("1.0.0", "1.0.0"))

        # Git hashes are always considered more recent that a version string.
        self.assertTrue(
            is_version_older("1.2.3", "b2cbcb9cefea668eb4ccf071e51cc650ebb27504")
        )
        self.assertFalse(
            is_version_older("b2cbcb9cefea668eb4ccf071e51cc650ebb27504", "1.2.3")
        )

        # Commits are the same.
        self.assertFalse(
            is_version_older(
                "b2cbcb9cefea668eb4ccf071e51cc650ebb27504",
                "b2cbcb9cefea668eb4ccf071e51cc650ebb27504",
            )
        )

        with self.assertRaises(sgtk.TankError):
            is_version_older("b2cbcb9cefea668eb4", "a2cbcb9cefea668eb4")
