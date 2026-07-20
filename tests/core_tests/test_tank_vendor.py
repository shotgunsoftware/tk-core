# Copyright (c) 2025 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import importlib
import os
import pathlib
import shutil
import sys
import tempfile
import unittest
from unittest import mock

from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import ShotgunTestBase

# Configuration: Add or remove packages here to test different third-party libraries
# Packages from pkgs.zip are always tested. Packages from requirements/any/
# are version-gated below.
PACKAGES_TO_TEST = [
    {
        "name": "yaml",
        "attributes": ["safe_load", "safe_dump"],  # Expected attributes
        "description": "YAML parser (ruamel.yaml)",
    },
    {
        "name": "shotgun_api3",
        "attributes": ["Shotgun", "__version__"],
        "description": "Shotgun API",
    },
    {
        "name": "packaging",
        "attributes": ["version", "__version__"],
        "description": "Package version handling",
    },
    {
        "name": "distro",
        "attributes": ["id", "name"],
        "description": "Linux distribution detection",
    },
]

# Flow Data SDK uses types.UnionType and typing.TypeAlias, both 3.10+ only.
# On 3.7/3.9 the shared loader will warn-and-continue; do not assert it here.
if sys.version_info >= (3, 10):
    PACKAGES_TO_TEST.append(
        {
            "name": "flow_data_sdk",
            "attributes": [
                "GQLClient",
                "WorkflowContext",
                "SDK_VERSION",
                "DEFAULT_ENDPOINT",
                "DEFAULT_AUTH_BASE_URL",
                "GQLAPIError",
            ],
            "description": "Autodesk Flow Data SDK (beta)",
        }
    )


class TestTankVendorImports(ShotgunTestBase):
    """Test importing third-party packages via tank_vendor namespace."""

    def test_direct_imports(self):
        """Test that all configured packages can be imported directly from tank_vendor."""
        for package_config in PACKAGES_TO_TEST:
            package_name = package_config["name"]
            expected_attrs = package_config["attributes"]

            with self.subTest(
                package=package_name, description=package_config["description"]
            ):
                # Import from tank_vendor namespace
                module = importlib.import_module(f"tank_vendor.{package_name}")

                # Verify module is not None
                self.assertIsNotNone(
                    module, f"Failed to import tank_vendor.{package_name}"
                )

                # Verify expected attributes exist
                for attr in expected_attrs:
                    self.assertTrue(
                        hasattr(module, attr),
                        f"tank_vendor.{package_name} missing attribute '{attr}'",
                    )

    def test_namespace_aliases(self):
        """Test that tank_vendor.* packages are aliased to direct imports."""
        for package_config in PACKAGES_TO_TEST:
            package_name = package_config["name"]

            with self.subTest(
                package=package_name, description=package_config["description"]
            ):
                # Import from both namespaces
                vendor_module = importlib.import_module(f"tank_vendor.{package_name}")
                direct_module = importlib.import_module(package_name)

                # Both imports should reference the same module object
                self.assertIs(
                    vendor_module,
                    direct_module,
                    f"tank_vendor.{package_name} is not aliased to {package_name}",
                )

    def test_submodule_import(self):
        """
        Test lazy import of submodules through tank_vendor namespace.

        This test verifies that the _TankVendorMetaFinder correctly handles
        nested/deep imports, not just top-level packages. For example:

        - Top-level: from tank_vendor import shotgun_api3  (handled by Step 2)
        - Nested: from tank_vendor.shotgun_api3.lib import httplib2  (handled by MetaFinder)

        The MetaFinder intercepts imports starting with "tank_vendor." and:
        1. Strips the "tank_vendor." prefix to get the real module name
        2. Imports the real module (e.g., "shotgun_api3.lib.httplib2")
        3. Creates an alias so both "shotgun_api3.lib.httplib2" and
           "tank_vendor.shotgun_api3.lib.httplib2" work

        This is called "lazy loading" because submodules aren't imported until
        they're actually needed, avoiding issues with incompatible code in
        packages that might not be used.
        """
        # Import a deeply nested submodule through tank_vendor namespace
        from tank_vendor.shotgun_api3.lib import httplib2

        # Should be importable and not None
        self.assertIsNotNone(httplib2)

        # Verify the module is actually usable (has expected functionality)
        self.assertTrue(hasattr(httplib2, "Http") or hasattr(httplib2, "__name__"))

    def test_sys_modules_registration(self):
        """Test that tank_vendor imports register in sys.modules correctly."""
        for package_config in PACKAGES_TO_TEST:
            package_name = package_config["name"]

            with self.subTest(
                package=package_name, description=package_config["description"]
            ):
                # Ensure module is imported
                importlib.import_module(f"tank_vendor.{package_name}")

                # Both names should exist in sys.modules
                self.assertIn(
                    package_name,
                    sys.modules,
                    f"{package_name} not found in sys.modules",
                )
                self.assertIn(
                    f"tank_vendor.{package_name}",
                    sys.modules,
                    f"tank_vendor.{package_name} not found in sys.modules",
                )

                # They should point to the same module
                self.assertIs(
                    sys.modules[package_name],
                    sys.modules[f"tank_vendor.{package_name}"],
                    f"sys.modules entries for {package_name} don't match",
                )

    def test_mock_patch_compatibility(self):
        """Test that mock.patch works with tank_vendor namespace."""
        # This is important for testing code that uses tank_vendor imports
        with mock.patch("tank_vendor.shotgun_api3.Shotgun") as mock_shotgun:
            from tank_vendor.shotgun_api3 import Shotgun

            # Should be the mocked class
            self.assertIs(Shotgun, mock_shotgun)


class TestTankVendorMetaFinder(ShotgunTestBase):
    """Test the _TankVendorMetaFinder import hook functionality."""

    def test_meta_finder_installed(self):
        """Test that the meta finder is installed in sys.meta_path."""
        import tank_vendor

        # Meta finder should be installed
        self.assertTrue(hasattr(sys, "_tank_vendor_meta_finder"))
        self.assertIn(sys._tank_vendor_meta_finder, sys.meta_path)

    def test_meta_finder_redirects_imports(self):
        """Test that the meta finder correctly redirects tank_vendor.* imports."""
        # Import a package through tank_vendor namespace
        # Import the same package directly
        from shotgun_api3 import Shotgun as DirectShotgun
        from tank_vendor.shotgun_api3 import Shotgun as VendorShotgun

        # They should be the exact same class
        self.assertIs(VendorShotgun, DirectShotgun)

    def test_meta_finder_handles_nonexistent_module(self):
        """Test that the meta finder handles nonexistent modules gracefully."""
        # Attempting to import a nonexistent module should raise ImportError
        with self.assertRaises(ImportError):
            from tank_vendor import nonexistent_module_xyz123  # noqa


class TestTankVendorPackageLoading(ShotgunTestBase):
    """Test package loading and validation from pkgs.zip."""

    def test_packages_available(self):
        """Test that all configured packages are available from tank_vendor."""
        for package_config in PACKAGES_TO_TEST:
            package_name = package_config["name"]

            with self.subTest(
                package=package_name, description=package_config["description"]
            ):
                # Should be able to import from tank_vendor
                module = importlib.import_module(f"tank_vendor.{package_name}")
                self.assertIsNotNone(
                    module, f"Failed to import tank_vendor.{package_name}"
                )

    def test_package_attributes_accessible(self):
        """Test that imported packages have their expected attributes accessible."""
        for package_config in PACKAGES_TO_TEST:
            package_name = package_config["name"]
            expected_attrs = package_config["attributes"]

            with self.subTest(
                package=package_name, description=package_config["description"]
            ):
                module = importlib.import_module(f"tank_vendor.{package_name}")

                # Verify all expected attributes are accessible
                for attr in expected_attrs:
                    self.assertTrue(
                        hasattr(module, attr),
                        f"tank_vendor.{package_name} missing expected attribute '{attr}'",
                    )


class TestShotgunAPI3CertPatch(ShotgunTestBase):
    """Test the shotgun_api3 certificate patching functionality."""

    def test_cert_patch_applied(self):
        """Test that certificate path patching is applied to shotgun_api3."""
        import shotgun_api3

        # The _get_certs_file method should exist
        self.assertTrue(hasattr(shotgun_api3.Shotgun, "_get_certs_file"))

        # Method should be callable
        self.assertTrue(callable(shotgun_api3.Shotgun._get_certs_file))

    def test_cert_file_returns_path(self):
        """Test that _get_certs_file returns a valid path."""
        import shotgun_api3

        # Call the method to get certificate path
        cert_path = shotgun_api3.Shotgun._get_certs_file()

        # Should return a string path
        self.assertIsInstance(cert_path, str)
        self.assertTrue(len(cert_path) > 0)


class TestShotgunAPI3CertPatchPrecedence(ShotgunTestBase):
    """
    Test SHOTGUN_API_CACERTS precedence in the shotgun_api3 certs patch (SG-44256).

    Prior to this fix, _patch_shotgun_api3_certs() unconditionally returned the
    Core-extracted cacert.pem whenever ca_certs wasn't explicitly passed, silently
    ignoring the documented SHOTGUN_API_CACERTS environment variable. When the
    extracted cert lives on a slow network share, this made every cold ShotGrid
    connection pay a large one-time filesystem cost that a local cert copy avoids.

    These tests call _patch_shotgun_api3_certs() directly against a throwaway
    fake "pkgs.zip" layout so they can control both the extracted cert file and
    the environment variable without depending on the real build-time layout.
    """

    def setUp(self):
        super().setUp()

        import shotgun_api3

        from tank_vendor import _patch_shotgun_api3_certs

        self._shotgun_api3 = shotgun_api3
        self._patch_shotgun_api3_certs = _patch_shotgun_api3_certs

        # Snapshot the raw descriptor currently installed (already patched
        # once at module import time) so we can restore it after each test.
        # Reading via __dict__ (not attribute access) preserves the
        # staticmethod wrapper itself, rather than the plain function it
        # unwraps to -- restoring the unwrapped function directly would
        # turn _get_certs_file into a bound instance method for every
        # Shotgun() call afterward, breaking unrelated tests with a
        # "takes 0 to 1 positional arguments but 2 were given" TypeError.
        self._original_get_certs_file = shotgun_api3.Shotgun.__dict__[
            "_get_certs_file"
        ]

        # Build a fake pkgs.zip layout with an extracted cert file beside it:
        #   <tmp_dir>/pkgs.zip
        #   <tmp_dir>/certs/shotgun_api3/lib/certifi/cacert.pem
        self._tmp_dir = tempfile.mkdtemp()
        cert_dir = (
            pathlib.Path(self._tmp_dir) / "certs" / "shotgun_api3" / "lib" / "certifi"
        )
        cert_dir.mkdir(parents=True)
        self._extracted_cert_file = cert_dir / "cacert.pem"
        self._extracted_cert_file.write_text("fake extracted core cert")
        self._fake_zip_path = pathlib.Path(self._tmp_dir) / "pkgs.zip"

        self._env_patcher = mock.patch.dict(os.environ, {}, clear=False)
        self._env_patcher.start()
        os.environ.pop("SHOTGUN_API_CACERTS", None)

    def tearDown(self):
        self._env_patcher.stop()
        self._shotgun_api3.Shotgun._get_certs_file = self._original_get_certs_file
        shutil.rmtree(self._tmp_dir, ignore_errors=True)
        super().tearDown()

    def test_environment_override_takes_precedence_over_extracted_cert(self):
        """SHOTGUN_API_CACERTS should win over the Core-extracted cert."""
        local_cert = os.path.join(self._tmp_dir, "local-cacert.pem")
        os.environ["SHOTGUN_API_CACERTS"] = local_cert

        self._patch_shotgun_api3_certs(self._fake_zip_path)

        self.assertEqual(
            self._shotgun_api3.Shotgun._get_certs_file(),
            local_cert,
        )

    def test_falls_back_to_extracted_cert_when_env_var_unset(self):
        """With no override set, behavior is unchanged: use the extracted cert."""
        self.assertNotIn("SHOTGUN_API_CACERTS", os.environ)

        self._patch_shotgun_api3_certs(self._fake_zip_path)

        self.assertEqual(
            self._shotgun_api3.Shotgun._get_certs_file(),
            str(self._extracted_cert_file),
        )

    def test_falls_back_to_extracted_cert_when_env_var_empty(self):
        """An empty SHOTGUN_API_CACERTS is treated the same as unset."""
        os.environ["SHOTGUN_API_CACERTS"] = ""

        self._patch_shotgun_api3_certs(self._fake_zip_path)

        self.assertEqual(
            self._shotgun_api3.Shotgun._get_certs_file(),
            str(self._extracted_cert_file),
        )

    def test_explicit_ca_certs_argument_still_takes_top_precedence(self):
        """An explicit ca_certs argument outranks both the env var and the extracted cert."""
        os.environ["SHOTGUN_API_CACERTS"] = os.path.join(
            self._tmp_dir, "local-cacert.pem"
        )

        self._patch_shotgun_api3_certs(self._fake_zip_path)

        explicit_cert = "/some/explicit/cert.pem"
        self.assertEqual(
            self._shotgun_api3.Shotgun._get_certs_file(explicit_cert),
            explicit_cert,
        )


@unittest.skipIf(
    sys.version_info < (3, 10),
    "Flow Data SDK requires Python 3.10+ (uses types.UnionType / typing.TypeAlias)",
)
class TestFlowDataSDK(ShotgunTestBase):
    """Test the Flow Data SDK loaded from requirements/any/."""

    def test_submodule_import(self):
        """Lazy meta-finder resolves nested imports inside the shared zip."""
        from tank_vendor.flow_data_sdk.base import client
        from tank_vendor.flow_data_sdk.base.exceptions import GQLAPIError

        self.assertTrue(hasattr(client, "BaseGQLClient"))
        self.assertIsNotNone(GQLAPIError)

    def test_sdk_version_resolved_from_dist_info(self):
        """
        Canary: SDK_VERSION must NOT fall back to 'local_dev'.

        flow_data_sdk/base/_version.py resolves SDK_VERSION via
        importlib.metadata, which only succeeds when the SDK's .dist-info
        directory was preserved in the shared zip. If this fails, the shared
        zip in requirements/any/ is missing its .dist-info.
        """
        from tank_vendor import flow_data_sdk

        self.assertNotEqual(
            flow_data_sdk.SDK_VERSION,
            "local_dev",
            "SDK_VERSION fell back to 'local_dev' — the shared zip is "
            "missing .dist-info.",
        )
        self.assertRegex(
            flow_data_sdk.SDK_VERSION,
            r"^\d+\.\d+",
            "SDK_VERSION is not a PEP 440 version",
        )

    def test_dist_info_via_importlib_metadata(self):
        """importlib.metadata sees the same version as the SDK reports."""
        from importlib.metadata import version

        from tank_vendor import flow_data_sdk

        self.assertEqual(version("flow-data-sdk"), flow_data_sdk.SDK_VERSION)


if __name__ == "__main__":
    unittest.main()
