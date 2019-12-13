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

from unittest2 import TestCase, skipIf
import sgtk
from tank_vendor.shotgun_api3.lib import six

char = "漢字"
unichar = unicode(char, encoding="utf8")

class TestUnicode(TestCase):

    skipIf(six.PY3, "Unicode data type does not exist on Python 3.")
    def test_convert_to_str(self):
        
        value = {
            unichar: [unichar, {unichar: unichar}],
            "char": unichar
        }

        expected = {
            char: [char, {char: char}],
            "char": char
        }

        self.assertEqual(
            sgtk.util.unicode.ensure_contains_str(value),
            expected
        )

    def test_dict_back_reference_do_not_loop_forever(self):

        value = {}
        value[unichar] = value

        expected = {}
        expected[char] = expected

        self.assertEqual(
            sgtk.util.unicode.ensure_contains_str(value),
            expected
        )

        self.assertEqual(id(value), id(expected))
        self.assertNotEqual(
            id(list(value.keys())[0]),
            id(list(expected.keys())[0])
        )
        self.assertEqual(id(value[unichar]), id(expected[char]))

    def test_list_back_reference_do_not_loop_forever(self):

        value = [unichar]
        value.append(value)

        expected = [unichar]
        expected.append(unichar)

        self.assertEqual(
            sgtk.util.unicode.ensure_contains_str(value),
            expected
        )

        self.assertEqual(id(value), id(expected))
        self.assertNotEqual(id(value[0]), id(expected[0]))
        self.assertEqual(id(value[1]), id(expected[1]))





