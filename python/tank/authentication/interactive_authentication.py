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
Authentication and session renewal handling.

This module handles asking the user for their password, login etc.
It will try to use a QT UI to prompt the user if possible, but may
fall back on a console (stdin/stdout) based workflow if QT isn't available.

--------------------------------------------------------------------------------
NOTE! This module is part of the authentication library internals and should
not be called directly. Interfaces and implementation of this module may change
at any point.
--------------------------------------------------------------------------------
"""

# Using "with" with the lock to make sure it is always released.

from __future__ import with_statement

from .errors import AuthenticationCancelled
from .console_authentication import ConsoleLoginHandler, ConsoleRenewSessionHandler
from .ui_authentication import UiAuthenticationHandler

from .. import LogManager

import threading
import sys
import os


logger = LogManager.get_logger(__name__)

###############################################################################################
# internal classes and methods

def _get_current_os_user():
    """
    Gets the current operating system username.

    :returns: The username string.
    """
    if sys.platform == "win32":
        # http://stackoverflow.com/questions/117014/how-to-retrieve-name-of-current-windows-user-ad-or-local-using-python
        return os.environ.get("USERNAME", None)
    else:
        try:
            import pwd
            pwd_entry = pwd.getpwuid(os.geteuid())
            return pwd_entry[0]
        except:
            return None


def _get_qt_state():
    """
    Returns the state of Qt: the libraries available and if we have a ui or not.
    :returns: If Qt is available, a tuple of (QtCore, QtGui, has_ui_boolean_flag).
              Otherwise, (None, None, False)
    """
    qt_core = None
    qt_gui = None
    qapp_instance_active = False
    try:
        from .ui.qt_abstraction import QtGui, QtCore
        qt_core = QtCore
        qt_gui = QtGui
        qapp_instance_active = (QtGui.QApplication.instance() is not None)
    except:
        pass
    return (qt_core, qt_gui, qapp_instance_active)


class SessionRenewal(object):
    """
    Handles multi-threaded session renewal. This class handles the use case when
    multiple threads simultaneously try to ask the user for a password.

    Use this class by calling the static method renew_session(). Please see this method
    for more details.
    """

    # Lock the assures only one thread at a time can execute the authentication logic.
    _renew_session_internal_lock = threading.Lock()

    # List of possible states for session renewal.
    WAITING, CANCELLED, SUCCESS = range(3)

    # When a thread cancels session renewal, this flag is set so other threads know
    # to raise an exception as well.
    _auth_state = WAITING

    # Makes access to the thread count and executing logic based on it thread
    # safe.
    _renew_session_lock = threading.Lock()
    # Number of threads who are trying to renew the session.
    _renew_session_thread_count = 0

    @staticmethod
    def _renew_session_internal(user, credentials_handler):
        """
        Prompts the user for the password. This method should never be called directly
        and _renew_session should be called instead.

        :param user: SessionUserImpl instance of the user that needs its session
                     renewed.
        :param credentials_handler: Object that actually prompts the user for
                                    credentials.

        :raises AuthenticationCancelled: Raised if the authentication is cancelled.
        """
        logger.debug("About to take the authentication lock.")
        with SessionRenewal._renew_session_internal_lock:

            logger.debug("Took the authentication lock.")

            # When authentication is cancelled, every thread who enter the authentication
            # critical section should throw as well.
            if SessionRenewal._auth_state == SessionRenewal.CANCELLED:
                raise AuthenticationCancelled()
            # If authentication was successful, simply return.
            elif SessionRenewal._auth_state == SessionRenewal.SUCCESS:
                return

            # We're the first thread, so authenticate.
            try:
                logger.debug("Not authenticated, requesting user input.")
                hostname, login, session_token, cookies = credentials_handler.authenticate(
                    user.get_host(),
                    user.get_login(),
                    user.get_http_proxy()
                )
                SessionRenewal._auth_state = SessionRenewal.SUCCESS
                logger.debug("Login successful!")
                user.set_session_token(session_token)
                user.set_cookies(cookies)
                # @FIXME: This should be obtained from the server.
                import time
                user.set_sso_session_expiration(int(time.time())+30)
            except AuthenticationCancelled:
                SessionRenewal._auth_state = SessionRenewal.CANCELLED
                logger.debug("Authentication cancelled")
                raise

    @staticmethod
    def renew_session(user, credentials_handler):
        """
        Prompts the user for the password. This method is thread-safe, meaning if
        multiple users call this method at the same time, it will keep track of
        how many threads are currently running inside it and all threads waiting
        for the authentication to complete will return with the same result
        as the thread that actually did the authentication, either returning or
        raising an exception.

        :param user: SessionUser we are re-authenticating.
        :param credentials_handler: Object that actually prompts the user for
                                    credentials.

        :raises AuthenticationCancelled: If the user cancels the authentication,
                                         this exception is raised.
        """
        # One more renewer.
        with SessionRenewal._renew_session_lock:
            SessionRenewal._renew_session_thread_count += 1

        try:
            # Renew the session
            SessionRenewal._renew_session_internal(user, credentials_handler)
        finally:
            # We're leaving the method somehow, cleanup!
            with SessionRenewal._renew_session_lock:
                # Decrement the thread count
                SessionRenewal._renew_session_thread_count -= 1
                # If we're the last one, clear the cancel flag.
                if SessionRenewal._renew_session_thread_count == 0:
                    SessionRenewal._auth_state = SessionRenewal.WAITING
                # At this point, if the method _renew_session_internal simply
                # returned, this method returns. If the method raised an exception,
                # it will keep being propagated.



###############################################################################################
# public methods

def renew_session(user, no_gui=False):
    """
    Prompts the user to enter this password on the console or in a ui to
    retrieve a new session token.

    :param user: SessionUser that needs its session token refreshed.

    :raises AuthenticationCancelled: If the user cancels the authentication,
                                     this exception is raised.
    """
    logger.debug("Credentials were out of date, renewing them.")
    QtCore, QtGui, has_ui = _get_qt_state()

    if has_ui:
        authenticator = UiAuthenticationHandler(is_session_renewal=True, cookies=user.get_cookies(), no_gui=no_gui)
    else:
        authenticator = ConsoleRenewSessionHandler()
    SessionRenewal.renew_session(user, authenticator)

def authenticate(default_host, default_login, http_proxy, fixed_host, cookies):
    """
    Prompts the user for his user name and password. If the host is not fixed,
    it is also possible to edit the host. If Qt is available and an QApplication
    instantiated, a dialog will prompt for user input. If not, the console will
    prompt instead.

    :param default_host: Default host to present to the user.
    :param default_login: Default login to present to the user.
    :param http_proxy: Proxy to use to connect to the host.
    :param fixed_host: If True, the host won't be editable.

    :returns: The (hostname, login, session token) tuple for this authenticated
              user.

    :raises AuthenticationCancelled: If the user cancels the authentication,
                                     this exception is raised.
    """
    # If there is no default login, let's provide the os user's instead.
    default_login = default_login or _get_current_os_user()

    QtCore, QtGui, has_ui = _get_qt_state()

    # If we have a gui, we need gui based authentication
    if has_ui:
        # If we are renewing for a background thread, use the invoker
        authenticator = UiAuthenticationHandler(is_session_renewal=False, fixed_host=fixed_host, cookies=cookies)
    else:
        # @TODO: Handle gracefully the case where we detect a SSO-enabled
        # Shotgun server, which will not support console-based login.
        authenticator = ConsoleLoginHandler(fixed_host=fixed_host)
    return authenticator.authenticate(default_host, default_login, http_proxy)
