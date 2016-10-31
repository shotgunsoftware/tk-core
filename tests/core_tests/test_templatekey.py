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

from __future__ import with_statement

from tank import TankError
import copy
import sys
import datetime
from mock import patch
from tank_test.tank_test_base import *
from tank.templatekey import StringKey, IntegerKey, SequenceKey, TimestampKey, make_keys


class TestTemplateKey(TankTestBase):
    """
    Tests functionality common to all key classes.
    """

    def test_override_default_at_runtime(self):
        """
        Makes sure that a key's default can be overriden at runtime.
        """
        sk = SequenceKey("sequencekey", format_spec="04")
        self.assertEquals(sk.default, "%04d")
        sk.default = "%03d"
        self.assertEquals(sk.default, "%03d")


class TestStringKey(TankTestBase):
    def setUp(self):
        super(TestStringKey, self).setUp()
        self.str_field = StringKey("field_name")
        self.alphanum_field = StringKey("field_name", filter_by="alphanumeric")
        self.alpha_field = StringKey("field_name", filter_by="alpha")

        self.regex_field = StringKey("field_name", filter_by="^[0-9]{3}@[a-z]+") # e.g 123@foo

        self.choice_field = StringKey("field_name", choices=["a", "b"])
        self.default_field = StringKey("field_name", default="b")

    def test_invalid(self):
        self.assertRaises(TankError, StringKey, "S!hot")

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

    def test_validate_regex_good(self):
        value = "123@foobar"
        self.assertTrue(self.regex_field.validate(value))

    def test_validate_regex_bad(self):
        bad_values = ["basd", "1234@asd", " 123@foo", "a-b", "*"]
        for bad_value in bad_values:
            self.assertFalse(self.regex_field.validate(bad_value))

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
        base_expected = "%s Illegal value '%%s' does not fit filter_by 'alphanumeric'" % self.alphanum_field
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
        base_expected = "%s Illegal value '%%s' does not fit filter_by 'alpha'" % self.alpha_field
        bad_values = ["a2b", "a_b", "a b", "a-b", "*"]
        for bad_value in bad_values:
            expected = base_expected % bad_value
            self.check_error_message(TankError, expected, self.alpha_field.str_from_value, bad_value)

    def test_str_from_value_ignore_type_alpha(self):
        bad_values = ["a2b", "a_b", "a b", "a-b", "*"]
        for bad_value in bad_values:
            expected = bad_value
            result = self.regex_field.str_from_value(bad_value, ignore_type=True)
            self.assertEquals(expected, result)

    def test_str_from_value_regex_good(self):
        value = "444@jlasdlkjasd"
        expected = value
        result = self.regex_field.str_from_value(value)
        self.assertEquals(expected, result)

    def test_str_from_value_regex_bad(self):
        base_expected = "%s Illegal value '%%s' does not fit filter_by '^[0-9]{3}@[a-z]+'" % self.regex_field
        bad_values = ["", " 121@fff", "asdasd", "123@", "*"]
        for bad_value in bad_values:
            expected = base_expected % bad_value
            self.check_error_message(TankError, expected, self.regex_field.str_from_value, bad_value)

    def test_str_from_value_ignore_type_regex(self):
        bad_values = ["", " 121@fff", "asdasd", "123@", "*"]
        for bad_value in bad_values:
            expected = bad_value
            result = self.regex_field.str_from_value(bad_value, ignore_type=True)
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

    def test_subset(self):
        """
        Test subset_format parameter
        """

        # test properties
        template_field = StringKey("field_name", subset="(.{3}).*")
        self.assertEquals("(.{3}).*", template_field.subset)
        # test bad regex
        self.assertRaises(TankError, StringKey, "field_name", subset="({4}.).*BROKENREGEX")

        # test basic regex
        template_field = StringKey("field_name", subset="(.{3}).*")

        tests = []

        # basic test
        tests.append({"short": "foo", "full": "foobar", "template": StringKey("field_name", subset="(.{3}).*")})
        tests.append({"short": u"foo", "full": u"foobar", "template": StringKey("field_name", subset="(.{3}).*")})

        # unicode
        tests.append({
            "short": u'\u3042\u308a\u304c',
            "full": u'\u3042\u308a\u304c\u3068',
            "template": StringKey("field_name", subset="(.{3}).*")}
        )

        # multi token
        tests.append({
            "short": 'JS',
            "full": 'John Smith',
            "template": StringKey("field_name", subset='([A-Z])[a-z]* ([A-Z])[a-z]*')}
        )

        for test in tests:

            short = test["short"]
            full = test["full"]
            template_field = test["template"]

            self.assertEquals(short, template_field.value_from_str(short))
            self.assertEquals(full, template_field.value_from_str(full))

            self.assertEquals(short, template_field.str_from_value(full))

            self.assertTrue(template_field.validate(full))

            self.assertFalse(template_field.validate(short[0]))
            self.assertRaises(TankError, template_field.str_from_value, short[0])



    def test_subset_format(self):
        """
        Test subset_format parameter
        """

        if sys.version_info < (2, 6):
            # subset format not supported in py25
            self.assertRaises(TankError, StringKey, "field_name", subset="(.{3}).*", subset_format="{0} FOO")
            return

        # test properties
        template_field = StringKey("field_name", subset="(.)().*", subset_format="{0} FOO")
        self.assertEquals("{0} FOO", template_field.subset_format)

        # cannot specify subset_format without subset
        self.assertRaises(TankError, StringKey, "field_name", subset_format="{0} FOO")

        tests = []

        # basic test
        tests.append( {
            "short": "\u3042foo ",
            "full": "foobar",
            "template": StringKey("field_name", subset="(.{3}).*", subset_format="\u3042{0} ")
            }
        )

        # unicode
        tests.append( {
            "short": u'\u3042\u308a\u304c ',
            "full": u'\u3042\u308a\u304c\u3068',
            "template": StringKey("field_name", subset="(.{3}).*", subset_format="{0} ")
            }
        )

        # multi token
        tests.append( {
            "short": 'S J',
            "full": 'John Smith',
            "template": StringKey("field_name", subset='([A-Z])[a-z]* ([A-Z])[a-z]*', subset_format="{1} {0}")
            }
        )

        for test in tests:

            print test

            short = test["short"]
            full = test["full"]
            template_field = test["template"]

            self.assertEquals(short, template_field.value_from_str(short))
            self.assertEquals(full, template_field.value_from_str(full))

            self.assertEquals(short, template_field.str_from_value(full))

            self.assertTrue(template_field.validate(full))

            self.assertFalse(template_field.validate(short[0]))
            self.assertRaises(TankError, template_field.str_from_value, short[0])




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
        expected = "%s Illegal value '%s', expected an Integer" % (str(self.int_field), value)
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

    def test_init_validation(self):
        """
        Makes sure that parameter validation is correct in the constructor.
        """
        # This should obviously work
        self._validate_key(
            IntegerKey("version_number"),
            strict_matching=None, format_spec=None
        )
        # When specifying parameters, they should be set accordingly.
        self._validate_key(
            IntegerKey("version_number", format_spec="03", strict_matching=True),
            strict_matching=True, format_spec="03"
        )
        self._validate_key(
            IntegerKey("version_number", format_spec="03", strict_matching=False),
            strict_matching=False, format_spec="03"
        )
        self._validate_key(
            IntegerKey("version_number", format_spec="3", strict_matching=False),
            strict_matching=False, format_spec="3"
        )
        # When specifying a format but not specifying the strict_matching, it should
        # still have strict_matching.
        self._validate_key(
            IntegerKey("version_number", format_spec="03"),
            strict_matching=True, format_spec="03"
        )
        # Make sure than an error is raised when wrong types are passed in.
        with self.assertRaisesRegexp(TankError, "is not of type boolean"):
            IntegerKey("version_number", strict_matching=1)

        with self.assertRaisesRegexp(TankError, "is not of type string"):
            IntegerKey("version_number", format_spec=1)

        # Make sure that if the user specifies strict_matching with no format
        # there is an error
        error_regexp = "strict_matching can't be set"
        with self.assertRaisesRegexp(TankError, error_regexp):
            IntegerKey("version_number", strict_matching=False)

        with self.assertRaisesRegexp(TankError, error_regexp):
            IntegerKey("version_number", strict_matching=True)

        # We support 4 format_spec values:
        # - None
        # - non zero positive number
        # - zero followed by a non zero positive number
        IntegerKey("version_number", format_spec=None)
        IntegerKey("version_number", format_spec="1")
        IntegerKey("version_number", format_spec="01")

        # Make sure invalid formats are caught
        with self.assertRaisesRegexp(TankError, "format_spec can't be empty"):
            IntegerKey("version_number", format_spec="")

        error_regexp = "has to either be"
        # We don't support the sign option.
        with self.assertRaisesRegexp(TankError, error_regexp):
            IntegerKey("version_number", format_spec=" 3", strict_matching=False)

        with self.assertRaisesRegexp(TankError, error_regexp):
            # Should throw because the padding number is not non zero.
            IntegerKey("version_number", format_spec="00")

        with self.assertRaisesRegexp(TankError, error_regexp):
            # Should throw because it is not a non zero positive integer
            IntegerKey("version_number", format_spec="0")

        with self.assertRaisesRegexp(TankError, error_regexp):
            # Should throw because the padding caracter is invalid
            IntegerKey("version_number", format_spec="a0")

        with self.assertRaisesRegexp(TankError, error_regexp):
            # Should throw because the padding size is not a number.
            IntegerKey("version_number", format_spec="0a")

    def test_no_format_spec(self):
        key = IntegerKey("version_number")
        key.value_from_str

    def _validate_key(self, key, strict_matching, format_spec):
        """
        Makes sure that an integer key's formatting options are correctly set.
        """
        self.assertEqual(key.strict_matching, strict_matching)
        self.assertEqual(key.format_spec, format_spec)

    def test_non_strict_matching(self):
        """
        In non strict mode, tokens can actually have less numbers than the padding requests. Also,
        if there are more, can also match.
        """
        self._test_non_strict_matching('0')
        self._test_non_strict_matching('')

    def _test_non_strict_matching(self, padding_char):
        """
        Allows to test strict matching with a specific padding character.

        :param padding_char: Character to test padding with. Should be space or 0.
        """
        key = IntegerKey("version_number", format_spec="%s3" % padding_char, strict_matching=False)

        # The padding char is missing in the format specifier, but we still need when validating
        # results.
        if padding_char == '':
            padding_char = ' '

        # It should match because they are valid numbers.

        self.assertEqual(key.value_from_str("000"), 0)
        self.assertEqual(key.value_from_str("0"), 0)
        self.assertEqual(key.value_from_str("0"), 0)

        # While the number doesn't make any sense as far as formatting is concerned, this used
        # to work in old versions of Toolkit and needs to keep working in non strict mode.
        self.assertEqual(key.value_from_str("%s000" % padding_char), 0)

        # It should match a template with too many digits...
        self.assertEqual(key.value_from_str("20000"), 20000)

        # ... even if they are all zeros because lossy matching.
        self.assertEqual(key.value_from_str("00000"), 0)

        # From path to tokens back to path should be lossy.
        value = key.value_from_str("1")
        self.assertEqual("%s%s1" % (padding_char, padding_char), key.str_from_value(value))

        self._test_nan(key, "expected an Integer")

    def _test_nan(self, key, error_msg):
        """
        Tests a key with against values that are not numbers.

        :param key: Key to test.
        :param error_msg: Text that partially matches the error message.
        """
        # Should fail because not a number
        with self.assertRaisesRegexp(TankError, error_msg):
            key.value_from_str("aaaa")
        with self.assertRaisesRegexp(TankError, error_msg):
            key.value_from_str("0a")
        with self.assertRaisesRegexp(TankError, error_msg):
            key.value_from_str("a0")
        with self.assertRaisesRegexp(TankError, error_msg):
            key.value_from_str("aa")

    def _test_strict_matching(self, padding_char):
        """
        Allows to test strict matching with any padding type.
        """
        # have a template that formats with two digits of padding.
        key = IntegerKey("version_number", format_spec="%s3" % padding_char, strict_matching=True)
        self.assertTrue(key.strict_matching)

        # The padding char is missing in the format specifier, but we still need when validating
        # results.
        if padding_char == '':
            padding_char = ' '

        # From path to tokens back to path should get back the same string when the expected number of
        # digits are found.
        value = key.value_from_str("%s%s1" % (padding_char, padding_char))
        self.assertEqual("%s%s1" % (padding_char, padding_char), key.str_from_value(value))

        # It should match a template with more digits.
        value = key.value_from_str("20000")
        self.assertEqual("20000", key.str_from_value(value))

        key.value_from_str("123")

        error_msg = "does not match format spec"

        # It should not match a string with too few digits
        with self.assertRaisesRegexp(TankError, error_msg):
            key.value_from_str("1")

        # It should not match a template with too many digits that are all zero because that would
        # lossy. (there are more zeros than the format spec can rebuild)
        with self.assertRaisesRegexp(TankError, error_msg):
            key.value_from_str("0000")

        # It should not match negative numbers either
        with self.assertRaisesRegexp(TankError, error_msg):
            key.value_from_str("-1000")

        # It should not match baddly padded numbers
        with self.assertRaisesRegexp(TankError, error_msg):
            key.value_from_str("0100")

        # It should not match negative values
        with self.assertRaisesRegexp(TankError, error_msg):
            key.value_from_str("-01")

        self._test_nan(key, error_msg)

    def test_strict_matching(self):
        """
        In strict mode, tokens have to have as much padding as the format specifier suggests. Less will not
        match.
        """
        self._test_strict_matching('')
        self._test_strict_matching('0')


class TestSequenceKey(TankTestBase):
    def setUp(self):
        super(TestSequenceKey, self).setUp()
        self.seq_field = SequenceKey("field_name")


    def test_framespec_no_format(self):
        seq_field = SequenceKey("field_name")
        expected_frame_specs = set(["%d", "#", "@", "$F", "<UDIM>", "$UDIM"])
        self.assertEquals(expected_frame_specs, set(seq_field._frame_specs))

    def test_framspec_short_format(self):
        format_spec = "02"
        expected_frame_specs = set(["%02d", "##", "@@", "$F2", "<UDIM>", "$UDIM"])
        seq_field = SequenceKey("field_name", format_spec=format_spec)
        self.assertEquals(expected_frame_specs, set(seq_field._frame_specs))

    def test_framespec_long_format(self):
        format_spec = "010"
        seq_field = SequenceKey("field_name", format_spec=format_spec)
        expected_frame_specs = set(["%010d", "@@@@@@@@@@", "##########", "$F10", "<UDIM>", "$UDIM"])
        self.assertEquals(expected_frame_specs, set(seq_field._frame_specs))

    def test_validate_good(self):
        good_values = copy.copy(self.seq_field._frame_specs)
        good_values.extend(["FORMAT:%d", "FORMAT:#", "FORMAT:@", "FORMAT:$F", "FORMAT:<UDIM>", "FORMAT:$UDIM"])
        good_values.extend(["FORMAT:  %d", "FORMAT:  #", "FORMAT:  @", "FORMAT:  $F",
                            "FORMAT:  <UDIM>", "FORMAT:  $UDIM"])
        good_values.extend(["243", "0123"])
        good_values.extend(["[243-13123123123]", "[0001-0122]"])
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
                            "[0001-0122]": "[0001-0122]",
                            "%d":"%d",
                            "#":"#",
                            "@":"@",
                            "$F":"$F",
                            "<UDIM>":"<UDIM>",
                            "$UDIM":"$UDIM"}
        for str_value, expected_value in valid_str_values.items():
            self.assertEquals(expected_value, self.seq_field.value_from_str(str_value))

    def test_str_from_value_good(self):

        # note - default case means frame spec is 01
        valid_value_strs = {12:"12",
                            0:"0",
                            "%d":"%d",
                            "[0001-0122]":"[0001-0122]",
                            "#":"#",
                            "@":"@",
                            "$F":"$F",
                            "<UDIM>":"<UDIM>",
                            "$UDIM":"$UDIM"}
        for value, str_value in valid_value_strs.items():
            self.assertEquals(str_value, self.seq_field.str_from_value(value))


    def test_str_from_value_bad(self):
        value = "a"
        expected = "%s Illegal value '%s', expected an Integer, a frame spec or format spec." % (str(self.seq_field), value)
        expected += "\nValid frame specs: ['%d', '#', '@', '$F', '<UDIM>', '$UDIM']"
        expected += ("\nValid format strings: ['FORMAT: %d', 'FORMAT: #', 'FORMAT: @', 'FORMAT: $F', "
                     "'FORMAT: <UDIM>', 'FORMAT: $UDIM']\n")

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

        expected = "<UDIM>"
        result = seq_field.str_from_value(value="FORMAT:<UDIM>")
        self.assertEquals(expected, result)

        expected = "$UDIM"
        result = seq_field.str_from_value(value="FORMAT:$UDIM")
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

        expected = "<UDIM>"
        result = seq_field.str_from_value(value="FORMAT:<UDIM>")
        self.assertEquals(expected, result)

        expected = "$UDIM"
        result = seq_field.str_from_value(value="FORMAT:$UDIM")
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

        expected = "<UDIM>"
        result = seq_field.str_from_value(value="FORMAT: <UDIM>")
        self.assertEquals(expected, result)

        expected = "$UDIM"
        result = seq_field.str_from_value(value="FORMAT: $UDIM")
        self.assertEquals(expected, result)

    def test_default_int(self):
        default = 13
        seq_frame = SequenceKey("field_name", default=default)
        self.assertEquals(default, seq_frame.default)

    def test_default_frame_spec(self):
        frame_specs = set(["%d", "#", "@", "$F", "<UDIM>", "$UDIM"])
        for frame_spec in frame_specs:
            seq_frame = SequenceKey("field_name", default=frame_spec)
            self.assertEquals(frame_spec, seq_frame.default)

    def test_default_frame_spec_choices(self):
        frame_specs = set(["%d", "#", "@", "$F", "<UDIM>", "$UDIM"])
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
        frame_specs = set(["%d", "#", "@", "$F", "<UDIM>", "$UDIM"])
        seq_frame = SequenceKey("field_name", choices=frame_specs)
        self.assertEquals(list(frame_specs), seq_frame.choices)


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


class TestTimestampKey(TankTestBase):
    """
    Test timestamp key type.
    """

    def setUp(self):
        """
        Creates a bunch of dates and strings for testing.
        """
        super(TestTimestampKey, self).setUp()
        self._datetime = datetime.datetime(2015, 6, 24, 21, 20, 30)
        self._datetime_string = "2015-06-24-21-20-30"

    def test_default_values(self):
        """
        Makes sure default values are as expected.
        """
        key = TimestampKey("name")
        self.assertEqual(key.format_spec, "%Y-%m-%d-%H-%M-%S")
        self.assertIsNone(key.default)

    def test_init(self):
        """
        Tests the __init__ of TimestampKey.
        """
        # No args should be time, it's just a timestamp with default formatting options.
        TimestampKey("name")
        # While unlikely, hardcoding a timestamp matching the format spec should be fine.
        TimestampKey("name", default="2015-07-03-09-09-00")
        # Hardcoding a default value with a custom format spec should be fine.
        TimestampKey("name", default="03-07-2015", format_spec="%d-%m-%Y")
        # utc and now are special cases that end up returning the current time as the default
        # value.
        key = TimestampKey("name", default="utc_now")
        # Make sure UTC time will be generated.
        self.assertEqual(key._default, key._TimestampKey__get_current_utc_time)
        key = TimestampKey("name", default="now")
        # Make sure localtime will be generated.
        self.assertEqual(key._default, key._TimestampKey__get_current_time)
        # One can override the format_spec without providing a default.
        TimestampKey("name", format_spec="%Y-%m-%d")

        # format_spec has to be a string.
        with self.assertRaisesRegexp(TankError, "is not of type string or None"):
            TimestampKey("name", default=1)

        # format_spec has to be a string.
        with self.assertRaisesRegexp(TankError, "is not of type string"):
            TimestampKey("name", format_spec=1)

        # Date that to be a valid time.
        with self.assertRaisesRegexp(TankError, "Invalid string"):
            TimestampKey("name", default="00-07-2015", format_spec="%d-%m-%Y")

        # Date that to be a valid time.
        with self.assertRaisesRegexp(TankError, "Invalid string"):
            TimestampKey("name", default="not_a_date")

    def test_str_from_value(self):
        """
        Convert all supported value types into a string and validates that
        we are getting the right result
        """
        key = TimestampKey("test")

        # Try and convert each and every date format to string
        self.assertEqual(
            key.str_from_value(self._datetime),
            self._datetime_string
        )

    def test_value_from_str(self):
        """
        Makes sure that a string can be converted to a datetime.
        """
        key = TimestampKey("test")
        self.assertEqual(
            key.value_from_str(self._datetime_string),
            self._datetime
        )
        self.assertEqual(
            key.value_from_str(unicode(self._datetime_string)),
            self._datetime
        )

    def test_bad_str(self):
        """
        Test with strings that don't match the specified format.
        """
        key = TimestampKey("test")
        # bad format
        with self.assertRaisesRegexp(TankError, "Invalid string"):
            key.value_from_str("1 2 3")
        # out of bound values
        with self.assertRaisesRegexp(TankError, "Invalid string"):
            key.value_from_str("2015-06-33-21-20-30")

        # Too much data
        with self.assertRaisesRegexp(TankError, "Invalid string"):
            key.value_from_str(self._datetime_string + "bad date")

    def test_bad_value(self):
        """
        Test with values that are not supported.
        """
        key = TimestampKey("test")
        with self.assertRaisesRegexp(TankError, "Invalid type"):
            key.str_from_value(1)

    @patch("tank.templatekey.TimestampKey._TimestampKey__get_current_time")
    def test_now_default_value(self,_get_time_mock):
        """
        Makes sure that a default value is proprely generated when the now default
        value is requested.
        """
        # Mock it to the expected date.
        _get_time_mock.return_value = self._datetime
        # Create the key
        key = TimestampKey("datetime", default="now")
        # Convert to a string and compare the result.
        self.assertEqual(key.str_from_value(None), self._datetime_string)

    @patch("tank.templatekey.TimestampKey._TimestampKey__get_current_utc_time")
    def test_utc_now_default_value(self, _get_utc_time_mock):
        """
        Makes sure that a default value is proprely generated when the utc_now default
        value is requested.
        """
        # Mock it to the expected date.
        _get_utc_time_mock.return_value = self._datetime
        # Create the key
        key = TimestampKey("datetime", default="utc_now")
        # Convert to a string and compare the result.
        self.assertEqual(key.str_from_value(None), self._datetime_string)

    def test_string_default_value(self):
        """
        Makes sure that a default value is proprely generated when a string default
        value is provided.
        """
        # Create a template using our key.
        key = TimestampKey("datetime", default=self._datetime_string)
        # Convert to a string and compare the result.
        self.assertEqual(key.str_from_value(None), self._datetime_string)
