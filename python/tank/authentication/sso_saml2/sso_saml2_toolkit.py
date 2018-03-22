# Copyright (c) 2017 Autodesk.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.
"""
Integration with Shotgun Toolkit API.
"""

from .sso_saml2 import (  # noqa
    SsoSaml2,
)


class SsoSaml2Toolkit(SsoSaml2):
    """
    This class provides a minimal interface to support SSO authentication.
    """

    def __init__(self, window_title=None, qt_modules=None):
        """
        Create a SSO login dialog, using a Web-browser like environment.

        :param window_title: Title to use for the window.
        :param qt_modules:   a dictionnary of required Qt modules.
                             For Qt4/PySide, we require modules QtCore, QtGui, QtNetwork and QtWebKit

        :returns: The SsoSaml2 oject.
        """
        super(SsoSaml2Toolkit, self).__init__(window_title, qt_modules)

    def get_session_data(self):
        """
        Get a mimimal subset of session data, for the Shotgun Toolkit.

        :returns: A tuple of the hostname, user_id, session_id and cookies.
        """
        return (
            self._core._session.host,
            self._core._session.user_id,
            self._core._session.session_id,
            self._core._session.cookies
        )
