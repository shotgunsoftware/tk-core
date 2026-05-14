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
ZIP archives. It provides:

1. Auto-discovery of packages in two locations:
   - requirements/<major>.<minor>/pkgs.zip   (per-Python-version, mandatory)
   - requirements/any/*.zip                  (Python-version-independent, optional)
2. Lazy import hook for transparent tank_vendor.* namespace aliasing
3. Package-specific patches (e.g., SSL certificate handling for shotgun_api3)

Usage:
    # Direct imports work automatically:
    from tank_vendor import yaml
    from tank_vendor.shotgun_api3 import Shotgun
    from tank_vendor import flow_data_sdk

    # Submodule imports work via lazy loading:
    from tank_vendor.shotgun_api3.lib import httplib2
    from tank_vendor.flow_data_sdk.base import client

    # Mock.patch works seamlessly:
    mock.patch("tank_vendor.shotgun_api3.Shotgun.find")

Shared zips in requirements/any/ are loaded after pkgs.zip, so per-version
pinned packages take precedence over anything in the shared directory.
Packages whose top-level name is already registered are skipped with a
warning.

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
    while the actual package is loaded from a ZIP without the tank_vendor prefix.

    Examples:
        from tank_vendor.shotgun_api3.lib import httplib2
        mock.patch("tank_vendor.shotgun_api3.lib.mockgun.Shotgun.upload")

    How it works:
        1. Intercepts imports starting with "tank_vendor."
        2. Strips the "tank_vendor." prefix to get the real module name
        3. Imports the real module (e.g., "shotgun_api3" -> tank_vendor.shotgun_api3)
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


def _discover_top_level_packages(zip_path):
    """
    Return the set of top-level importable package names inside a zip.

    Filters out:
        - .dist-info: Package metadata directories (still in zip for importlib.metadata,
          but not importable as packages)
        - __pycache__: Python bytecode cache
        - .pyd/.so/.dylib: Platform-specific binary extensions
        - _*: Private/internal modules (e.g., _ruamel_yaml.cp311-win_amd64.pyd)
    """
    with zipfile.ZipFile(zip_path, "r") as zf:
        top_level = set()
        for name in zf.namelist():
            parts = name.split("/")
            if parts[0] and not parts[0].endswith(".py"):
                top_level.add(parts[0])
            elif parts[0].endswith(".py") and parts[0] != "__pycache__":
                top_level.add(parts[0][:-3])

    return {
        pkg
        for pkg in top_level
        if not pkg.endswith(".dist-info")
        and pkg != "__pycache__"
        and not pkg.endswith(".py")
        and not pkg.endswith(".pyd")
        and not pkg.endswith(".so")
        and not pkg.endswith(".dylib")
        and not pkg.startswith("_")
    }


def _load_packages_from_zip(zip_path, *, required, path_position):
    """
    Validate a vendor zip, insert it on sys.path, and register its top-level
    packages under the tank_vendor namespace.

    Args:
        zip_path: pathlib.Path to the zip file.
        required: If True, failure to validate or import raises RuntimeError.
            If False, failures emit warnings and the loader continues.
        path_position: Index passed to sys.path.insert. Use 0 for the primary
            zip (pkgs.zip) so it wins over system installs; higher indices for
            additional zips so the primary still takes precedence.

    Returns:
        True if the zip was successfully loaded, False otherwise.
    """
    # Validate zip before attempting to load from it.
    if not zip_path.exists() or not zip_path.is_file():
        if required:
            return False
        # Optional zip simply absent: nothing to do, no warning.
        return False

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.namelist()
    except (zipfile.BadZipFile, OSError, IOError) as e:
        msg = (
            f"Failed to load packages from {zip_path}: {e}. "
            "Third-party dependencies from this zip will not be available."
        )
        if required:
            warnings.warn(msg, RuntimeWarning, stacklevel=2)
            return False
        warnings.warn(msg, RuntimeWarning, stacklevel=2)
        return False

    # Insertion ordering is load-bearing: importlib.metadata.version() resolves
    # dist-info inside a zip only after the zip is on sys.path.
    sys.path.insert(path_position, str(zip_path))

    try:
        import importlib

        top_level_packages = _discover_top_level_packages(zip_path)

        for package_name in sorted(top_level_packages):
            # Collision check: an earlier zip already claimed this name.
            # Earlier zips win (pkgs.zip is loaded before requirements/any/).
            if f"tank_vendor.{package_name}" in sys.modules:
                warnings.warn(
                    f"Skipping {package_name} from {zip_path}: "
                    f"already registered under tank_vendor.{package_name} "
                    f"from an earlier zip.",
                    RuntimeWarning,
                )
                continue

            try:
                mod = importlib.import_module(package_name)
                sys.modules[f"tank_vendor.{package_name}"] = mod
                globals()[package_name] = mod
            except ImportError as e:
                # Per-package import failures are tolerated. The most common
                # cause is a package using syntax newer than the current Python
                # (e.g. flow_data_sdk uses types.UnionType which is 3.10+).
                warnings.warn(
                    f"Could not import {package_name} from {zip_path}: {e}"
                )

    except Exception as e:
        # Clean up sys.path on a wholesale failure so we don't leave a
        # non-functional zip on the path interfering with other imports.
        try:
            sys.path.remove(str(zip_path))
        except ValueError:
            pass
        if required:
            raise RuntimeError(
                f"Failed to import required modules from {zip_path}: {e}"
            ) from e
        warnings.warn(
            f"Failed to import modules from {zip_path}: {e}",
            RuntimeWarning,
        )
        return False

    return True


# ============================================================================
# MAIN INITIALIZATION
# ============================================================================

_requirements_dir = pathlib.Path(__file__).resolve().parent.parent.parent / "requirements"

# 1. Per-Python-version zip (mandatory). Contains pinned dependencies with
#    binary extensions; load order keeps it ahead of any shared zips so its
#    versions take precedence on name collision.
_pkgs_zip_path = (
    _requirements_dir
    / f"{sys.version_info.major}.{sys.version_info.minor}"
    / "pkgs.zip"
)
_pkgs_loaded = _load_packages_from_zip(
    _pkgs_zip_path, required=True, path_position=0
)
if _pkgs_loaded and "shotgun_api3" in sys.modules:
    _patch_shotgun_api3_certs(_pkgs_zip_path)

# 2. Shared zips (optional, Python-version-independent). Drop a *.zip into
#    requirements/any/ and it will be loaded automatically. Shared vendors are
#    expected to use the system trust store and not ship data files that would
#    need extraction from inside the zip.
_shared_dir = _requirements_dir / "any"
if _shared_dir.is_dir():
    for _i, _shared_zip in enumerate(sorted(_shared_dir.glob("*.zip")), start=1):
        _load_packages_from_zip(
            _shared_zip, required=False, path_position=_i
        )

# 3. Install the lazy import hook for nested submodule access.
#    Idempotent via the _tank_vendor_meta_finder guard, so calling it once
#    after both load steps is safe and sufficient.
_install_import_hook()
