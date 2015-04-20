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
UI and console based login for Toolkit.
"""

# Using "with" with the lock to make sure it is always released.

from __future__ import with_statement
from getpass import getpass
import threading
from .errors import AuthenticationError, AuthenticationCancelled
from . import session_cache


# FIXME: Quick hack to easily disable logging in this module while keeping the
# code compatible. We have to disable it by default because Maya will print all out
# debug strings.
if False:
    # Configure logging
    import logging
    logger = logging.getLogger("sgtk.interactive_authentication")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler())
else:
    class logger:
        @staticmethod
        def debug(*args, **kwargs):
            pass

        @staticmethod
        def info(*args, **kwargs):
            pass

        @staticmethod
        def warning(*args, **kwargs):
            pass

        @staticmethod
        def error(*args, **kwargs):
            pass

        @staticmethod
        def exception(*args, **kwargs):
            pass


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


def _create_invoker():
    """
    Create the object used to invoke function calls on the main thread when
    called from a different thread.

    :returns: Invoker instance. If Qt is not available or there is no UI, a
              simple pass through method will execute the code in the same
              thread will be produced.
    """
    QtCore, QtGui, has_ui = _get_qt_state()
    # If we have a ui and we're not in the main thread, we'll need to send ui requests to the
    # main thread.
    if not has_ui:
        return lambda fn, *args, **kwargs: fn(*args, **kwargs)

    # If we are already in the main thread, no need for an invoker, invoke directly in this thread.
    if QtCore.QThread.currentThread() == QtGui.QApplication.instance().thread():
        return lambda f: f()

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


class ConsoleAuthenticationHandlerBase(object):
    """
    Base class for authenticating on the console. It will take care of the credential retrieval loop,
    requesting new credentials as long as they are invalid or until the user provides the right one
    or cancels the authentication. This class should not be instantiated directly and be used
    through the authenticate and renew_session methods.
    """

    def authenticate(self, hostname, login, http_proxy):
        """
        Prompts the user for this password to retrieve a new session token and rewews
        the session token.
        :param hostname: Host to renew a token for.
        :param login: User to renew a token for.
        :param http_proxy: Proxy to use for the request. Can be None.
        :returns: The (hostname, login, session token) tuple.
        :raises AuthenticationCancelled: If the user aborts the login process, this exception
                                         is raised.

        """
        logger.debug("Requesting password on command line.")
        while True:
            # Get the credentials from the user
            try:
                hostname, login, password = self._get_user_credentials(hostname, login)
            except EOFError:
                # Insert a \n on the current line so the print is displayed on a new time.
                print
                raise AuthenticationCancelled()

            session_token = self._get_session_token(hostname, login, password, http_proxy)
            if session_token:
                return hostname, login, session_token

    def _get_user_credentials(self, hostname, login):
        """
        Prompts the user for his credentials.
        :param host Host to authenticate for.
        :param login: User that needs authentication.
        :param http_proxy: Proxy to connect to when authenticating.
        :returns: A tuple of (hostname, login, password)
        :raises AuthenticationCancelled: If the user cancels the authentication process,
                 this exception will be thrown.
        """
        raise NotImplementedError

    def _get_password(self):
        """
        Prompts the user for his password. The password will not be visible on the console.
        :raises: AuthenticationCancelled If the user enters an empty password, the exception
                                         will be thrown.
        """
        password = getpass("Password (empty to abort): ")
        if not password:
            raise AuthenticationCancelled()
        return password

    def _get_keyboard_input(self, label, default_value=""):
        """
        Queries for keyboard input.
        :param label: The name of the input we require.
        :param default_value: The value to use if the user has entered no input.
        :returns: The user input or default_value if nothing was entered.
        """
        text = label
        if default_value:
            text += " [%s]" % default_value
        text += ": "
        user_input = None
        while not user_input:
            user_input = raw_input(text) or default_value
        return user_input

    def _get_session_token(self, hostname, login, password, http_proxy):
        """
        Retrieves a session token for the given credentials. If it fails, the user is informed
        :param hostname: The host to connect to.
        :param login: The user to get a session for.
        :param password: Password for the user.
        :param http_proxy: Proxy to use. Can be None.
        :returns: If the credentials were valid, returns a session token, otherwise returns None.
        """
        try:
            return session_cache.generate_session_token(hostname, login, password, http_proxy)
        except AuthenticationError:
            print "Login failed."
            return None


class ConsoleRenewSessionHandler(ConsoleAuthenticationHandlerBase):
    """
    Handles session renewal. Prompts for the user's password. This class should
    not be instantiated directly and be used through the authenticate and
    renew_session methods.
    """
    def _get_user_credentials(self, hostname, login):
        """
        Reads the user password from the keyboard.
        :param hostname: Name of the host we will be logging on.
        :param login: Current user
        :returns: The user's password.
        """
        print "%s, your current session has expired." % login
        print "Please enter your password to renew your session for %s" % hostname
        return hostname, login, self._get_password()


class ConsoleLoginHandler(ConsoleAuthenticationHandlerBase):
    """
    Handles username/password authentication. This class should not be
    instantiated directly and be used through the authenticate and renew_session
    methods.
    """
    def __init__(self, fixed_host):
        super(ConsoleLoginHandler, self).__init__()
        self._fixed_host = fixed_host

    def _get_user_credentials(self, hostname, login):
        """
        Reads the user credentials from the keyboard.
        :param hostname: Name of the host we will be logging on.
        :param login: Default value for the login.
        :returns: A tuple of (login, password) strings.
        """
        if self._fixed_host:
            print "Please enter your login credentials for %s" % hostname
        else:
            print "Please enter your login credentials."
            hostname = self._get_keyboard_input("Host", hostname)
        login = self._get_keyboard_input("Login", login)
        password = self._get_password()
        return hostname, login, password


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
        from .ui import login_dialog

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


# Lock the assures only one thread at a time can execute the authentication logic.
_renew_session_internal_lock = threading.Lock()
# When a thread cancels session renewal, this flag is set so other threads know
# to raise an exception as well.
_is_authentication_cancelled = False


def _renew_session_internal(user, session_token, credentials_handler):
    """
    Common login logic, regardless of how we are actually logging in. It will first try to reuse
    any existing session and if that fails then it will ask for credentials and upon success
    the credentials will be cached.
    :raises AuthenticationError: Raised if the authentication is cancelled.
    :raises AuthenticationDisabled: Raised if authentication was cancelled before.
    """
    logger.debug("About to take the authentication lock.")
    global _renew_session_internal_lock
    with _renew_session_internal_lock:
        global _is_authentication_cancelled
        if _is_authentication_cancelled:
            raise AuthenticationCancelled()

        # If somebody refreshed the session token on the user object since we tried with
        # the session token.
        if user.get_session_token() != session_token:
            return None
        logger.debug("Took the authentication lock.")

        try:
            logger.debug("Not authenticated, requesting user input.")
            # Do the actually credentials prompting and authenticating.
            hostname, login, session_token = credentials_handler.authenticate(
                user.get_host(),
                user.get_login(),
                user.get_http_proxy()
            )
        except AuthenticationCancelled:
            _is_authentication_cancelled = True
            logger.debug("Authentication cancelled")
            user.clear_saved_user(user.get_host())
            raise

        logger.debug("Login successful!")

        user.set_session_token(session_token)


# Makes access to the thread count and executing logic based on it thread
# safe.
_renew_session_lock = threading.Lock()
# Number of threads who are trying to renew the session.
_renew_session_thread_count = 0


def _renew_session(user, session_token, credentials_handler):
    # One more renewer.
    global _renew_session_lock
    with _renew_session_lock:
        global _renew_session_thread_count
        _renew_session_thread_count = _renew_session_thread_count + 1

    try:
        # Renew the session
        _renew_session_internal(user, session_token, credentials_handler)
    finally:
        # We're leaving the method somehow, cleanup!
        with _renew_session_lock:
            # Decrement the thread count
            _renew_session_thread_count = _renew_session_thread_count - 1
            # If we're the last one, clear the cancel flag.
            if _renew_session_thread_count == 0:
                global _is_authentication_cancelled
                _is_authentication_cancelled = False
            # At this point, if the method _renew_session_internal simply
            # returned, this method returns. If the method raised an exception,
            # it will keep being propagated.


def renew_session(user, session_token):
    """
    Prompts the user to enter this password on the console or in a ui to
    retrieve a new session token.

    :param user: SessionUser that needs its session token refreshed.
    :param session_token: The session token value that originally failed.

    :raises AuthenticationCancelled: If the user cancels the authentication,
                                     this exception is raised.
    """
    logger.debug("Credentials were out of date, renewing them.")
    QtCore, QtGui, has_ui = _get_qt_state()
    # If we have a gui, we need gui based authentication
    if has_ui:
        authenticator = UiAuthenticationHandler(is_session_renewal=True)
    else:
        authenticator = ConsoleRenewSessionHandler()
    _renew_session(user, session_token, authenticator)


def authenticate(default_host, default_login, http_proxy, fixed_host):
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
    QtCore, QtGui, has_ui = _get_qt_state()
    # If we have a gui, we need gui based authentication
    if has_ui:
        # If we are renewing for a background thread, use the invoker
        authenticator = UiAuthenticationHandler(is_session_renewal=False, fixed_host=fixed_host)
    else:
        authenticator = ConsoleLoginHandler(fixed_host=fixed_host)
    return authenticator.authenticate(default_host, default_login, http_proxy)
