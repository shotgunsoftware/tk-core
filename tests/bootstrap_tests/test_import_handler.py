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
        pass
    def tearDown(self):
        pass
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
        pass
    def test_find_spec_returns_spec_for_existing_package(self):
        pass
    def test_find_spec_returns_spec_for_existing_module(self):
        pass
    def test_find_spec_returns_none_for_nonexistent_module(self):
        pass
    def test_find_spec_returns_none_for_nonexistent_subpackage(self):
        pass
    def test_find_spec_returns_none_for_nonexistent_top_level_module(self):
        pass
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
        pass
    def tearDown(self):
        pass
    def test_load_module_converts_file_not_found_to_import_error(self):
        pass
class TestImportErrorNotFileNotFoundError(ShotgunTestBase):
    """Integration-style test verifying the full import path raises ImportError.

    Simulates the real scenario: importing a non-existent submodule from a
    tracked namespace package should raise ImportError, not FileNotFoundError.
    """

    def setUp(self):
        pass
    def tearDown(self):
        pass
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
        pass
