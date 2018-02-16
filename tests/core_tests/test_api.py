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

from mock import Mock, patch


import tank
from tank.api import Tank
from tank.template import TemplatePath, TemplateString
from tank.templatekey import StringKey, IntegerKey, SequenceKey

from tank_test.tank_test_base import TankTestBase, setUpModule # noqa

class TestInit(TankTestBase):
    """Tests basic initialization of the sgtk API"""

    def setUp(self):
        super(TestInit, self).setUp()
        self.setup_fixtures()

    def test_project_from_param(self):
        tank = Tank(self.project_root)
        self.assertEquals(self.project_root, tank.project_path)


class TestTemplateFromPath(TankTestBase):
    """Cases testing Tank.template_from_path method"""
    def setUp(self):
        super(TestTemplateFromPath, self).setUp()
        self.setup_fixtures()

    def test_defined_path(self):
        """Resolve a path which maps to a template in the standard config"""
        file_path = os.path.join(self.project_root,
                'sequences/Sequence_1/shot_010/Anm/publish/shot_010.jfk.v001.ma')
        template = self.tk.template_from_path(file_path)
        self.assertIsInstance(template, TemplatePath)

    def test_undefined_path(self):
        """Resolve a path which does not map to a template"""
        file_path = os.path.join(self.project_root,
                'sequences/Sequence 1/shot_010/Anm/publish/')
        template = self.tk.template_from_path(file_path)
        self.assertTrue(template is None)

    def test_template_string(self):
        """Resolve 'path' which is a resolved TemplateString."""
        # resolved version of 'nuke_publish_name'
        str_path = "Nuke Script Name, v002"
        template = self.tk.template_from_path(str_path)
        self.assertIsNotNone(template)
        self.assertIsInstance(template, TemplateString)


class TestTemplatesLoaded(TankTestBase):
    """Test case for the loading of templates from project level config."""
    def setUp(self):
        super(TestTemplatesLoaded, self).setUp()
        self.setup_multi_root_fixtures()
        # some template names we know exist in the standard template
        self.expected_names = ["maya_shot_work", "nuke_shot_work"]

    def test_templates_loaded(self):
        actual_names = self.tk.templates.keys()
        for expected_name in self.expected_names:
            self.assertTrue(expected_name in actual_names)

    def test_get_template(self):
        for expected_name in self.expected_names:
            template = self.tk.templates.get(expected_name)
            self.assertTrue(isinstance(template, TemplatePath))

    def test_project_roots_set(self):
        """Test project root on templates with alternate and primary roots are set correctly."""

        primary_template = self.tk.templates["shot_project"]
        self.assertEquals(self.project_root, primary_template.root_path)

        alt_template = self.tk.templates["maya_shot_publish"]
        self.assertEquals(self.alt_root_1, alt_template.root_path)


class TestPathsFromTemplate(TankTestBase):
    """Tests for tank.paths_from_template using test data based on sg_standard setup."""
    def setUp(self):
        super(TestPathsFromTemplate, self).setUp()
        self.setup_fixtures()
        # create project data
        # two sequences
        seq1_path = os.path.join(self.project_root, "sequences/Seq_1")
        self.add_production_path(seq1_path,
                            {"type":"Sequence", "id":1, "name": "Seq_1"})
        seq2_path = os.path.join(self.project_root, "sequences/Seq_2")
        self.add_production_path(seq2_path,
                            {"type":"Sequence", "id":2, "name": "Seq_2"})
        # one shot
        shot_path = os.path.join(seq1_path, "Shot_1")
        self.add_production_path(shot_path,
                            {"type":"Shot", "id":1, "name": "shot_1"})
        # one step
        step_path = os.path.join(shot_path, "step_name")
        self.add_production_path(step_path,
                            {"type":"Step", "id":1, "name": "step_name"})

        # using template from standard setup
        self.template = self.tk.templates.get("maya_shot_work")

        # make some fake files with different versions
        fields = {"Sequence":"Seq_1",
                  "Shot": "shot_1",
                  "Step": "step_name",
                  "name": "filename"}
        fields["version"] = 1
        file_path = self.template.apply_fields(fields)
        self.file_1 = file_path
        self.create_file(self.file_1)
        fields["version"] = 2
        file_path = self.template.apply_fields(fields)
        self.file_2 = file_path
        self.create_file(self.file_2)


    def test_skip_sequence(self):
        """
        Test skipping the template key 'Sequence', which is part of the path
        definition, returns files from other sequences.
        """
        skip_keys = "Sequence"
        fields = {}
        fields["Shot"] = "shot_1"
        fields["Step"] = "step_name"
        fields["version"] = 1
        fields["Sequence"] = "Seq_2"
        expected = [self.file_1]
        actual = self.tk.paths_from_template(self.template, fields, skip_keys=skip_keys)
        self.assertEquals(expected, actual)

    def test_skip_version(self):
        """
        Test skipping a template key which is part of the file definition returns
        multiple files.
        """
        skip_keys = "version"
        fields = {}
        fields["Shot"] = "shot_1"
        fields["Step"] = "step_name"
        fields["version"] = 3
        fields["Sequence"] = "Seq_1"
        expected = [self.file_1, self.file_2]
        actual = self.tk.paths_from_template(self.template, fields, skip_keys=skip_keys)
        self.assertEquals(set(expected), set(actual))

    def test_skip_invalid(self):
        """Test that files not valid for an template are not returned.

        This refers to bug reported in Ticket #17090
        """
        keys = {"Shot": StringKey("Shot"),
                "Sequence": StringKey("Sequence"),
                "Step": StringKey("Step"),
                "name": StringKey("name"),
                "version": IntegerKey("version", format_spec="03")}

        definition = "sequences/{Sequence}/{Shot}/{Step}/work/{name}.v{version}.nk"
        template = TemplatePath(definition, keys, self.project_root, "my_template")
        self.tk._templates = {template.name: template}
        bad_file_path = os.path.join(self.project_root, "sequences", "Sequence1", "Shot1", "Foot", "work", "name1.va.nk")
        good_file_path = os.path.join(self.project_root, "sequences", "Sequence1", "Shot1", "Foot", "work", "name.v001.nk")
        self.create_file(bad_file_path)
        self.create_file(good_file_path)
        ctx_fields = {"Sequence": "Sequence1", "Shot": "Shot1", "Step": "Foot"}
        result = self.tk.paths_from_template(template, ctx_fields)
        self.assertIn(good_file_path, result)
        self.assertNotIn(bad_file_path, result)


class TestAbstractPathsFromTemplate(TankTestBase):
    """Tests Tank.abstract_paths_from_template method."""
    def setUp(self):
        super(TestAbstractPathsFromTemplate, self).setUp()
        self.setup_fixtures()


        keys = {"Sequence": StringKey("Sequence"),
                "Shot": StringKey("Shot"),
                "eye": StringKey("eye",
                       default="%V",
                       choices=["left","right","%V"],
                       abstract=True),
                "name": StringKey("name"),
                "SEQ": SequenceKey("SEQ", format_spec="04")}

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
        # getting everything will return the two abstract fields
        # using their default abstract values %V and %04d
        expected = [ os.path.join(self.shot_a_path, "%V", "filename.%04d.exr"),
                     os.path.join(self.shot_b_path, "%V", "filename.%04d.exr"),
                     os.path.join(self.shot_a_path, "%V", "anothername.%04d.exr"),
                     os.path.join(self.shot_b_path, "%V", "anothername.%04d.exr")]

        result = self.tk.abstract_paths_from_template(self.template, {})
        self.assertEquals(set(expected), set(result))

    def test_specify_shot(self):
        expected = [ os.path.join(self.shot_a_path, "%V", "filename.%04d.exr"),
                     os.path.join(self.shot_a_path, "%V", "anothername.%04d.exr")]

        result = self.tk.abstract_paths_from_template(self.template, {"Shot": "AAA"})
        self.assertEquals(set(expected), set(result))

    def test_bad_seq(self):
        expected = []
        result = self.tk.abstract_paths_from_template(self.template, {"Shot": "AAA", "SEQ": "####"})
        self.assertEquals(set(expected), set(result))

    def test_specific_frame(self):
        expected = [os.path.join(self.shot_a_path, "%V", "filename.0003.exr"),
                    os.path.join(self.shot_a_path, "%V", "anothername.0003.exr")]

        result = self.tk.abstract_paths_from_template(self.template, {"Shot": "AAA", "SEQ": 3})
        self.assertEquals(set(expected), set(result))

    def test_specify_eye(self):
        expected = [os.path.join(self.shot_a_path, "left", "anothername.%04d.exr"),
                    os.path.join(self.shot_a_path, "left", "filename.%04d.exr")]

        result = self.tk.abstract_paths_from_template(self.template, {"Shot": "AAA", "eye": "left"})
        self.assertEquals(set(expected), set(result))


    def test_specify_shot_and_name(self):
        expected = [os.path.join(self.shot_a_path, "%V", "filename.%04d.exr")]

        result = self.tk.abstract_paths_from_template(self.template, {"Shot": "AAA", "name": "filename"})
        self.assertEquals(set(expected), set(result))

    def test_specify_name(self):
        expected = [os.path.join(self.shot_a_path, "%V", "filename.%04d.exr"),
                    os.path.join(self.shot_b_path, "%V", "filename.%04d.exr")]
        result = self.tk.abstract_paths_from_template(self.template, {"name": "filename"})
        self.assertEquals(set(expected), set(result))


class TestPathsFromTemplateGlob(TankTestBase):
    """Tests for Tank.paths_from_template method which check the string sent to glob.glob."""
    def setUp(self):
        super(TestPathsFromTemplateGlob, self).setUp()
        keys = {"Shot": StringKey("Shot"),
                "version": IntegerKey("version", format_spec="03"),
                "seq_num": SequenceKey("seq_num", format_spec="05")}

        self.template = TemplatePath("{Shot}/{version}/filename.{seq_num}", keys, root_path=self.project_root)

    @patch("tank.api.glob.iglob")
    def assert_glob(self, fields, expected_glob, skip_keys, mock_glob):
        # want to ensure that value returned from glob is returned
        expected = [os.path.join(self.project_root, "shot_1","001","filename.00001")]
        mock_glob.return_value = expected
        retval = self.tk.paths_from_template(self.template, fields, skip_keys=skip_keys)
        self.assertEquals(expected, retval)
        # Check glob string
        expected_glob = os.path.join(self.project_root, expected_glob)
        glob_actual = [x[0][0] for x in mock_glob.call_args_list][0]
        self.assertEquals(expected_glob, glob_actual)

    def test_fully_qualified(self):
        """Test case where all field values are supplied."""
        skip_keys = None
        fields = {}
        fields["Shot"] = "shot_name"
        fields["version"] = 4
        fields["seq_num"] = 45
        expected_glob = os.path.join("%(Shot)s", "%(version)03d", "filename.%(seq_num)05d") % fields
        self.assert_glob(fields, expected_glob, skip_keys)

    def test_skip_dirs(self):
        """Test matching skipping at the directory level."""
        skip_keys = ["version"]
        fields = {}
        fields["Shot"] = "shot_name"
        fields["version"] = 4
        fields["seq_num"] = 45
        sep = os.path.sep
        glob_str = "%(Shot)s" + sep + "*" + sep + "filename.%(seq_num)05i"
        expected_glob =  glob_str % fields
        self.assert_glob(fields, expected_glob, skip_keys)

    def test_skip_file_token(self):
        """Test matching skipping tokens in file name."""
        skip_keys = ["seq_num"]
        fields = {}
        fields["Shot"] = "shot_name"
        fields["version"] = 4
        fields["seq_num"] = 45
        sep = os.path.sep
        glob_str = "%(Shot)s" + sep + "%(version)03d" + sep + "filename.*"
        expected_glob =  glob_str % fields
        self.assert_glob(fields, expected_glob, skip_keys)

    def test_missing_values(self):
        """Test skipping fields rather than using skip_keys."""
        skip_keys = None
        fields = {}
        fields["Shot"] = "shot_name"
        fields["seq_num"] = 45
        sep = os.path.sep
        glob_str = "%(Shot)s" + sep + "*" + sep + "filename.%(seq_num)05i"
        expected_glob =  glob_str % fields
        self.assert_glob(fields, expected_glob, skip_keys)


class TestApiProperties(TankTestBase):
    def setUp(self):
        super(TestApiProperties, self).setUp()

    def test_version_property(self):
        """
        test api.version property
        """
        self.assertEquals(self.tk.version, "HEAD")

    def test_doc_property(self):
        """
        test api.documentation_url property
        """
        self.assertEquals(self.tk.documentation_url, "https://support.shotgunsoftware.com/hc/en-us/articles/219039808")

    def test_shotgun_url_property(self):
        """
        test api.shotgun_url property
        """
        self.assertEquals(self.tk.shotgun_url, "http://unit_test_mock_sg")

    def test_shotgun_property(self):
        """
        test api.shotgun property
        """
        self.assertEquals(self.tk.shotgun.__class__.__name__, "Shotgun")

    def test_configuration_name_property(self):
        """
        test api.configuration_name property
        """
        self.assertEquals(self.tk.configuration_name, "Primary")

    def test_roots_property(self):
        """
        test api.roots property
        """
        self.assertEquals(self.tk.roots, {self.primary_root_name: self.project_root})


    def test_project_path_property(self):
        """
        test api.project_path property
        """
        self.assertEquals(self.tk.project_path, self.project_root)



class TestApiCache(TankTestBase):
    """
    Test the built in instance cache
    """
    def setUp(self):
        super(TestApiCache, self).setUp()

    def test_get_set(self):
        """
        test api.get_cache_item
        """
        self.assertEquals(self.tk.get_cache_item("foo"), None)
        self.assertEquals(self.tk.get_cache_item("bar"), None)

        self.tk.set_cache_item("foo", 123)

        self.assertEquals(self.tk.get_cache_item("foo"), 123)
        self.assertEquals(self.tk.get_cache_item("bar"), None)

        self.tk.set_cache_item("bar", 456)

        self.assertEquals(self.tk.get_cache_item("foo"), 123)
        self.assertEquals(self.tk.get_cache_item("bar"), 456)

        self.tk.set_cache_item("foo", None)

        self.assertEquals(self.tk.get_cache_item("foo"), None)
        self.assertEquals(self.tk.get_cache_item("bar"), 456)

        self.tk.set_cache_item("bar", None)

        self.assertEquals(self.tk.get_cache_item("foo"), None)
        self.assertEquals(self.tk.get_cache_item("bar"), None)


    def test_isolation(self):
        """
        Test that two tk instances use separate caches
        """
        tk2 = tank.sgtk_from_path(self.tk.pipeline_configuration.get_path())
        tk = self.tk

        self.assertEquals(tk.get_cache_item("foo"), None)
        self.assertEquals(tk2.get_cache_item("foo"), None)

        tk.set_cache_item("foo", 123)

        self.assertEquals(tk.get_cache_item("foo"), 123)
        self.assertEquals(tk2.get_cache_item("foo"), None)

        tk2.set_cache_item("foo", 456)

        self.assertEquals(tk.get_cache_item("foo"), 123)
        self.assertEquals(tk2.get_cache_item("foo"), 456)

        tk.set_cache_item("foo", None)

        self.assertEquals(tk.get_cache_item("foo"), None)
        self.assertEquals(tk2.get_cache_item("foo"), 456)

        tk2.set_cache_item("foo", None)

        self.assertEquals(tk.get_cache_item("foo"), None)
        self.assertEquals(tk2.get_cache_item("foo"), None)





