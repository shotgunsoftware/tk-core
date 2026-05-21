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
from unittest.mock import patch

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


class TestSwapCoreVersionMismatch(ShotgunTestBase):
    """Tests that swap_core emits a version-mismatch diagnostic on import failure.

    These tests do not perform a real core swap. Instead they patch the internal
    helpers and inject a meta-path blocker so that the post-swap ``import tank``
    statement always raises ImportError, letting us assert the diagnostic path in
    isolation.
    """

    # ------------------------------------------------------------------
    # A meta-path finder that unconditionally raises ImportError for
    # 'tank'.  Inserting this at the front of sys.meta_path simulates a
    # broken target core without touching the filesystem.
    # ------------------------------------------------------------------
    class _TankImportBlocker:
        def find_spec(self, fullname, path, target=None):
            if fullname == "tank":
                raise ImportError("Simulated broken target core (test blocker)")
            return None

    def setUp(self):
        super().setUp()

        # Build a minimal fake target core layout:
        #
        #   <tmp_root>/
        #     install/
        #       core/
        #         info.yml   <- declares version v0.22.4
        #         python/    <- empty; no real tank modules
        self._target_root = tempfile.mkdtemp(prefix="tk_swap_mismatch_test_")
        core_dir = os.path.join(self._target_root, "install", "core")
        os.makedirs(core_dir)
        with open(os.path.join(core_dir, "info.yml"), "w") as fh:
            fh.write('version: "v0.22.4"\n')
        self._target_python = os.path.join(core_dir, "python")
        os.makedirs(self._target_python)

        # Snapshot sys.meta_path and the tank-related sys.modules entries so
        # tearDown can restore them regardless of what the test does.
        self._original_meta_path = sys.meta_path[:]
        self._stashed_tank_modules = {
            k: v
            for k, v in sys.modules.items()
            if k in ("tank", "sgtk", "tank_vendor")
            or k.startswith(("tank.", "sgtk.", "tank_vendor."))
        }

    def tearDown(self):
        sys.meta_path[:] = self._original_meta_path
        sys.modules.update(self._stashed_tank_modules)
        shutil.rmtree(self._target_root, ignore_errors=True)
        super().tearDown()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_fake_swap_core(self, handler):
        """Return a drop-in for ``_swap_core`` that simulates the two side effects
        that matter for these tests:

        1. Redirects the handler's ``_core_path`` to the new (empty) target.
        2. Clears all tank-namespaced modules from ``sys.modules`` so that
           the subsequent ``import tank`` actually goes through the import
           machinery (and hits our blocker).
        3. Inserts the blocker at the front of ``sys.meta_path``.
        """

        def _fake(core_path):
            handler._core_path = core_path
            for key in list(sys.modules):
                if key in ("tank", "sgtk", "tank_vendor") or key.startswith(
                    ("tank.", "sgtk.", "tank_vendor.")
                ):
                    del sys.modules[key]
            sys.meta_path.insert(0, TestSwapCoreVersionMismatch._TankImportBlocker())

        return _fake

    def _run_swap(self, handler_version, target_version_on_disk=None):
        """Run ``CoreImportHandler.swap_core`` with controlled versions.

        :param handler_version: The version reported by
            ``get_currently_running_api_version`` (the active/site core).
        :param target_version_on_disk: If given, overwrite the ``info.yml`` in
            the fake target root so ``get_core_api_version`` returns this value.
        :returns: The mock logger captured during the call.
        :raises ImportError: The patched import always raises; the caller
            decides whether to catch it.
        """
        if target_version_on_disk is not None:
            info_path = os.path.join(self._target_root, "install", "core", "info.yml")
            with open(info_path, "w") as fh:
                fh.write('version: "%s"\n' % target_version_on_disk)

        handler = CoreImportHandler(self._target_python)

        with patch(
            "tank.pipelineconfig_utils.get_currently_running_api_version",
            return_value=handler_version,
        ), patch.object(
            CoreImportHandler, "_initialize", return_value=handler
        ), patch.object(
            handler,
            "_swap_core",
            side_effect=self._make_fake_swap_core(handler),
        ), patch(
            "tank.bootstrap.import_handler.log"
        ) as mock_log, patch(
            # swap_core calls LogManager().uninitialize_base_file_handler() on
            # the process-wide singleton before the swap, and relies on the
            # post-swap `import tank` to re-initialize it.  Because our test
            # intentionally makes that import fail, the handler is never
            # restored, which leaks state into subsequent test classes.  Mock
            # the local import so the singleton is never touched.
            "tank.log.LogManager"
        ):
            with self.assertRaises(ImportError):
                CoreImportHandler.swap_core(self._target_python)
            return mock_log

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_mismatch_message_logged_when_target_is_older(self):
        """log.exception is called with version details when target < running core.

        Scenario: Desktop ships v0.23.8 (handler_version) but the project config
        still pins v0.22.4 (target_version). The post-swap ``import tank`` fails
        and the diagnostic must surface both version numbers and a link to the
        release notes.
        """
        mock_log = self._run_swap(handler_version="v0.23.8")

        logged = " ".join(str(c) for c in mock_log.exception.call_args_list)
        self.assertTrue(
            mock_log.exception.called,
            "Expected log.exception to be called for a version-mismatch but it "
            "was not. All log calls: %s" % mock_log.mock_calls,
        )
        self.assertIn(
            "v0.22.4",
            logged,
            "Target version v0.22.4 should appear in the mismatch message.",
        )
        self.assertIn(
            "v0.23.8",
            logged,
            "Running version v0.23.8 should appear in the mismatch message.",
        )
        self.assertIn(
            "tk-core/releases",
            logged,
            "Release notes URL should appear in the mismatch message.",
        )

    def test_no_mismatch_message_when_target_is_not_older(self):
        """log.exception is NOT called when the target core is the same version or newer.

        Scenario: The project config has already been updated to v0.23.8 while the
        running core is v0.22.4. Even though the import still fails (the fake
        blocker is always active), the version-mismatch branch must NOT fire
        because the target is not older than the handler.
        """
        mock_log = self._run_swap(
            handler_version="v0.22.4",
            target_version_on_disk="v0.23.8",
        )

        mismatch_calls = [
            c for c in mock_log.exception.call_args_list if "mismatch" in str(c).lower()
        ]
        self.assertFalse(
            mismatch_calls,
            "log.exception should NOT be called with a mismatch message when "
            "the target core is not older. Unexpected calls: %s" % mismatch_calls,
        )
