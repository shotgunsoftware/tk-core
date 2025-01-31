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


if pkgs_zip_path.exists():
    sys.path.insert(0, str(pkgs_zip_path))


def load_ruamel_yaml():
    """Carga ruamel.yaml asegurando que se use la versión correcta desde tank_vendor."""
    # Eliminar ruamel del cache de módulos si ya está cargado
    for mod in list(sys.modules):
        if mod.startswith("ruamel"):
            del sys.modules[mod]

    try:
        # Intentar importación normal
        import tank_vendor.ruamel_yaml
    except ModuleNotFoundError:
        # Si no está en sys.path, usar importlib para cargarlo
        ruamel_yaml_spec = importlib.util.find_spec("ruamel.yaml")
        if ruamel_yaml_spec:
            ruamel_yaml = importlib.util.module_from_spec(ruamel_yaml_spec)
            ruamel_yaml_spec.loader.exec_module(ruamel_yaml)
            sys.modules["tank_vendor.ruamel_yaml"] = ruamel_yaml
            return ruamel_yaml
        else:
            raise ImportError(f"No se pudo encontrar 'ruamel.yaml' en {pkgs_zip_path}")


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
print("YAML.__FILE__ from init: ", yaml.__file__)
print("DISTRO.__FILE__ from init: ", distro.__file__)
print("SIX.__FILE__ from init: ", six.__file__)
from tank_vendor.ruamel import yaml as  ruamel_yaml
print("RUAMEL_YAML.__FILE__ from load function: ", ruamel_yaml.__file__)
print("sys.modules: ", sys.modules)
print("sys.path: ", sys.path)
