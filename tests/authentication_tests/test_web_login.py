# -*- coding: utf-8 -*-

# Copyright (c) 2023 Autodesk.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import (
    ShotgunTestBase,
    only_run_on_nix,
    skip_if_pyside_missing,
)

from tank.authentication.sso_saml2 import SsoSaml2Toolkit


@only_run_on_nix  # This test issues a seg fault on Windows somehow...
@skip_if_pyside_missing
class WebLoginTests(ShotgunTestBase):
    def test_web_login(self):
        from tank.authentication.ui import qt_abstraction

        # Call function for coverage
        qt_abstraction.QtWebEngineCore

        if qt_abstraction.QtGui.QApplication.instance() is None:
            self._app = qt_abstraction.QtGui.QApplication([])

        obj = SsoSaml2Toolkit(
            "Test Web Login",
            qt_modules={
                "QtCore": qt_abstraction.QtCore,
                "QtGui": qt_abstraction.QtGui,
                "QtNetwork": qt_abstraction.QtNetwork,
                "QtWebKit": qt_abstraction.QtWebKit,
                "QtWebEngineWidgets": qt_abstraction.QtWebEngineWidgets,
            },
        )

        # coverage
        obj._view.page().createWindow(None)

        # And do nothing more... so coverage is happy
