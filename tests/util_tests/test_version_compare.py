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
        pass
    versions = {
        ("1.2.3", "1.2.3"): EQUAL,
        ("1.2.3", "1.0.0"): NEWER,
        ("v1.2.3", "v1.0.0"): NEWER,
        ("v1.2.3", "1.0.0"): NEWER,
        ("v1.200.3", "v1.12.345"): NEWER,
        ("6.3v6", "6.3.5"): NEWER,
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
        ("1.0.0", "unknown"): OLDER,
        ("unknown", "1.0.0"): NEWER,
        ("unknown", "unknown"): EQUAL,
    }

    def test_is_git_commit(self):
        pass
    def test_version_methods(self):
        pass
    def test_version_error_conditions(self):
        pass
