# -*- coding: utf-8 -*-
# Copyright (c) 2020 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from unittest import TestCase
import re
from tank.util import sgre


class TestSgre(TestCase):
    def test_wrap(self):
        r"""
        Ensure that sgre injects the re.ASCII flag appropriately, and that
        unicode characters do not match `\w` in Python 2 or 3.
        """
        char = u"漢字"
        expr = r"\w+"

        # test all wrapped methods
        self.assertFalse(bool(sgre.compile(expr).match(char)))
        self.assertEqual(len(sgre.findall(expr, char)), 0)
        self.assertFalse(bool(sgre.match(expr, char)))
        self.assertFalse(bool(sgre.search(expr, char)))
        self.assertEqual(len(sgre.split(expr, "$ %s @" % char)), 1)
        self.assertEqual(sgre.sub(expr, "@", char), char)

    def test_wrap_positional(self):
        r"""
        Ensure that sgre injects the re.ASCII flag appropriately when flags are
        also passed positonally, and that unicode characters do not match `\w`
        in Python 2 or 3.
        """
        char = u"a漢字"
        expr = r"a\w+"

        # test all wrapped methods
        self.assertFalse(bool(sgre.compile(expr, re.I).match(char)))
        self.assertEqual(len(sgre.findall(expr, char, re.I)), 0)
        self.assertFalse(bool(sgre.match(expr, char, re.I)))
        self.assertFalse(bool(sgre.search(expr, char, re.I)))
        self.assertEqual(len(sgre.split(expr, "$ %s @" % char, 0, re.I)), 1)
        self.assertEqual(sgre.sub(expr, "@", char, 0, re.I), char)

    def test_wrap_kwarg(self):
        r"""
        Ensure that sgre injects the re.ASCII flag appropriately when flags are
        also passed as keyword arguments, and that unicode characters do not
        match `\w` in Python 2 or 3.
        """
        char = u"a漢字"
        expr = r"a\w+"

        # test all wrapped methods
        self.assertFalse(bool(sgre.compile(expr, flags=re.I).match(char)))
        self.assertEqual(len(sgre.findall(expr, char, flags=re.I)), 0)
        self.assertFalse(bool(sgre.match(expr, char, flags=re.I)))
        self.assertFalse(bool(sgre.search(expr, char, flags=re.I)))
        self.assertEqual(len(sgre.split(expr, "$ %s @" % char, flags=re.I)), 1)
        self.assertEqual(sgre.sub(expr, "@", char, flags=re.I), char)

    def test_unicode_override(self):
        """
        Ensure that the unicode flag overrides the flag insertion behavior.
        """
        char = u"a漢字"
        expr = r"a\w+"

        # test all wrapped methods
        self.assertTrue(bool(sgre.compile(expr, flags=re.U).match(char)))
        self.assertEqual(len(sgre.findall(expr, char, flags=re.U)), 1)
        self.assertTrue(bool(sgre.match(expr, char, flags=re.U)))
        self.assertTrue(bool(sgre.search(expr, char, flags=re.U)))
        self.assertEqual(len(sgre.split(expr, "$ %s @" % char, flags=re.U)), 2)
        self.assertEqual(sgre.sub(expr, "@", char, flags=re.U), "@")

    def test_precompiled_expression(self):
        """
        Ensure that no flag injection is performed when using a compiled
        expression, as this raises an exception.
        """
        compiled_expression = sgre.compile("a")
        self.assertTrue(bool(compiled_expression.match("a")))
