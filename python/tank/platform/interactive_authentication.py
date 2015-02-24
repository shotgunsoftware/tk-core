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

from getpass import getpass
import logging
import threading

from tank.errors import TankAuthenticationError, TankAuthenticationDisabled
from tank.util import authentication
from tank.util.login import get_login_name
from tank.util import shotgun

# Configure logging
logger = logging.getLogger("sgtk.interactive_authentication")
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())


def _get_session_token(hostname, login, password, http_proxy):
    """
    Retrieves a session token for the given credentials.
    :param hostname: The host to connect to.
    :param login: The user to get a session for.
    :param password: Password for the user.
    :param http_proxy: Proxy to use. Can be None.
    :returns: If the credentials were valid, returns a session token, otherwise returns None.
    """
    try:
        return authentication.generate_session_token(hostname, login, password, http_proxy)
    except TankAuthenticationError:
        print "Authentication failed."
        return None


def _get_keyboard_input(label, default_value=""):
    """
    Queries for keyboard input.
    :param label: The name of the input we require.
    :param default_value: The value to use if the user has entered no input.
    :returns: The user input or default_value if nothing was entered.
    """
    text = label
    if default_value:
        text += ' [%s]' % default_value
    text += ": "
    user_input = None
    while not user_input:
        user_input = raw_input(text) or default_value
    return user_input


def _get_user_credentials_from_keyboard(hostname, login):
    """
    Reads the user credentials from the keyboard.
    :param hostname: Name of the host we will be logging on.
    :param login: Default value for the login.
    :returns: A tuple of (login, password) strings.
    """
    print "Please enter your login credentials for %s" % hostname
    login = _get_keyboard_input("Login", login)
    password = getpass()
    return login, password


def _get_user_pass_from_keyboard(hostname, login):
    """
    Reads the user password from the keyboard.
    :param hostname: Name of the host we will be logging on.
    :param login: Current user
    :returns: The user's password.
    """
    print "%s, your current session has expired." % login
    print "Please enter your password to renew your session for %s" % hostname
    password = getpass()
    return password


def _do_console_based_login(hostname, default_login, http_proxy):
    """
    Logs to the Shotgun site using username/password combo. Retries if the
    login attempt failed. Everything is done on the command line.
    :param default_hostname: Default value for the hostname.
    :param default_login: Default value for the login.
    :param http_proxy: Proxy to use when connecting.
    :returns: A tuple of (hostname, login, session_token)
    """
    logger.debug("Requesting username and password on the console.")
    while True:
        # Get the credentials from the user
        login, password = _get_user_credentials_from_keyboard(hostname, default_login)
        session_token = _get_session_token(hostname, login, password, http_proxy)
        if session_token:
            return hostname, login, session_token


def _do_ui_based_authentication(hostname, login, http_proxy, dialog_title, session_renewal):
    """
    Pops a dialog that asks for the hostname, login and password of the user. If there is a current
    engine, it will run the code in the main thread.
    :param hostname: Host to display in the dialog.
    :param login: login to display in the dialog.
    :param http_proxy: Proxy server to use when validating credentials. Can be None.
    :returns: A tuple of (hostname, login, session_token)
    """
    from .qt import login_dialog

    from tank.platform import engine

    def _do_ui():
        dlg = login_dialog.LoginDialog(
            dialog_title,
            hostname=hostname,
            login=login,
            session_renewal=session_renewal
        )
        return dlg.result()

    # If there is a current engine, execute from the main thread.
    if engine.current_engine():
        result = engine.current_engine().execute_in_main_thread(_do_ui)
    else:
        # Otherwise just run in the current one.
        result = _do_ui()
    if not result:
        raise TankAuthenticationError("No credentials provided.")
    return result


def _do_ui_based_login(hostname, login, http_proxy):
    """
    Pops a dialog that asks for the hostname, login and password of the user.
    :param hostname: Default value for the hostname.
    :param login: Default value for the login
    :param http_proxy: Proxy server to use when validating credentials. Can be None.
    :returns: A tuple of (hostname, login, session_token)
    """
    logger.debug("Requesting username and password in a dialog.")
    return _do_ui_based_authentication(hostname, login, http_proxy, "Shotgun login", False)


def _do_ui_based_session_renewal(hostname, login, http_proxy):
    """
    Pops a user interface that asks to provide the password for the current user.
    :param hostname: Host to renew a token for.
    :param login: User to renew a token for.
    :param http_proxy: Proxy to use for the request. Can be None.
    :returns: The (session token, login user) tuple.
    """
    logger.debug("Requesting password in a dialog.")
    return _do_ui_based_authentication(hostname, login, http_proxy, "Shotgun login", True)


def _do_console_based_session_renewal(hostname, login, http_proxy):
    """
    Prompts the user for this password to retrieve a new session token and rewews
    the session token.
    :param hostname: Host to renew a token for.
    :param login: User to renew a token for.
    :param http_proxy: Proxy to use for the request. Can be None.
    :returns: The (session token, login user) tuple.
    """
    logger.debug("Requesting password on command line.")
    while True:
        # Get the credentials from the user
        password = _get_user_pass_from_keyboard(hostname, login)
        session_token = _get_session_token(hostname, login, password, http_proxy)
        if session_token:
            return hostname, login, session_token

_authentication_lock = threading.Lock()
_disable_authentication = False


def _do_authentication(credentials_request_functor):
    """
    Common login logic, regardless of how we are actually logging in. It will first try to reuse
    any existing session and if that fails then it will ask for credentials and upon success
    the credentials will be cached.
    :param credentials_request_functor: Functor that gets invoked to retrieve the credentials of
                                        the user.
    """

    global _authentication_lock
    global _disable_authentication
    with _authentication_lock:
        # If we are authenticated, we're done here.
        if authentication.is_authenticated():
            return
        elif _disable_authentication:
            raise TankAuthenticationDisabled()

        config_data = shotgun.get_associated_sg_config_data()

        # We might not have login information, in that case use an empty dictionary.
        login_info = authentication.get_login_info(config_data["host"]) or {}

        # Ask for the credentials
        try:
            logger.debug("Not authenticated, requesting user input.")
            hostname, login, session_token = credentials_request_functor(
                config_data["host"],
                login_info.get("login", get_login_name()),
                config_data.get("http_proxy")
            )
        except TankAuthenticationError:
            _disable_authentication = True
            logger.debug("Authentication cancelled, disabling authentication.")
            raise

        logger.debug("Login successful!")

        # Cache the credentials so subsequent session based logins can reuse the session id.
        authentication.cache_session_data(hostname, login, session_token)


def console_renew_session():
    """
    Prompts the user to enter his password on the command line to retrieve a new session token.
    """
    _do_authentication(_do_console_based_session_renewal)


def ui_renew_session():
    """
    Prompts the user to enter his password in a dialog to retrieve a new session token.
    """
    _do_authentication(_do_console_based_session_renewal)


def ui_authenticate():
    """
    Prompts the user to login via a dialog and caches the session token for future reuse.
    """
    _do_authentication(_do_ui_based_login)


def console_authenticate():
    """
    Prompts the user to login on the command line and caches the session token for future reuse.
    """
    _do_authentication(_do_console_based_login)


def console_logout():
    """
    Logs out of the currently cached session and prints whether it worked or not.
    """
    if authentication.logout():
        print "Succesfully logged out of", shotgun.get_associated_sg_base_url()
    else:
        print "Not logged in."
