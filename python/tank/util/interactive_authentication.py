# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from tank_vendor.shotgun_authentication import interactive_authentication
from tank_vendor.shotgun_authentication.errors import AuthenticationError, AuthenticationDisabled
from tank.errors import TankAuthenticationError, TankAuthenticationDisabled


def _shotgun_authentication_function_decorator(function):
    def wrapper(*args):
        try:
            return function(*args)
        except AuthenticationError, e:
            raise TankAuthenticationError(str(e))
        except AuthenticationDisabled, e:
            raise TankAuthenticationDisabled(str(e))
    return wrapper


def launch_gui(process_ui):
    from tank.platform import engine
    # If there is a current engine, execute from the main thread.
    if engine.current_engine():
        result = engine.current_engine().execute_in_main_thread(process_ui)
    else:
        # Otherwise just run in the current one.
        result = process_ui()
    return result


@_shotgun_authentication_function_decorator
def ui_renew_session():
    """
    Prompts the user to enter his password in a dialog to retrieve a new session token.
    :param gui_launcher: Function that will launch the gui. The function will be receiving a callable object
                         which will take care of invoking the gui in the right thread. If None, the gui will
                         be launched in the current thread.
    """
    interactive_authentication.ui_renew_session(launch_gui)


@_shotgun_authentication_function_decorator
def ui_authenticate(gui_launcher=None):
    """
    Authenticates the current process. Authentication can be done through script user authentication
    or human user authentication. If doing human user authentication and there is no session cached, a
    dialgo asking for user credentials will appear.
    :param gui_launcher: Function that will launch the gui. The function will be receiving a callable object
                         which will take care of invoking the gui in the right thread. If None, the gui will
                         be launched in the current thread.
    """
    interactive_authentication.ui_renew_session(ui_authenticate)


@_shotgun_authentication_function_decorator
def console_renew_session():
    """
    Prompts the user to enter his password on the command line to retrieve a new session token.
    """
    interactive_authentication.console_renew_session()


@_shotgun_authentication_function_decorator
def console_authenticate():
    """
    Authenticates the current process. Authentication can be done through script user authentication
    or human user authentication. If doing human user authentication and there is no session cached, the
    user credentials will be retrieved from the console.
    """
    interactive_authentication.console_authenticate()


@_shotgun_authentication_function_decorator
def console_logout():
    """
    Logs out of the currently cached session and prints whether it worked or not.
    """
    interactive_authentication.console_logout()
