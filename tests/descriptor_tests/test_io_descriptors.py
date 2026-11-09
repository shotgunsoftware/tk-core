# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import builtins
import os
import sys

import sgtk
from tank_test.tank_test_base import (
    ShotgunTestBase,
    setUpModule,  # noqa
    temp_env_var,
)


class TestIODescriptors(ShotgunTestBase):
    """
    Testing the Shotgun deploy main API methods
    """

    def test_version_resolve(self):
        """
        Tests the is_descriptor_version_missing method
        """
        self.assertEqual(
            sgtk.descriptor.is_descriptor_version_missing(
                {"type": "app_store", "version": "v1.1.1", "name": "tk-bundle"}
            ),
            False,
        )
        self.assertEqual(
            sgtk.descriptor.is_descriptor_version_missing(
                {"type": "app_store", "name": "tk-bundle"}
            ),
            True,
        )
        self.assertEqual(
            sgtk.descriptor.is_descriptor_version_missing(
                "sgtk:descriptor:app_store?version=v0.1.2&name=tk-bundle"
            ),
            False,
        )
        self.assertEqual(
            sgtk.descriptor.is_descriptor_version_missing(
                "sgtk:descriptor:app_store?name=tk-bundle"
            ),
            True,
        )
        self.assertEqual(
            sgtk.descriptor.is_descriptor_version_missing(
                {"type": "dev", "path": "/tmp"}
            ),
            False,
        )
        self.assertEqual(
            sgtk.descriptor.is_descriptor_version_missing(
                {"type": "path", "path": "/tmp"}
            ),
            False,
        )
        self.assertEqual(
            sgtk.descriptor.is_descriptor_version_missing(
                {"type": "manual", "name": "foo"}
            ),
            True,
        )
        self.assertEqual(
            sgtk.descriptor.is_descriptor_version_missing(
                {"type": "shotgun", "name": "foo"}
            ),
            True,
        )
        self.assertEqual(
            sgtk.descriptor.is_descriptor_version_missing(
                {"type": "shotgun", "id": 123}
            ),
            True,
        )
        self.assertEqual(
            sgtk.descriptor.is_descriptor_version_missing(
                {"type": "git", "path": "foo"}
            ),
            True,
        )
        self.assertEqual(
            sgtk.descriptor.is_descriptor_version_missing(
                {"type": "git_branch", "path": "foo"}
            ),
            True,
        )

    def test_latest_cached(self):
        """
        Tests the find_latest_cached_version method
        """
        sg = self.mockgun
        root = os.path.join(self.project_root, "latest_cached_root")

        d = sgtk.descriptor.create_descriptor(
            sg,
            sgtk.descriptor.Descriptor.APP,
            {"type": "app_store", "version": "v1.1.1", "name": "tk-bundle"},
            bundle_cache_root_override=root,
        )

        d2 = sgtk.descriptor.create_descriptor(
            sg,
            sgtk.descriptor.Descriptor.APP,
            {"type": "app_store", "version": "v1.2.1", "name": "tk-bundle"},
            bundle_cache_root_override=root,
        )

        d3 = sgtk.descriptor.create_descriptor(
            sg,
            sgtk.descriptor.Descriptor.APP,
            {"type": "app_store", "version": "v1.3.1", "name": "tk-bundle"},
            bundle_cache_root_override=root,
        )

        self.assertEqual(d.get_path(), None)
        self.assertEqual(d.find_latest_cached_version(), None)

        app_path = os.path.join(root, "app_store", "tk-bundle", "v1.1.1")
        path = os.path.join(app_path, "info.yml")

        os.makedirs(app_path)
        fh = open(path, "wt")
        fh.write("test data\n")
        fh.close()

        self.assertEqual(d.get_path(), app_path)
        self.assertEqual(d.find_latest_cached_version(), d)

        self.assertEqual(d2.get_path(), None)

        app_path = os.path.join(root, "app_store", "tk-bundle", "v1.2.1")
        path = os.path.join(app_path, "info.yml")
        os.makedirs(app_path)
        fh = open(path, "wt")
        fh.write("test data\n")
        fh.close()

        self.assertEqual(d2.get_path(), app_path)
        self.assertEqual(d.find_latest_cached_version(), d2)

        # Check to make sure we find a bundle that doesn't have an info.yml.
        app_path = os.path.join(root, "app_store", "tk-bundle", "v1.3.1")
        os.makedirs(app_path)

        self.assertEqual(d3.get_path(), app_path)
        self.assertEqual(d.find_latest_cached_version(), d3)

        # now check constraints
        self.assertEqual(d.find_latest_cached_version("v1.1.x"), d)
        self.assertEqual(d.find_latest_cached_version("v1.2.x"), d2)
        self.assertEqual(d.find_latest_cached_version("v1.x.x"), d3)
        self.assertEqual(d.find_latest_cached_version("v2.x.x"), None)

    def test_cache_locations(self):
        """
        Tests locations of caches when using fallback paths and
        the bundle cache path environment variable.
        """
        sg = self.mockgun

        root_a = os.path.join(self.project_root, "cache_root_a")
        root_b = os.path.join(self.project_root, "cache_root_b")
        root_c = os.path.join(self.project_root, "cache_root_c")
        root_d = os.path.join(self.project_root, "cache_root_d")
        root_env = os.path.join(self.project_root, "cache_root_env")

        location = {"type": "app_store", "version": "v1.1.1", "name": "tk-bundle"}

        d = sgtk.descriptor.create_descriptor(
            sg,
            sgtk.descriptor.Descriptor.APP,
            location,
            bundle_cache_root_override=root_a,
            fallback_roots=[root_b, root_c, root_d],
        )

        self.assertEqual(
            d._io_descriptor._get_primary_cache_path(),
            os.path.join(root_a, "app_store", "tk-bundle", "v1.1.1"),
        )

        # the bundle cache path set in the environment should
        # take precedence other cache paths.
        with temp_env_var(SHOTGUN_BUNDLE_CACHE_PATH=root_env):
            desc_env = sgtk.descriptor.create_descriptor(
                sg,
                sgtk.descriptor.Descriptor.APP,
                location,
                bundle_cache_root_override=root_a,
                fallback_roots=[root_b, root_c, root_d],
            )

            self.assertEqual(
                desc_env._io_descriptor._get_primary_cache_path(),
                os.path.join(root_env, "app_store", "tk-bundle", "v1.1.1"),
            )

        self.assertEqual(
            d._io_descriptor._get_cache_paths(),
            [
                os.path.join(root_b, "app_store", "tk-bundle", "v1.1.1"),
                os.path.join(root_c, "app_store", "tk-bundle", "v1.1.1"),
                os.path.join(root_d, "app_store", "tk-bundle", "v1.1.1"),
                os.path.join(root_a, "app_store", "tk-bundle", "v1.1.1"),
                os.path.join(
                    root_a, "apps", "app_store", "tk-bundle", "v1.1.1"
                ),  # legacy path
            ],
        )

    def test_git_branch_descriptor_input(self):
        """
        Tests that Short integer commit hashes descriptors are converted to a str type
        """
        self.git_repo_uri = os.path.join(
            self.fixtures_root, "tk-multi-shotgunpanel.git"
        )
        sg = self.mockgun
        location = {
            "type": "git_branch",
            "version": 6547378,
            "branch": "master",
            "path": self.git_repo_uri,
        }
        d = sgtk.descriptor.create_descriptor(
            sg,
            sgtk.descriptor.Descriptor.APP,
            location,
        )

        self.assertEqual(
            d._io_descriptor._get_bundle_cache_path(self.cache_root),
            os.path.join(
                self.cache_root, "gitbranch", "tk-multi-shotgunpanel.git", "6547378"
            ),
        )
        self.assertEqual(d.version, "6547378")
        self.assertEqual(d._io_descriptor.get_dict()["version"], "6547378")

    def test_download_receipt(self):
        """
        Tests the download receipt logic
        """
        sg = self.mockgun
        root = os.path.join(self.project_root, "cache_root")

        d = sgtk.descriptor.create_descriptor(
            sg,
            sgtk.descriptor.Descriptor.APP,
            {"type": "app_store", "version": "v1.1.1", "name": "tk-bundle"},
            bundle_cache_root_override=root,
        )

        self.assertEqual(d.get_path(), None)
        self.assertEqual(d.find_latest_cached_version(), None)

        bundle_path = os.path.join(root, "app_store", "tk-bundle", "v1.1.1")
        info_path = os.path.join(bundle_path, "info.yml")

        os.makedirs(bundle_path)
        with open(info_path, "wt") as fh:
            fh.write("test data\n")

        self.assertEqual(d.get_path(), bundle_path)
        self.assertEqual(d.find_latest_cached_version(), d)

    def test_custom_io_descriptor_module(self) -> None:
        """
        Tests that modules listed in FLOWPT_IO_DESCRIPTOR_MODULES register types.
        """
        from sgtk.descriptor.errors import RegisterDescriptorError
        from sgtk.descriptor.io_descriptor import _register_custom_descriptors
        from sgtk.descriptor.io_descriptor.base import IODescriptorBase

        module_dir = os.path.join(self.tank_temp, "custom_io_modules")
        os.makedirs(module_dir)
        with open(os.path.join(module_dir, "custom_io_ok.py"), "wt") as fh:
            fh.write(
                "def register_io_descriptors(base):\n"
                "    base.register_descriptor_factory('custom_test', object)\n"
            )
        with open(os.path.join(module_dir, "custom_io_bad.py"), "wt") as fh:
            fh.write("raise ImportError('boom')\n")

        sys.path.insert(0, module_dir)
        self.addCleanup(sys.path.remove, module_dir)
        self.addCleanup(IODescriptorBase._factory.pop, "custom_test", None)

        with temp_env_var(FLOWPT_IO_DESCRIPTOR_MODULES="custom_io_ok"):
            _register_custom_descriptors()
        self.assertIn("custom_test", IODescriptorBase._factory)

        with temp_env_var(FLOWPT_IO_DESCRIPTOR_MODULES="custom_io_bad"):
            with self.assertRaises(RegisterDescriptorError):
                _register_custom_descriptors()

    def test_custom_io_descriptor_paths_and_reload(self) -> None:
        """
        Tests that FLOWPT_IO_DESCRIPTOR_PATHS makes modules importable and that
        a module is executed again on every registration, as after a core swap.
        """
        from sgtk.descriptor.io_descriptor import _register_custom_descriptors
        from sgtk.descriptor.io_descriptor.base import IODescriptorBase

        module_dir = os.path.join(self.tank_temp, "custom_io_paths")
        os.makedirs(module_dir)
        with open(os.path.join(module_dir, "custom_io_counter.py"), "wt") as fh:
            fh.write(
                "import builtins\n"
                "builtins._custom_io_runs = getattr(builtins, '_custom_io_runs', 0) + 1\n"
                "def register_io_descriptors(base):\n"
                "    base.register_descriptor_factory('custom_counter', object)\n"
            )

        self.addCleanup(lambda: sys.path.remove(module_dir))
        self.addCleanup(IODescriptorBase._factory.pop, "custom_counter", None)
        self.addCleanup(sys.modules.pop, "custom_io_counter", None)
        self.addCleanup(lambda: delattr(builtins, "_custom_io_runs"))

        with temp_env_var(
            FLOWPT_IO_DESCRIPTOR_PATHS=module_dir,
            FLOWPT_IO_DESCRIPTOR_MODULES="custom_io_counter",
        ):
            _register_custom_descriptors()
            _register_custom_descriptors()

        self.assertIn("custom_counter", IODescriptorBase._factory)
        self.assertEqual(builtins._custom_io_runs, 2)

    def test_custom_io_descriptor_package_reload(self) -> None:
        """
        Tests that submodules and siblings of a custom package are re-executed
        too, so classes are not left bound to a previous core.
        """
        from sgtk.descriptor.io_descriptor import _register_custom_descriptors
        from sgtk.descriptor.io_descriptor.base import IODescriptorBase

        root = os.path.join(self.tank_temp, "custom_io_package")
        package_dir = os.path.join(root, "custom_io_pkg")
        os.makedirs(package_dir)
        with open(os.path.join(package_dir, "__init__.py"), "wt") as fh:
            fh.write(
                "from .implementation import Impl\n"
                "import custom_io_helper\n"
                "def register_io_descriptors(base):\n"
                "    base.register_descriptor_factory('custom_pkg', Impl)\n"
                "    base.register_descriptor_factory(\n"
                "        'custom_pkg_helper', custom_io_helper.Helper\n"
                "    )\n"
            )
        with open(os.path.join(package_dir, "implementation.py"), "wt") as fh:
            fh.write("class Impl:\n    pass\n")
        with open(os.path.join(root, "custom_io_helper.py"), "wt") as fh:
            fh.write("class Helper:\n    pass\n")

        self.addCleanup(lambda: sys.path.remove(root))
        self.addCleanup(IODescriptorBase._factory.pop, "custom_pkg", None)
        self.addCleanup(IODescriptorBase._factory.pop, "custom_pkg_helper", None)
        for name in (
            "custom_io_pkg",
            "custom_io_pkg.implementation",
            "custom_io_helper",
        ):
            self.addCleanup(sys.modules.pop, name, None)

        with temp_env_var(
            FLOWPT_IO_DESCRIPTOR_PATHS=root,
            FLOWPT_IO_DESCRIPTOR_MODULES="custom_io_pkg",
        ):
            _register_custom_descriptors()
            first = IODescriptorBase._factory["custom_pkg"]
            first_helper = IODescriptorBase._factory["custom_pkg_helper"]
            _register_custom_descriptors()

        # A submodule of the package and a sibling module from the configured path.
        self.assertIsNot(IODescriptorBase._factory["custom_pkg"], first)
        self.assertIsNot(IODescriptorBase._factory["custom_pkg_helper"], first_helper)
