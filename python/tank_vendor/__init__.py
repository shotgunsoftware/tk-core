# Copyright (c) 2025 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import pathlib
import sys
import zipfile


def _patch_shotgun_api3_certs(zip_path):
    """
    Patch shotgun_api3.Shotgun._get_certs_file to return extracted certificate path.
    
    When shotgun_api3 is loaded from pkgs.zip, its certificate file is also inside
    the ZIP. Since SSL cannot read from ZIP files, we extract the certificate during
    build to requirements/<version>/certs/ and patch the method to return that path.
    """
    import shotgun_api3
    
    # Path to extracted certificates directory
    certs_dir = zip_path.parent / "certs"
    cert_file = certs_dir / "shotgun_api3" / "lib" / "certifi" / "cacert.pem"
    
    if cert_file.exists():
        # Save original method
        _original_get_certs_file = shotgun_api3.Shotgun._get_certs_file
        
        # Create patched version
        def _patched_get_certs_file(self):
            # Return extracted certificate path instead of ZIP path
            return str(cert_file)
        
        # Apply patch
        shotgun_api3.Shotgun._get_certs_file = _patched_get_certs_file


# Construct path to the Python version-specific pkgs.zip containing third-party dependencies.
# Path structure: <tk-core>/requirements/<major>.<minor>/pkgs.zip
pkgs_zip_path = (
    pathlib.Path(__file__).resolve().parent.parent.parent
    / "requirements"
    / f"{sys.version_info.major}.{sys.version_info.minor}"
    / "pkgs.zip"
)

# Only load from pkgs.zip if it exists as a valid ZIP file. This provides backward
# compatibility for installations that may still use vendored copies or are in
# temporary locations without the requirements directory structure.
_pkgs_zip_valid = False
if pkgs_zip_path.exists():
    # Check if it's a file (not a directory) - in some CI environments,
    # pkgs.zip might be extracted to a directory instead of kept as a ZIP.
    if pkgs_zip_path.is_file():
        # Validate that it's actually a valid ZIP file before adding to sys.path
        try:
            with zipfile.ZipFile(pkgs_zip_path, 'r') as zf:
                # Quick validation - just check that we can read the ZIP directory
                zf.namelist()
                _pkgs_zip_valid = True
        except (zipfile.BadZipFile, OSError, IOError):
            # Not a valid ZIP file or can't be read - skip loading from pkgs.zip
            pass

if _pkgs_zip_valid:
    # Add pkgs.zip to sys.path to enable importing packages from the archive.
    sys.path.insert(0, str(pkgs_zip_path))
    try:
        # Import third-party packages from pkgs.zip.
        # These simple imports create module attributes (e.g., tank_vendor.yaml)
        # that work for basic imports like "from tank_vendor import yaml".
        import distro
        import packaging
        import ruamel
        import shotgun_api3
        import yaml

        # Register modules in sys.modules to support nested imports.
        # This is required for imports like:
        #   - from tank_vendor.packaging.version import parse
        #   - from tank_vendor.ruamel.yaml import YAML
        #   - from tank_vendor.shotgun_api3 import Shotgun
        # Without this, Python cannot resolve the dotted path when looking up
        # submodules (e.g., .version, .yaml) because it searches sys.modules
        # for 'tank_vendor.packaging', not just the attribute tank_vendor.packaging.
        sys.modules["tank_vendor.packaging"] = sys.modules["packaging"]
        sys.modules["tank_vendor.ruamel"] = sys.modules["ruamel"]
        sys.modules["tank_vendor.shotgun_api3"] = sys.modules["shotgun_api3"]

        # Patch shotgun_api3._get_certs_file to return extracted certificate path
        # SSL cannot read files from ZIP, so we extract certificates during build
        _patch_shotgun_api3_certs(pkgs_zip_path)

    except Exception as e:
        sys.path.remove(str(pkgs_zip_path))
        raise RuntimeError(f"Failed to import required modules from {pkgs_zip_path}: {e}") from e
