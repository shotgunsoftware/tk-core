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
        super().setUp()

        # Make various types of keys(fields)
        self.keys = {
            "Sequence": StringKey("Sequence"),
            "Shot": StringKey("Shot", default="s1", choices=["s1", "s2", "shot_1"]),
            "Step": StringKey("Step"),
            "branch": StringKey("branch", filter_by="alphanumeric"),
            "name": StringKey("name"),
            "version": IntegerKey("version", format_spec="03"),
            "snapshot": IntegerKey("snapshot", format_spec="03"),
            "ext": StringKey("ext"),
            "seq_num": SequenceKey("seq_num"),
            "frame": SequenceKey("frame", format_spec="04"),
            "day_month_year": TimestampKey("day_month_year", format_spec="%d_%m_%Y"),
        }
        # Make a template
        self.definition = "shots/{Sequence}/{Shot}/{Step}/work/{Shot}.{branch}.v{version}.{snapshot}.{day_month_year}.ma"
        self.template = Template(self.definition, self.keys)


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
        super().setUp()
        self.keys = {"Shot": StringKey("Shot")}
        self.multi_os_data_roots = {
            "unit_tests": {
                "win32": os.path.join(self.tank_temp, "project_code"),
                "linux": os.path.join(self.tank_temp, "project_code"),
                "darwin": os.path.join(self.tank_temp, "project_code"),
            }
        }

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
        super().setUp()
        self.keys = {"Shot": StringKey("Shot")}
        self.template_path = TemplatePath(
            "something/{Shot}", self.keys, self.project_root
        )
        self.template_paths = {"template_path": self.template_path}

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
        super().setUp()
        self.setup_fixtures()

    def test_choices(self):
        pass
    def test_exclusions(self):
        pass
    def test_read_simple(self):
        pass
    def test_aliased_key(self):
        pass
