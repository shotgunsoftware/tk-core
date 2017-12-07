# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

from __future__ import print_function

import sys
import os

import tank
from tank import TankError

from tank.template import TemplatePath
from tank_test.tank_test_base import TankTestBase, setUpModule # noqa
from tank.templatekey import (TemplateKey, StringKey, IntegerKey, 
                                SequenceKey)

class TestTemplatePath(TankTestBase):
    """
    Base class for tests of TemplatePath. Do not add tests to this class directly.
    """
    def setUp(self):
        super(TestTemplatePath, self).setUp(
            parameters={"primary_root_name": "primary_with_a_different_name"}
        )
        # Make various types of keys(fields)
        self.keys = {"Sequence": StringKey("Sequence"),
                     "Shot": StringKey("Shot", default="s1", choices=["s1","s2","shot_1"]),
                     "Step": StringKey("Step"),
                     "branch": StringKey("branch", filter_by="alphanumeric"),
                     "name": StringKey("name"),
                     "name_alpha": StringKey("name_alpha", filter_by="alphanumeric"),
                     "version": IntegerKey("version", format_spec="03"),
                     "snapshot": IntegerKey("snapshot", format_spec="03"),
                     "ext": StringKey("ext"),
                     "seq_num": SequenceKey("seq_num"),
                     "frame": SequenceKey("frame", format_spec="04")}
        # Make a template
        self.definition = "shots/{Sequence}/{Shot}/{Step}/work/{Shot}.{branch}.v{version}.{snapshot}.ma"
        
        # legacy style template object which only knows about the currently running operating system
        self.template_path_current_os_only = TemplatePath(self.definition, self.keys, self.project_root)
        
        # new style template object which supports all recognized platforms
        # get all OS roots for primary storage
        all_roots = self.pipeline_configuration.get_all_platform_data_roots()[self.primary_root_name]
        
        self.template_path = TemplatePath(self.definition, 
                                          self.keys, 
                                          self.project_root, 
                                          per_platform_roots=all_roots)

        self.project_root_template = TemplatePath("/", 
                                                  self.keys, 
                                                  self.project_root, 
                                                  per_platform_roots=all_roots)

        # make template with sequence key
        self.sequence = TemplatePath("/path/to/seq.{frame}.ext", self.keys, "", "frame")

class TestInit(TestTemplatePath):
    def test_static_simple(self):
        definition = "shots/{Shot}/work/{Shot}.{version}.ma"
        sep = os.path.sep 
        first_token = os.path.join(self.project_root.lower(), "shots") + sep
        second_token = sep + "work" + sep
        expected = [[first_token, second_token, ".", ".ma"]]
        template = TemplatePath(definition, self.keys, root_path=self.project_root)
        self.assertEquals(expected, template._static_tokens)

    def test_static_tokens(self):
        definition = "{Sequence}/{Shot}/3d/maya/scenes/{branch}-v{version}.{ext}"
        if sys.platform.lower() == "win32":
            expected = [["\\", "\\3d\\maya\\scenes\\", "-v", "."]]
        else:
            expected = [["/", "/3d/maya/scenes/", "-v", "."]]
        template = TemplatePath(definition, self.keys, root_path="")
        self.assertEquals(expected, template._static_tokens)

class TestValidate(TestTemplatePath):
    """Test Case for validating a path"""
    def setUp(self):
        super(TestValidate, self).setUp()
        relative_path = os.path.join("shots",
                                     "seq_1",
                                     "shot_1",
                                     "Anm",
                                     "work",
                                     "shot_1.mmm.v001.002.ma")
        self.valid_path = os.path.join(self.project_root, relative_path)

    def test_project_root(self):
        """
        Test that validating the project root against the project root template ('/') works
        correctly
        """
        root = self.pipeline_configuration.get_primary_data_root()
        self.assertTrue(self.project_root_template.validate(root))

    def test_valid_path(self):
        self.assertTrue(self.template_path.validate(self.valid_path))

    def test_missing_directories(self):
        relative_path = os.path.join("shots",
                                     "seq_1",
                                     "Anm",
                                     "work",
                                     "shot_1.mmm.v001.002.ma")
        invalid_path = os.path.join(self.project_root, relative_path)
        self.assertFalse(self.template_path.validate(invalid_path))

    def test_missing_version(self):
        relative_path = os.path.join("shots",
                                     "seq_1",
                                     "shot_1",
                                     "Anm",
                                     "work",
                                     "shot_1.mmm.002.ma")
        invalid_path = os.path.join(self.project_root, relative_path)
        self.assertFalse(self.template_path.validate(invalid_path))

    def test_conflicting_shot(self):
        relative_path = os.path.join("shots",
                                     "seq_1",
                                     "shot_4",
                                     "Anm",
                                     "work",
                                     "shot_1.mmm.v001.002.ma")
        invalid_path = os.path.join(self.project_root, relative_path)
        self.assertFalse(self.template_path.validate(invalid_path))

    def test_with_valid_input_values(self):
        input_fields = {"Shot": "shot_1",
                        "Sequence":"seq_1"}
        result = self.template_path.validate(self.valid_path, fields=input_fields)
        self.assertTrue(result)

    def test_with_invalid_input_values(self):
        input_fields = {"Shot": "shot_5",
                        "Sequence":"seq_2"}
        result = self.template_path.validate(self.valid_path, fields=input_fields)
        self.assertFalse(result)

    def test_skipping_keys_key_present(self):
        input_fields = {"Shot": "shot_1",
                        "Sequence":"seq_1",
                        "Step": "Anm",
                        "branch": "mmm",
                        "version": 1,
                        "snapshot": 4}
        result = self.template_path.validate(self.valid_path, fields=input_fields, skip_keys=["snapshot"])
        self.assertTrue(result)
        
    def test_skipping_keys_key_missing(self):
        input_fields = {"Shot": "shot_1",
                        "Sequence":"seq_1",
                        "Step": "Anm",
                        "branch": "mmm",
                        "version": 1}
        result = self.template_path.validate(self.valid_path, fields=input_fields, skip_keys=["snapshot"])
        self.assertTrue(result)

    def test_skip_key_type_not_match(self):
        relative_path = os.path.join("shots",
                                     "seq_1",
                                     "shot_1",
                                     "Anm",
                                     "work",
                                     "shot_1.mmm.v001.###.ma")
        valid_path = os.path.join(self.project_root, relative_path)
        input_fields = {"Shot": "shot_1",
                        "Sequence":"seq_1",
                        "Step": "Anm",
                        "branch": "mmm",
                        "version": 1}
        result = self.template_path.validate(valid_path, fields=input_fields, skip_keys=["snapshot"])
        self.assertTrue(result)

    def test_frame_number_valid(self):
        frames_values = ["1000", "10000"] 
        self.assert_sequence_paths_valid(frames_values)

    def test_nuke_format_valid(self):
        frames_values = ["%04d"]
        self.assert_sequence_paths_valid(frames_values)

    def test_shake_format_valid(self):
        frames_values = ["@@@@"]
        self.assert_sequence_paths_valid(frames_values)

    def test_houdini_format_valid(self):
        frames_values = ["$F4"]
        self.assert_sequence_paths_valid(frames_values)

    def test_bad_characters(self):
        frames_values = ["U14", "X", "47p"]
        self.assert_sequence_paths_invalid(frames_values)

    def test_mixed_framespecs(self):
        frames_values = ["%04F", "@F4", "#@", "$F#"]
        self.assert_sequence_paths_invalid(frames_values)

    def test_incorrect_length(self):
        #TODO add incorrect length ints once that is fixed in template.validate
        frames_values = ["@", "@@@@@", "#####", "$F3", "$F5", "%03d", "%05d"]
        self.assert_sequence_paths_invalid(frames_values)

    def test_bad_base_path(self):
        base_path = "path/from/seq.%s.ext"
        frames_values = ["%04d", "#", "@@@@", "####", "$F4"]
        for frames_value in frames_values:
            candidate_path = base_path % frames_value
            self.assertFalse(self.sequence.validate(candidate_path))

    def assert_sequence_paths_valid(self, frames_values):
        """Checks that paths created using a list of values for the frames token of a path are valid.

        :param frames_values: List of valid frame values (might be "#", "@" for Shake)
        :type  frames_values: List.
        """
        base_path = "path/to/seq.%s.ext"
        for frames_value in frames_values:
            candidate_path = base_path % frames_value
            self.assertTrue(self.sequence.validate(candidate_path))
    
    def assert_sequence_paths_invalid(self, frames_values):
        """Checks that paths created using a list of values for the frames token of a path are invalid.

        :param frames_values: List of invalid frame values 
        :type  frames_values: List.
        """
        base_path = "path/to/seq.%s.ext"
        for frames_value in frames_values:
            candidate_path = base_path % frames_value
            if self.sequence.validate(candidate_path):
                print("Invalid path marked as valid: \n%s" % candidate_path)
            self.assertFalse(self.sequence.validate(candidate_path))

    def test_optional_values(self):
        definition = "shots/{Sequence}/{Shot}/{Step}/work/{Shot}[.{branch}][.v{version}][.{snapshot}.ma]"
        template = TemplatePath(definition, self.keys, self.project_root)

        # test all combinations of optional values
        # branch T   version T   snapshot T
        test_path = os.path.join(self.project_root, "shots", "seq_1", "s1", "Anm", "work", "s1.mmm.v003.002.ma")
        self.assertTrue(template.validate(test_path))

        # branch T   version T   snapshot F
        test_path = os.path.join(self.project_root, "shots", "seq_1", "s1", "Anm", "work", "s1.mmm.v003")
        self.assertTrue(template.validate(test_path))

        # branch T   version F   snapshot T
        test_path = os.path.join(self.project_root, "shots", "seq_1", "s1", "Anm", "work", "s1.mmm.002.ma")
        self.assertTrue(template.validate(test_path))

        # branch T   version F   snapshot F
        test_path = os.path.join(self.project_root, "shots", "seq_1", "s1", "Anm", "work", "s1.mmm")
        self.assertTrue(template.validate(test_path))

        # branch F   version T   snapshot T
        test_path = os.path.join(self.project_root, "shots", "seq_1", "s1", "Anm", "work", "s1.v003.002.ma")
        self.assertTrue(template.validate(test_path))

        # branch F   version T   snapshot F
        test_path = os.path.join(self.project_root, "shots", "seq_1", "s1", "Anm", "work", "s1.v003")
        self.assertTrue(template.validate(test_path))

        # branch F   version F   snapshot T
        test_path = os.path.join(self.project_root, "shots", "seq_1", "s1", "Anm", "work", "s1.002.ma")
        self.assertTrue(template.validate(test_path))

        # branch F   version F   snapshot F
        test_path = os.path.join(self.project_root, "shots", "seq_1", "s1", "Anm", "work", "s1")
        self.assertTrue(template.validate(test_path))


class TestApplyFields(TestTemplatePath):
    
    def test_simple(self):
        relative_path = os.path.join("shots",
                                     "seq_1",
                                     "s1",
                                     "Anm",
                                     "work",
                                     "s1.mmm.v003.002.ma")
        expected = os.path.join(self.project_root, relative_path)
        fields = {"Sequence": "seq_1",
                   "Shot": "s1",
                   "Step": "Anm",
                   "branch":"mmm",
                   "version": 3,
                   "snapshot": 2}
        
        result = self.template_path.apply_fields(fields)
        self.assertEquals(expected, result)        

    def test_project_root(self):
        """
        Test that applying fields to the project root template ('/') returns the project root
        """
        root = self.pipeline_configuration.get_primary_data_root()
        result = self.project_root_template.apply_fields({})
        self.assertEquals(root, result)

    def test_multi_platform(self):
        relative_path = os.path.join("shots",
                                     "seq_1",
                                     "s1",
                                     "Anm",
                                     "work",
                                     "s1.mmm.v003.002.ma")
        expected = os.path.join(self.project_root, relative_path)
        fields = {"Sequence": "seq_1",
                   "Shot": "s1",
                   "Step": "Anm",
                   "branch":"mmm",
                   "version": 3,
                   "snapshot": 2}        
        
        result = self.template_path.apply_fields(fields, "win32")
        root = self.pipeline_configuration.get_all_platform_data_roots()[self.primary_root_name]["win32"]
        expected = "%s\\%s" % (root, relative_path.replace(os.sep, "\\"))
        self.assertEquals(expected, result)

        result = self.template_path.apply_fields(fields, "linux2")
        root = self.pipeline_configuration.get_all_platform_data_roots()[self.primary_root_name]["linux2"]
        expected = "%s/%s" % (root, relative_path.replace(os.sep, "/"))
        self.assertEquals(expected, result)

        result = self.template_path.apply_fields(fields, "darwin")
        root = self.pipeline_configuration.get_all_platform_data_roots()[self.primary_root_name]["darwin"]
        expected = "%s/%s" % (root, relative_path.replace(os.sep, "/"))
        self.assertEquals(expected, result)

    def test_legacy_constructor_format(self):
        
        relative_path = os.path.join("shots",
                                     "seq_1",
                                     "s1",
                                     "Anm",
                                     "work",
                                     "s1.mmm.v003.002.ma")
        expected = os.path.join(self.project_root, relative_path)
        fields = {"Sequence": "seq_1",
                   "Shot": "s1",
                   "Step": "Anm",
                   "branch":"mmm",
                   "version": 3,
                   "snapshot": 2}
        
        result = self.template_path_current_os_only.apply_fields(fields)
        self.assertEquals(expected, result)

    def test_fields_missing(self):
        fields = {"Sequence": "seq_1",
                   "Shot": "shot_1",
                   "branch":"mmm",
                   "version": 3,
                   "snapshot": 2}
        self.assertRaises(TankError, self.template_path.apply_fields, fields)

    def test_none_value(self):
        fields = {"Sequence": "seq_1",
                   "Shot": "s1",
                   "Step": None,
                   "branch":"mmm",
                   "version": 3,
                   "snapshot": 2}
        self.assertRaises(TankError, self.template_path.apply_fields, fields)

    def test_wrong_type(self):
        fields = {"Sequence": "seq_1",
                  "Shot": "shot_1",
                  "Step": "Anm",
                  "branch":"mmm",
                  "version": "a",
                  "snapshot": 2}
        self.assertRaises(TankError, self.template_path.apply_fields, fields)

    def test_working_enum(self):
        template = TemplatePath("{Shot}/{Step}/file.ex", self.keys, root_path=self.project_root)
        expected = os.path.join(self.project_root, "s1", "Anm", "file.ex")
        fields = {"Shot": "s1", "Step": "Anm"}
        result = template.apply_fields(fields)
        self.assertEquals(expected, result)

    def test_enum_bad_key(self):
        fields = {"Shot": "s3", "Step": "Anm"}
        self.assertRaises(TankError, self.template_path.apply_fields, fields)

    def test_default(self):
        template = TemplatePath("{Shot}/{Step}/file.ex", self.keys, self.project_root)
        expected = os.path.join(self.project_root, "s1", "Anm", "file.ex")
        fields = {"Step": "Anm"}
        result = template.apply_fields(fields)
        self.assertEquals(expected, result)

    def test_bad_alphanumeric(self):
        """
        Tests applying non-alphanumeric values to keys of type alphanumeric.
        """
        # single key template
        key = StringKey("alpha_num", filter_by="alphanumeric")
        template = TemplatePath("{alpha_num}", {"alpha_num":key}, self.project_root)

        invalid_values = ["_underscore", "white space", "@mpersand", "par(enthes)", "###"]
        for invalid_value in invalid_values:
            expected_msg = "%s Illegal value '%s' does not fit filter_by 'alphanumeric'" % (str(key), invalid_value)
            self.check_error_message(TankError, expected_msg, template.apply_fields, {"alpha_num": invalid_value})

    def test_good_alphanumeric(self):
        """
        Tests applying valid values for alphanumeric key.
        """
        key = StringKey("alpha_num", filter_by="alphanumeric")
        template = TemplatePath("{alpha_num}", {"alpha_num":key}, self.project_root)

        valid_values = ["allChars", "123454", "mixed09", "29mixed", "mi2344xEd", "CAPS"]
        for valid_value in valid_values:
            result = template.apply_fields({"alpha_num": valid_value})
            expected = os.path.join(self.project_root, valid_value)
            self.assertEquals(expected, result)

    def test_aliased_key(self):
        """
        Apply values to a template which has an aliased key.
        """
        key = IntegerKey("aliased_name")
        keys = {"initial_name": key}
        definition = "{initial_name}"
        template = TemplatePath(definition, keys, self.project_root)

        expected = os.path.join(self.project_root, "2")
        fields = {"aliased_name": 2}
        self.assertEquals(expected, template.apply_fields(fields))

        fields = {"initial_name": 2}
        self.assertRaises(TankError, template.apply_fields, fields)

    # tests for template with a sequence key follow
    def test_frame_number(self):
        expected = os.path.join("path", "to", "seq.0003.ext")
        fields = {"frame": 3}
        result = self.sequence.apply_fields(fields)
        self.assertEqual(expected, result)

    def test_nuke_framespec(self):
        expected = os.path.join("path", "to", "seq.%04d.ext")
        fields = {"frame": "%04d"}
        result = self.sequence.apply_fields(fields)
        self.assertEqual(expected, result)

    def test_shake_hash_alt(self):
        expected = os.path.join("path", "to", "seq.####.ext")
        fields = {"frame": "####"}
        result = self.sequence.apply_fields(fields)
        self.assertEqual(expected, result)

    def test_shake_ampersand(self):
        expected = os.path.join("path", "to", "seq.@@@@.ext")
        fields = {"frame": "@@@@"}
        result = self.sequence.apply_fields(fields)
        self.assertEqual(expected, result)

    def test_houdini_framespec(self):
        expected = os.path.join("path", "to", "seq.$F4.ext")
        fields = {"frame": "$F4"}
        result = self.sequence.apply_fields(fields)
        self.assertEqual(expected, result)

    def test_bad_values_not_ints(self):
        bad_values = ["gggggg", "04F", "%P"]
        for bad_value in bad_values:
            fields = {"frame": bad_value}
            self.assertRaises(TankError, self.sequence.apply_fields, fields)
    # end sequence key tests

    def test_optional_values(self):
        definition = "shots/{Sequence}/{Shot}/{Step}/work/{Shot}[.{branch}][.v{version}][.{snapshot}.ma]"
        template_path = TemplatePath(definition, self.keys, self.project_root)

        relative_path = os.path.join("shots",
                                     "seq_1",
                                     "s1",
                                     "Anm",
                                     "work",
                                     "s1.mmm.v003.002.ma")
        expected = os.path.join(self.project_root, relative_path)

        fields = {"Sequence": "seq_1",
                   "Shot": "s1",
                   "Step": "Anm",
                   "branch":"mmm",
                   "version": 3,
                   "snapshot": 2}
        result = template_path.apply_fields(fields)
        self.assertEquals(expected, result)

        # remove optional value
        del(fields["snapshot"])
        relative_path = os.path.join("shots",
                                     "seq_1",
                                     "s1",
                                     "Anm",
                                     "work",
                                     "s1.mmm.v003")
        expected = os.path.join(self.project_root, relative_path)
        result = template_path.apply_fields(fields)
        self.assertEquals(expected, result)


        # remove optional value
        del(fields["branch"])
        relative_path = os.path.join("shots",
                                     "seq_1",
                                     "s1",
                                     "Anm",
                                     "work",
                                     "s1.v003")
        expected = os.path.join(self.project_root, relative_path)
        result = template_path.apply_fields(fields)
        self.assertEquals(expected, result)

    def test_multi_key_optional(self):
        """
        Test optional section containing multiple keys.
        """
        definition = "shots/{Shot}[.{branch}.v{version}][.{snapshot}.ma]"
        template_path = TemplatePath(definition, self.keys, self.project_root)

        relative_path = os.path.join("shots",
                                     "s1.mmm.v003.002.ma")

        expected = os.path.join(self.project_root, relative_path)

        fields = { "Shot": "s1",
                   "branch":"mmm",
                   "version": 3,
                   "snapshot": 2}
        result = template_path.apply_fields(fields)
        self.assertEquals(expected, result)

        # if one key from optional section missing, whole section skipped.
        relative_path = os.path.join("shots",
                                     "s1.002.ma")

        expected = os.path.join(self.project_root, relative_path)

        fields = { "Shot": "s1",
                   "branch":"mmm",
                   "snapshot": 2}

        result = template_path.apply_fields(fields)
        self.assertEquals(expected, result)

    def test_optional_none_value(self):
        definition = "shots/{Shot}[.{branch}][.v{version}][.{snapshot}.ma]"
        template_path = TemplatePath(definition, self.keys, self.project_root)

        fields = { "Shot": "s1",
                   "branch": None,
                   "version": 3,
                   "snapshot": 2}

        relative_path = os.path.join("shots",
                                     "s1.v003.002.ma")

        expected = os.path.join(self.project_root, relative_path)
        result = template_path.apply_fields(fields)
        self.assertEquals(expected, result)

    def test_format_default(self):
        definition = "shots/{Shot}.{branch}.{frame}.ext"
        template = TemplatePath(definition, self.keys, self.project_root)
        fields = { "Shot": "s1",
                   "branch": "loon"}
                   
        # default format
        expected = os.path.join(self.project_root, "shots", "s1.loon.%04d.ext")
        self.assertEquals(expected, template.apply_fields(fields))

        # specify default format
        expected = os.path.join(self.project_root, "shots", "s1.loon.####.ext")
        fields["frame"] = "FORMAT:#"
        self.assertEquals(expected, template.apply_fields(fields))


class Test_ApplyFields(TestTemplatePath):
    """Tests for private TemplatePath._apply_fields"""
    def test_skip_enum(self):
        expected = os.path.join(self.project_root, "*")
        key = StringKey("Shot", choices=["s1", "s2"])
        template = TemplatePath("{Shot}", {"Shot":key}, self.project_root)
        fields = {"Shot":"*"}
        skip_fields = ["Shot"]
        result = template._apply_fields(fields, ignore_types=skip_fields)
        self.assertEquals(expected, result)

    def test_ignore_type(self):
        relative_path = os.path.join("shots",
                                     "seq_1",
                                     "shot_1",
                                     "Anm",
                                     "work",
                                     "shot_1.mmm.v*.002.ma")
        expected = os.path.join(self.project_root, relative_path)
        fields = {"Sequence": "seq_1",
                   "Shot": "shot_1",
                   "Step": "Anm",
                   "branch":"mmm",
                   "version": "*",
                   "snapshot": 2}
        result = self.template_path._apply_fields(fields, ignore_types=["version"])
        self.assertEquals(result, expected)

class TestGetFields(TestTemplatePath):
    def test_anim_path(self):
        relative_path = os.path.join("shots",
                                     "seq_1",
                                     "shot_1",
                                     "Anm",
                                     "work",
                                     "shot_1.mmm.v003.002.ma")
        file_path = os.path.join(self.project_root, relative_path)
        expected = {"Sequence": "seq_1",
                    "Shot": "shot_1",
                    "Step": "Anm",
                    "branch":"mmm",
                    "version": 3,
                    "snapshot": 2}
        result = self.template_path.get_fields(file_path)
        self.assertEquals(result, expected)

    def test_project_root(self):
        """
        Test that the getting fields from a project root template ('/') returns an empty fields
        dictionary and doesn't error
        """
        root = self.pipeline_configuration.get_primary_data_root()
        result = self.project_root_template.get_fields(root)
        self.assertEquals({}, result)

    def test_key_first(self):
        definition = "{Sequence}/{Shot}/{Step}/work/{Shot}.{branch}.v{version}.{snapshot}.ma"
        template = TemplatePath(definition, self.keys, root_path=self.project_root)
        relative_path = os.path.join("seq_1",
                                     "shot_1",
                                     "Anm",
                                     "work",
                                     "shot_1.mmm.v003.002.ma")
        file_path = os.path.join(self.project_root, relative_path)
        expected = {"Sequence": "seq_1",
                    "Shot": "shot_1",
                    "Step": "Anm",
                    "branch":"mmm",
                    "version": 3,
                    "snapshot": 2}
        result = template.get_fields(file_path)
        self.assertEquals(result, expected)

    def test_key_first_short(self):
        definition =  "{Step}/{Shot}.png"
        template = TemplatePath(definition, self.keys, root_path=self.project_root)
        relative_path = os.path.join("Anm", "shot_1.png")
        file_path = os.path.join(self.project_root, relative_path)
        expected = {"Step": "Anm",
                    "Shot": "shot_1"}
        result = template.get_fields(file_path)
        self.assertEquals(result, expected)

    def test_one_key(self):
        definition = "{Shot}/boo.wtf"
        template = TemplatePath(definition, self.keys, root_path=self.project_root)
        relative_path = os.path.join("shot_1", "boo.wtf")
        file_path = os.path.join(self.project_root, relative_path)
        expected = {"Shot": "shot_1"}
        result = template.get_fields(file_path)
        self.assertEquals(result, expected)

    def test_one_key_no_match(self):
        definition = "comp/{Shot}s/boo.wtf"
        template = TemplatePath(definition, self.keys, root_path=self.project_root)
        relative_path = os.path.join("anim", "shot_1", "boo.wtf")
        file_path = os.path.join(self.project_root, relative_path)
        self.assertRaises(TankError, template.get_fields, file_path)

    def test_diff_seperators(self):
        definition = "shots/{Sequence}/{Shot}/{Step}/work"
        template = TemplatePath(definition, self.keys, root_path=self.project_root)
        relative_path = os.path.join("shots", "seq_1", "shot_1", "Anm", "work")
        file_path = os.path.join(self.project_root, relative_path)
        # adding extra seperator to end
        file_path = file_path + os.path.sep
        expected = {"Sequence": "seq_1",
                    "Shot": "shot_1",
                    "Step": "Anm"}
        result = template.get_fields(file_path)
        self.assertEquals(result, expected)
    
    def test_missing_values(self):
        relative_path = os.path.join("shots",
                                     "seq_1",
                                     "Anm",
                                     "work",
                                     "mmm.v003.002.ma")
        file_path = os.path.join(self.project_root, relative_path)
        self.assertRaises(TankError, self.template_path.get_fields, file_path)
        
    def test_conflicting_values(self):
        relative_path = os.path.join("shots",
                                     "seq_1",
                                     "shot_2",
                                     "Anm",
                                     "work",
                                     "shot_1.mmm.v003.002.ma")
        file_path = os.path.join(self.project_root, relative_path)
        self.assertRaises(TankError, self.template_path.get_fields, file_path)

    def test_skip_key(self):
        relative_path = os.path.join("shots",
                                     "seq_1",
                                     "shot_1",
                                     "Anm",
                                     "work",
                                     "shot_1.mmm.v003.###.ma")
        file_path = os.path.join(self.project_root, relative_path)
        expected = {"Sequence": "seq_1",
                    "Shot": "shot_1",
                    "Step": "Anm",
                    "branch":"mmm",
                    "version": 3}
        result = self.template_path.get_fields(file_path, skip_keys=["snapshot"])
        self.assertEquals(result, expected)


    def test_string_for_int_type(self):
        relative_path = os.path.join("shots",
                                     "seq_1",
                                     "shot_1",
                                     "Anm",
                                     "work",
                                     "shot_1.mmm.v003.###.ma")
        file_path = os.path.join(self.project_root, relative_path)
        self.assertRaises(TankError, self.template_path.get_fields, file_path)

    def test_different_case(self):
        relative_path = os.path.join("Shots",
                                     "Seq_1",
                                     "Shot_1",
                                     "anim",
                                     "Work",
                                     "Shot_1.mmm.v003.002.ma")
        file_path = os.path.join(self.project_root, relative_path)
        expected = {"Sequence": "Seq_1",
                    "Shot": "Shot_1",
                    "Step": "anim",
                    "branch": "mmm",
                    "version": 3,
                    "snapshot": 2}
        result = self.template_path.get_fields(file_path)
        self.assertEquals(result, expected)

    def test_matching_enum(self):
        template = TemplatePath("{Shot}", self.keys, root_path=self.project_root)
        file_path = os.path.join(self.project_root, "s2")
        expected = {"Shot": "s2"}
        result = template.get_fields(file_path)
        self.assertEquals(result, expected)

    def test_bad_enum(self):
        template = TemplatePath("{Shot}", self.keys, root_path=self.project_root)
        file_path = os.path.join(self.project_root, "s5")
        self.assertRaises(TankError, template.get_fields, file_path)

        
    def test_definition_short_end_static(self):
        """Tests case when input path longer than definition which
        ends with non key."""
        definition = "sequences/{Sequence}/{Shot}/{Step}/work"
        template = TemplatePath(definition, self.keys, root_path=self.project_root)
        relative_path = "sequences/Seq1/Shot_1/Anm/work/test.ma"
        input_path = os.path.join(self.project_root, relative_path)
        self.assertRaises(TankError, template.get_fields, input_path)

    def test_definition_short_end_key(self):
        """Tests case when input path longer than definition which ends with key."""
        definition = "sequences/{Sequence}/{Shot}/{Step}"
        template = TemplatePath(definition, self.keys, root_path=self.project_root)
        relative_path = "sequences/Seq1/Shot_1/Anm/work/test.ma"
        input_path = os.path.join(self.project_root, relative_path)
        self.assertRaises(TankError, template.get_fields, input_path)

    def test_key_at_end(self):
        definition = "sequences/{Sequence}/{Shot}/{Step}"
        template = TemplatePath(definition, self.keys, root_path=self.project_root)
        relative_path = "sequences/Seq1/Shot_1/Anm"
        input_path = os.path.join(self.project_root, relative_path)
        expected = {"Sequence": "Seq1",
                    "Shot": "Shot_1",
                    "Step": "Anm"}
        actual = template.get_fields(input_path)
        self.assertEquals(expected, actual)

    def test_double_int_key(self):
        """Test case that key of type int appears twice in definition."""
        int_key = IntegerKey("int_key")
        definition = "{int_key}/something/{int_key}.else"
        template = TemplatePath(definition, {"int_key": int_key}, root_path=self.project_root)
        expected = {"int_key": 4}
        relative_path = "4/something/4.else"
        input_path = os.path.join(self.project_root, relative_path)
        actual = template.get_fields(input_path)
        self.assertEquals(expected, actual)


    def test_valid_alphanumeric(self):
        """Bug reported in Ticket #17090"""
        template = TemplatePath("{branch}.v{version}.nk", self.keys, self.project_root)
        input_path = os.path.join(self.project_root, "comp.v001.nk")
        expected = {"branch": "comp",
                    "version": 1}
        result = template.get_fields(input_path)
        self.assertEquals(expected, result)

    def test_aliased_key(self):
        key = IntegerKey("aliased_name")
        keys = {"initial_name": key}
        definition = "{initial_name}"
        template = TemplatePath(definition, keys, self.project_root)
        input_path = os.path.join(self.project_root, "3")
        expected = {"aliased_name": 3}
        result = template.get_fields(input_path)
        self.assertEquals(expected, result)

    def test_frame_number(self):
        input_path = "path/to/seq.0003.ext"
        expected = {"frame": 3}
        result = self.sequence.get_fields(input_path)

    def test_nuke_framespec(self):
        input_path = "path/to/seq.%04d.ext"
        expected = {"frame": "%04d"}
        result = self.sequence.get_fields(input_path)
        self.assertEqual(expected, result)

    def test_shake_ampersand(self):
        input_path = "path/to/seq.@@@@.ext"
        expected = {"frame": "@@@@"}
        result = self.sequence.get_fields(input_path)
        self.assertEqual(expected, result)

    def test_houdini_framespec(self):
        input_path = "path/to/seq.$F4.ext"
        expected = {"frame": "$F4"}
        result = self.sequence.get_fields(input_path)
        self.assertEqual(expected, result)

    def test_optional_sections(self):
        """
        Test that definition using optional sections resolves for missing optional values.
        """
        definition = "shots/{Sequence}/{Shot}/{Step}/work/{Shot}[.{branch}][.v{version}][.{snapshot}.ma]"
        template = TemplatePath(definition, self.keys, self.project_root)

        relative_path = os.path.join("shots",
                                     "seq_1",
                                     "s1",
                                     "Anm",
                                     "work",
                                     "s1.mmm.v003.002.ma")
        input_path = os.path.join(self.project_root, relative_path)

        expected = {"Sequence": "seq_1",
                    "Shot": "s1",
                    "Step": "Anm",
                    "branch":"mmm",
                    "version": 3,
                    "snapshot": 2}

        result = template.get_fields(input_path)
        self.assertEqual(expected, result)

        # remove version value
        relative_path = os.path.join("shots",
                                     "seq_1",
                                     "s1",
                                     "Anm",
                                     "work",
                                     "s1.mmm.002.ma")
        input_path = os.path.join(self.project_root, relative_path)

        expected = {"Sequence": "seq_1",
                    "Shot": "s1",
                    "Step": "Anm",
                    "branch":"mmm",
                    "snapshot": 2}

        result = template.get_fields(input_path)
        self.assertEqual(expected, result)

        # remove all optional values
        relative_path = os.path.join("shots",
                                     "seq_1",
                                     "s1",
                                     "Anm",
                                     "work",
                                     "s1")
        input_path = os.path.join(self.project_root, relative_path)

        expected = {"Sequence": "seq_1",
                    "Shot": "s1",
                    "Step": "Anm"}

        result = template.get_fields(input_path)
        self.assertEqual(expected, result)

    def test_optional_with_underscore(self):
        """
        Simulating error Ryan encountered whilst testing, where
        optional section containing name key starts with an underscore,
        and an underscore is present in the value of the preceding field.
        """
        definition = "sequences/{Sequence}/{Shot}/{Step}/work/{Shot}[_{name}].v{version}.nk"
        template = tank.TemplatePath(definition, self.keys, self.project_root)
        # leave out optional 'name' field
        relative_path = os.path.join("sequences", "seq_1", "shot_1", "Anm", "work", "shot_1.v001.nk")
        input_path = os.path.join(self.project_root, relative_path)
        expected = {"Sequence": "seq_1",
                    "Shot": "shot_1",
                    "Step": "Anm",
                    "version": 1}
        result = template.get_fields(input_path)
        self.assertEqual(expected, result)

    def test_is_optional(self):
        """
        testing the is_optional method
        """
        definition = "sequences/{Sequence}/{Shot}/{Step}/work/{Shot}[_{name}].v{version}.nk"
        template = tank.TemplatePath(definition, self.keys, self.project_root)

        self.assertTrue(template.is_optional("name"))
        self.assertFalse(template.is_optional("version"))
        

    def test_no_keys_valid(self):
        template = tank.TemplatePath("no/keys", {}, self.project_root)
        input_path = os.path.join(self.project_root, "no/keys")
        self.assertEqual({}, template.get_fields(input_path))

    def test_no_keys_invalid(self):
        template = tank.TemplatePath("no/keys", {}, self.project_root)
        input_path = os.path.join(self.project_root, "some", "thing", "else")
        self.assertRaises(TankError, template.get_fields, input_path)


class TestGetKeysSepInValue(TestTemplatePath):
    """Tests for cases where seperator used between keys is used in value for keys."""
    def setUp(self):
        super(TestGetKeysSepInValue, self).setUp()
        self.keys["Asset"] = StringKey("Asset")

    def assert_path_matches(self, definition, input_path, expected):
        template = TemplatePath(definition, self.keys, "")
        result = template.get_fields(input_path)
        self.assertEquals(expected, result)

    def test_double_key_first_precise(self):
        definition = "build/{Asset}/maya/{Asset}_{name}.ext"
        input_path = "build/cat_man_fever/maya/cat_man_fever_doogle.ext"
        expected = {"Asset": "cat_man_fever",
                    "name": "doogle"}
        self.assert_path_matches(definition, input_path, expected)

    def test_double_key_first_ambiguous(self):
        definition = "build/{Asset}_{name}/maya/{Asset}.ext"
        input_path = "build/cat_man_fever_doogle/maya/cat_man_fever.ext"
        expected = {"Asset": "cat_man_fever",
                    "name": "doogle"}
        self.assert_path_matches(definition, input_path, expected)

    def test_enum_ambigous(self):
        key = StringKey("Asset", choices=["cat_man", "dog_man"])
        self.keys["Asset"] = key
        definition = "build/maya/{Asset}_{name}.ext"
        input_path = "build/maya/cat_man_doogle.ext"
        expected = {"Asset": "cat_man",
                    "name": "doogle"}
        self.assert_path_matches(definition, input_path, expected)

    def test_enum_after_ambiguous(self):
        keys = {"Asset": StringKey("Asset"),
                "name": StringKey("name", choices=["dagle", "doogle"])}
        self.keys.update(keys)
        definition = "build/maya/{Asset}_{name}.ext"
        input_path = "build/maya/cat_man_doogle.ext"
        expected = {"Asset": "cat_man",
                    "name": "doogle"}
        self.assert_path_matches(definition, input_path, expected)

    def test_ambiguous(self):
        """
        Can't resolve if values are too ambiguous
        """
        definition = "build/maya/{Asset}_{name}.ext"
        input_path = "build/maya/cat_man_doogle.ext"
        template = TemplatePath(definition, self.keys, "")          
        expected_msg = ("Template %s: Ambiguous values found for key 'Asset' could be any of: 'cat', 'cat_man'" 
                        % template)
        self.check_error_message(TankError, expected_msg, template.get_fields, input_path)        
        
    def test_ambiguous_begining(self):
        """
        Can't resolve if values are too ambiguous
        """
        definition = "{Asset}_{name}/maya"
        input_path = "cat_man_doogle/maya"
        template = TemplatePath(definition, self.keys, "")          
        expected_msg = ("Template %s: Ambiguous values found for key 'Asset' could be any of: 'cat', 'cat_man'" 
                        % template)
        self.check_error_message(TankError, expected_msg, template.get_fields, input_path)        

    def test_ambiguous_end(self):
        """
        Can't resolve if values are too ambiguous
        """
        definition = "build/maya/{Asset}_{name}"
        input_path = "build/maya/cat_man_doogle"
        template = TemplatePath(definition, self.keys, "")          
        expected_msg = ("Template %s: Ambiguous values found for key 'Asset' could be any of: 'cat', 'cat_man'"
                        % template)
        self.check_error_message(TankError, expected_msg, template.get_fields, input_path)

    def test_multi_ambiguous(self):
        """
        Can't resolve if values are too ambiguous
        """        
        self.keys["favorites"] = StringKey("favorites")
        definition = "build/{Asset}_{name}_{favorites}/maya"
        input_path = "build/cat_man_doogle_do_dandy_dod/maya"
        template = TemplatePath(definition, self.keys, "")          
        expected_msg = ("Template %s: Ambiguous values found for key 'Asset' could be any of: "
                        "'cat', 'cat_man', 'cat_man_doogle', 'cat_man_doogle_do'" % template)
        self.check_error_message(TankError, expected_msg, template.get_fields, input_path)         

    def test_ambiguous_wrong_type(self):
        keys = {"some_num": IntegerKey("some_num"),
                "other_num": IntegerKey("other_num")}
        self.keys.update(keys)
        definition = "build/{Asset}_{some_num}_{other_num}.{ext}"
        input_path = "build/cat_1_man_14_2.jpeg"
        expected = {"Asset": "cat_1_man",
                    "some_num": 14,
                    "other_num": 2,
                    "ext": "jpeg"}
        self.assert_path_matches(definition, input_path, expected)

    def test_ambigous_alphanum_first(self):
        definition = "build/maya/{name_alpha}_{Asset}.ext"
        input_path = "build/maya/doogle_cat_man_fever.ext"
        expected = {"Asset": "cat_man_fever",
                    "name_alpha": "doogle"}
        self.assert_path_matches(definition, input_path, expected)

    def test_ambigous_alphanum_middle(self):
        """
        Can't resolve if values are too ambiguous
        """        
        self.keys["favorites"] = StringKey("favorites")
        definition = "build/maya/{Asset}_{name_alpha}_{favorites}.ext"
        input_path = "build/maya/cat_man_doogle_fever.ext"
        template = TemplatePath(definition, self.keys, "")          
        expected_msg = ("Template %s: Ambiguous values found for key 'Asset' could be any of: 'cat', 'cat_man'"
                        % template)
        self.check_error_message(TankError, expected_msg, template.get_fields, input_path)
        
    def test_ambigous_alphanum_after(self):
        definition = "build/maya/{Asset}_{name_alpha}.ext"
        input_path = "build/maya/cat_man_fever_doogle.ext"
        expected = {"Asset": "cat_man_fever",
                    "name_alpha": "doogle"}
        self.assert_path_matches(definition, input_path, expected)        


class TestParent(TestTemplatePath):
    def test_parent_exists(self):
        expected_definition = os.path.join("shots",
                                            "{Sequence}",
                                            "{Shot}",
                                            "{Step}",
                                            "work")
        parent_def = self.template_path.parent
        self.assertTrue(isinstance(parent_def, TemplatePath))
        self.assertEquals(expected_definition, parent_def.definition, self.project_root)

    def test_project_root(self):
        """
        Test that a template with no keys (e.g. the project root '/') has no parent template
        """
        self.assertTrue(self.project_root_template.parent is None)

    def test_no_parent_exists(self):
        definition = "{Shot}"
        template = TemplatePath(definition, self.keys, root_path=self.project_root)
        parent_def = template.parent
        self.assertTrue(parent_def is None)

    def test_aliased_key(self):
        """Test template which uses aliased key in it's definition."""
        keys = {}
        keys["old_name"] =  StringKey("new_name")
        definition = "{old_name}/something"
        template = TemplatePath(definition, keys, root_path=self.project_root)
        result = template.parent
        self.assertEquals("{new_name}", result.definition)



