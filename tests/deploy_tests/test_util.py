"""
Copyright (c) 2012 Shotgun Software, Inc
"""
import os
import datetime

from mock import Mock, patch

import tank
from tank import context
from tank import TankError
from tank_test.tank_test_base import *
from tank.template import TemplatePath
from tank.templatekey import SequenceKey



class TestVersionCompare(TankTestBase):
    
    def setUp(self):
        super(TestVersionCompare, self).setUp()

    def test_is_version_newer(self):        
        
        from tank.deploy.util import is_version_newer
        
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
        
        from tank.deploy.util import is_version_older
        
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
        