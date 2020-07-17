import os
import sys

from tank_vendor import six

# TODO: this check should probably be for py3.4
if six.PY3:
    import importlib

    imp = None
    # Noqa
    from threading import Lock
else:
    import imp

    class Lock:
        def __enter__(self):
            imp.acquire_lock()

        def __exit__(self, type, value, traceback):
            imp.release_lock()


def find_spec(name, paths):
    if "." in name:
        _, _, module_name = name.rpartition(".")
    else:
        module_name = name

    for a_path in paths:
        spec = _get_spec(name, os.path.join(a_path, module_name))
        if spec:
            return spec


def _get_spec(name, path):
    """
    Will retrieve a ModuleSpec instance from the found module or package.
    It will attempt to find a package first that matches the path, failing that
    it will attempt to find a module that matches the path. The path should be
    path on disk excluding any file extension.

    In other words a path like this:
    /site-packages/my_module
    will check for packages:
    /site-packages/my_module/__init__.py
    and modules
    /site-packages/my_module.py

    It checks through all the valid extension types, e.g .py, .pyc ...

    :param name: Name of the module.
    :param path: Path of the package or module excluding the file extension.
    :return:
    """
    # This behaviour is mostly taken from imp.find_module, but with some changes.

    # Handle packages
    for suffix in (
        importlib.machinery.SOURCE_SUFFIXES + importlib.machinery.BYTECODE_SUFFIXES
    ):
        package_file_name = "__init__" + suffix
        file_path = os.path.join(path, package_file_name)
        if os.path.isfile(file_path):
            return importlib.util.spec_from_file_location(name, file_path)
    # Handle modules
    for suffix in (
        importlib.machinery.EXTENSION_SUFFIXES
        + importlib.machinery.SOURCE_SUFFIXES
        + importlib.machinery.BYTECODE_SUFFIXES
    ):
        file_path = path + suffix
        if os.path.isfile(file_path):
            return importlib.util.spec_from_file_location(name, file_path)


def import_module_from_path(name, path, package=False):
    # if package:
    #     imp.load_module(
    #         name, None, path, ("", "", imp.PKG_DIRECTORY)
    #     )

    spec = _get_spec(name, path)
    return import_module_from_spec(spec)


def load_source(name, file):
    """
    Aims to replicate imp.load_source in Python 3.4 and above.
    In versions of Python below 3.4 it will just use imp.load_source.
    :param name: The name the module will be given in sys.modules.
    :param file: A string path to a source file.
    :return: The imported module.
    """

    if imp:
        mod = imp.load_source(name, file)
        return mod
    else:
        loader = importlib.machinery.SourceFileLoader(name, file)
        spec = importlib.util.spec_from_loader(loader.name, loader)
        return import_module_from_spec(spec)


def import_module_from_spec(spec):
    """
    Given a ModuleSpec, it will load and execute the module and add it to sys.modules.
    :param spec: ModuleSpec instance.
    :return: The imported module.
    """
    module = importlib.util.module_from_spec(spec)

    sys.modules[spec.name] = module

    spec.loader.exec_module(module)
    return module


def new_module(name):
    if imp:
        return imp.new_module(name)
    else:
        spec = importlib.util.spec_from_loader(name, loader=None)
        return importlib.util.module_from_spec(spec)
