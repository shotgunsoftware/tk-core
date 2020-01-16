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

import unittest2
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

from tank_vendor.shotgun_api3.lib import sgsix


class TestTemplate(unittest2.TestCase):
    """Base class for tests of Template.
    Do no add tests to this class directly."""

    def setUp(self):
        super(TestTemplate, self).setUp()

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
        template = Template("some/definition", self.keys)
        self.assertRaises(AttributeError, setattr, template, "definition", "other")

    def test_default_enum_whitespace(self):
        self.keys["S hot"] = StringKey("S hot")
        template = Template("/something/{S hot}/something", self.keys)
        self.assertEqual(self.keys["S hot"], template.keys["S hot"])

    def test_default_period(self):
        self.keys["S.hot"] = StringKey("S.hot")
        template = Template("/something/{S.hot}/something", self.keys)
        self.assertEqual(self.keys["S.hot"], template.keys["S.hot"])

    def test_confilicting_key_names(self):
        """
        Two keys used in the same definition, both with the same alias.
        """
        alt_key = StringKey("Shot")
        self.keys["Alt_Shot"] = alt_key
        definition = "something/{Alt_Shot}/{Shot}"
        self.assertRaises(TankError, Template, definition, self.keys)

    def test_key_alias(self):
        """
        Test that key's aliased name is used in template.keys dict.
        """
        key = StringKey("alias_name")
        self.keys["not_alias_name"] = key
        definition = "something/{not_alias_name}"
        template = Template(definition, self.keys)
        template_key = template.keys["alias_name"]
        self.assertEqual(key, template_key)
        self.assertEqual("something/{alias_name}", template.definition)

    def test_illegal_optional(self):
        """
        Test that illegal option in definition is detected.
        """
        definition = "/some[thing]"
        self.assertRaises(TankError, Template, definition, self.keys)

        definition = "/some[thing{Shot}"
        self.assertRaises(TankError, Template, definition, self.keys)

        definition = "/something{Shot}]"
        self.assertRaises(TankError, Template, definition, self.keys)


class TestRepr(TestTemplate):
    def test_template(self):
        template_name = "template_name"
        template = Template(self.definition, self.keys, name=template_name)
        expected = "<Sgtk Template %s: %s>" % (template_name, self.definition)
        self.assertEqual(expected, template.__repr__())

    def test_optional(self):
        template_name = "tempalte_name"
        definition = "something/{Shot}[/{Step}]"
        template = Template(definition, self.keys, name=template_name)
        expected = "<Sgtk Template %s: %s>" % (template_name, definition)
        self.assertEqual(expected, template.__repr__())

    def test_no_name(self):
        template = Template(self.definition, self.keys, "")
        expected = "<Sgtk Template %s>" % self.definition
        self.assertEqual(expected, template.__repr__())


class TestKeys(TestTemplate):
    def test_keys_type(self):
        for key in self.template.keys.values():
            self.assertTrue(isinstance(key, TemplateKey))

    def test_existing_key(self):
        key_name = "Sequence"
        key = self.template.keys[key_name]
        self.assertEqual(key_name, key.name)

    def test_missing_key(self):
        key_name = "not a key"
        key = self.template.keys.get(key_name, None)
        self.assertIsNone(key)

    def test_mixed_keys(self):
        expected = [
            "Sequence",
            "Shot",
            "Step",
            "branch",
            "version",
            "snapshot",
            "day_month_year",
        ]
        # no predictable order
        self.assertEqual(set(self.template.keys), set(expected))

    def test_copy(self):
        client_copy = self.template.keys
        # modify it
        client_copy["new_key"] = "new value"
        self.assertNotEqual(self.template.keys, client_copy)


class TestMissingKeys(TestTemplate):
    def test_no_keys_missing(self):
        fields = {
            "Sequence": "seq_1",
            "Shot": "shot_1",
            "Step": "Anm",
            "branch": "mmm",
            "version": 3,
            "snapshot": 2,
            "day_month_year": time.gmtime(),
        }
        expected = []
        result = self.template.missing_keys(fields)
        self.assertEqual(set(result), set(expected))

    def test_all_keys_missing(self):
        fields = {"Sandwhich": "Mmmmmm"}
        expected = [
            "Sequence",
            "Shot",
            "Step",
            "branch",
            "version",
            "snapshot",
            "day_month_year",
        ]
        result = self.template.missing_keys(fields)
        # no predictable order
        self.assertEqual(set(result), set(expected))

    def test_empty_fields(self):
        fields = {}
        expected = [
            "Sequence",
            "Shot",
            "Step",
            "branch",
            "version",
            "snapshot",
            "day_month_year",
        ]
        result = self.template.missing_keys(fields)
        # no predictable order
        self.assertEqual(set(result), set(expected))

    def test_some_keys_missing(self):
        fields = {"Sandwhich": "Mmmmmm", "Shot": "shot_22"}
        expected = [
            "Sequence",
            "Step",
            "branch",
            "version",
            "snapshot",
            "day_month_year",
        ]
        result = self.template.missing_keys(fields)
        # no predictable order
        self.assertEqual(set(result), set(expected))

    def test_default_disabled(self):
        template = Template("{Shot}/{Step}", self.keys)
        fields = {"Step": "Anm"}
        expected = ["Shot"]
        result = template.missing_keys(fields)
        self.assertEqual(expected, result)

    def test_default_enabled(self):
        template = Template("{Shot}/{Step}", self.keys)
        fields = {"Step": "Anm"}
        expected = []
        result = template.missing_keys(fields, skip_defaults=True)
        self.assertEqual(expected, result)

    def test_aliased_key(self):
        key = StringKey("aliased_name")
        self.keys["initial_name"] = key
        definition = "something/{Shot}/{initial_name}"
        template = Template(definition, self.keys)
        fields = {"aliased_name": "some value", "Shot": "shot value"}
        result = template.missing_keys(fields)
        self.assertEqual([], result)
        fields = {"initial_name": "some_value", "Shot": "shot value"}
        result = template.missing_keys(fields)
        self.assertEqual(["aliased_name"], result)

    def test_optional_values(self):
        """
        Test that optional keys do not appear as missing.
        """
        definition = "shots/[{Sequence}]/{Shot}/{Step}/work/{Shot}.{branch}[.v{version}][.{snapshot}].ma"
        template = Template(definition, self.keys)
        fields = {"Shot": "shot value", "Step": "step value", "branch": "branch value"}

        # all optional fields skipped
        result = template.missing_keys(fields)
        self.assertEqual([], result)

        # value allowed for optional field
        fields["snapshot"] = "snapshot value"
        result = template.missing_keys(fields)
        self.assertEqual([], result)

        # required field missing
        del fields["Shot"]
        result = template.missing_keys(fields)
        self.assertEqual(["Shot"], result)

    def test_value_none(self):
        """
        Test that if key value is None, the field is treated as missing.
        """
        fields = {
            "Sequence": "seq_1",
            "Shot": None,
            "Step": "Anm",
            "branch": "mmm",
            "version": 3,
            "snapshot": 2,
            "day_month_year": time.gmtime(),
        }
        result = self.template.missing_keys(fields)
        self.assertEqual(["Shot"], result)


class TestSplitPath(unittest2.TestCase):
    def test_mixed_sep(self):
        "tests that split works with mixed seperators"
        input_path = r"hoken/poken\moken//doken"
        expected = ["hoken", "poken", "moken", "doken"]
        result = tank.template.split_path(input_path)
        self.assertEqual(expected, result)


class TestMakeTemplatePaths(ShotgunTestBase):
    def setUp(self):
        super(TestMakeTemplatePaths, self).setUp()
        self.keys = {"Shot": StringKey("Shot")}
        self.multi_os_data_roots = {
            "unit_tests": {
                "win32": os.path.join(self.tank_temp, "project_code"),
                "linux2": os.path.join(self.tank_temp, "project_code"),
                "darwin": os.path.join(self.tank_temp, "project_code"),
            }
        }

    def test_simple(self):
        data = {"template_name": "something/{Shot}"}
        result = make_template_paths(
            data, self.keys, self.multi_os_data_roots, default_root="unit_tests"
        )
        template_path = result.get("template_name")
        self.assertIsInstance(template_path, TemplatePath)
        self.assertEqual(self.keys.get("Shot"), template_path.keys.get("Shot"))

    def test_complex(self):
        data = {"template_name": {"definition": "something/{Shot}"}}
        result = make_template_paths(
            data, self.keys, self.multi_os_data_roots, default_root="unit_tests"
        )
        template_path = result.get("template_name")
        self.assertIsInstance(template_path, TemplatePath)
        self.assertEqual(self.keys.get("Shot"), template_path.keys.get("Shot"))

    def test_duplicate_definitions_simple(self):
        data = {
            "template_name": "something/{Shot}",
            "another_template": "something/{Shot}",
        }
        self.assertRaises(
            TankError, make_template_paths, data, self.keys, self.multi_os_data_roots
        )

    def test_duplicate_definitions_complex(self):
        data = {
            "template_name": {"definition": "something/{Shot}"},
            "another_template": {"definition": "something/{Shot}"},
        }
        self.assertRaises(
            TankError, make_template_paths, data, self.keys, self.multi_os_data_roots
        )

    def test_dup_def_diff_roots(self):

        # add another root
        modified_roots = copy.copy(self.multi_os_data_roots)

        modified_roots["alternate_1"] = {}
        modified_roots["alternate_1"]["win32"] = "z:\\some\\fake\\path"
        modified_roots["alternate_1"]["linux2"] = "/some/fake/path"
        modified_roots["alternate_1"]["darwin"] = "/some/fake/path"

        # Test with root names specified for all templates
        data = {
            "template_name": {
                "definition": "something/{Shot}",
                "root_name": self.primary_root_name,
            },
            "another_template": {
                "definition": "something/{Shot}",
                "root_name": "alternate_1",
            },
        }

        result = make_template_paths(
            data, self.keys, modified_roots, default_root=self.primary_root_name
        )
        prim_template = result.get("template_name")
        alt_templatte = result.get("another_template")
        self.assertEqual(self.project_root, prim_template.root_path)
        self.assertEqual(
            modified_roots["alternate_1"][sgsix.platform], alt_templatte.root_path
        )

        # Now test with the primary root name not specified, tk-core will assume
        # a "primary" root name, so make sure we have one.
        if self.primary_root_name != "primary":
            modified_roots["primary"] = modified_roots.pop(self.primary_root_name)
        data = {
            "template_name": {"definition": "something/{Shot}"},
            "another_template": {
                "definition": "something/{Shot}",
                "root_name": "alternate_1",
            },
        }
        result = make_template_paths(
            data, self.keys, modified_roots, default_root="primary"
        )
        prim_template = result.get("template_name")
        alt_templatte = result.get("another_template")
        self.assertEqual(self.project_root, prim_template.root_path)
        self.assertEqual(
            modified_roots["alternate_1"][sgsix.platform], alt_templatte.root_path
        )


class TestMakeTemplateStrings(ShotgunTestBase):
    def setUp(self):
        super(TestMakeTemplateStrings, self).setUp()
        self.keys = {"Shot": StringKey("Shot")}
        self.template_path = TemplatePath(
            "something/{Shot}", self.keys, self.project_root
        )
        self.template_paths = {"template_path": self.template_path}

    def test_simple(self):
        data = {"template_name": "something.{Shot}"}
        result = make_template_strings(data, self.keys, self.template_paths)
        template_string = result.get("template_name")
        self.assertIsInstance(template_string, TemplateString)
        self.assertEqual("template_name", template_string.name)

    def test_complex(self):
        data = {"template_name": {"definition": "something.{Shot}"}}
        result = make_template_strings(data, self.keys, self.template_paths)
        template_string = result.get("template_name")
        self.assertIsInstance(template_string, TemplateString)
        self.assertEqual("template_name", template_string.name)

    def test_duplicate_definitions(self):
        data = {"template_one": "something.{Shot}", "template_two": "something.{Shot}"}
        self.assertRaises(
            TankError, make_template_strings, data, self.keys, self.template_paths
        )

    def test_validate_with_set(self):
        data = {
            "template_name": {
                "definition": "something.{Shot}",
                "validate_with": "template_path",
            }
        }
        result = make_template_strings(data, self.keys, self.template_paths)
        template_string = result.get("template_name")
        self.assertEqual(self.template_path, template_string.validate_with)

    def test_validate_template_missing(self):
        data = {
            "template_name": {
                "definition": "something.{Shot}",
                "validate_with": "non-exitant-template",
            }
        }
        self.assertRaises(
            TankError, make_template_strings, data, self.keys, self.template_paths
        )


class TestReadTemplates(TankTestBase):
    """Test reading templates file."""

    def setUp(self):
        super(TestReadTemplates, self).setUp()
        self.setup_fixtures()

    def test_choices(self):
        """Check a template key which uses choices."""
        # check old-style (list) choices
        key = self.tk.templates["nuke_shot_render_stereo"].keys["eye"]
        # Order of the choices is not guaranteed, so enforce it.
        self.assertEqual(["Left", "Right"], sorted(key.choices))
        self.assertEqual({"Right": "Right", "Left": "Left"}, key.labelled_choices)

        # check new-style (dict) choices
        key = self.tk.templates["maya_shot_work"].keys["maya_extension"]
        # Order of the choices is not guaranteed, so enforce it.
        self.assertEqual(["ma", "mb"], sorted(key.choices))
        self.assertEqual(
            {"ma": "Maya Ascii (.ma)", "mb": "Maya Binary (.mb)"}, key.labelled_choices
        )

    def test_exclusions(self):
        key = self.tk.templates["asset_work_area"].keys["Asset"]
        self.assertEqual(["Seq", "Shot"], key.exclusions)

    def test_read_simple(self):
        """
        Test no error occur during read and that some known
        template is created correctly.
        """
        maya_publish_name = self.tk.templates["maya_publish_name"]
        self.assertIsInstance(maya_publish_name, TemplateString)
        for key_name in ["name", "version"]:
            self.assertIn(key_name, maya_publish_name.keys)

    def test_aliased_key(self):
        # this template has the key name_alpha aliased as name
        houdini_asset_publish = self.tk.templates["houdini_asset_publish"]
        self.assertIsInstance(houdini_asset_publish, TemplatePath)
        for key_name in ["sg_asset_type", "Asset", "Step", "name", "version"]:
            self.assertIn(key_name, houdini_asset_publish.keys)
