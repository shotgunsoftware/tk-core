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
from tank import context, errors
from tank.util import is_windows
from tank_test.tank_test_base import (
    mock,
    TankTestBase,
    setUpModule,
    only_run_on_windows,
    only_run_on_nix,
)


class TestShotgunRegisterPublish(TankTestBase):
    def setUp(self):
        """Sets up entities in mocked shotgun database and creates Mock objects
        to pass in as callbacks to Schema.create_folders. The mock objects are
        then queried to see what paths the code attempted to create.
        """
        super().setUp()

        self.setup_fixtures()

        self.storage = {"type": "LocalStorage", "id": 1, "code": "Tank"}

        self.storage_2 = {
            "type": "LocalStorage",
            "id": 2,
            "code": "my_other_storage",
            "mac_path": "/tmp/nix",
            "windows_path": r"x:\tmp\win",
            "linux_path": "/tmp/nix",
        }

        self.storage_3 = {
            "type": "LocalStorage",
            "id": 3,
            "code": "unc paths",
            "windows_path": r"\\server\share",
        }

        # Add these to mocked shotgun
        self.add_to_sg_mock_db([self.storage, self.storage_2, self.storage_3])

        self.shot = {
            "type": "Shot",
            "name": "shot_name",
            "id": 2,
            "project": self.project,
        }
        self.step = {"type": "Step", "name": "step_name", "id": 4}

        context_data = {
            "tk": self.tk,
            "project": self.project,
            "entity": self.shot,
            "step": self.step,
        }

        self.context = context.Context(**context_data)
        self.path = os.path.join(self.project_root, "foo", "bar")
        self.name = "Test Publish"
        self.version = 1

    def test_local_storage_disabled(self):
        """
        Checks that if local storage is disabled that we raise a more user friendly error
        than a CRUD message.
        """
        with mock.patch.object(
            self.tk.shotgun,
            "create",
            side_effect=Exception("[Attachment.local_storage] does not exist"),
        ):

            if is_windows():
                local_path = r"x:\tmp\win\path\to\file.txt"
            else:
                local_path = "/tmp/nix/path/to/file.txt"

            with self.assertRaisesRegex(
                tank.util.ShotgunPublishError,
                "Local File Linking seems to be turned off",
            ):
                tank.util.register_publish(
                    self.tk, self.context, local_path, self.name, self.version
                )

    def test_sequence_abstracted_path(self):
        """Test that if path supplied represents a sequence, the abstract version of that
        sequence is used."""

        # make sequence key
        keys = {"seq": tank.templatekey.SequenceKey("seq", format_spec="03")}
        # make sequence template
        seq_template = tank.template.TemplatePath(
            "/folder/name_{seq}.ext", keys, self.project_root
        )
        self.tk.templates["sequence_template"] = seq_template

        seq_path = os.path.join(self.project_root, "folder", "name_001.ext")

        create_data = []
        # wrap create so we can keep tabs of things
        def create_mock(entity_type, data, return_fields=None):
            create_data.append(data)
            return real_create(entity_type, data, return_fields)

        real_create = self.tk.shotgun.create
        self.tk.shotgun.create = create_mock

        publish_data = tank.util.register_publish(
            self.tk, self.context, seq_path, self.name, self.version, dry_run=True
        )
        self.assertIsInstance(publish_data, dict)

        # mock sg.create, check it for path value
        try:
            tank.util.register_publish(
                self.tk, self.context, seq_path, self.name, self.version
            )
        finally:
            self.tk.shotgun.create = real_create

        # check that path is modified before sent to shotgun
        expected_path = os.path.join(self.project_root, "folder", "name_%03d.ext")
        project_name = os.path.basename(self.project_root)
        expected_path_cache = "%s/%s/%s" % (project_name, "folder", "name_%03d.ext")

        actual_path = create_data[0]["path"]["local_path"]
        actual_path_cache = create_data[0]["path_cache"]

        self.assertEqual(expected_path, actual_path)
        self.assertEqual(expected_path_cache, actual_path_cache)

    @mock.patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.create")
    def test_url_paths(self, create_mock):
        """Tests the passing of urls via the path."""

        publish_data = tank.util.register_publish(
            self.tk,
            self.context,
            "file:///path/to/file with spaces.png",
            self.name,
            self.version,
            dry_run=True,
        )
        self.assertIsInstance(publish_data, dict)

        tank.util.register_publish(
            self.tk,
            self.context,
            "file:///path/to/file with spaces.png",
            self.name,
            self.version,
        )

        create_data = create_mock.call_args
        args, kwargs = create_data
        sg_dict = args[1]

        self.assertEqual(
            sg_dict["path"],
            {
                "url": "file:///path/to/file%20with%20spaces.png",
                "name": "file with spaces.png",
            },
        )
        self.assertEqual("pathcache" not in sg_dict, True)

    @mock.patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.create")
    def test_url_paths_host(self, create_mock):
        """Tests the passing of urls via the path."""

        publish_data = tank.util.register_publish(
            self.tk,
            self.context,
            "https://site.com",
            self.name,
            self.version,
            dry_run=True,
        )
        self.assertIsInstance(publish_data, dict)

        tank.util.register_publish(
            self.tk, self.context, "https://site.com", self.name, self.version
        )

        create_data = create_mock.call_args
        args, kwargs = create_data
        sg_dict = args[1]

        self.assertEqual(
            sg_dict["path"], {"url": "https://site.com", "name": "site.com"}
        )
        self.assertEqual("pathcache" not in sg_dict, True)

    @mock.patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.create")
    def test_local_storage_publish(self, create_mock):
        """
        Tests that we generate local file links when publishing to a known storage
        """
        if is_windows():
            values = [
                r"x:\tmp\win\path\to\file.txt",
                r"\\server\share\path\to\file.txt",
            ]

        else:
            values = ["/tmp/nix/path/to/file.txt"]

        # Various paths we support, Unix and Windows styles
        for local_path in values:

            publish_data = tank.util.register_publish(
                self.tk, self.context, local_path, self.name, self.version, dry_run=True
            )
            self.assertIsInstance(publish_data, dict)

            tank.util.register_publish(
                self.tk, self.context, local_path, self.name, self.version
            )

            create_data = create_mock.call_args
            args, kwargs = create_data
            sg_dict = args[1]

            self.assertEqual(sg_dict["path"], {"local_path": local_path})

            self.assertTrue("pathcache" not in sg_dict)

    @mock.patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.create")
    def test_freeform_publish(self, create_mock):
        """
        Tests that we generate url file:// links for freeform paths
        """
        if is_windows():
            values = {
                "C:/path/to/test file.png": {
                    "url": "file:///C:/path/to/test%20file.png",
                    "name": "test file.png",
                },
                "e:/path/to/test file.png": {
                    "url": "file:///E:/path/to/test%20file.png",
                    "name": "test file.png",
                },
                "//path/to/test file.png": {
                    "url": "file://path/to/test%20file.png",
                    "name": "test file.png",
                },
                r"C:\path\to\test file.png": {
                    "url": "file:///C:/path/to/test%20file.png",
                    "name": "test file.png",
                },
                r"e:\path\to\test file.png": {
                    "url": "file:///E:/path/to/test%20file.png",
                    "name": "test file.png",
                },
                r"\\path\to\test file.png": {
                    "url": "file://path/to/test%20file.png",
                    "name": "test file.png",
                },
            }

        else:
            values = {
                "/path/to/test file.png": {
                    "url": "file:///path/to/test%20file.png",
                    "name": "test file.png",
                }
            }

        # Various paths we support, Unix and Windows styles
        for (local_path, path_dict) in values.items():

            publish_data = tank.util.register_publish(
                self.tk, self.context, local_path, self.name, self.version, dry_run=True
            )
            self.assertIsInstance(publish_data, dict)

            tank.util.register_publish(
                self.tk, self.context, local_path, self.name, self.version
            )

            create_data = create_mock.call_args
            args, kwargs = create_data
            sg_dict = args[1]

            self.assertEqual(sg_dict["path"], path_dict)
            self.assertTrue("pathcache" not in sg_dict)

    def test_publish_errors(self):
        """Tests exceptions raised on publish errors."""

        # Try publishing with various wrong arguments and test the exceptions
        # being raised contain the PublishedEntity when it was created

        # Publish with an invalid Version, no PublishEntity should have been
        # created
        with self.assertRaises(tank.util.ShotgunPublishError) as cm:

            publish_data = tank.util.register_publish(
                self.tk,
                self.context,
                "bad_version",
                self.name,
                {"id": -1, "type": "Version"},
                dry_run=True,
            )
            self.assertIsInstance(publish_data, dict)

            tank.util.register_publish(
                self.tk,
                self.context,
                "bad_version",
                self.name,
                {"id": -1, "type": "Version"},
            )
        self.assertIsNone(cm.exception.entity)

        # Force failure after the PublishedFile was created and check we get it
        # in the Exception last args.

        # Replace upload_thumbnail with a constant failure
        def raise_value_error(*arg, **kwargs):
            raise ValueError("Failed")

        with mock.patch(
            "tank_vendor.shotgun_api3.lib.mockgun.Shotgun.upload_thumbnail",
            new=raise_value_error,
        ):
            with self.assertRaises(tank.util.ShotgunPublishError) as cm:

                publish_data = tank.util.register_publish(
                    self.tk,
                    self.context,
                    "Constant failure",
                    self.name,
                    self.version,
                    dependencies=[-1],
                    dry_run=True,
                )
                self.assertIsInstance(publish_data, dict)

                tank.util.register_publish(
                    self.tk,
                    self.context,
                    "Constant failure",
                    self.name,
                    self.version,
                    dependencies=[-1],
                )
        self.assertIsInstance(cm.exception.entity, dict)
        self.assertTrue(
            cm.exception.entity["type"]
            == tank.util.get_published_file_entity_type(self.tk)
        )

        # Replace upload_thumbnail with a constant IO error
        def raise_io_error(*arg, **kwargs):
            open("/this/file/does/not/exist/or/we/are/very/unlucky.txt", "r")

        with mock.patch(
            "tank_vendor.shotgun_api3.lib.mockgun.Shotgun.upload_thumbnail",
            new=raise_io_error,
        ):
            with self.assertRaises(tank.util.ShotgunPublishError) as cm:

                publish_data = tank.util.register_publish(
                    self.tk,
                    self.context,
                    "dummy_path.txt",
                    self.name,
                    self.version,
                    dependencies=[-1],
                    dry_run=True,
                )
                self.assertIsInstance(publish_data, dict)

                tank.util.register_publish(
                    self.tk,
                    self.context,
                    "dummy_path.txt",
                    self.name,
                    self.version,
                    dependencies=[-1],
                )
        self.assertIsInstance(cm.exception.entity, dict)
        self.assertTrue(
            cm.exception.entity["type"]
            == tank.util.get_published_file_entity_type(self.tk)
        )


class TestMultiRoot(TankTestBase):
    def setUp(self):
        super().setUp()
        self.setup_multi_root_fixtures()

        self.shot = {
            "type": "Shot",
            "name": "shot_name",
            "id": 2,
            "project": self.project,
        }
        self.step = {"type": "Step", "name": "step_name", "id": 4}

        context_data = {
            "tk": self.tk,
            "project": self.project,
            "entity": self.shot,
            "step": self.step,
        }

        self.context = context.Context(**context_data)
        self.path = os.path.join(self.project_root, "foo", "bar")
        self.name = "Test Publish"
        self.version = 1

        # mock server caps so we can test local storage mapping for publishes
        class server_capsMock:
            def __init__(self):
                self.version = (7, 0, 1)

        self.mockgun.server_caps = server_capsMock()

        # Prevents an actual connection to a Shotgun site.
        self._server_caps_mock = mock.patch("tank_vendor.shotgun_api3.Shotgun.server_caps")
        self._server_caps_mock.start()
        self.addCleanup(self._server_caps_mock.stop)

    def test_storage_misdirection(self):

        # publish a file to root 3 path. should map to alt 4 storage
        publish_data = tank.util.register_publish(
            self.tk,
            self.context,
            os.path.join(self.alt_root_3, "foo", "bar"),
            self.name,
            self.version,
            dry_run=True,
        )
        self.assertTrue(publish_data["path"]["local_storage"]["id"], 7780)

        # publish a file to root 4 path. should map to alt 3 storage
        publish_data = tank.util.register_publish(
            self.tk,
            self.context,
            os.path.join(self.alt_root_4, "foo", "bar"),
            self.name,
            self.version,
            dry_run=True,
        )
        self.assertTrue(publish_data["path"]["local_storage"]["id"], 7781)


class TestCalcPathCache(TankTestBase):
    @mock.patch("tank.pipelineconfig.PipelineConfiguration.get_local_storage_roots")
    def test_case_difference(self, get_local_storage_roots):
        """
        Case that root case is different between input path and that in roots file.
        Bug Ticket #18116
        """
        get_local_storage_roots.return_value = {"primary": self.tank_temp}

        relative_path = os.path.join("Some", "Path")
        wrong_case_root = self.project_root.swapcase()
        expected = os.path.join(
            os.path.basename(wrong_case_root), relative_path
        ).replace(os.sep, "/")

        input_path = os.path.join(wrong_case_root, relative_path)
        root_name, path_cache = tank.util.shotgun.publish_creation._calc_path_cache(
            self.tk, input_path
        )
        assert root_name == "primary"
        assert path_cache == expected

    @only_run_on_windows
    @mock.patch("tank.pipelineconfig.PipelineConfiguration.get_local_storage_roots")
    def test_path_normalization_win_drive_letter(self, get_local_storage_roots):
        """
        Ensures that a variety of different slash syntaxes are valid when splitting
        a path into a storage + path cache field while using a windows drive letter path.
        """
        # note - this return value is guaranteed to be normalized
        # so no need to test for edge cases
        get_local_storage_roots.return_value = {"primary": "P:\\"}

        input_paths = [
            r"P:\project_code\3d\Assets",
            r"P:/project_code/3d/Assets",
            r"P://project_code//3d//Assets",
            r"P:\\project_code\\3d\\Assets",
        ]

        for input_path in input_paths:
            root_name, path_cache = tank.util.shotgun.publish_creation._calc_path_cache(
                self.tk, input_path
            )
            self.assertEqual("primary", root_name)
            self.assertEqual("project_code/3d/Assets", path_cache)

    @only_run_on_windows
    @mock.patch("tank.pipelineconfig.PipelineConfiguration.get_local_storage_roots")
    def test_path_normalization_win_unc(self, get_local_storage_roots):
        """
        Ensures that a variety of different slash syntaxes are valid when splitting
        a path into a storage + path cache field while using a windows unc path
        """
        # note - this return value is guaranteed to be normalized
        # so no need to test for edge cases
        get_local_storage_roots.return_value = {"primary": "\\\\share"}

        input_paths = [
            r"\\share\project_code\3d\Assets",
            r"//share/project_code/3d/Assets",
        ]

        for input_path in input_paths:
            root_name, path_cache = tank.util.shotgun.publish_creation._calc_path_cache(
                self.tk, input_path
            )
            self.assertEqual("primary", root_name)
            self.assertEqual("project_code/3d/Assets", path_cache)

    @only_run_on_nix
    @mock.patch("tank.pipelineconfig.PipelineConfiguration.get_local_storage_roots")
    def test_path_normalization_nix(self, get_local_storage_roots):
        """
        Ensures that a variety of different slash syntaxes are valid when splitting
        a path into a storage + path cache field while using linux or mac
        """
        # note - this return value is guaranteed to be normalized
        # so no need to test for edge cases
        get_local_storage_roots.return_value = {"primary": "/mnt"}

        input_paths = [
            r"/mnt\project_code\3d\Assets",
            r"\mnt\project_code\3d\Assets",
            r"/mnt/project_code//3d///Assets",
        ]

        for input_path in input_paths:
            root_name, path_cache = tank.util.shotgun.publish_creation._calc_path_cache(
                self.tk, input_path
            )
            self.assertEqual("primary", root_name)
            self.assertEqual("project_code/3d/Assets", path_cache)

    @mock.patch("tank.pipelineconfig.PipelineConfiguration.get_local_storage_roots")
    def test_project_names_only_current_project(self, get_local_storage_roots):
        """
        Test _calc_path_cache with project_names as a single list containing the
        current project. The result shoudl be the as when not passing any project_names.
        """

        project_names = [self.tk.pipeline_configuration.get_project_disk_name()]
        get_local_storage_roots.return_value = {"primary": self.tank_temp}

        relative_path = os.path.join("Some", "Path")
        wrong_case_root = self.project_root.swapcase()
        expected = os.path.join(
            os.path.basename(wrong_case_root), relative_path
        ).replace(os.sep, "/")

        input_path = os.path.join(wrong_case_root, relative_path)
        root_name, path_cache = tank.util.shotgun.publish_creation._calc_path_cache(
            self.tk, input_path
        )
        root_name2, path_cache2 = tank.util.shotgun.publish_creation._calc_path_cache(
            self.tk, input_path, project_names=project_names
        )
        assert root_name == root_name2
        assert path_cache == path_cache2
        # make sure the results are correct
        assert root_name == "primary"
        assert path_cache == expected

    @mock.patch("tank.pipelineconfig.PipelineConfiguration.get_local_storage_roots")
    def test_project_names_multiple(self, get_local_storage_roots):
        """
        Test _calc_path_cache with project_names as a list of more than one.
        """

        # create and add a second project to the mock db
        _, proj_2_root = self.create_project({"name": "second project"})
        proj_2_name = os.path.basename(proj_2_root)
        current_project_name = self.tk.pipeline_configuration.get_project_disk_name()

        get_local_storage_roots.return_value = {"primary": self.tank_temp}
        relative_path = os.path.join("Some", "Path")

        # input and expected values for current project
        current_project_root = self.project_root.swapcase()
        current_project_expected = os.path.join(
            os.path.basename(current_project_root), relative_path
        ).replace(os.sep, "/")
        current_project_input_path = os.path.join(current_project_root, relative_path)

        # input and expected values for second project
        proj_2_expected = os.path.join(
            os.path.basename(proj_2_name), relative_path
        ).replace(os.sep, "/")
        proj_2_input_path = os.path.join(proj_2_root, relative_path)

        # exclude the project name associated with this input path
        root_name, path_cache = tank.util.shotgun.publish_creation._calc_path_cache(
            self.tk, current_project_input_path, project_names=[proj_2_name]
        )
        assert root_name is None
        assert path_cache is None
        # do the same for the second project
        root_name, path_cache = tank.util.shotgun.publish_creation._calc_path_cache(
            self.tk, proj_2_input_path, project_names=[current_project_name]
        )
        assert root_name is None
        assert path_cache is None

        # include the project name associated with the input path
        root_name, path_cache = tank.util.shotgun.publish_creation._calc_path_cache(
            self.tk,
            current_project_input_path,
            project_names=[proj_2_name, current_project_name],
        )
        assert root_name == "primary"
        assert path_cache == current_project_expected
        # do the same for the second project
        root_name, path_cache = tank.util.shotgun.publish_creation._calc_path_cache(
            self.tk,
            proj_2_input_path,
            project_names=[proj_2_name, current_project_name],
        )
        assert root_name == "primary"
        assert path_cache == proj_2_expected


class TestCalcPathCacheProjectWithSlash(TankTestBase):
    def setUp(self):
        """Sets up entities in mocked shotgun database and creates Mock objects
        to pass in as callbacks to Schema.create_folders. The mock objects are
        then queried to see what paths the code attempted to create.
        """
        super().setUp(
            {"project_tank_name": "foo/bar"}
        )

    @mock.patch("tank.pipelineconfig.PipelineConfiguration.get_local_storage_roots")
    def test_multi_project_root(self, get_local_storage_roots):
        """
        Testing path cache calculations for project names with slashes
        """
        get_local_storage_roots.return_value = {"primary": self.tank_temp}

        relative_path = os.path.join("Some", "Path")
        expected = os.path.join("foo", "bar", relative_path).replace(os.sep, "/")
        input_path = os.path.join(self.project_root, relative_path)

        root_name, path_cache = tank.util.shotgun.publish_creation._calc_path_cache(
            self.tk, input_path
        )
        self.assertEqual("primary", root_name)
        self.assertEqual(expected, path_cache)
