# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import copy
import datetime
import json
import os

from sgtk import TankError
from sgtk.util.yaml_cache import CacheItem, YamlCache, is_round_trip_safe
from tank_test.tank_test_base import (
    ShotgunTestBase,
    setUpModule,  # noqa
)
from tank_vendor import yaml


class TestYamlCache(ShotgunTestBase):
    """
    Tests to ensure that the YamlCache behaves correctly
    """

    def __init__(self, *args, **kwargs):
        """
        Construction
        """
        ShotgunTestBase.__init__(self, *args, **kwargs)

        # data root for all test data:
        self._data_root = os.path.join(self.fixtures_root, "misc", "yaml_cache")

    def test_empty_yml_return(self):
        """
        Tests that getting the contents of an empty yml file via the cache
        results in a None.
        """
        yaml_path = os.path.join(self._data_root, "empty.yml")
        yaml_cache = YamlCache()
        self.assertIsNone(yaml_cache.get(yaml_path))

    def test_get_incorrect_path(self):
        """
        Test that an error is correctly raised when the yaml cache is asked
        for data from an incorrect path
        """
        yaml_path = os.path.join(self._data_root, "incorrect_path.yml")

        yaml_cache = YamlCache()
        self.assertRaises(TankError, yaml_cache.get, yaml_path)

    def test_get_valid_path(self):
        """
        Test that the correct data is retrieved when a valid path is
        provided to YamlCache.get().

        Also ensure that the data returned from the cache is a copy of the
        cached data (to ensure it is clean and hasn't been accidentally
        overrwritten by the calling code) and that the cache correctly reloads
        the data from the file when it has been modified.
        """
        yaml_path = os.path.join(self.tank_temp, "test_data.yml")

        test_data = [
            1,
            "two",
            {"three": "A", "four": [5, 6, 7], 8: {9: "nine", "ten": 10}},
            [11, "twelve"],
            {13: 13, "fourteen": "fourteen"},
        ]

        modified_test_data = copy.deepcopy(test_data)
        modified_test_data.append({15: [16, "seventeen"]})

        # 1. Check that the cache loads the data correctly
        #

        # write out the test data:
        yaml_file = open(yaml_path, "w")
        try:
            yaml_file.write(yaml.dump(test_data))
        finally:
            yaml_file.close()

        # create a yaml cache instance and get the data from the file:
        yaml_cache = YamlCache()
        read_data = yaml_cache.get(yaml_path)

        # check the read data matches the input data:
        self.assertEqual(read_data, test_data)

        # 2. Ensure that the data returned is a copy of the cached data
        #

        # inspect the cache itself and make sure that the data returned is a copy
        # of the internal cached data and not the internal cached data itself:
        self.assertEqual(len(yaml_cache._cache), 1)
        self.assertEqual(list(yaml_cache._cache.keys())[0], yaml_path)
        self.assertEqual(list(yaml_cache._cache.values())[0]["data"], read_data)
        cached_data_id = id(list(yaml_cache._cache.values())[0]["data"])
        self.assertNotEqual(cached_data_id, id(read_data))

        # 3. Check that the data doesn't get reloaded if it hasn't changed
        #

        # ask for the data again...
        read_data = yaml_cache.get(yaml_path)

        # ...and check that the cached data is exactly the same (has the same id):
        self.assertEqual(len(yaml_cache._cache), 1)
        new_cached_data_id = id(list(yaml_cache._cache.values())[0]["data"])
        self.assertEqual(cached_data_id, new_cached_data_id)

        # 4. Check that the data does get reloaded if it has changed:
        #

        # update the data in the file:
        yaml_file = open(yaml_path, "w")
        try:
            yaml_file.write(yaml.dump(modified_test_data))
        finally:
            yaml_file.close()

        # ask for the data again...
        read_data = yaml_cache.get(yaml_path)

        # ...and check that the data in the cache has been updated:
        self.assertEqual(read_data, modified_test_data)

    def test_is_round_trip_safe(self):
        """
        SG-46278: only data that survives a JSON round-trip unchanged may be
        persisted in the (data-only) yaml cache; everything else must be
        reported as unsafe so it is read live from disk instead.
        """
        self.assertTrue(is_round_trip_safe({"a": 1, "b": [1, 2, "three"], "c": None}))
        self.assertTrue(is_round_trip_safe([1, "two", {"k": "v"}]))
        # A non-string mapping key would silently become a string through JSON.
        self.assertFalse(is_round_trip_safe({8: "eight"}))
        # datetimes and bytes are not JSON-serializable at all.
        self.assertFalse(is_round_trip_safe({"when": datetime.datetime(2020, 1, 1)}))
        self.assertFalse(is_round_trip_safe({"blob": b"bytes"}))

    def test_cache_item_to_from_dict_roundtrip(self):
        """
        SG-46278: CacheItem.to_dict/from_dict preserve the path, file stat and
        data as plain data (no pickling), and the reconstructed item compares
        equal to the original for cache-merge purposes without touching disk.
        """
        yaml_path = os.path.join(self.tank_temp, "roundtrip.yml")
        with open(yaml_path, "w") as fh:
            fh.write(yaml.dump({"a": 1, "list": [1, 2, 3]}))

        original = CacheItem(yaml_path, data={"a": 1, "list": [1, 2, 3]})
        item_dict = original.to_dict()

        # to_dict is pure, JSON-serializable data.
        self.assertEqual(set(item_dict.keys()), {"path", "mtime", "size", "data"})
        json.dumps(item_dict)

        restored = CacheItem.from_dict(item_dict)
        self.assertEqual(restored.path, original.path)
        self.assertEqual(restored.data, original.data)
        self.assertEqual(restored.stat.st_mtime, original.stat.st_mtime)
        self.assertEqual(restored.stat.st_size, original.stat.st_size)
        # The reconstructed item must be usable by the cache comparison logic
        # (equality and newer/size checks) without re-stat'ing the file.
        self.assertEqual(restored, original)
        self.assertFalse(original.given_item_newer(restored))
