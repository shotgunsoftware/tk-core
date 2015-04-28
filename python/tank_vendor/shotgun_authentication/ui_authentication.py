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
Ui based authentication.
"""

from .errors import AuthenticationCancelled

import logging

logger = logging.getLogger("shotgun_authentication").getChild(
    "interactive_authentication"
).getChild("ui_authentication")


def _create_invoker():
    """
    Create the object used to invoke function calls on the main thread when
    called from a different thread.

    :returns: Invoker instance. If Qt is not available or there is no UI, a
              simple pass through method will execute the code in the same
              thread will be produced.
    """
    from .ui.qt_abstraction import QtCore, QtGui

    # If we are already in the main thread, no need for an invoker, invoke directly in this thread.
    if QtCore.QThread.currentThread() == QtGui.QApplication.instance().thread():
        return lambda fn, *args, **kwargs: fn(*args, **kwargs)

    class MainThreadInvoker(QtCore.QObject):
        """
        Class that allows sending message to the main thread. This can be useful
        when a background thread needs to prompt the user via a dialog. The
        method passed into the invoker will be invoked on the main thread and
        the result, either a return value or exception, will be brought back
        to the invoking thread as if it was the thread that actually executed
        the code.
        """
        def __init__(self):
            """
            Constructor.
            """
            QtCore.QObject.__init__(self)
            self._res = None
            self._exception = None
            # Make sure that the invoker is bound to the main thread
            self.moveToThread(QtGui.QApplication.instance().thread())

        def __call__(self, fn, *args, **kwargs):
            """
            Asks the MainTheadInvoker to call a function with the provided parameters in the main
            thread.
            :param fn: Function to call in the main thread.
            :param args: Array of arguments for the method.
            :param kwargs: Dictionary of named arguments for the method.
            :returns: The result from the function.
            """
            self._fn = lambda: fn(*args, **kwargs)
            self._res = None

            logger.debug("Sending ui request to main thread.")

            QtCore.QMetaObject.invokeMethod(self, "_do_invoke", QtCore.Qt.BlockingQueuedConnection)

            # If an exception has been thrown, rethrow it.
            if self._exception:
                raise self._exception
            return self._res

        @QtCore.Slot()
        def _do_invoke(self):
            """
            Execute function and return result
            """
            try:
                logger.debug("Invoking from main thread.")
                self._res = self._fn()
            except Exception, e:
                self._exception = e

    return MainThreadInvoker()


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
        self._gui_launcher = _create_invoker()
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
        from . import login_dialog

        if self._is_session_renewal:
            logger.debug("Requesting password in a dialog.")
        else:
            logger.debug("Requesting username and password in a dialog.")

        def _process_ui():
            dlg = login_dialog.LoginDialog(
                "Shotgun Login",
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
