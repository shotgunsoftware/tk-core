import importlib.util
import sys
import zipfile

from pathlib import Path

# Dynamically determine the name of the current module (e.g., "tank_vendor").
PYTHON_VERSION = f"{sys.version_info.major}.{sys.version_info.minor}"
pkgs_zip_path = Path(__file__).resolve().parent.parent.parent / "requirements" / PYTHON_VERSION / "pkgs.zip"

# Add pkgs.zip to sys.path if it exists and isn't already present.
if not pkgs_zip_path.exists():
    raise RuntimeError(f"{pkgs_zip_path} does not exists")
sys.path.insert(0, str(pkgs_zip_path))

# # Import additional libraries from pkgs.zip or the global environment.
import yaml
import distro

# Explicitly import six and ruamel_yaml from the tank_vendor folder instead of dynamically loading from pkgs.zip.
# This ensures that these packages are always used from the tank_vendor namespace, 
# avoiding potential conflicts with versions inside pkgs.zip.
from tank_vendor import six
from tank_vendor import ruamel_yaml
