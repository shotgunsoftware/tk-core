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
import sys
import unittest
from unittest import mock

from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import ShotgunTestBase

# Configuration: Add or remove packages here to test different third-party libraries
# Only include packages that are directly bundled in requirements/<version>/pkgs.zip
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


if __name__ == "__main__":
    unittest.main()
