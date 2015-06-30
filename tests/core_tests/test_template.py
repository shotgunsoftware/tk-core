# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

from __future__ import with_statement
import os

import tank
from tank import TankError
from tank_test.tank_test_base import *
from tank.template import Template, TemplatePath, TemplateString
from tank.template import make_template_paths, make_template_strings, read_templates
from tank.templatekey import (TemplateKey, StringKey, IntegerKey, SequenceKey)

class TestTemplate(TankTestBase):
    """Base class for tests of Template.
    Do no add tests to this class directly."""
    def setUp(self):
        super(TestTemplate, self).setUp()

        # Make various types of keys(fields)
        self.keys = {"Sequence": StringKey("Sequence"),
                     "Shot": StringKey("Shot", default="s1", choices=["s1","s2","shot_1"]),
                     "Step": StringKey("Step"),
                     "branch": StringKey("branch", filter_by="alphanumeric"),
                     "name": StringKey("name"),
                     "version": IntegerKey("version", format_spec="03"),
                     "snapshot": IntegerKey("snapshot", format_spec="03"),
                     "ext": StringKey("ext"),
                     "seq_num": SequenceKey("seq_num"),
                     "frame": SequenceKey("frame", format_spec="04")}
        # Make a template
        self.definition = "shots/{Sequence}/{Shot}/{Step}/work/{Shot}.{branch}.v{version}.{snapshot}.ma"
        self.template = Template(self.definition, self.keys)



class TestInit(TestTemplate):
    def test_definition_read_only(self):
        template = Template("some/definition", self.keys)
        self.assertRaises(AttributeError, setattr, template, "definition", "other")

    def test_default_enum_whitespace(self):
        self.keys["S hot"] = StringKey("S hot")
        template = Template("/something/{S hot}/something", self.keys)
        self.assertEquals(self.keys["S hot"], template.keys["S hot"])

    def test_default_period(self):
        self.keys["S.hot"] = StringKey("S.hot")
        template = Template("/something/{S.hot}/something", self.keys)
        self.assertEquals(self.keys["S.hot"], template.keys["S.hot"])

    def test_confilicting_key_names(self):
        """
        Two keys used in the same definition, both with the same alias.
        """
        alt_key = StringKey("Shot")
        self.keys["Alt_Shot"] = alt_key
        definition =  "something/{Alt_Shot}/{Shot}"
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
        self.assertEquals(key, template_key)
        self.assertEquals("something/{alias_name}", template.definition)

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
        self.assertEquals(expected, template.__repr__())

    def test_optional(self):
        template_name = "tempalte_name"
        definition = "something/{Shot}[/{Step}]"
        template = Template(definition, self.keys, name=template_name) 
        expected = "<Sgtk Template %s: %s>" % (template_name, definition)
        self.assertEquals(expected, template.__repr__())

    def test_no_name(self):
        template = Template(self.definition, self.keys, "")
        expected = "<Sgtk Template %s>" % self.definition
        self.assertEquals(expected, template.__repr__())

        

class TestKeys(TestTemplate):
    def test_keys_type(self):
        for key in self.template.keys.values():
            self.assertTrue(isinstance(key, TemplateKey))

    def test_existing_key(self):
        key_name = "Sequence"
        key = self.template.keys[key_name]
        self.assertEquals(key_name, key.name)

    def test_missing_key(self):
        key_name = "not a key"
        key = self.template.keys.get(key_name, None)
        self.assertIsNone(key)

    def test_mixed_keys(self):
        expected = ["Sequence", "Shot", "Step", "branch", "version", "snapshot"]
        # no predictable order
        self.assertEquals(set(self.template.keys), set(expected))

    def test_copy(self):
        client_copy = self.template.keys
        # modify it
        client_copy["new_key"] = "new value"
        self.assertNotEqual(self.template.keys, client_copy)

class TestMissingKeys(TestTemplate):

    def test_no_keys_missing(self):
        fields = {"Sequence": "seq_1",
                   "Shot": "shot_1",
                   "Step": "Anm",
                   "branch":"mmm",
                   "version": 3,
                   "snapshot": 2}
        expected = []
        result = self.template.missing_keys(fields)
        self.assertEquals(set(result), set(expected))

    def test_all_keys_missing(self):
        fields = {"Sandwhich": "Mmmmmm"}
        expected = ["Sequence", "Shot", "Step", "branch", "version", "snapshot"]
        result = self.template.missing_keys(fields)
        # no predictable order
        self.assertEquals(set(result), set(expected))

    def test_empty_fields(self):
        fields = {}
        expected = ["Sequence", "Shot", "Step", "branch", "version", "snapshot"]
        result = self.template.missing_keys(fields)
        # no predictable order
        self.assertEquals(set(result), set(expected))

    def test_some_keys_missing(self):
        fields = {"Sandwhich": "Mmmmmm", "Shot": "shot_22"}
        expected = ["Sequence", "Step", "branch", "version", "snapshot"]
        result = self.template.missing_keys(fields)
        # no predictable order
        self.assertEquals(set(result), set(expected))

    def test_default_disabled(self):
        template = Template("{Shot}/{Step}", self.keys)
        fields = {"Step":"Anm"}
        expected = ["Shot"]
        result = template.missing_keys(fields)
        self.assertEquals(expected, result)

    def test_default_enabled(self):
        template = Template("{Shot}/{Step}", self.keys)
        fields = {"Step":"Anm"}
        expected = []
        result = template.missing_keys(fields, skip_defaults=True)
        self.assertEquals(expected, result)

    def test_aliased_key(self):
        key = StringKey("aliased_name")
        self.keys["initial_name"] = key
        definition = "something/{Shot}/{initial_name}"
        template = Template(definition, self.keys)
        fields = {"aliased_name": "some value",
                  "Shot": "shot value"}
        result = template.missing_keys(fields)
        self.assertEquals([], result)
        fields = {"initial_name": "some_value",
                  "Shot": "shot value"}
        result = template.missing_keys(fields)
        self.assertEquals(["aliased_name"], result)

    def test_optional_values(self):
        """
        Test that optional keys do not appear as missing.
        """
        definition = "shots/[{Sequence}]/{Shot}/{Step}/work/{Shot}.{branch}[.v{version}][.{snapshot}].ma"
        template = Template(definition, self.keys)
        fields = {"Shot": "shot value",
                  "Step": "step value",
                  "branch": "branch value"}

        # all optional fields skipped
        result = template.missing_keys(fields)
        self.assertEquals([], result)

        # value allowed for optional field
        fields["snapshot"] = "snapshot value"
        result = template.missing_keys(fields)
        self.assertEquals([], result)

        # required field missing
        del(fields["Shot"])
        result = template.missing_keys(fields)
        self.assertEquals(["Shot"], result)
        
    def test_value_none(self):
        """
        Test that if key value is None, the field is treated as missing.
        """
        fields = {"Sequence": "seq_1",
                   "Shot": None,
                   "Step": "Anm",
                   "branch":"mmm",
                   "version": 3,
                   "snapshot": 2}
        result = self.template.missing_keys(fields)
        self.assertEquals(["Shot"], result)


class TestSplitPath(TankTestBase):
    def test_mixed_sep(self):
        "tests that split works with mixed seperators"
        input_path = "hoken/poken\moken//doken"
        expected = ["hoken", "poken", "moken", "doken"]
        result = tank.template.split_path(input_path)
        self.assertEquals(expected, result)

class TestReadTemplates(TankTestBase):
    def setUp(self):
        super(TestReadTemplates, self).setUp()
        self.setup_fixtures()
        roots = {"primary": self.project_root}
        self.templates = read_templates(self.pipeline_configuration)

    def test_read_simple(self):
        """
        Test no error occur during read and that some known
        template is created correctly.
        """
        maya_publish_name = self.templates["maya_publish_name"]
        self.assertIsInstance(maya_publish_name, TemplateString)
        for key_name in ["name", "version"]:
            self.assertIn(key_name, maya_publish_name.keys)

    def test_aliased_key(self):
        # this template has the key name_alpha aliased as name
        houdini_asset_publish = self.templates["houdini_asset_publish"]
        self.assertIsInstance(houdini_asset_publish, TemplatePath)
        for key_name in ["sg_asset_type", "Asset", "Step", "name", "version"]:
            self.assertIn(key_name, houdini_asset_publish.keys)


class TestMakeTemplatePaths(TankTestBase):
    def setUp(self):
        super(TestMakeTemplatePaths, self).setUp()
        self.keys = {"Shot": StringKey("Shot")}
        self.roots = {"primary": self.project_root}


    def test_simple(self):
        data = {"template_name": "something/{Shot}"}
        result = make_template_paths(data, self.keys, self.roots)
        template_path = result.get("template_name")
        self.assertIsInstance(template_path, TemplatePath)
        self.assertEquals(self.keys.get("Shot"), template_path.keys.get("Shot"))

    def test_complex(self):
        data = {"template_name": {"definition": "something/{Shot}"}}
        result = make_template_paths(data, self.keys, self.roots)
        template_path = result.get("template_name")
        self.assertIsInstance(template_path, TemplatePath)
        self.assertEquals(self.keys.get("Shot"), template_path.keys.get("Shot"))

    def test_duplicate_definitions_simple(self):
        data = {"template_name": "something/{Shot}",
                "another_template": "something/{Shot}"}
        self.assertRaises(TankError, make_template_paths, data, self.keys, self.roots)

    def test_duplicate_definitions_complex(self):
        data = {"template_name": {"definition": "something/{Shot}"},
                "another_template": {"definition": "something/{Shot}"}}
        self.assertRaises(TankError, make_template_paths, data, self.keys, self.roots)

    def test_dup_def_diff_roots(self):
        alt_root = os.path.join("some","fake","path")
        roots = {"primary": self.project_root, 
                 "alternate_1": alt_root}
        data = {"template_name": {"definition": "something/{Shot}"},
                "another_template": {"definition": "something/{Shot}",
                                     "root_name": "alternate_1"}}
        result = make_template_paths(data, self.keys, roots)
        prim_template = result.get("template_name")
        alt_templatte = result.get("another_template")
        self.assertEquals(self.project_root, prim_template.root_path)
        self.assertEquals(alt_root, alt_templatte.root_path)
                

class TestMakeTemplateStrings(TankTestBase):
    def setUp(self):
        super(TestMakeTemplateStrings, self).setUp()
        self.keys = {"Shot": StringKey("Shot")}
        self.template_path = TemplatePath("something/{Shot}", self.keys, self.project_root)
        self.template_paths = {"template_path": self.template_path}

    def test_simple(self):
        data = {"template_name": "something.{Shot}"}
        result = make_template_strings(data, self.keys, self.template_paths)
        template_string = result.get("template_name")
        self.assertIsInstance(template_string, TemplateString)
        self.assertEquals("template_name", template_string.name)

    def test_complex(self):
        data = {"template_name": {"definition": "something.{Shot}"}}
        result = make_template_strings(data, self.keys, self.template_paths)
        template_string = result.get("template_name")
        self.assertIsInstance(template_string, TemplateString)
        self.assertEquals("template_name", template_string.name)

    def test_duplicate_definitions(self):
        data = {"template_one": "something.{Shot}",
                "template_two": "something.{Shot}"}
        self.assertRaises(TankError, make_template_strings, data, self.keys, self.template_paths)

    def test_validate_with_set(self):
        data = {"template_name": {"definition": "something.{Shot}",
                                  "validate_with": "template_path"}}
        result = make_template_strings(data, self.keys, self.template_paths)
        template_string = result.get("template_name")
        self.assertEquals(self.template_path, template_string.validate_with)

    def test_validate_template_missing(self):
        data = {"template_name": {"definition": "something.{Shot}",
                                  "validate_with": "non-exitant-template"}}
        self.assertRaises(TankError, make_template_strings, data, self.keys, self.template_paths)


class TestReadTemplates(TankTestBase):
    """Test reading templates file."""
    def setUp(self):
        super(TestReadTemplates, self).setUp()
        self.setup_fixtures()

    def test_choices(self):
        """Check a template key which uses choices."""
        # check old-style (list) choices
        key = self.tk.templates["nuke_shot_render_stereo"].keys["eye"]
        self.assertEquals(["Right", "Left"], key.choices)
        self.assertEquals({"Right":"Right", "Left":"Left"}, key.labelled_choices)
        
        # check new-style (dict) choices
        key = self.tk.templates["maya_shot_work"].keys["maya_extension"]
        self.assertEquals(["ma", "mb"], key.choices)
        self.assertEquals({'ma':'Maya Ascii (.ma)', 'mb':'Maya Binary (.mb)'}, key.labelled_choices)

    def test_exclusions(self):
        key = self.tk.templates["asset_work_area"].keys["Asset"]
        self.assertEquals(["Seq", "Shot"], key.exclusions)


class TestIntegerKey(TankTestBase):

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
        self._validate_key(
            IntegerKey("version_number", format_spec=" 3", strict_matching=False),
            strict_matching=False, format_spec=" 3"
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
        # - space followed by a non zero positive number
        # - zero followed by a non zero positive number
        IntegerKey("version_number", format_spec=None)
        IntegerKey("version_number", format_spec="1")
        IntegerKey("version_number", format_spec=" 1")
        IntegerKey("version_number", format_spec="01")

        # Make sure invalid formats are caught
        with self.assertRaisesRegexp(TankError, "format_spec can't be empty"):
            IntegerKey("version_number", format_spec="")

        error_regexp = "format_spec has to either be"
        with self.assertRaisesRegexp(TankError, error_regexp):
            # Should throw because the padding number is not non zero.
            IntegerKey("version_number", format_spec="00")

        with self.assertRaisesRegexp(TankError, error_regexp):
            # Should throw because the padding number is not non zero.
            IntegerKey("version_number", format_spec=" 0")

        with self.assertRaisesRegexp(TankError, error_regexp):
            # Should throw because it is not a non zero positive integer
            IntegerKey("version_number", format_spec="0")

        with self.assertRaisesRegexp(TankError, error_regexp):
            # Should throw because it missing a padding value
            IntegerKey("version_number", format_spec=" ")

        with self.assertRaisesRegexp(TankError, error_regexp):
            # Should throw because the padding caracter is invalid
            IntegerKey("version_number", format_spec="a0")

        with self.assertRaisesRegexp(TankError, error_regexp):
            # Should throw because the padding size is not a number.
            IntegerKey("version_number", format_spec="0a")

    def test_no_format_spec(self):
        key = IntegerKey("version_number")
        key.value_from_str

    def _test_non_strict_matching(self, padding_char):
        # have a template that formats with two digits of padding.
        key = IntegerKey("version_number", format_spec="%s3" % padding_char, strict_matching=False)
        keys = {
            "version_number": key
        }
        definition = "v_{version_number}"
        tpl = TemplatePath(definition, keys, "")

        # It should match because it is of the right length.
        fields = tpl.validate_and_get_fields("v_%s%s0" % (padding_char, padding_char))
        self.assertEqual(fields, {"version_number": 0})
        # It should also match because it is of the right length
        fields = tpl.validate_and_get_fields("v_000")
        self.assertEqual(fields, {"version_number": 0})

        # It should match a template with only one digit because we're not strict.
        fields = tpl.validate_and_get_fields("v_0")
        self.assertEqual(fields, {"version_number": 0})
        fields = tpl.validate_and_get_fields("v_1")
        self.assertEqual(fields, {"version_number": 1})

        # It should match a template with too many digits.
        fields = tpl.validate_and_get_fields("v_20000")
        self.assertEqual(fields, {"version_number": 20000})

        # From path to tokens back to path should be lossy.
        fields = tpl.validate_and_get_fields("v_1")
        self.assertEqual("v_%s%s1" % (padding_char, padding_char), tpl.apply_fields(fields))

        # It shouldn't match because the value 0 wouldn't take more space then the format spec
        # specifies
        error_msg = "not a non zero positive integer"
        with self.assertRaisesRegexp(TankError, error_msg):
            key.value_from_str("%s%s%s0" % (padding_char, padding_char, padding_char))

        with self.assertRaisesRegexp(TankError, error_msg):
            key.value_from_str("0000")

        # It shouldn't match because there is too much padding.
        with self.assertRaisesRegexp(TankError, error_msg):
            key.value_from_str("%s%s%s1" % (padding_char, padding_char, padding_char))

        # It shouldn't match because it is not a non zero integer
        with self.assertRaisesRegexp(TankError, error_msg):
            key.value_from_str("aaaa")

        # Equal or lower size should fail if not matching the spec
        with self.assertRaisesRegexp(TankError, "does not match format spec"):
            key.value_from_str("%sa" % padding_char)

        # Equal or lower size should fail if not matching the spec
        with self.assertRaisesRegexp(TankError, "does not match format spec"):
            key.value_from_str("a0")

        # Equal or lower size should fail if not matching the spec
        with self.assertRaisesRegexp(TankError, "does not match format spec"):
            key.value_from_str("aa")

        # Mixed padding is wrong.
        with self.assertRaisesRegexp(TankError, "does not match format spec"):
            key.value_from_str(" 01")
        with self.assertRaisesRegexp(TankError, "does not match format spec"):
            key.value_from_str("0 1")

        # It shouldn't match because there is padding when there shouldn't be.
        with self.assertRaisesRegexp(TankError, error_msg):
            IntegerKey(
                "version_number", format_spec="%s1" % padding_char, strict_matching=False
            ).value_from_str("01")

        # It shouldn't match because there is padding when there shouldn't be.
        with self.assertRaisesRegexp(TankError, error_msg):
            IntegerKey(
                "version_number", format_spec="%s1" % padding_char, strict_matching=False
            ).value_from_str("01")

        # Again, it shouldn't match because the value 0 wouldn't take more space then the format
        # spec specifies
        with self.assertRaisesRegexp(TankError, error_msg):
            IntegerKey(
                "version_number", format_spec="%s1" % padding_char, strict_matching=False
            ).value_from_str("00")

    def test_non_strict_matching(self):
        """
        In non strict mode, tokens can actually have less numbers than the padding requests. Also,
        if there are more, they will be matched all.
        """
        self._test_non_strict_matching(' ')
        self._test_non_strict_matching('0')

    def _validate_key(self, key, strict_matching, format_spec):
        """
        Makes sure that an integer key's formatting options are correctly set.
        """
        self.assertEqual(key.strict_matching, strict_matching)
        self.assertEqual(key.format_spec, format_spec)

    def test_strict_matching(self):
        """
        In strict mode, tokens have to have as much padding as the format specifier suggests. Less will not
        match.
        """
        # have a template that formats with two digits of padding.
        key = IntegerKey("version_number", format_spec="02", strict_matching=True)
        keys = {
            "version_number": key
        }
        self.assertTrue(keys["version_number"].strict_matching)
        definition = "v{version_number}"
        tpl = TemplatePath(definition, keys, "")

        # It should not match a template with only one digit.
        fields = tpl.validate_and_get_fields("v1")
        self.assertIsNone(fields)

        # From path to tokens back to path should get back the same string when the expected number of
        # digits are found.
        fields = tpl.validate_and_get_fields("v01")
        self.assertEqual("v01", tpl.apply_fields(fields))

        # It should match a template with too many digits.
        fields = tpl.validate_and_get_fields("v20000")
        self.assertEqual(fields, {"version_number": 20000})
        self.assertEqual("v20000", tpl.apply_fields(fields))
