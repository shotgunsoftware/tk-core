# Copyright (c) 2025 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import json
import os
import sys
import tempfile
import unittest

from tank_test.tank_test_base import setUpModule  # noqa

from tank_vendor.adsk_auth import file_store


class FileStoreRoundTripTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.storage_dir = self._tmpdir.name

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_persist_and_get_access_token(self):
        file_store.persist_tokens(
            self.storage_dir, "myapp", "alice", {"access_token": "acc123"}
        )
        result = file_store.get_access_token(self.storage_dir, "myapp", "alice")
        self.assertEqual(result, "acc123")

    def test_persist_and_get_refresh_token(self):
        file_store.persist_tokens(
            self.storage_dir,
            "myapp",
            "alice",
            {"access_token": "acc123", "refresh_token": "ref456"},
        )
        result = file_store.get_refresh_token(self.storage_dir, "myapp", "alice")
        self.assertEqual(result, "ref456")

    def test_missing_file_returns_none(self):
        self.assertIsNone(
            file_store.get_access_token(self.storage_dir, "myapp", "nobody")
        )
        self.assertIsNone(
            file_store.get_refresh_token(self.storage_dir, "myapp", "nobody")
        )

    def test_missing_profile_returns_none(self):
        file_store.persist_tokens(
            self.storage_dir, "myapp", "alice", {"access_token": "acc123"}
        )
        self.assertIsNone(
            file_store.get_access_token(self.storage_dir, "myapp", "bob")
        )

    def test_delete_tokens_clears_entry(self):
        file_store.persist_tokens(
            self.storage_dir,
            "myapp",
            "alice",
            {"access_token": "acc123", "refresh_token": "ref456"},
        )
        file_store.delete_tokens(self.storage_dir, "myapp", "alice")
        self.assertIsNone(
            file_store.get_access_token(self.storage_dir, "myapp", "alice")
        )
        self.assertIsNone(
            file_store.get_refresh_token(self.storage_dir, "myapp", "alice")
        )

    def test_delete_tokens_on_missing_file_is_silent(self):
        # Should not raise when no tokens exist yet.
        file_store.delete_tokens(self.storage_dir, "myapp", "alice")

    def test_delete_tokens_only_removes_target_profile(self):
        file_store.persist_tokens(
            self.storage_dir, "myapp", "alice", {"access_token": "acc_a"}
        )
        file_store.persist_tokens(
            self.storage_dir, "myapp", "bob", {"access_token": "acc_b"}
        )
        file_store.delete_tokens(self.storage_dir, "myapp", "alice")
        self.assertIsNone(
            file_store.get_access_token(self.storage_dir, "myapp", "alice")
        )
        self.assertEqual(
            file_store.get_access_token(self.storage_dir, "myapp", "bob"), "acc_b"
        )

    def test_persist_overwrites_existing_token(self):
        file_store.persist_tokens(
            self.storage_dir, "myapp", "alice", {"access_token": "old"}
        )
        file_store.persist_tokens(
            self.storage_dir, "myapp", "alice", {"access_token": "new"}
        )
        self.assertEqual(
            file_store.get_access_token(self.storage_dir, "myapp", "alice"), "new"
        )

    def test_storage_dir_created_on_first_write(self):
        nested = os.path.join(self.storage_dir, "a", "b", "c")
        file_store.persist_tokens(nested, "myapp", "alice", {"access_token": "t"})
        self.assertTrue(os.path.isdir(nested))

    @unittest.skipIf(sys.platform == "win32", "POSIX permissions only")
    def test_file_permissions_are_restrictive(self):
        file_store.persist_tokens(
            self.storage_dir, "myapp", "alice", {"access_token": "t"}
        )
        path = os.path.join(self.storage_dir, "adsk_flow_tokens.json")
        mode = oct(os.stat(path).st_mode & 0o777)
        self.assertEqual(mode, oct(0o600))

    def test_token_file_is_valid_json(self):
        file_store.persist_tokens(
            self.storage_dir,
            "myapp",
            "alice",
            {"access_token": "acc", "refresh_token": "ref"},
        )
        path = os.path.join(self.storage_dir, "adsk_flow_tokens.json")
        with open(path) as fh:
            data = json.load(fh)
        self.assertIn("adsk.flow.myapp.access_token", data)
        self.assertIn("adsk.flow.myapp.refresh_token", data)


class GetUserProfileTests(unittest.TestCase):
    def test_returns_provided_profile(self):
        self.assertEqual(file_store.get_user_profile("alice"), "alice")

    def test_defaults_to_os_user(self):
        import getpass

        self.assertEqual(file_store.get_user_profile(None), getpass.getuser())
