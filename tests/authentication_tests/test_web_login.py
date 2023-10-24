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
    skip_if_pyside6,
)

from tank.authentication.sso_saml2 import SsoSaml2Toolkit


@skip_if_pyside_missing
class WebLoginTests(ShotgunTestBase):
    def test_web_login(self):
        from tank.authentication.ui import qt_abstraction

        if qt_abstraction.QtGui.QApplication.instance() is None:
            self._app = qt_abstraction.QtGui.QApplication([])

        SsoSaml2Toolkit(
            "Test Web Login",
            qt_modules={
                "QtCore": qt_abstraction.QtCore,
                "QtGui": qt_abstraction.QtGui,
                "QtNetwork": qt_abstraction.QtNetwork,
                "QtWebKit": qt_abstraction.QtWebKit,
                "QtWebEngineWidgets": qt_abstraction.QtWebEngineWidgets,
            },
        )

        # And do nothing more... so coverage is happy
