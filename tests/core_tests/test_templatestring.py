# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Tests of class TemplateString
"""

import os

from tank_test.tank_test_base import ShotgunTestBase, setUpModule  # noqa

from tank.errors import TankError
from tank.template import TemplateString
from tank.templatekey import StringKey, IntegerKey


class TestTemplateString(ShotgunTestBase):
    """Base class for TemplateString tests."""

    def setUp(self):
        super().setUp()
        self.keys = {
            "Sequence": StringKey("Sequence"),
            "Shot": StringKey("Shot"),
            "version": IntegerKey("version"),
        }
        self.template_string = TemplateString("something-{Shot}.{Sequence}", self.keys)


class TestInit(TestTemplateString):
    def test_static_simple(self):
        pass
    def test_static_key_first(self):
        pass
    def test_definition_preseves_leading_slash(self):
        pass
    def test_definition_preserves_back_slashes(self):
        pass
class TestParent(TestTemplateString):
    def test_none(self):
        pass
class TestValidate(TestTemplateString):
    def test_valid(self):
        pass
    def test_key_first(self):
        pass
    def test_missing_static(self):
        pass
    def test_conflicting_values(self):
        pass
    def test_optional_values(self):
        pass
class TestApplyFields(TestTemplateString):
    def test_good(self):
        pass
    def test_value_missing(self):
        pass
    def test_optional_value(self):
        pass
class TestGetFields(TestTemplateString):
    def test_simple(self):
        pass
    def test_key_first(self):
        pass
    def test_key_only(self):
        pass
    def test_missing_value(self):
        pass
    def test_conflicting_values(self):
        pass
    def test_definition_short_end_static(self):
        pass
    def test_optional_values(self):
        pass
    # TODO this won't pass with current algorithm


#    def test_definition_short_end_key(self):
#        """Tests case when input string longer than definition which ends with key."""
#        definition = "something.{Shot}"
#        template_string = TemplateString(definition, self.keys)
#        input_string = "something.shot_1-more-stuff"
#        self.assertRaises(TankError, self.template_string.get_fields, input_string)
