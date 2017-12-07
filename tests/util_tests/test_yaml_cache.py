# Copyright (c) 2015 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import copy

import sgtk
from sgtk.util.yaml_cache import YamlCache
from sgtk import TankError
from tank_vendor import yaml
from tank_test.tank_test_base import *

class TestYamlCache(TankTestBase):
    """
    Tests to ensure that the YamlCache behaves correctly
    """

    def __init__(self, *args, **kwargs):
        """
        Construction
        """
        TankTestBase.__init__(self, *args, **kwargs)

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
        yaml_path = os.path.join(self._data_root, "test_data.yml")

        test_data = [1, 
                     "two", 
                     {"three":"A", "four":[5,6,7], 8:{9:"nine", "ten":10}}, 
                     [11, "twelve"], 
                     {13:13, "fourteen":"fourteen"}
                     ]

        modified_test_data = copy.deepcopy(test_data)
        modified_test_data.append({15:[16, "seventeen"]})

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
        self.assertEquals(read_data, test_data)

        # 2. Ensure that the data returned is a copy of the cached data
        #

        # inspect the cache itself and make sure that the data returned is a copy 
        # of the internal cached data and not the internal cached data itself:
        self.assertEquals(len(yaml_cache._cache), 1)
        self.assertEquals(yaml_cache._cache.keys()[0], yaml_path)
        self.assertEquals(yaml_cache._cache.values()[0]["data"], read_data)
        cached_data_id = id(yaml_cache._cache.values()[0]["data"])
        self.assertNotEquals(cached_data_id, id(read_data))

        # 3. Check that the data doesn't get reloaded if it hasn't changed
        #

        # ask for the data again...
        read_data = yaml_cache.get(yaml_path)

        # ...and check that the cached data is exactly the same (has the same id):
        self.assertEquals(len(yaml_cache._cache), 1)
        new_cached_data_id = id(yaml_cache._cache.values()[0]["data"])
        self.assertEquals(cached_data_id, new_cached_data_id)

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
        self.assertEquals(read_data, modified_test_data)




