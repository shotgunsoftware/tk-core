import importlib.util
import sys
import zipfile

from pathlib import Path

# Dynamically determine the name of the current module (e.g., "tank_vendor").
MODULE_NAME = Path(__file__).resolve().parent.name
PYTHON_VERSION = f"{sys.version_info.major}.{sys.version_info.minor}"
pkgs_zip_path = Path(__file__).resolve().parent.parent.parent / "requirements" / PYTHON_VERSION / "pkgs.zip"

# Add pkgs.zip to sys.path if it exists and isn't already present.
if not pkgs_zip_path.exists():
    raise RuntimeError(f"{pkgs_zip_path} does not exists")
sys.path.insert(0, str(pkgs_zip_path))


def register_alone_pgks():
    """
    Registers standalone Python files (modules) from pkgs.zip under the current module's namespace.

    This function is used to dynamically load individual Python files that exist at the root of pkgs.zip.
    These are not part of a package directory structure (i.e., they do not reside inside subfolders).

    Purpose:
    - Some standalone modules (e.g., `six.py`, `distro.py`) might not be installed as standard packages
      and are instead stored as single files inside pkgs.zip.
    - This function ensures that such modules can be imported under the `tank_vendor` namespace, 
      making them accessible like `import tank_vendor.six` instead of needing manual extraction.

    Example:
        Assume pkgs.zip contains:
        - six.py
        - distro.py
        - ruamel/yaml/__init__.py (ignored by this function, as it's inside a subfolder)

        After calling `register_alone_py_pgks()`, you can do:

        ```python
        from tank_vendor import six, distro

        print(six.__file__)  # Should print the path inside pkgs.zip
        print(distro.__file__)  # Should also print the path inside pkgs.zip
        ```

    Raises:
        RuntimeError: If pkgs.zip does not exist.
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
register_alone_pgks()

# Import additional libraries from pkgs.zip or the global environment.
import yaml
import distro

# Explicitly import six and ruamel_yaml from the tank_vendor folder instead of dynamically loading from pkgs.zip.
# This ensures that these packages are always used from the tank_vendor namespace, 
# avoiding potential conflicts with versions inside pkgs.zip.
from tank_vendor import six
from tank_vendor import ruamel_yaml
