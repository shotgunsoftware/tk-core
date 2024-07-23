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

from unittest import TestCase, skipIf
import sgtk
from tank_vendor import six

if six.PY2:
    char = "漢字"
    unichar = unicode(char, encoding="utf8")


class TestUnicode(TestCase):
    @skipIf(six.PY3, "Unicode data type does not exist on Python 3.")
    def test_convert_to_str(self):
        """
        Ensure all values are property converted to str with utf-8 strings
        in Python.
        """
        value = {unichar: [unichar, {unichar: unichar}], "char": unichar}
        expected = {char: [char, {char: char}], "char": char}
        self.assertEqual(sgtk.util.unicode.ensure_contains_str(value), expected)

    def test_dict_back_reference_do_not_loop_forever(self):
        """
        Ensure cycles involving dicts do not cause problems.
        """
        # Create a dictionary with a circular reference it itself.
        original = {}
        original["key"] = original

        # Take a reference of the original key and the value associated
        # to it.
        original_value = original["key"]

        # We'll now convert the object.
        converted = sgtk.util.unicode.ensure_contains_str(original)

        # Make sure we're still using the same dictionary as before.
        self.assertEqual(id(original), id(converted))
        # Make sure that we're still referencing the same original array.
        self.assertEqual(id(original_value), id(converted["key"]))

    def test_list_back_reference_do_not_loop_forever(self):
        """
        Ensure cycles involving arrays do not cause problems.
        """
        # Create an array with a circular reference.
        value = ["item"]
        value.append(value)

        converted_value = sgtk.util.unicode.ensure_contains_str(value)

        # We should still be dealing with the same array
        self.assertEqual(id(value), id(converted_value))
        # The second element should always be pointing back to the original
        # array object.
        self.assertEqual(id(value), id(converted_value[1]))

    def test_tuple_are_converted(self):
        """
        Ensure tuples are properly iterated on and converted.
        """
        # Create an array with a circular reference.
        value = ["item"]
        a_tuple = (value, value, value)
        value.append(a_tuple)

        converted_value = sgtk.util.unicode.ensure_contains_str(value)

        # We should still have a tuple at position 1.
        self.assertIsInstance(converted_value[1], tuple)
        # Each item of the tuple should be the same instance
        self.assertEqual(id(value), id(converted_value[1][0]))
        self.assertEqual(id(value), id(converted_value[1][1]))
        self.assertEqual(id(value), id(converted_value[1][2]))

    def test_convert_to_str_with_different_languages(self):
        """
        Ensure all values encoded with ISO-8859-1 are properly converted to str
        in Python 2 and 3.
        """
        logins = [
            'AñoVolvió',
            'JiříVyčítal',
            '日本のユーザー*',
            '이사이트에서는개발자가',
            'およびその他の教育リソース'
            '工作流技术总监或将要设置工作流并希望开发',
            'Martin Tlustý',
        ]

        for login in logins:
            expected_value = {
                'type': 'SessionUser',
                'data': {
                    'http_proxy': None,
                    'host': 'https://xyxyxyxyx.jjj',
                    'login': login,
                    'session_token': 'de97e6ff868b6b2ce332',
                    'session_metadata': 'G9kZXNrLmNvbTsgcGF0aD0v'
                }
            }

            dumps_value = sgtk.util.pickle.dumps(expected_value)
            received_value = sgtk.util.pickle.loads(dumps_value)
            self.assertEqual(expected_value, received_value)
