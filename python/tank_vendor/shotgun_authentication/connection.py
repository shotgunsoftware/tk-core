# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Shotgun connection creation.
"""

from tank_vendor.shotgun_api3 import Shotgun
from tank_vendor.shotgun_api3.lib import httplib2
from tank_vendor.shotgun_api3 import AuthenticationFault, ProtocolError

from .errors import AuthenticationError

_shotgun_instance_factory = Shotgun

# FIXME: Quick hack to easily disable logging in this module while keeping the
# code compatible. We have to disable it by default because Maya will print all out
# debug strings.
if False:
    # Configure logging
    import logging
    logger = logging.getLogger("sgtk.connection")
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


def generate_session_token(hostname, login, password, http_proxy, shotgun_instance_factory=Shotgun):
    """
    Generates a session token for a given username/password on a given site.
    :param hostname: The host to connect to.
    :param login: The user to get a session for.
    :param password: Password for the user.
    :param http_proxy: Proxy to use. Can be None.
    :param shotgun_instance_factory: Shotgun API instance factory. Defaults to Shotgun.
    :returns: The generated session token for that user/password/site combo.
    :raises: TankAuthenticationError if the credentials were invalid.
    """
    try:
        # Create the instance...
        sg = shotgun_instance_factory(
            hostname,
            login=login,
            password=password,
            http_proxy=http_proxy
        )
        # .. and generate the session token. If it throws, we have invalid credentials.
        return sg.get_session_token()
    except AuthenticationFault:
        raise AuthenticationError("Authentication failed.")
    except (ProtocolError, httplib2.ServerNotFoundError):
        raise AuthenticationError("Server %s was not found." % hostname)
    except:
        # We couldn't login, so try again.
        logging.exception("There was a problem logging in.")


def create_sg_connection_from_session(connection_information):
    """
    Tries to auto login to the site using the existing session_token that was saved.
    :param connection_information: Authentication credentials.
    :param shotgun_instance_factory: Shotgun API instance factory. Defaults to Shotgun.
    :returns: Returns a Shotgun instance.
    """
    logger.debug("Trying to create a connection from a connection information.")

    if "login" not in connection_information or "session_token" not in connection_information:
        logger.debug("Nothing was cached.")
        return None

    # Try to refresh the data
    logger.debug("Validating token.")

    sg = _validate_session_token(
        connection_information["host"],
        connection_information["session_token"],
        connection_information.get("http_proxy"),
    )
    if sg:
        logger.debug("Token is still valid!")
        return sg
    else:
        logger.debug("Failed refreshing the token.")
        return None


def _validate_session_token(host, session_token, http_proxy):
    """
    Validates the session token by attempting to an authenticated request on the site.
    :param session_token: Session token to use to connect to the host.
    :param host: Host for that session
    :param http_proxy: http_proxy to use to connect. If no proxy is required, provide None or an empty string.
    :param shotgun_instance_factory: Shotgun API instance factory.
    :returns: A Shotgun instance if the session token was valid, None otherwise.
    """
    # Connect to the site
    logger.debug("Creating shotgun instance")
    global _shotgun_instance_factory
    sg = _shotgun_instance_factory(
        host,
        session_token=session_token,
        http_proxy=http_proxy
    )
    try:
        sg.find_one("HumanUser", [])
        return sg
    except AuthenticationFault, e:
        # Session was expired.
        logger.exception(e)
        return None


def create_sg_connection_from_script_user(connection_information):
    """
    Create a Shotgun connection based on a script user.
    :param connection_information: A dictionary with keys host, api_script, api_key and an optional http_proxy.
    :returns: A Shotgun instance.
    """
    global _shotgun_instance_factory
    return _shotgun_instance_factory(
        connection_information["host"],
        script_name=connection_information["api_script"],
        api_key=connection_information["api_key"],
        http_proxy=connection_information.get("http_proxy", None)
    )


def _get_qt_state():
    """
    Returns the state of Qt: the librairies available and if we have a ui or not.
    :returns: If Qt is available, a tuple of (QtCore, QtGui, has_ui_boolean_flag).
              Otherwise, (None, None, None)
    """
    try:
        from .ui.qt_abstraction import QtGui, QtCore
    except ImportError:
        return None, None, None
    return QtCore, QtGui, QtGui.QApplication.instance() is not None


def _create_invoker():
    """
    Create the object used to invoke function calls on the main thread when
    called from a different thread.

    :returns:  Invoker instance. If Qt is not available or there is no UI, no invoker will be returned.
    """
    QtCore, QtGui, has_ui = _get_qt_state()
    # If we have a ui and we're not in the main thread, we'll need to send ui requests to the
    # main thread.
    if not QtCore or not QtGui or not has_ui:
        return lambda fn, *args, **kwargs: fn(*args, **kwargs)

    class MainThreadInvoker(QtCore.QObject):
        """
        Class that allows sending message to the main thread.
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
                self._res = self._fn()
            except Exception, e:
                self._exception = e

    return MainThreadInvoker()


def _renew_session():
    from . import interactive_authentication
    QtCore, QtGui, has_ui = _get_qt_state()
    # If we have a gui, we need gui based authentication
    if has_ui:
        # If we are renewing for a background thread, use the invoker
        if QtCore.QThread.currentThread() != QtGui.QApplication.instance().thread():
            _create_invoker()(interactive_authentication.ui_renew_session)
        else:
            interactive_authentication.ui_renew_session()
    else:
        interactive_authentication.console_renew_session()


def _create_or_renew_sg_connection_from_session(connection_information):
    """
    Creates a shotgun connection using the current session token or a new one if the old one
    expired.
    :param connection_information: A dictionary holding the connection information.
    :returns: A valid Shotgun instance.
    :raises TankAuthenticationError: If we couldn't get a valid session, a TankAuthenticationError is thrown.
    """

    # If the Shotgun login was not automated, then try to create a Shotgun
    # instance from the cached session id.
    sg = create_sg_connection_from_session(connection_information)
    # If worked, just return the result.
    if sg:
        return sg

    from . import authentication

    try:
        _renew_session()
        sg = create_sg_connection_from_session(
            authentication.get_connection_information()
        )
        if not sg:
            raise AuthenticationError("Authentication failed.")
    except:
        # If the authentication failed, clear the cached credentials. Only do it here instead of befor
        # the renewal otherwise multiple threads who are about to ask for credentials might clear
        # the newer credentials that another thread cached.
        authentication.clear_cached_credentials()
        raise
    return sg


def create_authenticated_sg_connection():
    """
    Creates an authenticated Shotgun connection.
    :param config_data: A dictionary holding the site configuration.
    :returns: A Shotgun instance.
    """
    from . import authentication

    connection_information = authentication.get_connection_information()
    # If no configuration information
    if authentication.is_script_user_authenticated(connection_information):
        # create API
        create_sg_connection_from_script_user(connection_information)
    else:
        return _create_or_renew_sg_connection_from_session(connection_information)
