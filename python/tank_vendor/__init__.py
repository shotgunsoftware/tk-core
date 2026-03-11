# Copyright (c) 2025 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
tank_vendor module - Third-party dependency management for Shotgun Toolkit.

This module handles loading and importing third-party Python packages from
version-specific ZIP archives (pkgs.zip). It provides:

1. Auto-discovery of packages in pkgs.zip
2. Lazy import hook for transparent tank_vendor.* namespace aliasing
3. Package-specific patches (e.g., SSL certificate handling for shotgun_api3)

Usage:
    # Direct imports work automatically:
    from tank_vendor import yaml
    from tank_vendor.shotgun_api3 import Shotgun

    # Submodule imports work via lazy loading:
    from tank_vendor.shotgun_api3.lib import httplib2

    # Mock.patch works seamlessly:
    mock.patch("tank_vendor.shotgun_api3.Shotgun.find")

Supported Python versions: 3.7+
"""

import pathlib
import sys
import warnings
import zipfile


class _TankVendorMetaFinder:
    """
    Meta path finder that redirects tank_vendor.* imports to real packages.

    Implements the modern importlib.abc.MetaPathFinder protocol (PEP 451)
    using find_spec, create_module, and exec_module methods for Python 3.4+.

    This finder is installed at the beginning of sys.meta_path, so it's
    consulted before Python's default import mechanisms.
    """

    def find_spec(self, fullname, path, target=None):
        """
        Locate a module spec for tank_vendor.* imports.

        Called by Python's import system to determine if this finder can
        handle the requested module import.

        Args:
            fullname: Full module name (e.g., "tank_vendor.shotgun_api3.lib")
            path: Parent package's __path__ attribute (or None for top-level)
            target: Module object being reloaded (optional, rarely used)

        Returns:
            ModuleSpec: If we can handle this import (starts with "tank_vendor.")
            None: If this import should be handled by another finder
        """
        # Only handle tank_vendor.* imports
        if fullname.startswith("tank_vendor."):
            # Extract the real module name
            real_name = fullname[len("tank_vendor.") :]

            # Check if the real module exists or can be imported
            if real_name in sys.modules:
                # Create a spec that redirects to the existing module
                real_module = sys.modules[real_name]
                is_package = hasattr(real_module, "__path__")
                from importlib.machinery import ModuleSpec

                spec = ModuleSpec(
                    fullname,
                    self,
                    is_package=is_package,
                )
                # For packages, copy the __path__ so Python knows where to find submodules
                if is_package:
                    spec.submodule_search_locations = list(real_module.__path__)
                return spec

            # Try to import the real module to see if it exists
            try:
                __import__(real_name)
                # Success - create spec for this module
                real_module = sys.modules[real_name]
                is_package = hasattr(real_module, "__path__")
                from importlib.machinery import ModuleSpec

                spec = ModuleSpec(
                    fullname,
                    self,
                    is_package=is_package,
                )
                # For packages, copy the __path__ so Python knows where to find submodules
                if is_package:
                    spec.submodule_search_locations = list(real_module.__path__)
                return spec
            except ImportError:
                # Module doesn't exist, let normal import handle it
                return None

        return None

    def exec_module(self, module):
        """
        Execute module initialization code.

        Called after create_module to run the module's code. In our case,
        the module is already fully initialized (it's an alias), so we
        don't need to do anything here.

        Args:
            module: The module object returned by create_module
        """
        # Module is already aliased and initialized in create_module
        pass

    def create_module(self, spec):
        """
        Create and return the module object for the given spec.

        Instead of creating a new module, we return the existing real module
        and register it under both names (real and tank_vendor alias) in
        sys.modules. This ensures both import paths work identically.

        Args:
            spec: ModuleSpec from find_spec containing module metadata

        Returns:
            module: The real module object (aliased)
            None: To use Python's default module creation (shouldn't happen)
        """
        # Extract real module name from the spec name
        fullname = spec.name
        if fullname.startswith("tank_vendor."):
            real_name = fullname[len("tank_vendor.") :]

            # Import the real module if not already imported
            if real_name not in sys.modules:
                __import__(real_name)

            # Return the real module (alias it)
            # sys.modules will be updated by the import machinery
            sys.modules[fullname] = sys.modules[real_name]
            return sys.modules[real_name]

        # Shouldn't get here, but return None to use default creation
        return None


def _patch_shotgun_api3_certs(zip_path):
    """
    Patch shotgun_api3 to use extracted SSL certificates instead of ZIP-embedded ones.

    When shotgun_api3 is loaded from pkgs.zip, its certificate file is also inside
    the ZIP. Since SSL cannot read from ZIP files, we extract the certificate during
    build to requirements/<version>/certs/ and patch the method to return that path.

    Args:
        zip_path: Path to the pkgs.zip file (used to locate extracted certs directory)
    """
    # Only patch if shotgun_api3 was successfully imported
    if "shotgun_api3" not in sys.modules:
        return

    shotgun_api3 = sys.modules["shotgun_api3"]

    # Path to extracted certificates directory
    certs_dir = zip_path.parent / "certs"
    cert_file = certs_dir / "shotgun_api3" / "lib" / "certifi" / "cacert.pem"

    if cert_file.exists():
        # Save original method
        _original_get_certs_file = shotgun_api3.Shotgun._get_certs_file

        # Create patched version - static method, only receives ca_certs parameter
        def _patched_get_certs_file(ca_certs=None):
            # If ca_certs explicitly provided, use original behavior
            if ca_certs is not None:
                return _original_get_certs_file(ca_certs)
            # Otherwise return extracted certificate path instead of ZIP path
            return str(cert_file)

        # Apply patch
        shotgun_api3.Shotgun._get_certs_file = staticmethod(_patched_get_certs_file)


def _install_import_hook():
    """
    Install a lazy import hook that redirects tank_vendor.* imports to real packages.

    This enables transparent namespace aliasing, allowing code to use tank_vendor.package
    while the actual package is loaded from pkgs.zip without the tank_vendor prefix.

    Examples:
        from tank_vendor.shotgun_api3.lib import httplib2
        mock.patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.upload")

    How it works:
        1. Intercepts imports starting with "tank_vendor."
        2. Strips the "tank_vendor." prefix to get the real module name
        3. Imports the real module (e.g., "shotgun_api3" → tank_vendor.shotgun_api3)
        4. Creates an alias in sys.modules so both names refer to the same module

    Why lazy loading:
        Avoids eagerly importing all submodules, which can fail with version-incompatible
        code (e.g., Python 3.7 can't parse newer typing syntax in some packages).
        Only imports what's actually needed, when it's needed.

    Implementation:
        Uses Python's importlib meta path finder API (PEP 302/451) with find_spec,
        create_module, and exec_module methods for Python 3.4+ compatibility.
    """
    # Only install once
    if not hasattr(sys, "_tank_vendor_meta_finder"):
        # Install the meta finder
        sys._tank_vendor_meta_finder = _TankVendorMetaFinder()
        sys.meta_path.insert(0, sys._tank_vendor_meta_finder)


# ============================================================================
# MAIN INITIALIZATION: Load third-party packages from pkgs.zip
# ============================================================================

# Construct path to Python version-specific pkgs.zip containing third-party dependencies.
# Path structure: <tk-core>/requirements/<major>.<minor>/pkgs.zip
# Example: requirements/3.11/pkgs.zip for Python 3.11
pkgs_zip_path = (
    pathlib.Path(__file__).resolve().parent.parent.parent
    / "requirements"
    / f"{sys.version_info.major}.{sys.version_info.minor}"
    / "pkgs.zip"
)

# Validate pkgs.zip before attempting to load from it.
# This provides backward compatibility for:
# - Installations using old vendored copies
# - Temporary locations without the requirements directory
# - CI/CD environments where pkgs.zip might be extracted to a directory
_pkgs_zip_valid = False
if pkgs_zip_path.exists():
    # Check if it's a file (not a directory) - in some CI environments,
    # pkgs.zip might be extracted to a directory instead of kept as a ZIP.
    if pkgs_zip_path.is_file():
        # Validate that it's actually a valid ZIP file before adding to sys.path
        try:
            with zipfile.ZipFile(pkgs_zip_path, "r") as zf:
                # Quick validation - just check that we can read the ZIP directory
                zf.namelist()
                _pkgs_zip_valid = True
        except (zipfile.BadZipFile, OSError, IOError) as e:
            # Not a valid ZIP file or can't be read - skip loading from pkgs.zip
            warnings.warn(
                f"Failed to load packages from {pkgs_zip_path}: {e}. "
                "Third-party dependencies will be loaded from the Python environment instead.",
                RuntimeWarning,
                stacklevel=2,
            )

# If pkgs.zip is not found, assume pip-style installation where dependencies
# are installed directly in the Python environment. In this case, we still
# install the import hook to enable tank_vendor.* aliasing for compatibility.
if not _pkgs_zip_valid:
    # Install import hook even without pkgs.zip for pip installations
    _install_import_hook()
else:
    # Add pkgs.zip to sys.path so Python can import packages directly from the ZIP.
    # Insert at position 0 to prioritize over other installed packages.
    sys.path.insert(0, str(pkgs_zip_path))
    try:
        # Step 1: Auto-discover all top-level packages in pkgs.zip
        import importlib

        with zipfile.ZipFile(pkgs_zip_path, "r") as zf:
            # Get all top-level package names from the ZIP
            top_level_packages = set()
            for name in zf.namelist():
                # Extract first component of path (top-level package/module)
                parts = name.split("/")
                if parts[0] and not parts[0].endswith(".py"):
                    # It's a package directory
                    top_level_packages.add(parts[0])
                elif parts[0].endswith(".py") and parts[0] != "__pycache__":
                    # It's a top-level module file
                    top_level_packages.add(parts[0][:-3])  # Remove .py

            # Filter out non-importable items:
            # - .dist-info: Package metadata directories
            # - __pycache__: Python bytecode cache
            # - .py: Single file modules (already captured as packages)
            # - .pyd/.so/.dylib: Platform-specific binary extensions
            # - _*: Private/internal modules (e.g., _ruamel_yaml.cp311-win_amd64.pyd)
            top_level_packages = {
                pkg
                for pkg in top_level_packages
                if not pkg.endswith(".dist-info")
                and pkg != "__pycache__"
                and not pkg.endswith(".py")
                and not pkg.endswith(".pyd")  # Windows binary modules
                and not pkg.endswith(".so")  # Unix/Linux binary modules
                and not pkg.endswith(".dylib")  # macOS binary modules
                and not pkg.startswith("_")  # Private/internal modules
            }

        # Step 2: Import and register each top-level package under tank_vendor namespace
        for package_name in sorted(top_level_packages):
            try:
                # Import the package
                mod = importlib.import_module(package_name)

                # Register in sys.modules under tank_vendor namespace
                sys.modules[f"tank_vendor.{package_name}"] = mod

                # Also set as attribute on tank_vendor module for direct access
                globals()[package_name] = mod

            except ImportError as e:
                # Some packages might not import cleanly on all platforms
                # Log but don't fail - they might not be needed
                warnings.warn(f"Could not import {package_name} from pkgs.zip: {e}")

        # Step 3: Install import hook for lazy submodule loading
        # This enables imports like: from tank_vendor.shotgun_api3.lib import httplib2
        # without pre-importing all submodules (which can fail on version incompatibilities)
        _install_import_hook()

        # Step 4: Apply package-specific patches
        # These patches work around limitations or fix issues with specific packages
        if "shotgun_api3" in sys.modules:
            _patch_shotgun_api3_certs(pkgs_zip_path)

    except Exception as e:
        # Clean up sys.path on failure to avoid leaving it in an inconsistent state
        # with a non-functional ZIP path that could interfere with subsequent imports
        sys.path.remove(str(pkgs_zip_path))
        raise RuntimeError(
            f"Failed to import required modules from {pkgs_zip_path}: {e}"
        ) from e
