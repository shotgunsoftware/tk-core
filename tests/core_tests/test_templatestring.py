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

from tank_test.tank_test_base import ShotgunTestBase, setUpModule # noqa

from tank.errors import TankError
from tank.template import TemplateString
from tank.templatekey import (StringKey, IntegerKey)


class TestTemplateString(ShotgunTestBase):
    """Base class for TemplateString tests."""
    def setUp(self):
        super(TestTemplateString, self).setUp()
        self.keys = {"Sequence": StringKey("Sequence"),
                     "Shot": StringKey("Shot"),
                     "version": IntegerKey("version")}
        self.template_string = TemplateString("something-{Shot}.{Sequence}", self.keys)


class TestInit(TestTemplateString):
    def test_static_simple(self):
        definition = "something-{Shot}.{Sequence}"
        template = TemplateString(definition, self.keys)
        expected = [["%s%ssomething-" % (template._prefix, os.path.sep), "."]]
        self.assertEquals(expected, template._static_tokens)

    def test_static_key_first(self):
        definition = "{Shot}something-{Sequence}."
        template = TemplateString(definition, self.keys)
        expected = [["%s%s" % (template._prefix, os.path.sep), "something-", "."]]
        self.assertEquals(expected, template._static_tokens)

    def test_definition_preseves_leading_slash(self):
        """
        The TemplateString should not change the use of os seperators in the 
        input definition.
        """
        # forward slashes with leading slash
        definition = "/tmp/{Shot}/something/{Sequence}/"
        template_string = TemplateString(definition, self.keys)
        self.assertEquals(definition, template_string.definition)

    def test_definition_preserves_back_slashes(self):
        # back slashes with leading slash
        definition = r"\something\{Shot}\\"
        template_string = TemplateString(definition, self.keys)
        self.assertEquals(definition, template_string.definition)

class TestParent(TestTemplateString):
    def test_none(self):
        self.assertIsNone(self.template_string.parent)


class TestValidate(TestTemplateString):
    def test_valid(self):
        valid_string = "something-Shot_name.Seq_name"
        self.assertTrue(self.template_string.validate(valid_string))

    def test_key_first(self):
        definition = "{Shot}something-{Sequence}."
        template_string = TemplateString(definition, self.keys)
        valid_string = "shot_1something-Seq_12."
        self.assertTrue(template_string.validate(valid_string))

    def test_missing_static(self):
        invalid_string = "shot_1.Seq_12"
        self.assertFalse(self.template_string.validate(invalid_string))

    def test_conflicting_values(self):
        definition = "{Shot}-{Sequence}.{Shot}"
        template_string = TemplateString(definition, self.keys)
        invalid_string = "shot_1-Seq_12.shot_2"
        self.assertFalse(self.template_string.validate(invalid_string))

    def test_optional_values(self):
        template_string = TemplateString("something-{Shot}[.{Sequence}]", self.keys)

        input_string = "something-shot_1.seq_2"
        expected = {"Shot": "shot_1",
                    "Sequence": "seq_2"}

        self.assertTrue(template_string.validate(input_string))


        # without optional value
        input_string = "something-shot_1"
        expected = {"Shot": "shot_1"}

        self.assertTrue(template_string.validate(input_string))


class TestApplyFields(TestTemplateString):
    def test_good(self):
        fields = {"Shot": "shot_1",
                  "Sequence": "seq_2"}
        expected = "something-shot_1.seq_2"
        result = self.template_string.apply_fields(fields)
        self.assertEquals(expected, result)

    def test_value_missing(self):
        fields = {"Shot": "shot_1"}
        self.assertRaises(TankError, self.template_string.apply_fields, fields)

    def test_optional_value(self):
        template_string = TemplateString("something-{Shot}[.{Sequence}]", self.keys)
        fields = {"Shot": "shot_1",
                  "Sequence": "seq_2"}
        expected = "something-shot_1.seq_2"
        result = template_string.apply_fields(fields)
        self.assertEquals(expected, result)

        # remove optional value
        del(fields["Sequence"])
        expected = "something-shot_1"
        result = template_string.apply_fields(fields)
        self.assertEquals(expected, result)


class TestGetFields(TestTemplateString):

    def test_simple(self):
        input_string = "something-shot_1.Seq_12"
        expected = {"Shot": "shot_1",
                    "Sequence": "Seq_12"}
        result = self.template_string.get_fields(input_string)
        self.assertEquals(expected, result)
        
    def test_key_first(self):
        definition = "{Shot}.{Sequence}"
        template_string = TemplateString(definition, self.keys)
        input_string = "shot_1.Seq_12"
        expected = {"Shot": "shot_1",
                    "Sequence": "Seq_12"}
        result = template_string.get_fields(input_string)
        self.assertEquals(expected, result)

    def test_key_only(self):
        definition = "{Shot}"
        template_string = TemplateString(definition, self.keys)
        input_string = "shot_1"
        expected = {"Shot": "shot_1"}
        result = template_string.get_fields(input_string)
        self.assertEquals(expected, result)

    def test_missing_value(self):
        input_string = "shot_1."
        self.assertRaises(TankError, self.template_string.get_fields, input_string)

    def test_conflicting_values(self):
        definition = "{Shot}.{Shot}"
        input_string = "shot_1.shot_2"
        self.assertRaises(TankError, self.template_string.get_fields, input_string)

    def test_definition_short_end_static(self):
        """Tests case when input string longer than definition which
        ends with non key."""
        definition = "{Shot}.something"
        template_string = TemplateString(definition, self.keys)
        input_string = "shot_1.something-else"
        self.assertRaises(TankError, self.template_string.get_fields, input_string)

    def test_optional_values(self):
        """
        Test definition containing optional sections resolves correctly.
        """
        template_string = TemplateString("something-{Shot}[.{Sequence}]", self.keys)

        input_string = "something-shot_1.seq_2"
        expected = {"Shot": "shot_1",
                    "Sequence": "seq_2"}

        result = template_string.get_fields(input_string)
        self.assertEquals(expected, result)


        # without optional value
        input_string = "something-shot_1"
        expected = {"Shot": "shot_1"}

        result = template_string.get_fields(input_string)
        self.assertEquals(expected, result)
    
    #TODO this won't pass with current algorithm
#    def test_definition_short_end_key(self):
#        """Tests case when input string longer than definition which ends with key."""
#        definition = "something.{Shot}"
#        template_string = TemplateString(definition, self.keys)
#        input_string = "something.shot_1-more-stuff"
#        self.assertRaises(TankError, self.template_string.get_fields, input_string)




    


