import sys

from pathlib import Path

# Dynamically determine the name of the current module (e.g., "tank_vendor").
PYTHON_VERSION = f"{sys.version_info.major}.{sys.version_info.minor}"
pkgs_zip_path = Path(__file__).resolve().parent.parent.parent / "requirements" / PYTHON_VERSION / "pkgs.zip"

# Add pkgs.zip to sys.path if it exists and isn't already present.
if not pkgs_zip_path.exists():
    raise RuntimeError(f"{pkgs_zip_path} does not exists")
sys.path.insert(0, str(pkgs_zip_path))

# If other modules use from tank_vendor import distro, Python expects tank_vendor.distro
# to exist in sys.modules, which doesn’t happen automatically by just adding pkgs.zip to
# sys.path. Importing distro and yaml globally in __init__.py ensures
# they are properly registered and accessible
import yaml
import distro

# Explicitly import six and ruamel_yaml from the tank_vendor folder instead of loading from pkgs.zip.
# This ensures that these packages are always used from the tank_vendor namespace, 
# avoiding potential conflicts with versions inside pkgs.zip.
from tank_vendor import six
from tank_vendor import ruamel_yaml
