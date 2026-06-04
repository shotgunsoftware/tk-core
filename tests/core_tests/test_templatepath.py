# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os

import tank
from tank import TankError

from tank.template import TemplatePath
from tank_test.tank_test_base import ShotgunTestBase, setUpModule  # noqa
from tank.templatekey import StringKey, IntegerKey, SequenceKey
from tank.util import is_windows


class TestTemplatePath(ShotgunTestBase):
    """
    Base class for tests of TemplatePath. Do not add tests to this class directly.
    """

    def setUp(self):
        super().setUp(parameters={"primary_root_name": "primary_with_a_different_name"})
        # Make various types of keys(fields)
        self.keys = {
            "Sequence": StringKey("Sequence"),
            "Shot": StringKey("Shot", default="s1", choices=["s1", "s2", "shot_1"]),
            "Step": StringKey("Step"),
            "branch": StringKey("branch", filter_by="alphanumeric"),
            "name": StringKey("name"),
            "name_alpha": StringKey("name_alpha", filter_by="alphanumeric"),
            "version": IntegerKey("version", format_spec="03"),
            "snapshot": IntegerKey("snapshot", format_spec="03"),
            "ext": StringKey("ext"),
            "seq_num": SequenceKey("seq_num"),
            "frame": SequenceKey("frame", format_spec="04"),
        }
        # Make a template
        self.definition = "shots/{Sequence}/{Shot}/{Step}/work/{Shot}.{branch}.v{version}.{snapshot}.ma"

        # legacy style template object which only knows about the currently running operating system
        self.template_path_current_os_only = TemplatePath(
            self.definition, self.keys, self.project_root
        )

        project_root = os.path.join(self.tank_temp, "project_code")
        self._project_roots = {self.primary_root_name: {}}
        # Create the roots.yml like structure. Double down on the key names so it can be used in all scenarios
        # where we require the roots.
        for os_name in [
            "windows_path",
            "linux_path",
            "mac_path",
            "win32",
            "linux",
            "darwin",
        ]:
            self._project_roots[self.primary_root_name][os_name] = project_root
        self._primary_project_root = project_root

        # new style template object which supports all recognized platforms
        # get all OS roots for primary storage
        all_roots = self._project_roots[self.primary_root_name]

        self.template_path = TemplatePath(
            self.definition, self.keys, self.project_root, per_platform_roots=all_roots
        )

        self.project_root_template = TemplatePath(
            "/", self.keys, self.project_root, per_platform_roots=all_roots
        )

        # make template with sequence key
        self.sequence = TemplatePath("/path/to/seq.{frame}.ext", self.keys, "", "frame")


class TestInit(TestTemplatePath):
    def test_static_simple(self):
        pass
    def test_static_tokens(self):
        pass
class TestValidate(TestTemplatePath):
    """Test Case for validating a path"""

    def setUp(self):
        super().setUp()
        relative_path = os.path.join(
            "shots", "seq_1", "shot_1", "Anm", "work", "shot_1.mmm.v001.002.ma"
        )
        self.valid_path = os.path.join(self.project_root, relative_path)

    def test_project_root(self):
        pass
    def test_valid_path(self):
        pass
    def test_missing_directories(self):
        pass
    def test_missing_version(self):
        pass
    def test_conflicting_shot(self):
        pass
    def test_with_valid_input_values(self):
        pass
    def test_with_invalid_input_values(self):
        pass
    def test_skipping_keys_key_present(self):
        pass
    def test_skipping_keys_key_missing(self):
        pass
    def test_skip_key_type_not_match(self):
        pass
    def test_frame_number_valid(self):
        pass
    def test_nuke_format_valid(self):
        pass
    def test_shake_format_valid(self):
        pass
    def test_houdini_format_valid(self):
        pass
    def test_bad_characters(self):
        pass
    def test_mixed_framespecs(self):
        pass
    def test_incorrect_length(self):
        pass
    def test_bad_base_path(self):
        pass
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
        pass
class TestApplyFields(TestTemplatePath):
    def test_simple(self):
        pass
    def test_project_root(self):
        pass
    def test_multi_platform(self):
        pass
    def test_legacy_constructor_format(self):
        pass
    def test_fields_missing(self):
        pass
    def test_none_value(self):
        pass
    def test_wrong_type(self):
        pass
    def test_working_enum(self):
        pass
    def test_enum_bad_key(self):
        pass
    def test_default(self):
        pass
    def test_bad_alphanumeric(self):
        pass
    def test_not_using_defaults(self):
        pass
    def test_using_defaults(self):
        pass
    def test_good_alphanumeric(self):
        pass
    def test_aliased_key(self):
        pass
    # tests for template with a sequence key follow
    def test_frame_number(self):
        pass
    def test_nuke_framespec(self):
        pass
    def test_shake_hash_alt(self):
        pass
    def test_shake_ampersand(self):
        pass
    def test_houdini_framespec(self):
        pass
    def test_bad_values_not_ints(self):
        pass
    # end sequence key tests

    def test_optional_values(self):
        pass
    def test_multi_key_optional(self):
        pass
    def test_optional_none_value(self):
        pass
    def test_format_default(self):
        pass
class Test_ApplyFields(TestTemplatePath):
    """Tests for private TemplatePath._apply_fields"""

    def test_skip_enum(self):
        pass
    def test_ignore_type(self):
        pass
class TestGetFields(TestTemplatePath):
    def test_anim_path(self):
        pass
    def test_project_root(self):
        pass
    def test_key_first(self):
        pass
    def test_key_first_short(self):
        pass
    def test_one_key(self):
        pass
    def test_one_key_no_match(self):
        pass
    def test_diff_seperators(self):
        pass
    def test_missing_values(self):
        pass
    def test_conflicting_values(self):
        pass
    def test_skip_key(self):
        pass
    def test_string_for_int_type(self):
        pass
    def test_different_case(self):
        pass
    def test_matching_enum(self):
        pass
    def test_bad_enum(self):
        pass
    def test_definition_short_end_static(self):
        pass
    def test_definition_short_end_key(self):
        pass
    def test_key_at_end(self):
        pass
    def test_double_int_key(self):
        pass
    def test_valid_alphanumeric(self):
        pass
    def test_aliased_key(self):
        pass
    def test_frame_number(self):
        pass
    def test_nuke_framespec(self):
        pass
    def test_shake_ampersand(self):
        pass
    def test_houdini_framespec(self):
        pass
    def test_optional_sections(self):
        pass
    def test_optional_with_underscore(self):
        pass
    def test_is_optional(self):
        pass
    def test_no_keys_valid(self):
        pass
    def test_no_keys_invalid(self):
        pass
class TestGetKeysSepInValue(TestTemplatePath):
    """Tests for cases where seperator used between keys is used in value for keys."""

    def setUp(self):
        super().setUp()
        self.keys["Asset"] = StringKey("Asset")

    def assert_path_matches(self, definition, input_path, expected):
        template = TemplatePath(definition, self.keys, "")
        result = template.get_fields(input_path)
        self.assertEqual(expected, result)

    def test_double_key_first_precise(self):
        pass
    def test_double_key_first_ambiguous(self):
        pass
    def test_enum_ambigous(self):
        pass
    def test_enum_after_ambiguous(self):
        pass
    def test_ambiguous(self):
        pass
    def test_ambiguous_begining(self):
        pass
    def test_ambiguous_end(self):
        pass
    def test_multi_ambiguous(self):
        pass
    def test_ambiguous_wrong_type(self):
        pass
    def test_ambigous_alphanum_first(self):
        pass
    def test_ambigous_alphanum_middle(self):
        pass
    def test_ambigous_alphanum_after(self):
        pass
class TestParent(TestTemplatePath):
    def test_parent_exists(self):
        pass
    def test_project_root(self):
        pass
    def test_no_parent_exists(self):
        pass
    def test_aliased_key(self):
        pass
