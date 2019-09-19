# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Qt version abstraction layer.
"""

import os

from ..log import LogManager
logger = LogManager.get_logger(__name__)


class QtImporter(object):
    """
    Imports different versions of Qt and makes their API compatible with PySide.

    .. code-block:: python
        try:
            importer = QtImporter()
        except Exception as e:
            print "Couldn't import a Qt Wrapper: " % (e,)
        else:
            importer.QtGui.QApplication([])
            ...
    """

    QT4, QT5 = range(4, 6)

    def __init__(self, interface_version_requested=QT4):
        """
        Imports the Qt modules and sets the QtCore, QtGui and wrapper attributes
        on this object.

        :param interface_version_request: Indicates which version of the Qt API is requested.
        """
        self._binding_name, self._binding_version, self._binding, self._modules, self._qt_version_tuple =\
            self._import_modules(interface_version_requested)

    @property
    def QtCore(self):
        """
        :returns: QtCore module, if available.
        """
        return self._modules["QtCore"] if self._modules else None

    @property
    def QtGui(self):
        """
        :returns: QtGui module, if available.
        """
        return self._modules["QtGui"] if self._modules else None

    @property
    def QtWebKit(self):
        """
        :returns: QtWebKit module, if available.
        """
        return self._modules["QtWebKit"] if self._modules else None

    @property
    def QtNetwork(self):
        """
        :returns: QtNetwork module, if available.
        """
        return self._modules["QtNetwork"] if self._modules else None

    @property
    def binding(self):
        """
        :returns: The PySide* or PyQt* root module.
        """
        return self._binding

    @property
    def binding_name(self):
        """
        :returns: The name of the Qt binding.
        """
        return self._binding_name

    @property
    def binding_version(self):
        """
        :returns: The version of the Qt binding.
        """
        return self._binding_version

    @property
    def modules(self):
        """
        :returns: A dictionary of all the Python modules available for this Qt binding.
        """
        return self._modules

    @property
    def base(self):
        """
        :returns: A dictionary representing the base of the Qt binding. The name and version of the
            binding are stored as __name__ and __version__ respectively.
        """
        if not self._modules:
            return {}

        qt_base = {}

        qt_base.update(self._modules)
        qt_base["__name__"] = self._binding_name
        qt_base["__version__"] = self._binding_version

        return qt_base

    @property
    def qt_version_tuple(self):
        return self._qt_version_tuple

    def _import_module_by_name(self, parent_module_name, module_name):
        """
        Import a module by its string name.

        :returns: The module loaded, or None if it could not be loaded.
        """
        module = None
        try:
            module = __import__(parent_module_name, globals(), locals(), [module_name])
            module = getattr(module, module_name)
        except Exception as e:
            logger.debug("Unable to import module '%s': %s", module_name, e)
            pass
        return module

    def _import_pyside(self):
        """
        Imports PySide.

        :returns: The (binding name, binding version, modules) tuple.
        """
        from PySide import QtCore, QtGui

        QtNetwork = self._import_module_by_name("PySide", "QtNetwork")
        QtWebKit = self._import_module_by_name("PySide", "QtWebKit")

        import PySide
        # Some old versions of PySide don't include version information
        # so add something here so that we can use PySide.__version__
        # later without having to check!

        # Note: Do not remove this. It was briefly introduced so that engines
        # could introspec the wrapper for all sorts of things, but we've moving
        # away from modifying the modules themselves, so keep this is for now and
        # we'll be able to deprecate it at some point in the future.
        if not hasattr(PySide, "__version__"):
            PySide.__version__ = "<unknown>"

        # PySide stick a \n at the end of the __name__ for some reason. Strip it!
        return PySide.__name__.strip(), PySide.__version__, PySide, {
            "QtCore": QtCore,
            "QtGui": QtGui,
            "QtNetwork": QtNetwork,
            "QtWebKit": QtWebKit,
        }, self._to_version_tuple(QtCore.qVersion())

    def _import_pyside2(self):
        """
        This will be called at initialization to discover every PySide 2 modules.

        :returns: The ("PySide2", PySide2 version, PySide2 module, [Qt* modules]) tuple.
        """
        # Quick check if PySide 2 is available. Try to import a well known module. If that fails it will
        # throw an import error which will be handled by the calling code. Note that PySide2 can be
        # imported even if the Qt binaries are missing, so it's better to try importing QtCore for
        # testing.
        from PySide2 import QtCore

        # List of all Qt 5 modules.
        sub_modules = [
            "QtGui", "QtHelp", "QtNetwork", "QtPrintSupport", "QtQml", "QtQuick", "QtQuickWidgets",
            "QtScript", "QtSvg", "QtTest", "QtUiTools", "QtWebChannel",
            "QtWebKit", "QtWebKitWidgets", "QtWidgets", "QtWebSockets", "QtXml", "QtXmlPatterns",
            "QtScriptSql", "QtScriptTools", "QtOpenGL", "QtMultimedia"
        ]

        # We have the potential for a deadlock in Maya 2018 on Windows if this
        # is imported. We set the env var from the tk-maya engine when we
        # detect that we are in this situation.
        if "SHOTGUN_SKIP_QTWEBENGINEWIDGETS_IMPORT" not in os.environ:
            sub_modules.append("QtWebEngineWidgets")

        modules_dict = {
            "QtCore": QtCore
        }

        # Depending on the build of PySide 2 being used, more or less modules are supported. Instead
        # of assuming a base set of functionality, simply try every module one at a time.
        #
        # First, if a module is missing the __import__ function doesn't raise an exception.
        # This is why we have to test for existence of the attribute on the PySide 2 module.
        #
        # Second, if the library couldn't load because of missing symbols with in Qt (e.g.
        # both Maya 2017 and the PySide 2 built on my machine are missing some symbols in order to load
        # QtScriptTools), it will raise an ImportError.
        #
        # Testing each module like this individually helps get as many as possible.
        for module_name in sub_modules:
            try:
                wrapper = __import__("PySide2", globals(), locals(), [module_name])
                if hasattr(wrapper, module_name):
                    modules_dict[module_name] = getattr(wrapper, module_name)
            except Exception as e:
                logger.debug("'%s' was skipped: %s", module_name, e)
                pass

        import PySide2
        return PySide2.__name__, PySide2.__version__, PySide2, modules_dict, self._to_version_tuple(QtCore.qVersion())

    def _import_pyside2_as_pyside(self):
        """
        Imports PySide2.

        :returns: The (binding name, binding version, modules) tuple.
        """
        import PySide2
        from PySide2 import QtCore, QtGui, QtWidgets
        from .pyside2_patcher import PySide2Patcher

        QtCore, QtGui = PySide2Patcher.patch(QtCore, QtGui, QtWidgets, PySide2)
        QtNetwork = self._import_module_by_name("PySide2", "QtNetwork")
        QtWebKit = self._import_module_by_name("PySide2.QtWebKitWidgets", "QtWebKit")

        return "PySide2", PySide2.__version__, PySide2, {
            "QtCore": QtCore,
            "QtGui": QtGui,
            "QtNetwork": QtNetwork,
            "QtWebKit": QtWebKit,
        }, self._to_version_tuple(QtCore.qVersion())

    def _import_pyqt4(self):
        """
        Imports PyQt4.

        :returns: The (binding name, binding version, modules) tuple.
        """
        from PyQt4 import QtCore, QtGui, Qt

        # hot patch the library to make it compatible with PySide-based apps.
        QtCore.Signal = QtCore.pyqtSignal
        QtCore.Slot = QtCore.pyqtSlot
        QtCore.Property = QtCore.pyqtProperty

        QtNetwork = self._import_module_by_name("PyQt4", "QtNetwork")
        QtWebKit = self._import_module_by_name("PyQt4", "QtWebKit")

        # Note: Do not remove this. It was briefly introduced so that engines
        # could introspec the wrapper for all sorts of things, but we've moving
        # away from modifying the modules themselves, so keep this is for now and
        # we'll be able to deprecate it at some point in the future.
        import PyQt4
        PyQt4.__version__ = Qt.PYQT_VERSION_STR

        return "PyQt4", PyQt4.__version__, PyQt4, {
            "QtCore": QtCore,
            "QtGui": QtGui,
            "QtNetwork": QtNetwork,
            "QtWebKit": QtWebKit,
        }, self._to_version_tuple(QtCore.QT_VERSION_STR)

    def _to_version_tuple(self, version_str):
        """
        Converts a version string with the dotted notation into a tuple
        of integers.

        :param version_str: Version string to convert.

        :returns: A tuple of integer representing the version.
        """
        return tuple([int(c) for c in version_str.split(".")])

    def _import_modules(self, interface_version_requested):
        """
        Tries to import different Qt binding implementation in the following order:
            - PySide2
            - PySide
            - PyQt4

        :returns: The (binding name, binding version, modules) tuple or (None, None, None) if
            no binding is avaialble.
        """
        logger.debug(
            "Requesting %s-like interface",
            "Qt4" if interface_version_requested == self.QT4 else "Qt5"
        )
        # First try PySide 2.
        if interface_version_requested == self.QT4:
            try:
                pyside2 = self._import_pyside2_as_pyside()
                logger.debug("Imported PySide2 as PySide.")
                return pyside2
            except ImportError as e:
                pass
        elif interface_version_requested == self.QT5:
            try:
                pyside2 = self._import_pyside2()
                logger.debug("Imported PySide2.")
                return pyside2
            except ImportError:
                pass

        # We do not test for PyQt5 since it is supported on Python 3 only at the moment.

        # Now try PySide 1
        if interface_version_requested == self.QT4:
            try:
                pyside = self._import_pyside()
                logger.debug("Imported PySide1.")
                return pyside
            except ImportError:
                pass

        # Now try PyQt4
        if interface_version_requested == self.QT4:
            try:
                pyqt = self._import_pyqt4()
                logger.debug("Imported PyQt4.")
                return pyqt
            except ImportError:
                pass

        logger.debug("No Qt matching that interface was found.")

        return (None, None, None, None, None)
