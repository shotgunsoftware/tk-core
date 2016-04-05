# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import imp
import os
import sys


class CoreImportHandler(object):
    """A custom import handler to allow for core version switching.

    Usage:
        >>> import sys
        >>> from tank.shotgun_deploy import CoreImportHandler
        >>> importer = CoreImportHandler("/path/to/a/version/of/tk-core")
        >>> sys.meta_path.append(importer)
        >>> # import/run a bunch of code
        >>> # context change, need to use a different core
        >>> importer.set_core_path("/path/to/a/different/version/of/tk-core")
        >>> # namespaces cleared. new imports will come from new core location

    When an instance of this object is added to `sys.meta_path`, it is used to
    alter the way python imports packages.

    The core path is used to locate modules attempting to be loaded. The core
    path can be set via `set_core_path` to alter the location of existing and
    future core imports.

    For more information on custom import hooks, see PEP 302:
        https://www.python.org/dev/peps/pep-0302/

    """

    def __init__(self, core_path):
        """Initialize the custom importer.

        :param core_path: A str path to the core location to import from.

        """

        self._core_path = None
        self._namespaces = []

        # a dictionary to hold module information after it is found, before
        # it is loaded.
        self._module_info = {}

        # re-imports any existing modules for the core namespaces
        self.set_core_path(core_path)

    def __repr__(self):
        """
        A unique representation of the handler.

        :return: str representation.
        """

        return (
            "<CoreImportHandler for core located in: '%s'" % (self.core_path,))

    def find_module(self, module_fullname, package_path=None):
        """Locates the given module in the current core.

        :param module_fullname: The fullname of the module to import
        :param package_path: None for a top-level module, or
            package.__path__ for submodules or subpackages

        The package_path is currently ignored by this method as it ensures we're
        importing the module from the current core path.

        For further info, see the docs on find_module here:
            https://docs.python.org/2/library/imp.html#imp.find_module

        :returns: this object (also a loader) if module found, None otherwise.
        """

        # get the package name (first part of the module fullname)
        module_path_parts = module_fullname.split('.')
        package_name = module_path_parts[0]

        # make sure the package is in the list of namespaces before continuing.
        if package_name not in self._namespaces:
            # the package is not in one of the core namespaces. returning
            # None tells python to use the next importer available (likely the
            # default import mechanism).
            return None

        # module path without the target module name
        module_name = module_path_parts.pop()

        # partial path to the module on disk
        if len(module_path_parts):
            module_path = os.path.join(*module_path_parts)
        else:
            module_path = ""

        # if it exists, this should be the full directory path to the module in
        # the current core.
        path = os.path.join(self.core_path, module_path)

        try:
            # find the module and store its info in a lookup based on the
            # full module name. The module info is a tuple of the form:
            #
            #   (file_obj, filename, description)
            #
            # If this find is successful, we'll need the info in order
            # to load it later.
            module_info = imp.find_module(module_name, [path])
            self._module_info[module_fullname] = module_info
        except ImportError:
            # no module found, fall back to regular import
            return None

        # since this object is also the "loader" return itself
        return self

    def load_module(self, module_fullname):
        """Custom loader.

        Called by python if the find_module was successful.

        For further info, see the docs on `load_module` here:
            https://docs.python.org/2/library/imp.html#imp.load_module

        :param module_fullname: The fullname of the module to import

        :returns: The loaded module object.

        """

        file_obj = None
        try:
            # retrieve the found module info
            (file_obj, filename, desc) = self._module_info[module_fullname]

            # attempt to load the module. if this fails, allow it to raise
            # the usual `ImportError`
            module = imp.load_module(module_fullname, file_obj, filename, desc)
        finally:
            # as noted in the imp.load_module docs, must close the file handle.
            if file_obj:
                file_obj.close()

            # no need to carry around the module info now that we've loaded it.
            # once the module is in `sys.modules`, the custom importer will
            # no longer run.
            del self._module_info[module_fullname]

        # the module needs to know the loader so that reload() works
        module.__loader__ = self

        # the module has been loaded from the proper core location!
        return module

    def set_core_path(self, path):
        """Set the core path to use.

        This method clears out `sys.modules` of all previously imported modules.
        This method locks the global interpreter to prevent problems from
        modifying sys.modules in a multithreaded context.

        :param path: str path to the core to import from.

        :raises: ValueError - if the supplied path does not exist or is not
            a valid directory.
        """

        # the paths are the same. No need to do anything.
        if path == self.core_path:
            return

        if not os.path.exists(path):
            raise ValueError(
                "The supplied core path is not a valid directory: '%s'."
                % (path,)
            )

        # TODO: ensure that the directory looks like core?

        # hold on to the old core namespaces
        old_namespaces = self._namespaces

        # set the core path internally. now that this is set,
        self._core_path = path

        # get the new namespaces
        self._namespaces = [d for d in os.listdir(path)
                            if not d.startswith(".")]

        # acquire a lock to prevent issues with other threads importing at the
        # same time.
        imp.acquire_lock()

        # sort by package depth, deeper modules first
        module_names = sorted(
            sys.modules.keys(),
            key=lambda module_name: module_name.count("."),
            reverse=True
        )

        for module_name in module_names:

            # just to be safe, don't re-import this module.
            # we always use the first one added to `sys.meta_path` anyway.
            if module_name == __name__:
                continue

            # extract just the package name
            pkg_name = module_name.split(".")[0]

            if pkg_name in old_namespaces and pkg_name in self._namespaces:
                # the package name exists in an old core namespace and in the
                # new core namespace. we delete it from sys.modules so that
                # the custom import can run.
                del sys.modules[module_name]

        # clear out the previously found module info
        self._module_info = {}

        # release the lock so that other threads can continue importing from
        # the new core location.
        imp.release_lock()

    @property
    def core_path(self):
        """The core_path for this importer.

        :returns: str path to the core being used for imports
        """
        return self._core_path

    @property
    def namespaces(self):
        """The namespaces this importer operates on.

        :returns: a list where each item is a namespace str
        """
        return self._namespaces

def swap_core(core_path):
    """Swap the current core with the core located at the supplied path

    Actually just unloads the existing core and ensures an import handler
    exists that points to the supplied core path. When this method completes,
    all core namespaces will be removed from `sys.modules`. The required
    modules will need to be reimported after this method is called.

    :param core_path: The path to the new core to use upon import.

    """

    # see if there's already a core import handler in use
    import_handler = None
    for handler in sys.meta_path:
        if isinstance(handler, CoreImportHandler):
            import_handler = handler
            break

    if not import_handler:
        # no import handler yet, create a new one
        import_handler = CoreImportHandler(core_path)

        # add the new import handler to the meta path so that it starts
        # taking over core-related imports
        sys.meta_path.append(import_handler)

    # the core we want to load differs from the one the import handler
    # is using. we'll set it so that future imports of core namespaces
    # use this new location
    import_handler.set_core_path(core_path)

    # NOTE: once this is called, any imported modules in the core python
    # namespaces will be unloaded. the calling code will need to reimport
    # everything necessary before continuing.