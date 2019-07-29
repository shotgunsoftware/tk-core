# -*- coding: utf-8 -*-
# Copyright (c) 2018 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import tempfile
import json

from unittest2 import TestCase
from sgtk.util import json as tk_json


class JSONTests(TestCase):
    """
    Ensures unserializing json from file or a string will always yield
    str objects instead of unicode.
    """

    kanji = str("漢字")

    def _value_to_string_to_value(self, value):
        """
        Dumps a value to a json formatted string and reloads it.

        :param value: Value to dump to a string.

        :returns: Value that was loaded back from the string.
        """
        return tk_json.loads(json.dumps(value))

    def _value_to_file_to_value(self, value):
        """
        Dumps a value to a json formatted file and reloads it.

        :param value: Value to dump to a file.

        :returns: Value that was loaded back from the file.
        """
        with tempfile.TemporaryFile() as fp:
            json.dump(value, fp)
            # Return at the beginning of the file so the load method can read
            # something.
            fp.seek(0)
            return tk_json.load(fp)

    def _assert_no_unicode(self, value):
        """
        Ensures there is no unicode anywhere inside the value.

        Just make sure there the string "u'" is not in the original value. ;)
        """
        # Get the repr of the value. If there is a unicode string,
        # we'll get a u'value' somewhere in the output, which means
        # there is a unicode string.
        if "u'" in repr(value):
            raise Exception("unicode string found in %r" % value)

    def test_repr_generates_u_strings(self):
        """
        Ensures the unicode detection method actually works.
        """
        self._assert_no_unicode({})
        self._assert_no_unicode(1)
        self._assert_no_unicode(False)
        self._assert_no_unicode(None)
        self._assert_no_unicode(self.kanji)
        self._assert_no_unicode({"k": "v"})

        with self.assertRaisesRegex(Exception, "unicode string found in u'allo'"):
            self._assert_no_unicode(u"allo")

    def test_scalar_values(self):
        """
        Ensures we can properly encode scalar values.
        """
        # Integer
        self._assert_no_unicode_after_load(1)
        # BigNum
        self._assert_no_unicode_after_load(100000000000000000000000)
        # Floats
        self._assert_no_unicode_after_load(1.0)
        # Booleans
        self._assert_no_unicode_after_load(True)
        self._assert_no_unicode_after_load(False)
        # None
        self._assert_no_unicode_after_load(None)
        # Strings
        self._assert_no_unicode_after_load("a")
        self._assert_no_unicode_after_load(u"b")
        self._assert_no_unicode_after_load(self.kanji)

    def test_array_values(self):
        """
        Ensure we can properly encode an array.
        """
        self._assert_no_unicode_after_load([
            1, 100000000000000000000000, 1.0, True, False, None,
            {"a": "b", u"c": u"d"},
            "e", u"f"
        ])

    def test_dict_value(self):
        """
        Ensures we can properly encode a dictionary.
        """
        self._assert_no_unicode_after_load({})
        self._assert_no_unicode_after_load({"a": "b", u"c": u"d"})
        self._assert_no_unicode_after_load({
            "e": ["f"], u"g": [u"h"]
        })
        self._assert_no_unicode_after_load({
            "i": [{"j": ["k"]}],
            u"l": [{u"m": [u"n"]}],
        })

    def _assert_no_unicode_after_load(self, original_value, converter=None):
        """
        Ensures the values are the same after the serialize/unserialize and that the
        strings are all str and not unicode objects.
        """
        # We need to test serialization to disk and to string for the input.
        for converter in [self._value_to_string_to_value, self._value_to_file_to_value]:
            converted_value = converter(original_value)

            self._assert_no_unicode(converted_value)
            self.assertEqual(original_value, converted_value)
