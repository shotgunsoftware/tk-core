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
import sys
import datetime

from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import (
    mock,
    ShotgunTestBase,
)

from tank.templatekey import StringKey, IntegerKey, SequenceKey, TimestampKey, make_keys


class TestTemplateKey(ShotgunTestBase):
    """
    Tests functionality common to all key classes.
    """

    def test_override_default_at_runtime(self):
        pass
class TestStringKey(ShotgunTestBase):
    def setUp(self):
        super().setUp()
        self.str_field = StringKey("field_name")
        self.alphanum_field = StringKey("field_name", filter_by="alphanumeric")
        self.alpha_field = StringKey("field_name", filter_by="alpha")

        self.regex_field = StringKey(
            "field_name", filter_by="^[0-9]{3}@[a-z]+"
        )  # e.g 123@foo

        self.choice_field = StringKey("field_name", choices=["a", "b"])
        self.default_field = StringKey("field_name", default="b")

    def test_invalid(self):
        pass
    def test_default(self):
        pass
    def test_no_default(self):
        pass
    def test_choices(self):
        pass
    def test_exclusions(self):
        pass
    def test_illegal_choice_alphanumic(self):
        pass
    def test_default_choices_mismatch(self):
        pass
    def test_choices_exclusions_conflict(self):
        pass
    def test_name_set(self):
        pass
    def test_validate_string_good(self):
        pass
    def test_validate_alphanum_good(self):
        pass
    def test_validate_alphanum_bad(self):
        pass
    def test_validate_regex_good(self):
        pass
    def test_validate_regex_bad(self):
        pass
    def test_validate_alpha_good(self):
        pass
    def test_validate_alpha_bad(self):
        pass
    def test_str_from_value_good(self):
        pass
    def test_str_from_value_empty(self):
        pass
    def test_str_from_value_good_choice(self):
        pass
    def test_str_from_value_bad_choice(self):
        pass
    def test_str_from_value_use_default(self):
        pass
    def test_str_from_value_no_default(self):
        pass
    def test_str_from_value_alphanum_good(self):
        pass
    def test_str_from_value_alphanum_empty(self):
        pass
    def test_str_from_value_alphanum_bad(self):
        pass
    def test_str_from_value_ignore_type_alphanum(self):
        pass
    def test_str_from_value_alpha_good(self):
        pass
    def test_str_from_value_alpha_empty(self):
        pass
    def test_str_from_value_alpha_bad(self):
        pass
    def test_str_from_value_ignore_type_alpha(self):
        pass
    def test_str_from_value_regex_good(self):
        pass
    def test_str_from_value_regex_bad(self):
        pass
    def test_str_from_value_ignore_type_regex(self):
        pass
    def test_value_from_str(self):
        pass
    def test_shotgun_entity_type_set(self):
        pass
    def test_shotgun_field_name_without_entity_type(self):
        pass
    def test_shotgun_field_name_set(self):
        pass
    def test_repr(self):
        pass
    def test_subset(self):
        pass
    def test_subset_format(self):
        pass
class TestIntegerKey(ShotgunTestBase):
    def setUp(self):
        super().setUp()
        self.int_field = IntegerKey("field_name")

    def test_bad_default(self):
        pass
    def test_illegal_choice(self):
        pass
    def test_format_set(self):
        pass
    def test_validate_string_good(self):
        pass
    def test_validate_int_good(self):
        pass
    def test_validate_bad(self):
        pass
    def test_str_from_value_good(self):
        pass
    def test_str_from_value_zero(self):
        pass
    def test_str_from_value_bad(self):
        pass
    def test_str_from_value_formatted(self):
        pass
    def test_str_from_value_ignore_type(self):
        pass
    def test_value_from_str(self):
        pass
    def test_repr(self):
        pass
    def test_init_validation(self):
        pass
    def test_no_format_spec(self):
        pass
    def _validate_key(self, key, strict_matching, format_spec):
        """
        Makes sure that an integer key's formatting options are correctly set.
        """
        self.assertEqual(key.strict_matching, strict_matching)
        self.assertEqual(key.format_spec, format_spec)

    def test_non_strict_matching(self):
        pass
    def _test_non_strict_matching(self, padding_char):
        """
        Allows to test strict matching with a specific padding character.

        :param padding_char: Character to test padding with. Should be space or 0.
        """
        key = IntegerKey(
            "version_number", format_spec="%s3" % padding_char, strict_matching=False
        )

        # The padding char is missing in the format specifier, but we still need when validating
        # results.
        if padding_char == "":
            padding_char = " "

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
        self.assertEqual(
            "%s%s1" % (padding_char, padding_char), key.str_from_value(value)
        )

        self._test_nan(key, "expected an Integer")

    def _test_nan(self, key, error_msg):
        """
        Tests a key with against values that are not numbers.

        :param key: Key to test.
        :param error_msg: Text that partially matches the error message.
        """
        # Should fail because not a number
        with self.assertRaisesRegex(TankError, error_msg):
            key.value_from_str("aaaa")
        with self.assertRaisesRegex(TankError, error_msg):
            key.value_from_str("0a")
        with self.assertRaisesRegex(TankError, error_msg):
            key.value_from_str("a0")
        with self.assertRaisesRegex(TankError, error_msg):
            key.value_from_str("aa")

    def _test_strict_matching(self, padding_char):
        """
        Allows to test strict matching with any padding type.
        """
        # have a template that formats with two digits of padding.
        key = IntegerKey(
            "version_number", format_spec="%s3" % padding_char, strict_matching=True
        )
        self.assertTrue(key.strict_matching)

        # The padding char is missing in the format specifier, but we still need when validating
        # results.
        if padding_char == "":
            padding_char = " "

        # From path to tokens back to path should get back the same string when the expected number of
        # digits are found.
        value = key.value_from_str("%s%s1" % (padding_char, padding_char))
        self.assertEqual(
            "%s%s1" % (padding_char, padding_char), key.str_from_value(value)
        )

        # It should match a template with more digits.
        value = key.value_from_str("20000")
        self.assertEqual("20000", key.str_from_value(value))

        key.value_from_str("123")

        error_msg = "does not match format spec"

        # It should not match a string with too few digits
        with self.assertRaisesRegex(TankError, error_msg):
            key.value_from_str("1")

        # It should not match a template with too many digits that are all zero because that would
        # lossy. (there are more zeros than the format spec can rebuild)
        with self.assertRaisesRegex(TankError, error_msg):
            key.value_from_str("0000")

        # It should not match negative numbers either
        with self.assertRaisesRegex(TankError, error_msg):
            key.value_from_str("-1000")

        # It should not match baddly padded numbers
        with self.assertRaisesRegex(TankError, error_msg):
            key.value_from_str("0100")

        # It should not match negative values
        with self.assertRaisesRegex(TankError, error_msg):
            key.value_from_str("-01")

        self._test_nan(key, error_msg)

    def test_strict_matching(self):
        pass
class TestSequenceKey(ShotgunTestBase):
    def setUp(self):
        super().setUp()
        self.seq_field = SequenceKey("field_name")

    def test_framespec_no_format(self):
        pass
    def test_framspec_short_format(self):
        pass
    def test_framespec_long_format(self):
        pass
    def test_validate_good(self):
        pass
    def test_validate_bad(self):
        pass
    def test_value_from_str(self):
        pass
    def test_str_from_value_good(self):
        pass
    def test_str_from_value_bad(self):
        pass
    def test_str_from_value_formatted(self):
        pass
    def test_str_from_value_ignore_type(self):
        pass
    def test_str_from_value_default_one(self):
        pass
    def test_str_from_value_default_three(self):
        pass
    def test_str_from_value_format_whitespace(self):
        pass
    def test_default_int(self):
        pass
    def test_default_frame_spec(self):
        pass
    def test_default_frame_spec_choices(self):
        pass
    def test_default_bad(self):
        pass
    def test_choices_int(self):
        pass
    def test_choices_frame_spec(self):
        pass
class TestMakeKeys(ShotgunTestBase):
    def test_no_data(self):
        pass
    def test_string(self):
        pass
    def test_int(self):
        pass
    def test_sequence(self):
        pass
    def test_shotgun_fields(self):
        pass
    def test_bad_format(self):
        pass
    def test_bad_type(self):
        pass
    def test_aliases(self):
        pass
class TestEyeKey(ShotgunTestBase):
    """
    Tests that key representing eye can be setup.
    """

    def setUp(self):
        super().setUp()
        self.eye_key = StringKey("eye", default="%V", choices=["%V", "L", "R"])
        self.default_value = "%V"

    def test_validate(self):
        pass
    def test_str_from_value_default(self):
        pass
    def test_set_choices(self):
        pass
class TestTimestampKey(ShotgunTestBase):
    """
    Test timestamp key type.
    """

    def setUp(self):
        """
        Creates a bunch of dates and strings for testing.
        """
        super().setUp()
        self._datetime = datetime.datetime(2015, 6, 24, 21, 20, 30)
        self._datetime_string = "2015-06-24-21-20-30"

    def test_default_values(self):
        pass
    def test_init(self):
        pass
    def test_str_from_value(self):
        pass
    def test_value_from_str(self):
        pass
    def test_bad_str(self):
        pass
    def test_bad_value(self):
        pass
    @mock.patch("tank.templatekey.TimestampKey._TimestampKey__get_current_time")
    def test_now_default_value(self, _get_time_mock):
        pass
    @mock.patch("tank.templatekey.TimestampKey._TimestampKey__get_current_utc_time")
    def test_utc_now_default_value(self, _get_utc_time_mock):
        pass
    def test_string_default_value(self):
        pass
