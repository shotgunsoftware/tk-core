# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import copy
import os
import time
import sys

import unittest
import tank
from tank import TankError
from tank_test.tank_test_base import TankTestBase, ShotgunTestBase, setUpModule  # noqa
from tank.template import Template, TemplatePath, TemplateString
from tank.template import make_template_paths, make_template_strings
from tank.templatekey import (
    TemplateKey,
    StringKey,
    IntegerKey,
    SequenceKey,
    TimestampKey,
)


class TestTemplate(unittest.TestCase):
    """Base class for tests of Template.
    Do no add tests to this class directly."""

    def setUp(self):
        pass
class TestInit(TestTemplate):
    def test_definition_read_only(self):
        pass
    def test_default_enum_whitespace(self):
        pass
    def test_default_period(self):
        pass
    def test_confilicting_key_names(self):
        pass
    def test_key_alias(self):
        pass
    def test_illegal_optional(self):
        pass
class TestRepr(TestTemplate):
    def test_template(self):
        pass
    def test_optional(self):
        pass
    def test_no_name(self):
        pass
class TestKeys(TestTemplate):
    def test_keys_type(self):
        pass
    def test_existing_key(self):
        pass
    def test_missing_key(self):
        pass
    def test_mixed_keys(self):
        pass
    def test_copy(self):
        pass
class TestMissingKeys(TestTemplate):
    def test_no_keys_missing(self):
        pass
    def test_all_keys_missing(self):
        pass
    def test_empty_fields(self):
        pass
    def test_some_keys_missing(self):
        pass
    def test_default_disabled(self):
        pass
    def test_default_enabled(self):
        pass
    def test_aliased_key(self):
        pass
    def test_optional_values(self):
        pass
    def test_value_none(self):
        pass
class TestSplitPath(unittest.TestCase):
    def test_mixed_sep(self):
        pass
class TestMakeTemplatePaths(ShotgunTestBase):
    def setUp(self):
        pass
    def test_simple(self):
        pass
    def test_complex(self):
        pass
    def test_duplicate_definitions_simple(self):
        pass
    def test_duplicate_definitions_complex(self):
        pass
    def test_dup_def_diff_roots(self):
        pass
class TestMakeTemplateStrings(ShotgunTestBase):
    def setUp(self):
        pass
    def test_simple(self):
        pass
    def test_complex(self):
        pass
    def test_duplicate_definitions(self):
        pass
    def test_validate_with_set(self):
        pass
    def test_validate_template_missing(self):
        pass
class TestReadTemplates(TankTestBase):
    """Test reading templates file."""

    def setUp(self):
        pass
    def test_choices(self):
        pass
    def test_exclusions(self):
        pass
    def test_read_simple(self):
        pass
    def test_aliased_key(self):
        pass
