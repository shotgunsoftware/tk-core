# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.


import sys

from tank_test.tank_test_base import *
from mock import patch
import tank_vendor
from tank_vendor.shotgun_authentication import user_impl, interactive_authentication, login_dialog, invoker


@skip_if_pyside_missing
class InteractiveTests(TankTestBase):

    def setUp(self, *args, **kwargs):
        """
        Adds Qt modules to tank.platform.qt and initializes QApplication
        """
        from PySide import QtGui
        # Only configure qApp once, it's a singleton.
        if QtGui.qApp is None:
            self._app = QtGui.QApplication(sys.argv)
        super(InteractiveTests, self).setUp()

    def test_site_and_user_disabled_on_session_renewal(self):
        """
        Make sure that the site and user fields are disabled when doing session renewal
        """
        ld = login_dialog.LoginDialog(is_session_renewal=True)
        self.assertTrue(ld.ui.site.isReadOnly())
        self.assertTrue(ld.ui.login.isReadOnly())

    def _test_login(self, console):
        self._print_message(
            "We're about to test authentication. Simply enter valid credentials.",
            console
        )
        interactive_authentication.authenticate(
            "https://.shotgunstudio.com",
            "",
            "",
            fixed_host=False
        )
        self._print_message(
            "Test successful",
            console
        )

    @interactive
    def test_login_ui(self):
        """
        Pops the ui and lets the user authenticate.
        :param cache_session_data_mock: Mock for the tank.util.session_cache.cache_session_data
        """
        self._test_login(console=False)

    @patch("tank_vendor.shotgun_authentication.interactive_authentication._get_qt_state")
    @interactive
    def test_login_console(self, _get_qt_state_mock):
        """
        Pops the ui and lets the user authenticate.
        :param cache_session_data_mock: Mock for the tank.util.session_cache.cache_session_data
        """
        _get_qt_state_mock.return_value = None, None, None
        self._test_login(console=True)

    def _print_message(self, text, test_console):
        if test_console:
            print
            print "=" * len(text)
            print text
            print "=" * len(text)
        else:
            from PySide import QtGui
            mb = QtGui.QMessageBox()
            mb.setText(text)
            mb.exec_()

    def _test_session_renewal(self, test_console):
        """
        First asks for the complete host and user information.
        Then prompts for password renewal with that information filled in.
        :param test_console: True is testing console prompt, False is we are testing ui prompt.
        """
        self._print_message(
            "We're about to test session renewal. We'll first prompt you for your "
            "credentials and then we'll fake a session that is expired.\nYou will then have to "
            "re-enter your password.", test_console
        )
        # Get the basic user credentials.
        host, login, session_token = interactive_authentication.authenticate(
            "https://enter_your_host_name_here.shotgunstudio.com",
            "enter_your_username_here",
            "",
            fixed_host=False
        )
        sg_user = user_impl.SessionUser(
            host=host, login=login, session_token=session_token, http_proxy=None
        )
        self._print_message("We're about to fake an expired session. Hang tight!", test_console)
        # Test the session renewal code.
        tank_vendor.shotgun_authentication.interactive_authentication.renew_session(
            sg_user
        )
        self._print_message("Test successful", test_console)

    @interactive
    def test_session_renewal_ui(self):
        self._test_session_renewal(test_console=False)

    @patch("tank_vendor.shotgun_authentication.interactive_authentication._get_qt_state")
    @interactive
    def test_session_renewal_console(self,_get_qt_state_mock):
        # Doing this forces the prompting code to use the console.
        _get_qt_state_mock.return_value = None, None, None
        self._test_session_renewal(test_console=True)

    @skip_if_pyside_missing
    def test_invoker_rethrows_exception(self):
        """
        Makes sure that the invoker will carry the exception back to the calling thread.
        This test is a bit convoluted but it's written in a way to make sure that the test fails
        in the main thread.

        From the background thread, we will create an invoker and use it to invoke the thrower
        method in the main thread. This thrower method will throw a FromMainThreadException.
        If everything works as planned, the exception will be caught by the invoker and rethrown
        in the background thread. The background thread will then raise an exception and when the 
        main thread calls wait it will assert that the exception that was thrown was coming
        from the thrower function.
        """

        class FromMainThreadException(Exception):
            """
            Exception that will be thrown from the main thead.
            """
            pass

        from PySide import QtCore, QtGui

        # Create a QApplication instance.
        if not QtGui.QApplication.instance():
            QtGui.QApplication(sys.argv)

        def thrower():
            """
            Method that will throw.
            :throws: FromMainThreadException
            """
            if QtGui.QApplication.instance().thread() != QtCore.QThread.currentThread():
                raise Exception("This should have been invoked in the main thread.")
            raise FromMainThreadException()

        class BackgroundThread(QtCore.QThread):
            """
            Thread that will invoke a method that will throw from the invoked thread.
            """

            def __init__(self):
                """
                Constructor.
                """
                QtCore.QThread.__init__(self)
                self._exception = Exception("No exception was caught!")

            def run(self):
                """
                Calls the thrower method using the invoker and catches an exception if one is
                thrown.
                """
                try:
                    invoker_obj = invoker.create()
                    # Make sure we have a QObject derived object and not a regular Python function.
                    if not isinstance(invoker_obj, QtCore.QObject):
                        raise Exception("Invoker is not a QObject")
                    if invoker_obj.thread() != QtGui.QApplication.instance().thread():
                        raise Exception("Invoker should be of the same thread as the QApplication.")
                    if QtCore.QThread.currentThread() != self:
                        raise Exception("Current thread not self.")
                    if QtGui.QApplication.instance().thread == self:
                        raise Exception("QApplication should be in the main thread, not self.")
                    invoker_obj(thrower)
                except Exception, e:
                    self._exception = e
                finally:
                    QtGui.QApplication.instance().exit()

            def wait(self):
                """
                Waits for the thread to complete and rethrows the exception that was caught in the
                thread.
                """
                QtCore.QThread.wait(self)
                if self._exception:
                    raise self._exception

        # Launch a background thread
        bg = BackgroundThread()
        bg.start()
        # process events
        QtGui.QApplication.instance().exec_()

        # Make sure the thread got the exception that was thrown from the main thread.
        with self.assertRaises(FromMainThreadException):
            bg.wait()
