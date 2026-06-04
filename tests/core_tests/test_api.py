# Copyright (c) 2013 Shotgun Software Inc.
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
from tank.api import Tank
from tank.template import TemplatePath, TemplateString
from tank.templatekey import StringKey, IntegerKey, SequenceKey

from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import (
    mock,
    TankTestBase,
)


class TestInit(TankTestBase):
    """Tests basic initialization of the sgtk API"""

    def setUp(self):
        super().setUp()
        self.setup_fixtures()

    def test_project_from_param(self):
        pass
class TestTemplateFromPath(TankTestBase):
    """Cases testing Tank.template_from_path method"""

    def setUp(self):
        super().setUp()
        self.setup_fixtures()

    def test_defined_path(self):
        pass
    def test_undefined_path(self):
        pass
    def test_template_string(self):
        pass
class TestTemplatesLoaded(TankTestBase):
    """Test case for the loading of templates from project level config."""

    def setUp(self):
        super().setUp()
        self.setup_multi_root_fixtures()
        # some template names we know exist in the standard template
        self.expected_names = ["maya_shot_work", "nuke_shot_work"]

    def test_templates_loaded(self):
        pass
    def test_get_template(self):
        pass
    def test_project_roots_set(self):
        pass
class TestPathsFromTemplate(TankTestBase):
    """Tests for tank.paths_from_template using test data based on sg_standard setup."""

    def setUp(self):
        super().setUp()
        self.setup_fixtures()
        # create project data
        # two sequences
        seq1_path = os.path.join(self.project_root, "sequences/Seq_1")
        self.add_production_path(
            seq1_path, {"type": "Sequence", "id": 1, "name": "Seq_1"}
        )
        seq2_path = os.path.join(self.project_root, "sequences/Seq_2")
        self.add_production_path(
            seq2_path, {"type": "Sequence", "id": 2, "name": "Seq_2"}
        )
        # one shot
        shot_path = os.path.join(seq1_path, "Shot_1")
        self.add_production_path(shot_path, {"type": "Shot", "id": 1, "name": "shot_1"})
        # one step
        step_path = os.path.join(shot_path, "step_name")
        self.add_production_path(
            step_path, {"type": "Step", "id": 1, "name": "step_name"}
        )

        # using template from standard setup
        self.template = self.tk.templates.get("maya_shot_work")

        # make some fake files with different versions
        fields = {
            "Sequence": "Seq_1",
            "Shot": "shot_1",
            "Step": "step_name",
            "name": "filename",
        }
        fields["version"] = 1
        file_path = self.template.apply_fields(fields)
        self.file_1 = file_path
        self.create_file(self.file_1)
        fields["version"] = 2
        file_path = self.template.apply_fields(fields)
        self.file_2 = file_path
        self.create_file(self.file_2)

    def test_skip_sequence(self):
        pass
    def test_skip_version(self):
        pass
    def test_skip_invalid(self):
        pass
    def test_filenames_without_optional_keys(self):
        pass
class TestAbstractPathsFromTemplate(TankTestBase):
    """Tests Tank.abstract_paths_from_template method."""

    def setUp(self):
        super().setUp()
        self.setup_fixtures()

        keys = {
            "Sequence": StringKey("Sequence"),
            "Shot": StringKey("Shot"),
            "eye": StringKey(
                "eye", default="%V", choices=["left", "right", "%V"], abstract=True
            ),
            "name": StringKey("name"),
            "SEQ": SequenceKey("SEQ", format_spec="04"),
        }

        definition = "sequences/{Sequence}/{Shot}/{eye}/{name}.{SEQ}.exr"

        self.template = TemplatePath(definition, keys, self.project_root)

        # create fixtures
        seq_path = os.path.join(self.project_root, "sequences", "SEQ_001")
        self.shot_a_path = os.path.join(seq_path, "AAA")
        self.shot_b_path = os.path.join(seq_path, "BBB")

        eye_left_a = os.path.join(self.shot_a_path, "left")

        self.create_file(os.path.join(eye_left_a, "filename.0001.exr"))
        self.create_file(os.path.join(eye_left_a, "filename.0002.exr"))
        self.create_file(os.path.join(eye_left_a, "filename.0003.exr"))
        self.create_file(os.path.join(eye_left_a, "filename.0004.exr"))
        self.create_file(os.path.join(eye_left_a, "anothername.0001.exr"))
        self.create_file(os.path.join(eye_left_a, "anothername.0002.exr"))
        self.create_file(os.path.join(eye_left_a, "anothername.0003.exr"))
        self.create_file(os.path.join(eye_left_a, "anothername.0004.exr"))

        eye_left_b = os.path.join(self.shot_b_path, "left")

        self.create_file(os.path.join(eye_left_b, "filename.0001.exr"))
        self.create_file(os.path.join(eye_left_b, "filename.0002.exr"))
        self.create_file(os.path.join(eye_left_b, "filename.0003.exr"))
        self.create_file(os.path.join(eye_left_b, "filename.0004.exr"))
        self.create_file(os.path.join(eye_left_b, "anothername.0001.exr"))
        self.create_file(os.path.join(eye_left_b, "anothername.0002.exr"))
        self.create_file(os.path.join(eye_left_b, "anothername.0003.exr"))
        self.create_file(os.path.join(eye_left_b, "anothername.0004.exr"))

        eye_right_a = os.path.join(self.shot_a_path, "right")

        self.create_file(os.path.join(eye_right_a, "filename.0001.exr"))
        self.create_file(os.path.join(eye_right_a, "filename.0002.exr"))
        self.create_file(os.path.join(eye_right_a, "filename.0003.exr"))
        self.create_file(os.path.join(eye_right_a, "filename.0004.exr"))
        self.create_file(os.path.join(eye_right_a, "anothername.0001.exr"))
        self.create_file(os.path.join(eye_right_a, "anothername.0002.exr"))
        self.create_file(os.path.join(eye_right_a, "anothername.0003.exr"))
        self.create_file(os.path.join(eye_right_a, "anothername.0004.exr"))

        eye_right_b = os.path.join(self.shot_b_path, "right")

        self.create_file(os.path.join(eye_right_b, "filename.0001.exr"))
        self.create_file(os.path.join(eye_right_b, "filename.0002.exr"))
        self.create_file(os.path.join(eye_right_b, "filename.0003.exr"))
        self.create_file(os.path.join(eye_right_b, "filename.0004.exr"))
        self.create_file(os.path.join(eye_right_b, "anothername.0001.exr"))
        self.create_file(os.path.join(eye_right_b, "anothername.0002.exr"))
        self.create_file(os.path.join(eye_right_b, "anothername.0003.exr"))
        self.create_file(os.path.join(eye_right_b, "anothername.0004.exr"))

    def test_all_abstract(self):
        pass
    def test_specify_shot(self):
        pass
    def test_bad_seq(self):
        pass
    def test_specific_frame(self):
        pass
    def test_specify_eye(self):
        pass
    def test_specify_shot_and_name(self):
        pass
    def test_specify_name(self):
        pass
class TestPathsFromTemplateGlob(TankTestBase):
    """Tests for Tank.paths_from_template method which check the string sent to glob.glob."""

    def setUp(self):
        super().setUp()
        keys = {
            "Shot": StringKey("Shot"),
            "version": IntegerKey("version", format_spec="03"),
            "seq_num": SequenceKey("seq_num", format_spec="05"),
        }

        self.template = TemplatePath(
            "{Shot}/{version}/filename.{seq_num}", keys, root_path=self.project_root
        )

    @mock.patch("tank.api.glob.iglob")
    def assert_glob(self, fields, expected_glob, skip_keys, mock_glob):
        # want to ensure that value returned from glob is returned
        expected = [os.path.join(self.project_root, "shot_1", "001", "filename.00001")]
        mock_glob.return_value = expected
        retval = self.tk.paths_from_template(self.template, fields, skip_keys=skip_keys)
        self.assertEqual(expected, retval)
        # Check glob string
        expected_glob = os.path.join(self.project_root, expected_glob)
        glob_actual = [x[0][0] for x in mock_glob.call_args_list][0]
        self.assertEqual(expected_glob, glob_actual)

    def test_fully_qualified(self):
        pass
    def test_skip_dirs(self):
        pass
    def test_skip_file_token(self):
        pass
    def test_missing_values(self):
        pass
class TestApiProperties(TankTestBase):
    def setUp(self):
        super().setUp()

    def test_version_property(self):
        pass
    def test_doc_property(self):
        pass
    def test_shotgun_url_property(self):
        pass
    def test_shotgun_property(self):
        pass
    def test_configuration_name_property(self):
        pass
    def test_configuration_id_property(self):
        pass
    def test_configuration_mode_property(self):
        pass
    def test_roots_property(self):
        pass
    def test_project_path_property(self):
        pass
class TestApiCache(TankTestBase):
    """
    Test the built in instance cache
    """

    def setUp(self):
        super().setUp()

    def test_get_set(self):
        pass
    def test_isolation(self):
        pass
