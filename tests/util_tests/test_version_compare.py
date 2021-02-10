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
from sgtk.util import (
    is_version_older,
    is_version_newer,
    is_version_newer_or_equal,
    is_version_older_or_equal,
)
from sgtk import TankError

OLDER = "older"
NEWER = "newer"
EQUAL = "equal"

git_sha = "b2cbcb9cefea668eb4ccf071e51cc650ebb27504"


class TestVersionCompare(ShotgunTestBase):
    def setUp(self):
        super(TestVersionCompare, self).setUp()

    versions = {
        ("1.2.3", "1.2.3"): EQUAL,
        ("1.2.3", "1.0.0"): NEWER,
        ("v1.2.3", "v1.0.0"): NEWER,
        ("v1.2.3", "1.0.0"): NEWER,
        ("v1.200.3", "v1.12.345"): NEWER,
        ("HEaD", "v1.12.345"): NEWER,
        ("MAsTER", "v1.12.345"): NEWER,
        ("HEaD", "1.12.345"): NEWER,
        ("MAsTER", "1.12.345"): NEWER,
        ("v0.12.3", "HEaD"): OLDER,
        ("v0.12.3", "MAsTER"): OLDER,
        ("0.12.3", "HEaD"): OLDER,
        ("0.12.3", "MAsTER"): OLDER,
        ("v0.12.3", "1.2.3"): OLDER,
        ("v0.12.3", "0.12.4"): OLDER,
        ("1.0.0", "1.0.0"): EQUAL,
        ("1.2.3", "1.0.0"): NEWER,
        (git_sha, "1.0.0"): NEWER,
        ("1.0.0", git_sha): OLDER,
        (git_sha, git_sha): EQUAL,
    }

    def test_is_git_commit(self):
        """
        Test detection of git commits when passing in a version.
        """
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

    def test_version_methods(self):
        """
        Test all version comparison methods and making sure they return
        the expected result for all inputs.
        """
        for (left, right), expected in self.versions.items():
            # We test for the expected result on the right hand-side, which
            # allows us to know that result we should be getting from the
            # function call.
            assert is_version_older(left, right) == (expected == OLDER)
            assert is_version_older_or_equal(left, right) == (
                expected in [OLDER, EQUAL]
            )
            assert is_version_newer(left, right) == (expected == NEWER)
            assert is_version_newer_or_equal(left, right) == (
                expected in [NEWER, EQUAL]
            )

    def test_version_error_conditions(self):
        """
        We can't compare two different git commit shas together and that should
        return an error.
        """
        with self.assertRaises(TankError):
            is_version_newer("b2cbcb9cefea668eb4", "a2cbcb9cefea668eb4")
        with self.assertRaises(TankError):
            is_version_older("b2cbcb9cefea668eb4", "a2cbcb9cefea668eb4")
        with self.assertRaises(TankError):
            is_version_newer_or_equal("b2cbcb9cefea668eb4", "a2cbcb9cefea668eb4")
        with self.assertRaises(TankError):
            is_version_newer_or_equal("b2cbcb9cefea668eb4", "a2cbcb9cefea668eb4")
