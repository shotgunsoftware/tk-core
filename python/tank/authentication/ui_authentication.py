# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
QT based UI login prompting.

--------------------------------------------------------------------------------
NOTE! This module is part of the authentication library internals and should
not be called directly. Interfaces and implementation of this module may change
at any point.
--------------------------------------------------------------------------------
"""
import logging

from .errors import AuthenticationCancelled
from . import invoker
from .. import LogManager

logger = LogManager.get_logger(__name__)


class UiAuthenticationHandler(object):
    """
    Handles ui based authentication. This class should not be instantiated
    directly and be used through the authenticate and renew_session methods.
    """

    def __init__(self, is_session_renewal, fixed_host=False):
        """
        Creates the UiAuthenticationHandler object.
        :param is_session_renewal: Boolean indicating if we are renewing a session. True if we are, False otherwise.
        """
        self._is_session_renewal = is_session_renewal
        self._gui_launcher = invoker.create()
        self._fixed_host = fixed_host

    def authenticate(self, hostname, login, http_proxy):
        """
        Pops a dialog that asks for the hostname, login and password of the user. If there is a current
        engine, it will run the code in the main thread.
        :param hostname: Host to display in the dialog.
        :param login: login to display in the dialog.
        :param http_proxy: Proxy server to use when validating credentials. Can be None.
        :returns: A tuple of (hostname, login, session_token)
        """
        
        # deferred import because the login dialog contains QT references.
        from . import login_dialog

        if self._is_session_renewal:
            logger.debug("Requesting password in a dialog.")
        else:
            logger.debug("Requesting username and password in a dialog.")

        def _process_ui():
            dlg = login_dialog.LoginDialog(
                is_session_renewal=self._is_session_renewal,
                hostname=hostname,
                login=login,
                http_proxy=http_proxy,
                fixed_host=self._fixed_host
            )
            return dlg.result()

        result = self._gui_launcher(_process_ui)

        if not result:
            raise AuthenticationCancelled()
        return result
