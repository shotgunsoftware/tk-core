"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------
Tests for templatefield module.
"""
from tank import TankError
from tank_test.tank_test_base import *
from tank.templatekey import TemplateKey, StringKey, IntegerKey, SequenceKey, make_keys

class TestStringKey(TankTestBase):
    def setUp(self):
        super(TestStringKey, self).setUp()
        self.str_field = StringKey("field_name")
        self.alpha_field = StringKey("field_name", filter_by="alphanumeric")
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
        self.assertTrue(self.alpha_field.validate(value))

    def test_validate_alphanum_bad(self):
        bad_values = ["a_b", "a b", "a-b", "*"]
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
        with self.assertRaises(TankError) as cm:
            self.choice_field.str_from_value(value)
        self.assertEquals(expected, cm.exception.message)

    def test_str_from_value_use_default(self):
        expected = "b"
        result = self.default_field.str_from_value()
        self.assertEquals(expected, result)

    def test_str_from_value_no_default(self):
        expected = "No value provided and no default available for %s" % self.str_field
        with self.assertRaises(TankError) as cm:
            self.str_field.str_from_value()
        self.assertEquals(expected, cm.exception.message)

    def test_str_from_value_alphanum_good(self):
        value = "a9b9C"
        expected = value
        result = self.alpha_field.str_from_value(value)
        self.assertEquals(expected, result)

    def test_str_from_value_alphanum_empty(self):
        value = ""
        expected = value
        result = self.alpha_field.str_from_value(value)
        self.assertEquals(expected, result)

    def test_str_from_value_alphanum_bad(self):
        base_expected = "%s Illegal value '%%s' does not fit filter" % self.alpha_field
        bad_values = ["a_b", "a b", "a-b", "*"]
        for bad_value in bad_values:
            expected = base_expected % bad_value
            with self.assertRaises(TankError) as cm:
                self.alpha_field.str_from_value(bad_value)
            self.assertEquals(expected, cm.exception.message)

    def test_str_from_value_ignore_type_alphanum(self):
        bad_values = ["a_b", "a b", "a-b", "*"]
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
        expected = "<Tank StringKey field_name>"
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
        with self.assertRaises(TankError) as cm:
            self.int_field.str_from_value(value)
            
        self.assertEquals(expected, cm.exception.message)

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
        expected = "<Tank IntegerKey field_name>"
        self.assertEquals(expected, str(self.int_field))


class TestSequenceKey(TankTestBase):
    def setUp(self):
        super(TestSequenceKey, self).setUp()
        self.seq_field = SequenceKey("field_name")


    def test_framespec_no_format(self):
        seq_field = SequenceKey("field_name")
        expected_frame_specs = set(["%01d", "%d", "#", "@", "$F1", "$F"])
        self.assertEquals(expected_frame_specs, seq_field.frame_specs)

    def test_framspec_short_format(self):
        format_spec = "02"
        expected_frame_specs = set(["%02d", "#", "@@", "##", "$F2"])
        seq_field = SequenceKey("field_name", format_spec=format_spec)
        self.assertEquals(expected_frame_specs, seq_field.frame_specs)

    def test_framespec_long_format(self):
        format_spec = "010"
        seq_field = SequenceKey("field_name", format_spec=format_spec)
        expected_frame_specs = set(["%010d", "#", "@@@@@@@@@@", "##########", "$F10"])
        self.assertEquals(expected_frame_specs, seq_field.frame_specs)

    def test_validate_good(self):
        good_values = self.seq_field.frame_specs
        good_values.update([1, "243"])
        for good_value in good_values:
            self.assertTrue(self.seq_field.validate(good_value))

    def test_validate_bad(self):
        bad_values = ["a", "$G", "23d"]
        for bad_value in bad_values:
            self.assertFalse(self.seq_field.validate(bad_value))

    def test_value_from_str(self):
        valid_str_values = {"12":12,
                            "0":0,
                            "%01d":"%01d",
                            "%d":"%d",
                            "#":"#",
                            "@":"@",
                            "$F1":"$F1",
                            "$F":"$F"}
        for str_value, expected_value in valid_str_values.items():
            self.assertEquals(expected_value, self.seq_field.value_from_str(str_value))

    def test_str_from_value_good(self):
        valid_value_strs = {12:"12",
                            0:"0",
                            "%01d":"%01d",
                            "%d":"%d",
                            "#":"#",
                            "@":"@",
                            "$F1":"$F1",
                            "$F":"$F"}
        for value, str_value in valid_value_strs.items():
            self.assertEquals(str_value, self.seq_field.str_from_value(value))
        

    def test_str_from_value_bad(self):
        value = "a"
        expected = "%s Illegal value %s, expected an Integer" % (str(self.seq_field), value)
        with self.assertRaises(TankError) as cm:
            self.seq_field.str_from_value(value)
            
        self.assertEquals(expected, cm.exception.message)

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

    def test_str_from_value_abstract_one(self):
        """
        abstract frame spec value can be returned, frame spec with 
        one place has special cases.
        """
        value = 999 # any valid value should work
        seq_field = SequenceKey("field_name")
        expected = "%01d"
        result = seq_field.str_from_value(value, frame_spec="%0d")
        self.assertEquals(expected, result)

        expected = "%d"
        result = seq_field.str_from_value(value, frame_spec="%d")
        self.assertEquals(expected, result)

        expected = "#"
        result = seq_field.str_from_value(value, frame_spec="#")
        self.assertEquals(expected, result)

        expected = "@"
        result = seq_field.str_from_value(value, frame_spec="@d")
        self.assertEquals(expected, result)

        expected = "$F1"
        result = seq_field.str_from_value(value, frame_spec="$Fd")
        self.assertEquals(expected, result)

        expected = "$F"
        result = seq_field.str_from_value(value, frame_spec="$F")
        self.assertEquals(expected, result)

    def test_str_from_value_abstract_three(self):
        """
        Test abstract frame spec value returned for framespec with more than
        one places.
        """
        value = 999 # any valid value should work
        seq_field = SequenceKey("field_name", format_spec="03")
        expected = "%03d"
        result = seq_field.str_from_value(value, frame_spec="%0d")
        self.assertEquals(expected, result)

        expected = "#"
        result = seq_field.str_from_value(value, frame_spec="#")
        self.assertEquals(expected, result)

        expected = "#d"
        result = seq_field.str_from_value(value, frame_spec="###")
        self.assertEquals(expected, result)

        expected = "@@@"
        result = seq_field.str_from_value(value, frame_spec="@d")
        self.assertEquals(expected, result)

        expected = "$F3"
        result = seq_field.str_from_value(value, frame_spec="$Fd")
        self.assertEquals(expected, result)

    def test_str_from_value_abstract_none(self):
        """
        Test abstract frame spec value returned with no value supplied.
        """
        seq_field = SequenceKey("field_name", format_spec="03")
        expected = "%03d"
        result = seq_field.str_from_value(frame_spec="%0d")
        self.assertEquals(expected, result)

    def test_default_int(self):
        default = 13
        seq_frame = SequenceKey("field_name", default=default)
        self.assertEquals(default, seq_frame.default)

    def test_default_frame_spec(self):
        frame_specs = set(["%01d", "%d", "#", "@", "$F1", "$F"])
        for frame_spec in frame_specs:
            seq_frame = SequenceKey("field_name", default=frame_spec)
            self.assertEquals(frame_spec, seq_frame.default)

    def test_default_frame_spec_choices(self):
        frame_specs = set(["%01d", "%d", "#", "@", "$F1", "$F"])
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
        frame_specs = set(["%01d", "%d", "#", "@", "$F1", "$F"])
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
        self.assertEquals(None, simple_key.format_spec)

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
