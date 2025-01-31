import importlib
import importlib.util
import sys
import zipfile

from pathlib import Path

# Dynamically determine the name of the current module (e.g., "tank_vendor").
MODULE_NAME = Path(__file__).resolve().parent.name
PYTHON_VERSION = f"{sys.version_info.major}.{sys.version_info.minor}"
# raise Exception(PYTHON_VERSION)
pkgs_zip_path = Path(__file__).resolve().parent.parent.parent / "requirements" / PYTHON_VERSION / "pkgs.zip"

# Add pkgs.zip to sys.path if it exists and isn't already present.

for mod in ["ruamel", "ruamel.yaml"]:
    if mod in sys.modules:
        del sys.modules[mod]

if pkgs_zip_path.exists():
    sys.path.insert(0, str(pkgs_zip_path))


def register_alone_py_pgks():
    """
    Registers standalone Python files (modules) from pkgs.zip under the current module's namespace.
    This is for flat .py files that are not part of a subdirectory structure in pkgs.zip.
    """
    with zipfile.ZipFile(pkgs_zip_path, 'r') as zf:
        for file_name in zf.namelist():
            if file_name.endswith(".py") and "/" not in file_name:
                module_name = file_name.rsplit(".", 1)[0]  # Extract the module name (e.g., "six").
                with zf.open(file_name) as file:
                    module_code = file.read()
                    # Create a module specification under the current namespace (e.g., "tank_vendor.six").
                    spec = importlib.util.spec_from_loader(f"{MODULE_NAME}.{module_name}", loader=None)
                    module = importlib.util.module_from_spec(spec)
                    # Execute the module's code and populate its namespace.
                    exec(module_code, module.__dict__)
                    # Register the module in sys.modules to make it importable.
                    sys.modules[f"{MODULE_NAME}.{module_name}"] = module


# Register top-level .py files from pkgs.zip.
register_alone_py_pgks()

# Import additional libraries from pkgs.zip or the global environment.
import six
import yaml
import distro
importlib.invalidate_caches()
import ruamel
from ruamel import yaml as ruamel_yaml  
print("YAML.__FILE__ from init: ", yaml.__file__)
print("DISTRO.__FILE__ from init: ", distro.__file__)
print("SIX.__FILE__ from init: ", six.__file__)
print("RUAMEL.__FILE__ from init: ", ruamel.__file__)
print("RUAMEL_YAML.__FILE__ from init: ", ruamel_yaml.__file__)
print("sys.modules: ", sys.modules)
print("sys.path: ", sys.path)
