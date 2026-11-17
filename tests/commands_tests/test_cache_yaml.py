# Copyright (c) 2026 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Unit tests for the tank cache_yaml command.
"""

import json
import logging
import os
from unittest import mock

from tank.errors import TankError
from tank.util import yaml_cache
from tank.util.yaml_cache import CacheItem, _CachedStat
from tank_test.tank_test_base import TankTestBase, setUpModule  # noqa


class TestCacheYamlCommand(TankTestBase):
    """
    SG-46278 / PSIRT-3972: the yaml cache command must write a data-only JSON
    file (never a pickle) and must skip any item whose data would not survive
    a JSON round-trip unchanged, rather than silently corrupting it.
    """

    def setUp(self):
        super().setUp()
        self.setup_fixtures()

        # Items we inject into the global cache for the command to serialize.
        # Use paths under the config root so they look like real cache entries.
        config_root = self.tk.pipeline_configuration.get_path()
        self._safe_path = os.path.normpath(os.path.join(config_root, "_safe.yml"))
        self._unsafe_path = os.path.normpath(os.path.join(config_root, "_unsafe.yml"))

        # A JSON round-trip-safe payload.
        yaml_cache.g_yaml_cache._cache[self._safe_path] = CacheItem(
            self._safe_path, data={"engine": "tk-test"}, stat=_CachedStat(1.0, 10)
        )
        # JSON-serializable but NOT round-trip safe: an int mapping key would
        # silently come back as a string. The command must skip it.
        yaml_cache.g_yaml_cache._cache[self._unsafe_path] = CacheItem(
            self._unsafe_path, data={1: "int-key"}, stat=_CachedStat(1.0, 10)
        )
        self.addCleanup(self._remove_injected_items)

    def _remove_injected_items(self):
        for path in (self._safe_path, self._unsafe_path):
            yaml_cache.g_yaml_cache._cache.pop(path, None)

    def test_cache_yaml_writes_json_and_skips_unsafe(self):
        command = self.tk.get_command("cache_yaml")
        command.set_logger(logging.getLogger("test.cache_yaml"))
        command.execute({})

        cache_path = self.tk.pipeline_configuration.get_yaml_cache_location()
        self.assertTrue(cache_path.endswith("yaml_cache.json"))
        self.assertTrue(os.path.exists(cache_path))

        # The cache is data-only JSON (a list of dicts), never a pickle.
        with open(cache_path, "r", encoding="utf-8") as fh:
            items = json.load(fh)
        self.assertIsInstance(items, list)
        self.assertTrue(all(isinstance(item, dict) for item in items))

        paths = [item["path"] for item in items]
        # The round-trip-safe item is cached...
        self.assertIn(self._safe_path, paths)
        # ...and the unsafe (int-key) item is skipped, not corrupted.
        self.assertNotIn(self._unsafe_path, paths)

    def test_cache_yaml_raises_tankerror_on_write_failure(self):
        """
        A failure while writing the cache is surfaced as a TankError rather
        than an opaque low-level error.
        """
        command = self.tk.get_command("cache_yaml")
        command.set_logger(logging.getLogger("test.cache_yaml"))
        with mock.patch(
            "tank.commands.cache_yaml.json.dump",
            side_effect=OSError("simulated write failure"),
        ):
            with self.assertRaises(TankError):
                command.execute({})
