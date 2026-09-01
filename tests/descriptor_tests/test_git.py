# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os

import sgtk
from sgtk.descriptor import Descriptor
from tank_test.tank_test_base import (
    ShotgunTestBase,
    setUpModule,  # noqa
    skip_if_git_missing,
)


class TestGitIODescriptor(ShotgunTestBase):
    """
    Testing the Shotgun deploy main API methods
    """

    def setUp(self):
        """
        Sets up the next test's environment.
        """
        ShotgunTestBase.setUp(self)

        # bare repo cloned from our official default config
        # multiple branches and tags
        self.git_repo_uri = os.path.join(
            self.fixtures_root, "misc", "tk-config-default.git"
        )

        # Bare-minimum repo with both annotated and lightweight tags
        self.git_tag_repo_uri = os.path.join(
            self.fixtures_root, "misc", "tag-test-repo.git"
        )

        self.bundle_cache = os.path.join(self.project_root, "bundle_cache")

    def _create_desc(self, location, resolve_latest=False, desc_type=Descriptor.CONFIG):
        """
        Helper method around create_descriptor
        """
        return sgtk.descriptor.create_descriptor(
            self.mockgun,
            desc_type,
            location,
            bundle_cache_root_override=self.bundle_cache,
            resolve_latest=resolve_latest,
        )

    @skip_if_git_missing
    def test_latest(self):

        location_dict = {
            "type": "git_branch",
            "path": self.git_repo_uri,
            "branch": "master",
        }

        desc = self._create_desc(location_dict, True)
        self.assertEqual(desc.version, "30c293f29a50b1e58d2580522656695825523dba")

        location_dict = {"type": "git", "path": self.git_repo_uri}

        desc = self._create_desc(location_dict, True)
        self.assertEqual(desc.version, "v0.16.1")

    @skip_if_git_missing
    def test_tag(self):

        location_dict = {"type": "git", "path": self.git_repo_uri, "version": "v0.16.0"}

        desc = self._create_desc(location_dict)

        self.assertIsNone(desc.find_latest_cached_version())

        self.assertEqual(desc.version, "v0.16.0")
        self.assertEqual(desc.get_path(), None)

        desc.ensure_local()

        self.assertEqual(desc.find_latest_cached_version().version, "v0.16.0")

        self.assertIsNone(desc.find_latest_cached_version("v0.18.x"))

        self.assertEqual(
            desc.get_path(),
            os.path.join(self.bundle_cache, "git", "tk-config-default.git", "v0.16.0"),
        )

        latest_desc = desc.find_latest_version()

        self.assertEqual(latest_desc.version, "v0.16.1")
        self.assertEqual(latest_desc.get_path(), None)

        latest_desc.ensure_local()

        self.assertEqual(latest_desc.find_latest_cached_version().version, "v0.16.1")

        self.assertEqual(
            latest_desc.find_latest_cached_version("v0.16.x").version, "v0.16.1"
        )

        self.assertEqual(
            latest_desc.get_path(),
            os.path.join(self.bundle_cache, "git", "tk-config-default.git", "v0.16.1"),
        )

        latest_desc = desc.find_latest_version("v0.15.x")

        self.assertEqual(latest_desc.version, "v0.15.11")
        self.assertEqual(latest_desc.get_path(), None)

        latest_desc.ensure_local()

        self.assertEqual(
            latest_desc.get_path(),
            os.path.join(self.bundle_cache, "git", "tk-config-default.git", "v0.15.11"),
        )

        # test that the copy method copies the .git folder
        copy_target = os.path.join(self.project_root, "test_copy_target")
        latest_desc.copy(copy_target)
        self.assertTrue(os.path.exists(os.path.join(copy_target, ".git")))

    @skip_if_git_missing
    def test_branch_shorthash(self):

        location_dict = {
            "type": "git_branch",
            "path": self.git_repo_uri,
            "branch": "master",
            "version": "3d3de30",
        }

        desc = self._create_desc(location_dict)

        self.assertEqual(desc.get_path(), None)

        desc.ensure_local()

        self.assertEqual(
            desc.get_path(),
            os.path.join(
                self.bundle_cache, "gitbranch", "tk-config-default.git", "3d3de30"
            ),
        )

    @skip_if_git_missing
    def test_branch(self):

        location_dict = {
            "type": "git_branch",
            "path": self.git_repo_uri,
            "branch": "master",
            "version": "3e6a681234a02237e8bf35861b6439e7df73e05d",
        }

        desc = self._create_desc(location_dict)

        self.assertEqual(desc.get_path(), None)

        desc.ensure_local()

        self.assertEqual(
            desc.get_path(),
            os.path.join(
                self.bundle_cache, "gitbranch", "tk-config-default.git", "3e6a681"
            ),
        )

        latest_desc = desc.find_latest_version()

        self.assertEqual(
            latest_desc.version, "30c293f29a50b1e58d2580522656695825523dba"
        )
        self.assertEqual(latest_desc.get_path(), None)

        latest_desc.ensure_local()

        self.assertEqual(
            latest_desc.get_path(),
            os.path.join(
                self.bundle_cache, "gitbranch", "tk-config-default.git", "30c293f"
            ),
        )

        location_dict = {
            "type": "git_branch",
            "path": self.git_repo_uri,
            "branch": "018_test",
            "version": "9035355e4e578dd874536ba333fedda0177d97a3",
        }

        desc = self._create_desc(location_dict)

        self.assertEqual(desc.get_path(), None)

        desc.ensure_local()

        self.assertEqual(
            desc.get_path(),
            os.path.join(
                self.bundle_cache, "gitbranch", "tk-config-default.git", "9035355"
            ),
        )

        latest_desc = desc.find_latest_version()

        self.assertEqual(
            latest_desc.version, "7fa75a749c1dfdbd9ad93ee3497c7eaa8e1a488d"
        )
        self.assertEqual(latest_desc.get_path(), None)

        latest_desc.ensure_local()

        self.assertEqual(
            latest_desc.get_path(),
            os.path.join(
                self.bundle_cache, "gitbranch", "tk-config-default.git", "7fa75a7"
            ),
        )

        # test that the copy method copies the .git folder
        copy_target = os.path.join(self.project_root, "test_copy_target")
        latest_desc.copy(copy_target)
        self.assertTrue(os.path.exists(os.path.join(copy_target, ".git")))

    @skip_if_git_missing
    def test_fail(self):

        location_dict = {
            "type": "git_branch",
            "path": self.git_repo_uri,
            "branch": "bad",
        }

        with self.assertRaises(sgtk.descriptor.errors.TankDescriptorError):
            self._create_desc(location_dict, True)

    def test_credential_sanitization(self):
        """
        Test that credentials in git URLs are properly sanitized in string representations.
        """
        from sgtk.descriptor.io_descriptor.git import _sanitize_url

        # Test GitHub PAT token
        url_with_pat = (
            "https://ghp_1234567890abcdefghijklmnopqrstuv@github.com/org/repo.git"
        )
        sanitized = _sanitize_url(url_with_pat)
        self.assertEqual(sanitized, "https://***@github.com/org/repo.git")
        self.assertNotIn("ghp_", sanitized)

        # Test username:password format
        url_with_userpass = "https://user:password@example.com/repo.git"
        sanitized = _sanitize_url(url_with_userpass)
        self.assertEqual(sanitized, "https://***@example.com/repo.git")
        self.assertNotIn("user", sanitized)
        self.assertNotIn("password", sanitized)

        # Test URL with port
        url_with_port = "https://token@github.enterprise.com:8443/org/repo.git"
        sanitized = _sanitize_url(url_with_port)
        self.assertEqual(
            sanitized, "https://***@github.enterprise.com:8443/org/repo.git"
        )
        self.assertNotIn("token", sanitized)

        # Test SSH URL (should not be modified)
        ssh_url = "git@github.com:org/repo.git"
        sanitized = _sanitize_url(ssh_url)
        self.assertEqual(sanitized, ssh_url)

        # Test local path (should not be modified)
        local_path = "/path/to/local/repo.git"
        sanitized = _sanitize_url(local_path)
        self.assertEqual(sanitized, local_path)

        # Test URL without credentials (should not be modified)
        url_no_creds = "https://github.com/org/repo.git"
        sanitized = _sanitize_url(url_no_creds)
        self.assertEqual(sanitized, url_no_creds)

        # Test None value
        sanitized = _sanitize_url(None)
        self.assertIsNone(sanitized)

        # Test empty string
        sanitized = _sanitize_url("")
        self.assertEqual(sanitized, "")

    @skip_if_git_missing
    def test_descriptor_repr_sanitization(self):
        """
        Test that descriptor __repr__ and __str__ methods sanitize credentials.
        """
        # Test git_branch descriptor with PAT token
        location_dict_with_token = {
            "type": "git_branch",
            "path": "https://ghp_secret123@github.com/org/repo.git",
            "branch": "master",
            "version": "abc1234",
        }

        desc = self._create_desc(location_dict_with_token)

        # Check that repr doesn't contain the token
        desc_repr = repr(desc)
        self.assertNotIn("ghp_secret123", desc_repr)
        # The repr may URL-encode *** as %2A%2A%2A
        self.assertTrue(
            "***" in desc_repr or "%2A%2A%2A" in desc_repr,
            "Sanitization marker not found in repr",
        )

        # Check that str doesn't contain the token
        # Note: str(desc) uses Descriptor.__str__() which returns "system_name version"
        # and doesn't include the URL, so we just verify no credentials leak
        desc_str = str(desc)
        self.assertNotIn("ghp_secret123", desc_str)

        # Check that the IO descriptor's str representation sanitizes credentials
        io_desc_str = str(desc._io_descriptor)
        self.assertNotIn("ghp_secret123", io_desc_str)
        self.assertIn("***", io_desc_str)

        # Test git descriptor (tag-based) with credentials
        location_dict_git = {
            "type": "git",
            "path": "https://user:pass@example.com/repo.git",
            "version": "v1.0.0",
        }

        desc_git = self._create_desc(location_dict_git)

        # Check that repr doesn't contain credentials
        desc_repr = repr(desc_git)
        self.assertNotIn("user", desc_repr)
        # Note: "pass" might appear in "sgtk:descriptor:git?pass=..." so we check more carefully
        # In the sanitized version, the credentials should be replaced with ***
        self.assertTrue(
            "***" in desc_repr or "%2A%2A%2A" in desc_repr,
            "Sanitization marker not found in repr",
        )

        # Check that the IO descriptor's str representation sanitizes credentials
        io_desc_str_git = str(desc_git._io_descriptor)
        self.assertNotIn("user", io_desc_str_git)
        self.assertNotIn("pass", io_desc_str_git)
        self.assertIn("***", io_desc_str_git)

    def test_exception_sanitization(self):
        """
        Test that SubprocessCalledProcessError exceptions are sanitized.
        """
        from sgtk.descriptor.io_descriptor.git import (
            _sanitize_command,
            _sanitize_exception,
        )
        from tank.util.process import SubprocessCalledProcessError

        # Test sanitization of command list
        cmd_list = [
            "git",
            "ls-remote",
            "https://ghp_secret123@github.com/org/repo.git",
            "master",
        ]
        sanitized_list = _sanitize_command(cmd_list)
        self.assertNotIn("ghp_secret123", str(sanitized_list))
        self.assertIn("***", str(sanitized_list))

        # Test sanitization of command string
        cmd_string = 'git clone "https://user:pass@example.com/repo.git" /tmp/repo'
        sanitized_string = _sanitize_command(cmd_string)
        self.assertNotIn("user", sanitized_string)
        self.assertNotIn("pass", sanitized_string)
        self.assertIn("***", sanitized_string)

        # Test sanitization of SubprocessCalledProcessError with list command
        exc = SubprocessCalledProcessError(128, cmd_list, output=b"some error")
        sanitized_exc = _sanitize_exception(exc)
        exc_str = str(sanitized_exc)
        self.assertNotIn("ghp_secret123", exc_str)
        self.assertIn("***", exc_str)
        self.assertEqual(sanitized_exc.returncode, 128)

        # Test sanitization of SubprocessCalledProcessError with string command
        exc_str_cmd = SubprocessCalledProcessError(128, cmd_string, output=b"error")
        sanitized_exc_str = _sanitize_exception(exc_str_cmd)
        exc_str_repr = str(sanitized_exc_str)
        self.assertNotIn("user", exc_str_repr)
        self.assertNotIn("pass", exc_str_repr)
        self.assertIn("***", exc_str_repr)

    def test_exception_chain_sanitization(self):
        """
        Test that exception __cause__ and __context__ are sanitized to prevent
        credential leaks in exception chains.
        """
        from sgtk.descriptor.io_descriptor.git import _sanitize_exception
        from tank.util.process import SubprocessCalledProcessError

        # Create an exception with credentials in the command
        cmd_with_creds = [
            "git",
            "ls-remote",
            "https://ghp_secret123@github.com/org/repo.git",
            "master",
        ]
        original_exc = SubprocessCalledProcessError(128, cmd_with_creds)

        # Sanitize it
        sanitized_exc = _sanitize_exception(original_exc)

        # Verify the sanitized exception doesn't contain credentials
        self.assertNotIn("ghp_secret123", str(sanitized_exc))
        self.assertIn("***", str(sanitized_exc))

        # Verify __cause__ is sanitized (if set)
        if sanitized_exc.__cause__ is not None:
            self.assertNotIn("ghp_secret123", str(sanitized_exc.__cause__))

        # Verify __context__ is sanitized (if set)
        if sanitized_exc.__context__ is not None:
            self.assertNotIn("ghp_secret123", str(sanitized_exc.__context__))

    @skip_if_git_missing
    def test_git_branch_error_handling_sanitizes_credentials(self):
        """
        Integration test: Verify that when git_branch descriptor fails with
        credentials in the URL, the error and exception chain are sanitized.
        """
        import logging
        from io import StringIO

        # Create a descriptor with credentials that will fail
        location_dict = {
            "type": "git_branch",
            "path": "https://ghp_secret123@github.com/fake/nonexistent.git",
            "branch": "master",
            "version": "abc1234",
        }

        # Set up log capture to check what gets logged
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setLevel(logging.DEBUG)
        logger = logging.getLogger("sgtk.core.descriptor.io_descriptor.git_branch")
        original_level = logger.level
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)

        try:
            desc = self._create_desc(location_dict)

            # Try to check if it's the latest commit - this should fail
            # because the repo doesn't exist
            try:
                desc._is_latest_commit("abc1234", "master")
                self.fail("Expected TankGitError to be raised")
            except Exception as e:
                # Verify the exception message doesn't contain credentials
                exc_str = str(e)
                self.assertNotIn("ghp_secret123", exc_str)

                # Check the entire exception chain
                current_exc = e
                while current_exc is not None:
                    self.assertNotIn(
                        "ghp_secret123",
                        str(current_exc),
                        "Credentials found in exception chain: %s" % type(current_exc),
                    )
                    # Check both __cause__ and __context__
                    if current_exc.__cause__ is not None:
                        current_exc = current_exc.__cause__
                    elif current_exc.__context__ is not None:
                        current_exc = current_exc.__context__
                    else:
                        break

            # Check that nothing was logged with credentials
            log_contents = log_stream.getvalue()
            self.assertNotIn(
                "ghp_secret123",
                log_contents,
                "Credentials found in log output:\n%s" % log_contents,
            )

        finally:
            logger.removeHandler(handler)
            logger.setLevel(original_level)

    def test_git_tag_exception_sanitization(self):
        """
        Test that git_tag.py properly sanitizes exceptions in error handlers.
        """
        from sgtk.descriptor.io_descriptor.git_tag import IODescriptorGitTag
        from tank.descriptor.errors import TankDescriptorError

        # Create a git tag descriptor with credentials
        location_dict = {
            "type": "git",
            "path": "https://token123@github.com/fake/nonexistent.git",
            "version": "v1.0.0",
        }

        desc = IODescriptorGitTag(location_dict, None, None)

        # Mock _tmp_clone_then_execute_git_commands to raise an error
        from unittest.mock import patch

        from tank.util.process import SubprocessCalledProcessError

        cmd_with_creds = [
            "git",
            "clone",
            "https://token123@github.com/fake/nonexistent.git",
        ]
        mock_exc = SubprocessCalledProcessError(128, cmd_with_creds)

        with patch.object(
            desc, "_tmp_clone_then_execute_git_commands", side_effect=mock_exc
        ):
            try:
                desc._fetch_tags()
                self.fail("Expected TankDescriptorError to be raised")
            except TankDescriptorError as e:
                # Verify credentials are not in the error message
                error_msg = str(e)
                self.assertNotIn("token123", error_msg)
                self.assertIn("***", error_msg)
