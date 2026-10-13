# Copyright (c) 2026 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from __future__ import annotations  # needed for python 3.9 support

import os
import re
import subprocess

import sgtk
from tank.util.process import SubprocessCalledProcessError
from tank.util.version import is_version_newer
from tank_test.tank_test_base import (
    ShotgunTestBase,
    mock,
    setUpModule,  # noqa
    skip_if_git_missing,
)
from tank_vendor.packaging.version import Version

CHECK_OUTPUT = "tank.descriptor.io_descriptor.dev._check_output"


class TestDevDescriptorVersion(ShotgunTestBase):
    """
    Tests the version reported by dev descriptors pointing at a git clone.

    The mocked tests hardcode our expectations of ``git describe --tags --long``
    output, so a change in how it is parsed is caught without needing git.
    """

    def setUp(self) -> None:
        super().setUp()
        self.dev_path = os.path.join(self.tank_temp, "dev_bundle")

    def _get_version(self, **descriptor_dict: str) -> str:
        """
        Creates a dev descriptor for the test path and returns its version.

        :param descriptor_dict: Extra keys for the descriptor dictionary.
        :returns: The descriptor version.
        """
        descriptor_dict.setdefault("path", self.dev_path)
        desc = sgtk.descriptor.create_descriptor(
            self.mockgun,
            sgtk.descriptor.Descriptor.APP,
            dict(type="dev", **descriptor_dict),
        )
        return desc.version

    def test_explicit_version_is_kept(self) -> None:
        """
        Tests that an explicit version is returned without running git.
        """
        with mock.patch(CHECK_OUTPUT) as check_output_mock:
            self.assertEqual(self._get_version(version="v1.0.0"), "v1.0.0")
        check_output_mock.assert_not_called()

    def test_git_describe_command(self) -> None:
        """
        Tests the git command run to describe the clone.
        """
        with mock.patch(
            CHECK_OUTPUT, return_value="v1.2.3-0-g1a2b3c4\n"
        ) as check_output_mock:
            self._get_version()
        check_output_mock.assert_called_once_with(
            ["git", "-C", self.dev_path, "describe", "--tags", "--long"]
        )

    def test_git_describe_conversion(self) -> None:
        """
        Tests that git describe output is converted to a PEP 440 version.
        """
        cases = [
            # Exactly on a tag.
            ("v1.2.3-0-g1a2b3c4\n", "v1.2.3+g1a2b3c4"),
            # Commits past a tag.
            ("v1.2.3-5-g1a2b3c4\n", "v1.2.3.post5+g1a2b3c4"),
            # A longer sha, used when 7 characters are ambiguous.
            ("v1.2.3-12-g1a2b3c4d5e6\n", "v1.2.3.post12+g1a2b3c4d5e6"),
            # Pre-release tags, which contain dashes themselves.
            ("v1.7.9-alpha1-6-gdb78cfd\n", "v1.7.9-alpha1.post6+gdb78cfd"),
            ("v1.7.0-alpha.3-0-gabc1234\n", "v1.7.0-alpha.3+gabc1234"),
            ("v1.7.8-rc3-2-gabc1234\n", "v1.7.8-rc3.post2+gabc1234"),
        ]
        for describe_output, expected in cases:
            with self.subTest(describe_output=describe_output):
                with mock.patch(CHECK_OUTPUT, return_value=describe_output):
                    version = self._get_version()
                self.assertEqual(version, expected)
                # Must be a valid PEP 440 version.
                Version(version)

    def test_version_ordering(self) -> None:
        """
        Tests that converted versions sort correctly against released versions
        using the sgtk version system.
        """

        def describe(output: str) -> str:
            with mock.patch(CHECK_OUTPUT, return_value=output):
                return self._get_version()

        ordered = [
            "v1.2.3",
            describe("v1.2.3-0-g1a2b3c4"),
            describe("v1.2.3-5-g1a2b3c4"),
            describe("v1.2.3-12-g1a2b3c4"),
            "v1.2.4",
        ]
        ordered_pre_release = [
            "v1.7.9-alpha1",
            describe("v1.7.9-alpha1-0-gdb78cfd"),
            describe("v1.7.9-alpha1-6-gdb78cfd"),
            "v1.7.9",
        ]
        for versions in (ordered, ordered_pre_release):
            for older, newer in zip(versions, versions[1:]):
                with self.subTest(older=older, newer=newer):
                    self.assertTrue(is_version_newer(newer, older))
                    self.assertFalse(is_version_newer(older, newer))

    def test_git_failures_fall_back(self) -> None:
        """
        Tests that the undefined version is returned when git cannot help.
        """
        cases = {
            "not a git clone or no tags": SubprocessCalledProcessError(
                128, "git describe", "fatal: No names found"
            ),
            "git not installed": FileNotFoundError("git"),
        }
        for name, error in cases.items():
            with self.subTest(name):
                with mock.patch(CHECK_OUTPUT, side_effect=error):
                    self.assertEqual(self._get_version(), "Undefined")

        for output in ("", "\n", "unexpected-output"):
            with self.subTest(output=output):
                with mock.patch(CHECK_OUTPUT, return_value=output):
                    self.assertEqual(self._get_version(), "Undefined")

    @skip_if_git_missing
    def test_real_git_describe(self) -> None:
        """
        Tests against a real git clone, to validate that git describe still
        produces the output format the mocked tests expect.
        """
        repo = os.path.join(self.tank_temp, "dev_git_clone")
        os.makedirs(repo)

        def git(*args: str) -> None:
            subprocess.check_call(
                [
                    "git",
                    "-C",
                    repo,
                    "-c",
                    "user.name=tk-core tests",
                    "-c",
                    "user.email=tk-core-tests@example.com",
                    "-c",
                    "commit.gpgsign=false",
                    "-c",
                    "tag.gpgsign=false",
                    *args,
                ]
            )

        git("init", "-q")
        git("commit", "-q", "--allow-empty", "-m", "first")
        git("tag", "-a", "v1.2.2", "-m", "annotated tag")
        git("commit", "-q", "--allow-empty", "-m", "second")
        # Lightweight tag, like the ones releases use. --tags is required to
        # match it over the older annotated tag.
        git("tag", "v1.2.3")

        version = self._get_version(path=repo)
        self.assertRegex(version, r"^v1\.2\.3\+g[0-9a-f]{7,}$")

        git("commit", "-q", "--allow-empty", "-m", "third")
        git("commit", "-q", "--allow-empty", "-m", "fourth")

        version = self._get_version(path=repo)
        self.assertRegex(version, r"^v1\.2\.3\.post2\+g[0-9a-f]{7,}$")
        self.assertTrue(is_version_newer(version, "v1.2.3"))
        self.assertTrue(is_version_newer("v1.2.4", version))

        # The sha must match the clone's current commit.
        head = subprocess.check_output(
            ["git", "-C", repo, "rev-parse", "HEAD"], text=True
        ).strip()
        sha = re.search(r"\+g([0-9a-f]+)$", version).group(1)
        self.assertTrue(head.startswith(sha))
