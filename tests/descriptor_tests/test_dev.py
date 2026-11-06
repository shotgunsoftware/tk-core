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
import unittest.mock

import sgtk
from tank.util import process
from tank_test import tank_test_base
from tank_test.tank_test_base import setUpModule  # noqa: F401 - run by unittest
from tank_vendor.packaging import version

CHECK_OUTPUT = "tank.descriptor.io_descriptor.git._check_output"


class TestDevDescriptorVersion(tank_test_base.ShotgunTestBase):
    """
    Tests the version reported by dev descriptors pointing at a git clone.

    The mocked tests hardcode our expectations of ``git describe --tags --long``
    output, so a change in how it is parsed is caught without needing git.
    """

    def setUp(self) -> None:
        super().setUp()
        self.dev_path = os.path.join(self.tank_temp, "dev_bundle")
        # Make the path look like the root of a git clone.
        os.makedirs(os.path.join(self.dev_path, ".git"), exist_ok=True)

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
        with unittest.mock.patch(CHECK_OUTPUT) as check_output_mock:
            self.assertEqual(self._get_version(version="v1.0.0"), "v1.0.0")
        check_output_mock.assert_not_called()

    def test_not_a_clone_root(self) -> None:
        """
        Tests that git is not run when the path is not the root of a git clone.
        """
        path = os.path.join(self.tank_temp, "not_a_clone_root")
        os.makedirs(path, exist_ok=True)
        with unittest.mock.patch(CHECK_OUTPUT) as check_output_mock:
            self.assertEqual(self._get_version(path=path), "Undefined")
        check_output_mock.assert_not_called()

    def test_git_describe_command(self) -> None:
        """
        Tests the git command run to describe the clone.
        """
        with unittest.mock.patch(
            CHECK_OUTPUT, return_value="v1.2.3-0-g1a2b3c4\n"
        ) as check_output_mock:
            self._get_version()
        check_output_mock.assert_called_once_with(
            [
                "git",
                "-C",
                self.dev_path,
                "describe",
                "--tags",
                "--long",
                "--dirty=.dirty",
            ]
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
            # Uncommitted changes to tracked files.
            ("v1.2.3-0-g1a2b3c4.dirty\n", "v1.2.3+g1a2b3c4.dirty"),
            ("v1.2.3-5-g1a2b3c4.dirty\n", "v1.2.3.post5+g1a2b3c4.dirty"),
        ]
        for describe_output, expected in cases:
            with self.subTest(describe_output=describe_output):
                with unittest.mock.patch(CHECK_OUTPUT, return_value=describe_output):
                    dev_version = self._get_version()
                self.assertEqual(dev_version, expected)
                # Must be a valid PEP 440 version.
                version.Version(dev_version)

    def test_version_ordering(self) -> None:
        """
        Tests that converted versions sort correctly against released versions
        using the sgtk version system.
        """

        def describe(output: str) -> str:
            with unittest.mock.patch(CHECK_OUTPUT, return_value=output):
                return self._get_version()

        ordered = [
            "v1.2.3",
            describe("v1.2.3-0-g1a2b3c4"),
            describe("v1.2.3-5-g1a2b3c4"),
            describe("v1.2.3-5-g1a2b3c4.dirty"),
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
                    self.assertTrue(sgtk.util.is_version_newer(newer, older))
                    self.assertFalse(sgtk.util.is_version_newer(older, newer))

    def test_git_failures_fall_back(self) -> None:
        """
        Tests that the undefined version is returned when git cannot help.
        """
        cases = {
            "not a git clone or no tags": process.SubprocessCalledProcessError(
                128, "git describe", "fatal: No names found"
            ),
            "git not installed": FileNotFoundError("git"),
        }
        for name, error in cases.items():
            with self.subTest(name):
                with unittest.mock.patch(CHECK_OUTPUT, side_effect=error):
                    self.assertEqual(self._get_version(), "Undefined")

        for output in (
            "",
            "\n",
            "unexpected-output",
            # Tags that do not produce a valid PEP 440 version.
            "release-1.2.3-0-g1a2b3c4\n",
            "v1.2.3.post1-5-g1a2b3c4\n",
        ):
            with self.subTest(output=output):
                with unittest.mock.patch(CHECK_OUTPUT, return_value=output):
                    self.assertEqual(self._get_version(), "Undefined")

    @tank_test_base.skip_if_git_missing
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
        tracked_file = os.path.join(repo, "info.yml")
        with open(tracked_file, "w") as fh:
            fh.write("version: HEAD\n")
        git("add", "info.yml")
        git("commit", "-q", "-m", "first")
        git("tag", "-a", "v1.2.2", "-m", "annotated tag")
        git("commit", "-q", "--allow-empty", "-m", "second")
        # Lightweight tag, like the ones releases use. --tags is required to
        # match it over the older annotated tag.
        git("tag", "v1.2.3")

        dev_version = self._get_version(path=repo)
        self.assertRegex(dev_version, r"^v1\.2\.3\+g[0-9a-f]{7,}$")

        git("commit", "-q", "--allow-empty", "-m", "third")
        git("commit", "-q", "--allow-empty", "-m", "fourth")

        dev_version = self._get_version(path=repo)
        self.assertRegex(dev_version, r"^v1\.2\.3\.post2\+g[0-9a-f]{7,}$")
        self.assertTrue(sgtk.util.is_version_newer(dev_version, "v1.2.3"))
        self.assertTrue(sgtk.util.is_version_newer("v1.2.4", dev_version))

        # The sha must match the clone's current commit.
        head = subprocess.check_output(
            ["git", "-C", repo, "rev-parse", "HEAD"], text=True
        ).strip()
        sha = re.search(r"\+g([0-9a-f]+)$", dev_version).group(1)
        self.assertTrue(head.startswith(sha))

        # Uncommitted changes to a tracked file mark the version as dirty.
        with open(tracked_file, "a") as fh:
            fh.write("# local change\n")
        dirty_version = self._get_version(path=repo)
        self.assertEqual(dirty_version, f"{dev_version}.dirty")
        version.Version(dirty_version)

        # A folder nested in the clone must not report the clone's version.
        nested = os.path.join(repo, "bundles", "my_app")
        os.makedirs(nested)
        self.assertEqual(self._get_version(path=nested), "Undefined")
