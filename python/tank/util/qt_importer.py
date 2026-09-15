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
import pkgutil
import sys

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

    QT4, QT5, QT6 = range(4, 7)

    def __init__(self, interface_version_requested=QT4):
        """
        Imports the Qt modules and sets the QtCore, QtGui and wrapper attributes
        on this object.

        :param interface_version_request: Indicates which version of the Qt API is requested.
        """
        (
            self._binding_name,
            self._binding_version,
            self._binding,
            self._modules,
            self._qt_version_tuple,
        ) = self._import_modules(interface_version_requested)

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
    def QtNetwork(self):
        """
        :returns: QtNetwork module, if available.
        """
        return self._modules["QtNetwork"] if self._modules else None

    @property
    def QtWebEngineWidgets(self):
        """
        :returns: QtWebEngineWidgets module, if available.
        """
        return self._modules["QtWebEngineWidgets"] if self._modules else None

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

    @property
    def shiboken(self):
        """
        :returns: The compatible shiboken module for the imported PySide version if available.
        """
        return self._modules.get("shiboken") if self._modules else None

    def _import_module_by_name(self, parent_module_name, module_name):
        """
        Import a module by its string name.

        :returns: The module loaded, or None if it could not be loaded.
        """

        try:
            module = __import__(parent_module_name, globals(), locals(), [module_name])
            return getattr(module, module_name)
        except Exception as e:
            logger.debug("Unable to import module '%s': %s", module_name, e)

    def _import_pyside2(self):
        """
        This will be called at initialization to discover every PySide 2 modules.

        :returns: The ("PySide2", PySide2 version, PySide2 module, [Qt* modules]) tuple.
        """
        # Quick check if PySide 2 is available. Try to import a well known module. If that fails it will
        # throw an import error which will be handled by the calling code. Note that PySide2 can be
        # imported even if the Qt binaries are missing, so it's better to try importing QtCore for
        # testing.
        import shiboken2
        from PySide2 import QtCore

        # List of all Qt 5 modules.
        sub_modules = [
            "QtGui",
            "QtHelp",
            "QtNetwork",
            "QtPrintSupport",
            "QtQml",
            "QtQuick",
            "QtQuickWidgets",
            "QtScript",
            "QtSvg",
            "QtTest",
            "QtUiTools",
            "QtWebChannel",
            "QtWidgets",
            "QtWebSockets",
            "QtXml",
            "QtXmlPatterns",
            "QtScriptSql",
            "QtScriptTools",
            "QtOpenGL",
            "QtMultimedia",
        ]

        # We have the potential for a deadlock in Maya 2018 on Windows if this
        # is imported. We set the env var from the tk-maya engine when we
        # detect that we are in this situation.
        if "SHOTGUN_SKIP_QTWEBENGINEWIDGETS_IMPORT" not in os.environ:
            sub_modules.append("QtWebEngineWidgets")

        modules_dict = {"QtCore": QtCore}

        # Add shiboken2 to the modules dict
        modules_dict["shiboken"] = shiboken2

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

        return (
            PySide2.__name__,
            PySide2.__version__,
            PySide2,
            modules_dict,
            self._to_version_tuple(QtCore.qVersion()),
        )

    def _import_pyside2_as_pyside(self):
        """
        Imports PySide2.

        :returns: The (binding name, binding version, modules) tuple.
        """
        import PySide2
        import shiboken2
        from PySide2 import QtCore, QtGui, QtWidgets

        from .pyside2_patcher import PySide2Patcher

        QtCore, QtGui = PySide2Patcher.patch(QtCore, QtGui, QtWidgets, PySide2)
        QtNetwork = self._import_module_by_name("PySide2", "QtNetwork")
        QtWebEngineWidgets = None
        if "SHOTGUN_SKIP_QTWEBENGINEWIDGETS_IMPORT" not in os.environ:
            QtWebEngineWidgets = self._import_module_by_name(
                "PySide2", "QtWebEngineWidgets"
            )

        return (
            "PySide2",
            PySide2.__version__,
            PySide2,
            {
                "QtCore": QtCore,
                "QtGui": QtGui,
                "QtNetwork": QtNetwork,
                "QtWebEngineWidgets": QtWebEngineWidgets,
                "shiboken": shiboken2,
            },
            self._to_version_tuple(QtCore.qVersion()),
        )

    def _import_pyside6_as_pyside(self):  # pragma: no cover
        """
        Import PySide6 and expose its modules through the Qt4 (PySide) interface.

        :returns: The (binding name, binding version, modules) tuple.
        """

        import PySide6
        import shiboken6

        from .pyside6_patcher import PySide6Patcher

        QtWebEngineWidgets, QtWebEngineCore = None, None
        if "SHOTGUN_SKIP_QTWEBENGINEWIDGETS_IMPORT" not in os.environ:
            QtWebEngineWidgets = self._import_module_by_name(
                "PySide6", "QtWebEngineWidgets"
            )
            QtWebEngineCore = self._import_module_by_name("PySide6", "QtWebEngineCore")

        QtCore, QtGui, QtWebEngineWidgets = PySide6Patcher.patch(
            QtWebEngineWidgets,
            QtWebEngineCore,
        )

        QtNetwork = self._import_module_by_name("PySide6", "QtNetwork")

        return (
            PySide6.__name__,
            PySide6.__version__,
            PySide6,
            {
                "QtCore": QtCore,
                "QtGui": QtGui,
                "QtNetwork": QtNetwork,
                "QtWebEngineWidgets": QtWebEngineWidgets,
                "shiboken": shiboken6,
            },
            self._to_version_tuple(QtCore.qVersion()),
        )

    def _import_pyside6(self):
        """
        Import PySide6.

        :returns: The (binding name, binding version, modules) tuple.
        """

        import PySide6
        import shiboken6

        sub_modules = pkgutil.iter_modules(PySide6.__path__)

        if "SHOTGUN_SKIP_QTWEBENGINEWIDGETS_IMPORT" in os.environ:
            sub_modules = [
                m for m in sub_modules if not m.name.startswith("QtWebEngine")
            ]

        modules_dict = {}
        # Add shiboken6 to the modules dict
        modules_dict["shiboken"] = shiboken6
        for module in sub_modules:
            module_name = module.name
            try:
                wrapper = __import__("PySide6", globals(), locals(), [module_name])
                if hasattr(wrapper, module_name):
                    modules_dict[module_name] = getattr(wrapper, module_name)
            except Exception as e:
                logger.debug("'%s' was skipped: %s", module_name, e)
                pass

        return (
            PySide6.__name__,
            PySide6.__version__,
            PySide6,
            modules_dict,
            self._to_version_tuple(PySide6.__version__),
        )

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
        Tries to import a Qt binding compatible with the requested interface.

        For the QT4 interface, PySide2 and PySide6 are tried in whichever order is
        most likely to succeed for the running Python version, falling back to the
        other one if the first attempt fails.

        :returns: The (binding name, binding version, modules) tuple or (None, None, None) if
            no binding is avaialble.
        """

        interface = {
            self.QT4: "Qt4",
            self.QT5: "Qt5",
            self.QT6: "Qt6",
        }.get(interface_version_requested)
        logger.debug("Requesting %s-like interface", interface)
        failures = []

        if interface_version_requested == self.QT4:
            # Try the binding most likely to succeed first, based on the running
            # Python version and the VFX Reference Platform's Python/Qt pairing.
            # This is only a heuristic: individual DCCs don't always track the
            # reference platform exactly.
            if sys.version_info < (3, 11):
                # VFX Reference Platform CY2023 and earlier: PySide2/Qt5
                attempts = (
                    ("PySide2", self._import_pyside2_as_pyside),
                    ("PySide6", self._import_pyside6_as_pyside),
                )
            else:
                # VFX Reference Platform CY2024+: PySide6/Qt6
                attempts = (
                    ("PySide6", self._import_pyside6_as_pyside),
                    ("PySide2", self._import_pyside2_as_pyside),
                )

            for binding_name, import_as_pyside in attempts:
                try:
                    result = import_as_pyside()
                    logger.debug(f"Imported {binding_name} as PySide.")
                    return result
                except ImportError as e:
                    logger.debug(
                        f"Unable to import {binding_name} as PySide: {e}",
                        exc_info=True,
                    )
                    failures.append(f"{binding_name}: {e}")

        elif interface_version_requested == self.QT5:
            try:
                pyside2 = self._import_pyside2()
                logger.debug("Imported PySide2.")
                return pyside2
            except ImportError as e:
                logger.debug("Unable to import PySide2: %s", e, exc_info=True)
                failures.append(f"PySide2: {e}")

            # We do not test for PyQt5 since it is supported on Python 3 only at the moment.

        elif interface_version_requested == self.QT6:
            try:
                pyside6 = self._import_pyside6()
                logger.debug("Imported PySide6.")
                return pyside6
            except ImportError as e:
                logger.debug("Unable to import PySide6: %s", e, exc_info=True)
                failures.append(f"PySide6: {e}")

            # TODO migrate qt base from Qt4 interface to Qt6 will require patching Qt5 as Qt6
            logger.debug("Qt6 interface not implemented for Qt5")

        if failures:
            logger.warning(
                f"Unable to import a Qt binding for the {interface} interface: "
                f"{'; '.join(failures)}"
            )
        else:
            logger.warning(
                f"Unable to import a Qt binding for the {interface} interface."
            )

        return (None, None, None, None, None)
