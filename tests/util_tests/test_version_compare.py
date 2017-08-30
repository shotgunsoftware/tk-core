# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import datetime

from mock import Mock, patch

import tank
from tank import context
from tank import TankError
from tank_test.tank_test_base import *
from tank.template import TemplatePath
from tank.templatekey import SequenceKey
from tank.util.version import Version as Version


class TestVersionCompare(TankTestBase):
    
    def setUp(self):
        super(TestVersionCompare, self).setUp()

    def test_is_version_newer(self):        
        
        from tank.util.version import is_version_newer
        
        self.assertTrue( is_version_newer("1.2.3", "1.0.0") )
        self.assertTrue( is_version_newer("v1.2.3", "v1.0.0") )
        self.assertTrue( is_version_newer("v1.2.3", "1.0.0") )
        
        self.assertTrue( is_version_newer("v1.200.3", "v1.12.345") )
        
        self.assertTrue( is_version_newer("HEaD", "v1.12.345") )
        self.assertTrue( is_version_newer("MAsTER", "v1.12.345") )
        
        self.assertTrue( is_version_newer("HEaD", "1.12.345") )
        self.assertTrue( is_version_newer("MAsTER", "1.12.345") )

        self.assertFalse( is_version_newer("v0.12.3", "HEaD") )
        self.assertFalse( is_version_newer("v0.12.3", "MAsTER") )
        
        self.assertFalse( is_version_newer("0.12.3", "HEaD") )
        self.assertFalse( is_version_newer("0.12.3", "MAsTER") )

        self.assertFalse( is_version_newer("v0.12.3", "1.2.3") )
        self.assertFalse( is_version_newer("v0.12.3", "0.12.4") )
        
        self.assertFalse( is_version_newer("1.0.0", "1.0.0") )

        
    def test_is_version_older(self):        
        
        from tank.util.version import is_version_older
        
        self.assertFalse( is_version_older("1.2.3", "1.0.0") )
        self.assertFalse( is_version_older("v1.2.3", "v1.0.0") )
        self.assertFalse( is_version_older("v1.2.3", "1.0.0") )
        
        self.assertFalse( is_version_older("v1.200.3", "v1.12.345") )
        
        self.assertFalse( is_version_older("HEaD", "v1.12.345") )
        self.assertFalse( is_version_older("MAsTER", "v1.12.345") )
        
        self.assertFalse( is_version_older("HEaD", "1.12.345") )
        self.assertFalse( is_version_older("MAsTER", "1.12.345") )

        self.assertTrue( is_version_older("v0.12.3", "HEaD") )
        self.assertTrue( is_version_older("v0.12.3", "MAsTER") )
        
        self.assertTrue( is_version_older("0.12.3", "HEaD") )
        self.assertTrue( is_version_older("0.12.3", "MAsTER") )

        self.assertTrue( is_version_older("v0.12.3", "1.2.3") )
        self.assertTrue( is_version_older("v0.12.3", "0.12.4") )
        
        self.assertFalse( is_version_older("1.0.0", "1.0.0") )


class TestVersion(TankTestBase):

    def test_init_with_misc_test_strings(self):
        """ Simply testing for unhandled exception when supplying different kind of strings."""
        Version("My Super App 2.1")
        Version("My Super App 2.")
        Version("My Super App 2")
        Version("My Super App")
        Version("")
        Version(None)
        Version("2.3.4.5.")
        Version("i2348y7982y4")
        Version("&?%*?&%$?&$&%?$&?%$&?")
        Version(" .. . . . . ")
        Version("      \n\t\r   ")
        Version("")
        Version(None)

    def test_init_with_single_word_app_name(self):
        """ Simply testing various strings and making sure we're not causing unexpected exception."""

        obj = Version("Maya 2017")
        self.assertEqual(obj.app_name, "Maya")
        self.assertEqual(repr(obj), "2017")
        self.assertEqual(obj.major, 2017)
        self.assertEqual(obj.minor, -1)

        obj = Version("Maya   2017")
        self.assertEqual(obj.app_name, "Maya")
        self.assertEqual(repr(obj), "2017")
        self.assertEqual(obj.major, 2017)
        self.assertEqual(obj.minor, -1)

        obj = Version(" Maya  2017.2")
        self.assertEqual(obj.app_name, "Maya")
        self.assertEqual(repr(obj), "2017.2")
        self.assertEqual(obj.major, 2017)
        self.assertEqual(obj.minor, 2)

    def test_init_with_app_name_and_version_numbers(self):

        obj = Version("My Super App 2.17.300b")
        self.assertEqual(obj.app_name, "My Super App")
        self.assertEqual(repr(obj), "2.17.300b")
        self.assertEqual(obj.major, 2)
        self.assertEqual(obj.minor, 17)

        # Check that trailing '.' is removed
        obj = Version("My Super App 2.")
        self.assertEqual(obj.app_name, "My Super App")
        self.assertEqual(repr(obj), "2")
        self.assertEqual(obj.major, 2)
        self.assertEqual(obj.minor, -1)

        obj = Version("My Super App 2")
        self.assertEqual(obj.app_name, "My Super App")
        self.assertEqual(repr(obj), "2")
        self.assertEqual(obj.major, 2)
        self.assertEqual(obj.minor, -1)

        obj = Version("My Super App")
        self.assertEqual(obj.app_name, "My Super App")
        self.assertEqual(repr(obj), "None")
        self.assertEqual(obj.major, -1)
        self.assertEqual(obj.minor, -1)

    def test_init_without_app_names(self):

        obj = Version("2.17.300b")
        self.assertEqual(obj.app_name, None)
        self.assertEqual(repr(obj), "2.17.300b")
        self.assertEqual(obj.major, 2)
        self.assertEqual(obj.minor, 17)

    def test_init_with_none(self):

        obj = Version(None)
        self.assertEqual(obj.app_name, None)
        self.assertEqual(repr(obj), "None")
        self.assertEqual(obj.major, -1)
        self.assertEqual(obj.minor, -1)

    def test_init_with_empty_strimg(self):

        obj = Version("")
        self.assertEqual(obj.app_name, None)
        self.assertEqual(repr(obj), "None")
        self.assertEqual(obj.major, -1)
        self.assertEqual(obj.minor, -1)


