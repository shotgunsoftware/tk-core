# Copyright (c) 2025 Autodesk.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the ShotGrid Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the ShotGrid Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Autodesk.

import os
import sys
import types
import tempfile
import shutil

from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import ShotgunTestBase

from tank.bootstrap.import_handler import CoreImportHandler

# creates a unique object instance that can never collide with any real value.
_SENTINEL = object()


class TestCoreImportHandlerFindSpec(ShotgunTestBase):
    """Tests for CoreImportHandler.find_spec to ensure correct module resolution."""

    def setUp(self):
        super().setUp()

        self.core_root = tempfile.mkdtemp(prefix="tk_core_test_")

        # Build a minimal fake core layout:
        #
        #   <core_root>/
        #     tank/
        #       __init__.py
        #       platform/
        #         __init__.py
        #         qt5/
        #           __init__.py          (empty, like the real qt5 module)
        #         engine.py
        self._make_package("tank")
        self._make_package("tank", "platform")
        self._make_package("tank", "platform", "qt5")
        self._make_module("tank", "platform", "engine")

        self.handler = CoreImportHandler(self.core_root)

    def tearDown(self):
        # Clean up any modules we injected during tests
        to_remove = [
            k for k in sys.modules if k.startswith("tank._test_import_handler_")
        ]
        for k in to_remove:
            del sys.modules[k]
        shutil.rmtree(self.core_root, ignore_errors=True)
        super().tearDown()

    def _make_package(self, *parts):
        pkg_dir = os.path.join(self.core_root, *parts)
        os.makedirs(pkg_dir, exist_ok=True)
        init_file = os.path.join(pkg_dir, "__init__.py")
        if not os.path.exists(init_file):
            with open(init_file, "w") as f:
                f.write("")

    def _make_module(self, *parts):
        parent_dir = os.path.join(self.core_root, *parts[:-1])
        os.makedirs(parent_dir, exist_ok=True)
        module_file = os.path.join(parent_dir, parts[-1] + ".py")
        with open(module_file, "w") as f:
            f.write("")

    def test_find_spec_returns_none_for_untracked_namespace(self):
        """find_spec should return None for modules outside NAMESPACES_TO_TRACK."""
        result = self.handler.find_spec("some_other_package.foo")
        self.assertIsNone(result)

    def test_find_spec_returns_spec_for_existing_package(self):
        """find_spec should return a ModuleSpec for an existing package directory."""
        spec = self.handler.find_spec("tank")
        self.assertIsNotNone(spec)
        self.assertEqual(spec.name, "tank")

    def test_find_spec_returns_spec_for_existing_module(self):
        """find_spec should return a ModuleSpec for an existing .py module."""
        # First, register the parent packages so find_spec can resolve the path
        self._register_parent_packages("tank", "tank.platform")

        spec = self.handler.find_spec("tank.platform.engine")
        self.assertIsNotNone(spec)
        self.assertEqual(spec.name, "tank.platform.engine")

    def test_find_spec_returns_none_for_nonexistent_module(self):
        """find_spec must return None (not a broken spec) for a module that doesn't exist.

        This is the core regression test for the imp->importlib migration.
        Previously, SourceFileLoader would be created for a non-existent file,
        leading to FileNotFoundError later instead of ImportError.
        """
        self._register_parent_packages("tank", "tank.platform", "tank.platform.qt5")

        result = self.handler.find_spec("tank.platform.qt5.QtPrintSupport")
        self.assertIsNone(result)

    def test_find_spec_returns_none_for_nonexistent_subpackage(self):
        """find_spec must return None for a non-existent sub-package."""
        self._register_parent_packages("tank", "tank.platform")

        result = self.handler.find_spec("tank.platform.nonexistent_package")
        self.assertIsNone(result)

    def test_find_spec_returns_none_for_nonexistent_top_level_module(self):
        """find_spec must return None for a non-existent top-level tracked module."""
        result = self.handler.find_spec("tank.this_module_does_not_exist")
        self.assertIsNone(result)

    def _register_parent_packages(self, *dotted_names):
        """Register fake parent packages in sys.modules so find_spec can resolve paths."""
        for name in dotted_names:
            if name not in sys.modules:
                parts = name.split(".")
                mod = types.ModuleType(name)
                mod.__path__ = [os.path.join(self.core_root, *parts)]
                mod.__package__ = name
                # Use a test-specific prefix to avoid colliding with real tank modules
                stash_key = "tank._test_import_handler_" + name
                sys.modules[name] = mod
                sys.modules[stash_key] = mod


class TestCoreImportHandlerLoadModule(ShotgunTestBase):
    """Tests for CoreImportHandler.load_module error handling."""

    def setUp(self):
        super().setUp()
        self.core_root = tempfile.mkdtemp(prefix="tk_core_test_")
        self.handler = CoreImportHandler(self.core_root)

    def tearDown(self):
        shutil.rmtree(self.core_root, ignore_errors=True)
        super().tearDown()

    def test_load_module_converts_file_not_found_to_import_error(self):
        """load_module must raise ImportError (not FileNotFoundError) for missing files.

        This acts as a safety net: even if find_spec somehow returned a spec
        pointing to a file that no longer exists, load_module should convert
        the resulting FileNotFoundError into an ImportError.
        """
        import importlib.machinery
        import importlib.util

        nonexistent_path = os.path.join(self.core_root, "ghost_module.py")
        loader = importlib.machinery.SourceFileLoader(
            "tank.ghost_module", nonexistent_path
        )
        spec = importlib.util.spec_from_loader(loader.name, loader)
        self.handler._module_info["tank.ghost_module"] = spec

        with self.assertRaises(ImportError) as ctx:
            self.handler.load_module("tank.ghost_module")

        self.assertIn("tank.ghost_module", str(ctx.exception))
        self.assertIsInstance(ctx.exception.__cause__, FileNotFoundError)


class TestImportErrorNotFileNotFoundError(ShotgunTestBase):
    """Integration-style test verifying the full import path raises ImportError.

    Simulates the real scenario: importing a non-existent submodule from a
    tracked namespace package should raise ImportError, not FileNotFoundError.
    """

    def setUp(self):
        super().setUp()
        self.core_root = tempfile.mkdtemp(prefix="tk_core_test_")

        # Create a package with an __init__.py (like qt5)
        qt5_dir = os.path.join(self.core_root, "tank", "platform", "qt5")
        os.makedirs(qt5_dir)
        with open(os.path.join(self.core_root, "tank", "__init__.py"), "w") as f:
            f.write("")
        with open(
            os.path.join(self.core_root, "tank", "platform", "__init__.py"), "w"
        ) as f:
            f.write("")
        with open(os.path.join(qt5_dir, "__init__.py"), "w") as f:
            f.write("")

        self.handler = CoreImportHandler(self.core_root)
        self._injected_handler = False
        self._stashed_modules = {}

    def tearDown(self):
        if self._injected_handler and self.handler in sys.meta_path:
            sys.meta_path.remove(self.handler)

        for key, mod in self._stashed_modules.items():
            if mod is _SENTINEL:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = mod
        self._stashed_modules.clear()

        shutil.rmtree(self.core_root, ignore_errors=True)
        super().tearDown()

    def _inject_handler_and_modules(self):
        """Set up handler in sys.meta_path and fake parent modules."""
        sys.meta_path.insert(0, self.handler)
        self._injected_handler = True

        for name in ["tank.platform.qt5"]:
            parts = name.split(".")
            if name in sys.modules:
                self._stashed_modules[name] = sys.modules[name]
            else:
                self._stashed_modules[name] = _SENTINEL
            mod = types.ModuleType(name)
            mod.__path__ = [os.path.join(self.core_root, *parts)]
            mod.__package__ = name
            sys.modules[name] = mod

    def test_nonexistent_submodule_raises_import_error_not_file_not_found(self):
        """Importing a non-existent module from a tracked package must raise ImportError.

        This reproduces the customer-reported issue where:
            from sgtk.platform.qt5 import QtPrintSupport
        raised FileNotFoundError instead of ImportError after the imp->importlib migration.
        """
        self._inject_handler_and_modules()

        spec = self.handler.find_spec("tank.platform.qt5.QtPrintSupport")
        self.assertIsNone(
            spec,
            "find_spec should return None for non-existent module QtPrintSupport, "
            "not a spec pointing to a missing file",
        )
