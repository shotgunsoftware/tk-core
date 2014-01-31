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
Tests for templatefield module.
"""

from tank import TankError
import copy
from tank_test.tank_test_base import *
from tank.templatekey import TemplateKey, StringKey, IntegerKey, SequenceKey, make_keys

class TestStringKey(TankTestBase):
    def setUp(self):
        super(TestStringKey, self).setUp()
        self.str_field = StringKey("field_name")
        self.alphanum_field = StringKey("field_name", filter_by="alphanumeric")
        self.alpha_field = StringKey("field_name", filter_by="alpha")
        self.choice_field = StringKey("field_name", choices=["a", "b"])
        self.default_field = StringKey("field_name", default="b")

    def test_default(self):
        default_value = "default_value"
        template_field = StringKey("field_name", default=default_value)
        self.assertEquals(default_value, template_field.default)

    def test_no_default(self):
        template_field = StringKey("field_name")
        self.assertIsNone(template_field.default)

    def test_choices(self):
        choices_value = ["a", "b"]
        template_field = StringKey("field_name", choices=choices_value)
        self.assertEquals(choices_value, template_field.choices)

    def test_exclusions(self):
        exclusions = ["a", "b"]
        template_field = StringKey("field_name", exclusions=exclusions)
        self.assertEquals(exclusions, template_field.exclusions)
        self.assertFalse(template_field.validate("a"))
        self.assertFalse(template_field.validate("b"))

    def test_illegal_choice_alphanumic(self):
        choices_value = ["@", "b"]
        self.assertRaises(TankError,
                          StringKey,
                          "field_name",
                          choices=choices_value,
                          filter_by="alphanumeric")

    def test_default_choices_mismatch(self):
        """Case that default value is not part of enumerated choices."""
        default_value = "c"
        choices_value = ["a", "b"]
        self.assertRaises(TankError, StringKey, "field_name", choices=choices_value, default=default_value)

    def test_choices_exclusions_conflict(self):
        """Case that same value is put as valid and invalid choice."""
        choices = ["a", "b"]
        exclusions = ["c", "a"]
        self.assertRaises(TankError, StringKey, "field_name", choices=choices, exclusions=exclusions)

    def test_name_set(self):
        name = "field_name"
        template_field = StringKey("field_name")
        self.assertEquals(name, template_field.name)

    def test_validate_string_good(self):
        value = "some string"
        self.assertTrue(self.str_field.validate(value))

    def test_validate_alphanum_good(self):
        value = "some0alphanumeric0string"
        self.assertTrue(self.alphanum_field.validate(value))

    def test_validate_alphanum_bad(self):
        bad_values = ["a_b", "a b", "a-b", "*"]
        for bad_value in bad_values:
            self.assertFalse(self.alphanum_field.validate(bad_value))

    def test_validate_alpha_good(self):
        value = "somealphastring"
        self.assertTrue(self.alpha_field.validate(value))

    def test_validate_alpha_bad(self):
        bad_values = ["a2b", "a_b", "a b", "a-b", "*"]
        for bad_value in bad_values:
            self.assertFalse(self.alpha_field.validate(bad_value))

    def test_str_from_value_good(self):
        value = "a string"
        expected = value
        result = self.str_field.str_from_value(value)
        self.assertEquals(expected, result)

    def test_str_from_value_empty(self):
        value = ""
        expected = value
        result = self.str_field.str_from_value(value)
        self.assertEquals(expected, result)

    def test_str_from_value_good_choice(self):
        value = "b"
        expected = value
        result = self.choice_field.str_from_value(value)
        self.assertEquals(expected, result)

    def test_str_from_value_bad_choice(self):
        value = "c"
        expected = "%s Illegal value: 'c' not in choices: ['a', 'b']" % str(self.choice_field)
        self.check_error_message(TankError, expected, self.choice_field.str_from_value, value)

    def test_str_from_value_use_default(self):
        expected = "b"
        result = self.default_field.str_from_value()
        self.assertEquals(expected, result)

    def test_str_from_value_no_default(self):
        expected = "No value provided and no default available for %s" % self.str_field
        self.check_error_message(TankError, expected, self.str_field.str_from_value)

    def test_str_from_value_alphanum_good(self):
        value = "a9b9C"
        expected = value
        result = self.alphanum_field.str_from_value(value)
        self.assertEquals(expected, result)

    def test_str_from_value_alphanum_empty(self):
        value = ""
        expected = value
        result = self.alphanum_field.str_from_value(value)
        self.assertEquals(expected, result)

    def test_str_from_value_alphanum_bad(self):
        base_expected = "%s Illegal value '%%s' does not fit filter" % self.alphanum_field
        bad_values = ["a_b", "a b", "a-b", "*"]
        for bad_value in bad_values:
            expected = base_expected % bad_value
            self.check_error_message(TankError, expected, self.alphanum_field.str_from_value, bad_value)

    def test_str_from_value_ignore_type_alphanum(self):
        bad_values = ["a_b", "a b", "a-b", "*"]
        for bad_value in bad_values:
            expected = bad_value
            result = self.alphanum_field.str_from_value(bad_value, ignore_type=True)
            self.assertEquals(expected, result)

    def test_str_from_value_alpha_good(self):
        value = "abC"
        expected = value
        result = self.alpha_field.str_from_value(value)
        self.assertEquals(expected, result)

    def test_str_from_value_alpha_empty(self):
        value = ""
        expected = value
        result = self.alpha_field.str_from_value(value)
        self.assertEquals(expected, result)

    def test_str_from_value_alpha_bad(self):
        base_expected = "%s Illegal value '%%s' does not fit filter" % self.alpha_field
        bad_values = ["a2b", "a_b", "a b", "a-b", "*"]
        for bad_value in bad_values:
            expected = base_expected % bad_value
            self.check_error_message(TankError, expected, self.alpha_field.str_from_value, bad_value)

    def test_str_from_value_ignore_type_alpha(self):
        bad_values = ["a2b", "a_b", "a b", "a-b", "*"]
        for bad_value in bad_values:
            expected = bad_value
            result = self.alpha_field.str_from_value(bad_value, ignore_type=True)
            self.assertEquals(expected, result)

    def test_value_from_str(self):
        str_value = "something"
        self.assertEquals(str_value, self.str_field.value_from_str(str_value))

    def test_shotgun_entity_type_set(self):
        str_field = StringKey("field_name", shotgun_entity_type="Shot")
        self.assertEquals("Shot", str_field.shotgun_entity_type)

    def test_shotgun_field_name_without_entity_type(self):
        """
        Test that setting shotgun_field name is not possible if not setting shotgun_entity_type.
        """
        self.assertRaises(TankError, StringKey, "field_name", shotgun_field_name="code")

    def test_shotgun_field_name_set(self):
        str_field = StringKey("field_name", shotgun_entity_type="Shot", shotgun_field_name="code")
        self.assertEquals("Shot", str_field.shotgun_entity_type)
        self.assertEquals("code", str_field.shotgun_field_name)


    def test_repr(self):
        expected = "<Sgtk StringKey field_name>"
        self.assertEquals(expected, str(self.str_field))


class TestIntegerKey(TankTestBase):
    def setUp(self):
        super(TestIntegerKey, self).setUp()
        self.int_field = IntegerKey("field_name")

    def test_bad_default(self):
        """Case that specified default does not match type."""
        default_value = "default_value"
        self.assertRaises(TankError, IntegerKey, "field_name", default=default_value)

    def test_illegal_choice(self):
        """Choice conflict with type."""
        choices_value = ["a", "b"]
        self.assertRaises(TankError, IntegerKey, "field_name", choices=choices_value)

    def test_format_set(self):
        format_spec = "03"
        template_field = IntegerKey("field_name", format_spec=format_spec)
        self.assertEquals(format_spec, template_field.format_spec)

    def test_validate_string_good(self):
        value = "23"
        self.assertTrue(self.int_field.validate(value))

    def test_validate_int_good(self):
        value = 23
        self.assertTrue(self.int_field.validate(value))

    def test_validate_bad(self):
        value = "a"
        self.assertFalse(self.int_field.validate(value))

    def test_str_from_value_good(self):
        value = 3
        expected = "%s" % value
        result = self.int_field.str_from_value(value)
        self.assertEquals(expected, result)

    def test_str_from_value_zero(self):
        value = 0
        expected = "%d" % value
        result = self.int_field.str_from_value(value)
        self.assertEquals(expected, result)

    def test_str_from_value_bad(self):
        value = "a"
        expected = "%s Illegal value %s, expected an Integer" % (str(self.int_field), value)
        self.check_error_message(TankError, expected, self.int_field.str_from_value, value)

    def test_str_from_value_formatted(self):
        formatted_field = IntegerKey("field_name", format_spec="03")
        value = 3
        expected = "%03d" % value
        result = formatted_field.str_from_value(value)
        self.assertEquals(expected, result)

    def test_str_from_value_ignore_type(self):
        value = "a"
        expected = value
        result = self.int_field.str_from_value(value, ignore_type=True)
        self.assertEquals(expected, result)

    def test_value_from_str(self):
        str_value = "32"
        self.assertEquals(32, self.int_field.value_from_str(str_value))

    def test_repr(self):
        expected = "<Sgtk IntegerKey field_name>"
        self.assertEquals(expected, str(self.int_field))


class TestSequenceKey(TankTestBase):
    def setUp(self):
        super(TestSequenceKey, self).setUp()
        self.seq_field = SequenceKey("field_name")


    def test_framespec_no_format(self):
        seq_field = SequenceKey("field_name")
        expected_frame_specs = set(["%d", "#", "@", "$F"])
        self.assertEquals(expected_frame_specs, set(seq_field._frame_specs))

    def test_framspec_short_format(self):
        format_spec = "02"
        expected_frame_specs = set(["%02d", "##", "@@", "$F2"])
        seq_field = SequenceKey("field_name", format_spec=format_spec)
        self.assertEquals(expected_frame_specs, set(seq_field._frame_specs))

    def test_framespec_long_format(self):
        format_spec = "010"
        seq_field = SequenceKey("field_name", format_spec=format_spec)
        expected_frame_specs = set(["%010d", "@@@@@@@@@@", "##########", "$F10"])
        self.assertEquals(expected_frame_specs, set(seq_field._frame_specs))

    def test_validate_good(self):
        good_values = copy.copy(self.seq_field._frame_specs)
        good_values.extend(["FORMAT:%d", "FORMAT:#", "FORMAT:@", "FORMAT:$F"])
        good_values.extend(["FORMAT:  %d", "FORMAT:  #", "FORMAT:  @", "FORMAT:  $F"])
        good_values.extend(["243", "0123"])
        for good_value in good_values:
            self.assertTrue(self.seq_field.validate(good_value))

    def test_validate_bad(self):
        bad_values = ["a", "$G", "23d"]
        for bad_value in bad_values:
            self.assertFalse(self.seq_field.validate(bad_value))

    def test_value_from_str(self):
        
        # note - default case means frame spec is 01
        valid_str_values = {"12":12,
                            "0":0,
                            "%d":"%d",
                            "#":"#",
                            "@":"@",
                            "$F":"$F"}
        for str_value, expected_value in valid_str_values.items():
            self.assertEquals(expected_value, self.seq_field.value_from_str(str_value))

    def test_str_from_value_good(self):
        
        # note - default case means frame spec is 01
        valid_value_strs = {12:"12",
                            0:"0",
                            "%d":"%d",
                            "#":"#",
                            "@":"@",
                            "$F":"$F"}
        for value, str_value in valid_value_strs.items():
            self.assertEquals(str_value, self.seq_field.str_from_value(value))
        

    def test_str_from_value_bad(self):
        value = "a"
        expected = "%s Illegal value '%s', expected an Integer, a frame spec or format spec." % (str(self.seq_field), value)
        expected += "\nValid frame specs: ['%d', '#', '@', '$F']"
        expected += "\nValid format strings: ['FORMAT: %d', 'FORMAT: #', 'FORMAT: @', 'FORMAT: $F']\n"

        self.check_error_message(TankError, expected, self.seq_field.str_from_value, value)

    def test_str_from_value_formatted(self):
        formatted_field = SequenceKey("field_name", format_spec="03")
        value = 3
        expected = "%03d" % value
        result = formatted_field.str_from_value(value)
        self.assertEquals(expected, result)

    def test_str_from_value_ignore_type(self):
        value = "a"
        expected = value
        result = self.seq_field.str_from_value(value, ignore_type=True)
        self.assertEquals(expected, result)

    def test_str_from_value_default_one(self):
        """
        default frame spec value can be returned, frame spec with 
        one place has special cases.
        """
        value = None
        seq_field = SequenceKey("field_name")
        expected = "%d"
        result = seq_field.str_from_value(value="FORMAT:%d")
        self.assertEquals(expected, result)

        expected = "#"
        result = seq_field.str_from_value(value="FORMAT:#")
        self.assertEquals(expected, result)

        expected = "@"
        result = seq_field.str_from_value(value="FORMAT:@")
        self.assertEquals(expected, result)

        expected = "$F"
        result = seq_field.str_from_value(value="FORMAT:$F")
        self.assertEquals(expected, result)

        # no pattern specified
        expected = "%d"
        result = seq_field.str_from_value()
        self.assertEquals(expected, result)

    def test_str_from_value_default_three(self):
        """
        Test default frame spec value returned for framespec with more than
        one places.
        """
        seq_field = SequenceKey("field_name", format_spec="03")
        
        expected = "%03d"
        result = seq_field.str_from_value("FORMAT:%d")
        self.assertEquals(expected, result)

        expected = "###"
        result = seq_field.str_from_value("FORMAT:#")
        self.assertEquals(expected, result)

        expected = "@@@"
        result = seq_field.str_from_value("FORMAT:@")
        self.assertEquals(expected, result)

        expected = "$F3"
        result = seq_field.str_from_value("FORMAT:$F")
        self.assertEquals(expected, result)

        # no pattern specified
        expected = "%03d"
        result = seq_field.str_from_value()
        self.assertEquals(expected, result)

    def test_str_from_value_format_whitespace(self):
        """Use of FORMAT: prefix with whitespace."""
        
        seq_field = SequenceKey("field_name", format_spec="03")
        
        expected = "%03d"
        result = seq_field.str_from_value("FORMAT: %d")
        self.assertEquals(expected, result)

        expected = "###"
        result = seq_field.str_from_value("FORMAT: #")
        self.assertEquals(expected, result)

        expected = "@@@"
        result = seq_field.str_from_value("FORMAT: @")
        self.assertEquals(expected, result)

        expected = "$F3"
        result = seq_field.str_from_value("FORMAT: $F")
        self.assertEquals(expected, result)

    def test_default_int(self):
        default = 13
        seq_frame = SequenceKey("field_name", default=default)
        self.assertEquals(default, seq_frame.default)

    def test_default_frame_spec(self):
        frame_specs = set(["%d", "#", "@", "$F"])
        for frame_spec in frame_specs:
            seq_frame = SequenceKey("field_name", default=frame_spec)
            self.assertEquals(frame_spec, seq_frame.default)

    def test_default_frame_spec_choices(self):
        frame_specs = set(["%d", "#", "@", "$F"])
        for frame_spec in frame_specs:
            seq_frame = SequenceKey("field_name", default=frame_spec, choices=[1,2])
            self.assertEquals(frame_spec, seq_frame.default)

    def test_default_bad(self):
        default = "bad default"
        self.assertRaises(TankError, SequenceKey, "field_name", default=default)

    def test_choices_int(self):
        choices = [1]
        seq_frame = SequenceKey("field_name", choices=choices)
        self.assertEquals(choices, seq_frame.choices)

    def test_choices_frame_spec(self):
        frame_specs = set(["%d", "#", "@", "$F"])
        seq_frame = SequenceKey("field_name", choices=frame_specs)
        self.assertEquals(frame_specs, seq_frame.choices)


class TestMakeKeys(TankTestBase):
    def test_no_data(self):
        data = {}
        result = make_keys(data)
        self.assertEquals({}, result)

    def test_string(self):
        data = {"simple": {"type": "str"},
                "alpha" : {"type": "str", "filter_by": "alphanumeric"},
                "complex": {"type": "str", "default": "a", "choices": ["a", "b"]}}
        result = make_keys(data)
        # check type
        for key in result.values():
            self.assertIsInstance(key, StringKey)

        simple_key = result.get("simple")
        alpha_key = result.get("alpha")
        complex_key = result.get("complex")

        self.assertEquals("simple", simple_key.name)
        self.assertEquals(None, simple_key.default)
        self.assertEquals([], simple_key.choices)

        self.assertEquals("alpha", alpha_key.name)
        self.assertEquals(None, alpha_key.default)
        self.assertEquals([], alpha_key.choices)
        self.assertEquals("alphanumeric", alpha_key.filter_by)

        self.assertEquals("complex", complex_key.name)
        self.assertEquals("a", complex_key.default)
        self.assertEquals(["a", "b"], complex_key.choices)

    def test_int(self):
        data = {"simple": {"type": "int"},
                "complex": {"type": "int", "default": 2, "choices": [1,2], "format_spec": "03"}}
        result = make_keys(data)
        # check type
        for key in result.values():
            self.assertIsInstance(key, IntegerKey)

        simple_key = result.get("simple")
        complex_key = result.get("complex")
        
        self.assertEquals("simple", simple_key.name)
        self.assertEquals(None, simple_key.default)
        self.assertEquals([], simple_key.choices)

        self.assertEquals("complex", complex_key.name)
        self.assertEquals(2, complex_key.default)
        self.assertEquals([1, 2], complex_key.choices)
        self.assertEquals("03", complex_key.format_spec)

    def test_sequence(self):
        data = {"simple": {"type": "sequence"},
                "complex": {"type": "sequence", "format_spec": "03"}}

        result = make_keys(data)
        # check type
        for key in result.values():
            self.assertIsInstance(key, SequenceKey)

        simple_key = result.get("simple")
        complex_key = result.get("complex")

        self.assertEquals("simple", simple_key.name)
        self.assertEquals("01", simple_key.format_spec)

        self.assertEquals("complex", complex_key.name)
        self.assertEquals("03", complex_key.format_spec)

    def test_shotgun_fields(self):
        """
        Test keys made with shotgun entity type and field name.
        """
        data = {"string" : {"type": "str",
                            "shotgun_entity_type": "entity one",
                            "shotgun_field_name": "field one"},
               "integer" : {"type": "int",
                            "shotgun_entity_type": "entity two",
                            "shotgun_field_name": "field two"},
               "sequence" : {"type": "sequence",
                            "shotgun_entity_type": "entity three",
                            "shotgun_field_name": "field three"}}

        result = make_keys(data)

        str_key = result.get("string")
        self.assertIsInstance(str_key, StringKey)
        self.assertEquals("entity one", str_key.shotgun_entity_type)
        self.assertEquals("field one", str_key.shotgun_field_name)

        int_key = result.get("integer")
        self.assertIsInstance(int_key, IntegerKey)
        self.assertEquals("entity two", int_key.shotgun_entity_type)
        self.assertEquals("field two", int_key.shotgun_field_name)

        seq_key = result.get("sequence")
        self.assertIsInstance(seq_key, SequenceKey)
        self.assertEquals("entity three", seq_key.shotgun_entity_type)
        self.assertEquals("field three", seq_key.shotgun_field_name)

    def test_bad_format(self):
        data = {"bad": {"type": "int", "format_spec": 3}}
        self.assertRaises(TankError, make_keys, data)

    def test_bad_type(self):
        data = {"key_name": {"type":"bad_type"}}
        self.assertRaises(TankError, make_keys, data)

    def test_aliases(self):
        data = {"real_key_name": {"type":"str", "alias":"alias_name"}}
        keys = make_keys(data)
        key = keys.get("real_key_name")
        self.assertIsInstance(key, StringKey)
        self.assertEquals("alias_name", key.name)

class TestEyeKey(TankTestBase):
    """
    Tests that key representing eye can be setup.
    """
    def setUp(self):
        super(TestEyeKey, self).setUp()
        self.eye_key = StringKey("eye", default="%V", choices=["%V","L","R"])
        self.default_value = "%V"

    def test_validate(self):
        self.assertTrue(self.eye_key.validate(self.default_value))
        self.assertTrue(self.eye_key.validate("L"))
        self.assertTrue(self.eye_key.validate("R"))

    def test_str_from_value_default(self):
        self.assertEquals(self.default_value, self.eye_key.str_from_value())

    def test_set_choices(self):
        eye_key = StringKey("eye", default="%V", choices=["l","r", "%V"])
        self.assertTrue(self.eye_key.validate(self.default_value))
        self.assertTrue(self.eye_key.validate("l"))
        self.assertTrue(self.eye_key.validate("r"))

