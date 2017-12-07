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
import sys
import unittest2 as unittest

from mock import Mock, patch
from tank_vendor import yaml

import sgtk

import tank
from tank.api import Tank
from tank.errors import TankError
from tank.template import TemplatePath, TemplateString
from tank.templatekey import StringKey, IntegerKey, SequenceKey

from tank_test.tank_test_base import TankTestBase, setUpModule # noqa

class TestInit(TankTestBase):

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
        self.assertEquals(self.tk.documentation_url, None)

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


class TestTankFromPath(TankTestBase):

    def setUp(self):
        super(TestTankFromPath, self).setUp()
        self.setup_multi_root_fixtures()

    def test_primary_branch(self):
        """
        Test path from primary branch.
        """
        child_path = os.path.join(self.project_root, "child_dir")
        os.mkdir(os.path.join(self.project_root, "child_dir"))
        result = tank.tank_from_path(child_path)
        self.assertIsInstance(result, Tank)
        self.assertEquals(result.project_path, self.project_root)

    def test_alternate_branch(self):
        """
        Test path not from primary branch.
        """
        os.mkdir(os.path.join(self.alt_root_1, "child_dir"))
        child_path = os.path.join(self.alt_root_1, "child_dir")
        result = tank.tank_from_path(child_path)
        self.assertIsInstance(result, Tank)
        self.assertEquals(result.project_path, self.project_root)

    def test_bad_path(self):
        """
        Test path not in project tree.
        """
        bad_path = os.path.dirname(self.tank_temp)
        self.assertRaises(TankError, tank.tank_from_path, bad_path)

    def test_tank_temp(self):
        """
        Test passing in studio path.
        """
        self.assertRaises(TankError, tank.tank_from_path, self.tank_temp)


class TestTankFromPathDuplicatePcPaths(TankTestBase):
    """
    Test behavior and error messages when multiple pipeline
    configurations are pointing at the same location
    """

    def setUp(self):
        super(TestTankFromPathDuplicatePcPaths, self).setUp()

        # define an additional pipeline config with overlapping paths
        self.overlapping_pc = {
            "type": "PipelineConfiguration",
            "code": "Primary",
            "id": 123456,
            "project": self.project,
            "windows_path": self.pipeline_config_root,
            "mac_path": self.pipeline_config_root,
            "linux_path": self.pipeline_config_root}

        self.add_to_sg_mock_db(self.overlapping_pc)

    def test_primary_duplicates_from_path(self):
        """
        Test primary dupes
        """
        self.assertRaisesRegexp(TankError,
                                "The path '.*' is associated with more than one Primary pipeline configuration.",
                                sgtk.sgtk_from_path,
                                self.project_root)

    def test_primary_duplicates_from_entity(self):
        """
        Test primary dupes
        """
        self.assertRaisesRegexp(TankError,
                                "More than one primary pipeline configuration is associated with the entity",
                                sgtk.sgtk_from_entity,
                                "Project",
                                self.project["id"])

class TestTankFromEntityWithMixedSlashes(TankTestBase):
    """
    Tests the case where a Windows local storage uses forward slashes.
    """

    def test_with_mixed_slashes(self):
        """
        Check that a sgtk init works for this path
        """
        # only run this test on windows
        if sys.platform == "win32":

            self.sg_pc_entity["windows_path"] = self.pipeline_config_root.replace("\\", "/")
            self.add_to_sg_mock_db(self.sg_pc_entity)
            self.add_to_sg_mock_db(self.project)
            self.add_to_sg_mock_db({
                "type": "Shot",
                "id": 1,
                "project": self.project
            })

            os.environ["TANK_CURRENT_PC"] = self.pipeline_config_root
            try:
                sgtk.sgtk_from_entity("Shot", 1)
            finally:
                del os.environ["TANK_CURRENT_PC"]


class TestGetConfigInstallLocationPathSlashes(TankTestBase):
    """
    Tests the case where a Windows config location uses double slashes.
    """

    @patch("tank.pipelineconfig_utils._get_install_locations")
    def test_config_path_cleanup(self, get_install_locations_mock):
        """
        Check that any glitches in the path are correctly cleaned up.
        """
        # only run this test on windows
        if sys.platform == "win32":

            # This path has multiple issues we've encountered in the wild
            # It without any escaping sequence, it reads as
            # "   C:/configs\\site//project   "
            # 1. it has whitespace at the begging and end.
            # 2. Uses double slashes instead of single backslash
            # 3. Uses slash instead of backslash
            # 4. Uses double backslashes as a folder separator.
            get_install_locations_mock.return_value = sgtk.util.ShotgunPath("   C:/configs\\\\site//project   ", None, None)

            self.assertEqual(
                # We don't need to pass an actual path since _get_install_location is mocked.
                tank.pipelineconfig_utils.get_config_install_location(None),
                "C:\\configs\\site\\project"
            )


class TestTankFromPathWindowsNoSlash(TankTestBase):
    """
    Tests the edge case where a Windows local storage is set to be 'C:'
    """

    PROJECT_NAME = "temp"
    STORAGE_ROOT = "C:"

    def setUp(self):

        # set up a project named temp, so that it will end up in c:\temp
        super(TestTankFromPathWindowsNoSlash, self).setUp(parameters = {"project_tank_name": self.PROJECT_NAME})
        
        # set up std fixtures
        self.setup_fixtures()

        # patch primary local storage def
        self.primary_storage["windows_path"] = self.STORAGE_ROOT
        # re-add it
        self.add_to_sg_mock_db(self.primary_storage)

        # now re-write roots.yml
        roots = {"primary": {}}
        for os_name in ["windows_path", "linux_path", "mac_path"]:
            #TODO make os specific roots
            roots["primary"][os_name] = self.sg_pc_entity[os_name]
        roots_path = os.path.join(self.pipeline_config_root,
                                  "config",
                                  "core",
                                  "roots.yml")
        roots_file = open(roots_path, "w")
        roots_file.write(yaml.dump(roots))
        roots_file.close()

        # need a new pipeline config object that is
        # using the new roots def file we just created
        self.pipeline_configuration = sgtk.pipelineconfig_factory.from_path(self.pipeline_config_root)
        # push this new pipeline config into the tk api
        self.tk._Tank__pipeline_config = self.pipeline_configuration
        # force reload templates
        self.tk.reload_templates()


    def test_project_path_lookup(self):
        """
        Check that a sgtk init works for this path
        """
        # only run this test on windows
        if sys.platform == "win32":

            # probe a path inside of project
            test_path = "%s\\%s\\toolkit_test_path" % (self.STORAGE_ROOT, self.PROJECT_NAME)
            if not os.path.exists(test_path):
                os.makedirs(test_path)
            self.assertIsInstance(sgtk.sgtk_from_path(test_path), Tank)





class TestTankFromPathOverlapStorage(TankTestBase):
    """
    Tests edge case with overlapping storages

    For example, imagine the following setup:
    Storages: f:\ and f:\foo
    Project names: foo and bar
    This means we have the following project roots:
    (1) f:\foo      (storage f:\, project foo)
    (2) f:\bar      (storage f:\, project bar)
    (3) f:\foo\foo  (storage f:\foo, project foo)
    (4) f:\foo\bar  (storage f:\foo, project bar)

    The path f:\foo\bar\hello_world.ma could either belong to
    project bar (matching 4) or project foo (matching 1).

    In this case, sgtk_from_path() should succeed in case you are using a local
    tank command or API and fail if you are using a studio level command.

    """

    def setUp(self):

        # set up two storages and two projects
        super(TestTankFromPathOverlapStorage, self).setUp(parameters = {"project_tank_name": "foo"})

        # add second project
        self.project_2 = {"type": "Project",
                          "id": 2345,
                          "tank_name": "bar",
                          "name": "project_name"}

        # define entity for pipeline configuration
        self.project_2_pc = {"type": "PipelineConfiguration",
                             "code": "Primary",
                             "id": 123456,
                             "project": self.project_2,
                             "windows_path": "F:\\temp\\bar_pc",
                             "mac_path": "/tmp/bar_pc",
                             "linux_path": "/tmp/bar_pc"}

        self.add_to_sg_mock_db(self.project_2)
        self.add_to_sg_mock_db(self.project_2_pc)

        # set up std fixtures
        self.setup_multi_root_fixtures()

        # patch storages
        self.alt_storage_1["windows_path"] = "C:\\temp"
        self.alt_storage_1["mac_path"] = "/tmp"
        self.alt_storage_1["linux_path"] = "/tmp"

        self.alt_storage_2["windows_path"] = "C:\\temp\\foo"
        self.alt_storage_2["mac_path"] = "/tmp/foo"
        self.alt_storage_2["linux_path"] = "/tmp/foo"

        self.add_to_sg_mock_db(self.alt_storage_1)
        self.add_to_sg_mock_db(self.alt_storage_2)

        # Write roots file
        roots = {"primary": {}, "alternate_1": {}, "alternate_2": {}}
        for os_name in ["windows_path", "linux_path", "mac_path"]:
            roots["primary"][os_name] = os.path.dirname(self.project_root)
            roots["alternate_1"][os_name] = self.alt_storage_1[os_name]
            roots["alternate_2"][os_name] = self.alt_storage_2[os_name]
        roots_path = os.path.join(self.pipeline_config_root, "config", "core", "roots.yml")
        roots_file = open(roots_path, "w")
        roots_file.write(yaml.dump(roots))
        roots_file.close()

        # need a new pipeline config object that is using the new
        # roots def file we just created
        self.pipeline_configuration = sgtk.pipelineconfig_factory.from_path(self.pipeline_config_root)
        # push this new pipeline config into the tk api
        self.tk._Tank__pipeline_config = self.pipeline_configuration
        # force reload templates
        self.tk.reload_templates()


    def test_project_path_lookup_studio_mode(self):
        """
        When running this edge case from a studio install, we expect an error:

        TankError: The path '/tmp/foo/bar' is potentially associated with more than one primary
        pipeline configuration. This can happen if there is ambiguity in your project setup,
        where projects store their data in an overlapping fashion. In this case, try creating
        your API instance (or tank command) directly from the pipeline configuration rather
        than via the studio level API. This will explicitly call out which project you are
        intending to use in conjunction with he path. The pipeline configuration paths
        associated with this path are:
        ['/var/folders/fq/65bs7wwx3mz7jdsh4vxm34xc0000gn/T/tankTemporaryTestData_1422967258.765262/pipeline_configuration',
        '/tmp/bar_pc']

        """

        probe_path = {}
        probe_path["win32"] = "C:\\temp\\foo\\bar\\test.ma"
        probe_path["darwin"] = "/tmp/foo/bar/test.ma"
        probe_path["linux2"] = "/tmp/foo/bar/test.ma"

        test_path = probe_path[sys.platform]
        test_path_dir = os.path.dirname(test_path)

        if not os.path.exists(test_path_dir):
            os.makedirs(test_path_dir)

        self.assertRaisesRegexp(TankError,
                                "The path '.*' is associated with more than one Primary pipeline configuration.",
                                sgtk.sgtk_from_path,
                                test_path)



    def test_project_path_lookup_local_mode(self):
        """
        Check that a sgtk init works for this path
        """

        # By setting the TANK_CURRENT_PC, we emulate the behaviour
        # of a local API running. Push this variable
        old_tank_current_pc = None
        if "TANK_CURRENT_PC" in os.environ:
            old_tank_current_pc = os.environ["TANK_CURRENT_PC"]
        os.environ["TANK_CURRENT_PC"] = self.pipeline_config_root

        probe_path = {}
        probe_path["win32"] = "C:\\temp\\foo\\bar\\test.ma"
        probe_path["darwin"] = "/tmp/foo/bar/test.ma"
        probe_path["linux2"] = "/tmp/foo/bar/test.ma"

        test_path = probe_path[sys.platform]
        test_path_dir = os.path.dirname(test_path)

        if not os.path.exists(test_path_dir):
            os.makedirs(test_path_dir)

        self.assertIsInstance(sgtk.sgtk_from_path(test_path), Tank)

        # and pop the modification
        if old_tank_current_pc is None:
            del os.environ["TANK_CURRENT_PC"]
        else:
            os.environ["TANK_CURRENT_PC"] = old_tank_current_pc




