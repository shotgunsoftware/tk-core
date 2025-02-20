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

# Dynamically determine the name of the current module (e.g., "tank_vendor").
pkgs_zip_path = (
    pathlib.Path(__file__).resolve().parent.parent.parent /
    "requirements" /
    f"{sys.version_info.major}.{sys.version_info.minor}" /
    "pkgs.zip"
)

# Add pkgs.zip to sys.path if it exists and isn't already present.
if not pkgs_zip_path.exists():
    raise RuntimeError(f"{pkgs_zip_path} does not exists")

sys.path.insert(0, str(pkgs_zip_path))
try:
    # If other modules use from tank_vendor import distro, Python expects
    # tank_vendor.distro to exist in sys.modules, which doesn’t happen
    # automatically by just adding pkgs.zip to sys.path. Importing distro and
    # yaml globally in __init__.py ensures they are properly registered and
    # accessible.
    import yaml
    import distro

    # Explicitly import six and ruamel_yaml from the tank_vendor folder instead
    # of loading from pkgs.zip.
    # This ensures that these packages are always used from the tank_vendor
    # namespace, avoiding potential conflicts with versions inside pkgs.zip.
    from . import ruamel_yaml, six

except Exception as e:
    sys.path.remove(str(pkgs_zip_path))
    raise RuntimeError(f"Failed to import required modules: {e}") from e