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
Unit tests for interactive authentication.
"""

from __future__ import with_statement, print_function

import contextlib

import sys

from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import (
    ShotgunTestBase,
    skip_if_pyside_missing,
    interactive,
    suppress_generated_code_qt_warnings,
)
from mock import patch
from tank.authentication import (
    console_authentication,
    ConsoleLoginNotSupportedError,
    ConsoleLoginWithSSONotSupportedError,
    interactive_authentication,
    invoker,
    user_impl,
)

import tank


@skip_if_pyside_missing
class InteractiveTests(ShotgunTestBase):
    """
    Tests ui and console based authentication.
    """

    def setUp(self, *args, **kwargs):
        """
        Adds Qt modules to tank.platform.qt and initializes QApplication
        """
        from tank.authentication.ui.qt_abstraction import QtGui

        # See if a QApplication instance exists, and if not create one.  Use the
        # QApplication.instance() method, since qApp can contain a non-None
        # value even if no QApplication has been constructed on PySide2.
        if not QtGui.QApplication.instance():
            self._app = QtGui.QApplication(sys.argv)
        super(InteractiveTests, self).setUp()

    def tearDown(self):
        super(InteractiveTests, self).tearDown()
        from tank.authentication.ui.qt_abstraction import QtGui

        QtGui.QApplication.processEvents()

    @suppress_generated_code_qt_warnings
    def test_site_and_user_disabled_on_session_renewal(self):
        """
        Make sure that the site and user fields are disabled when doing session renewal
        """
        with self._login_dialog(is_session_renewal=True) as ld:
            self.assertTrue(ld.ui.site.lineEdit().isReadOnly())
            self.assertTrue(ld.ui.login.lineEdit().isReadOnly())

    def _prepare_window(self, ld):
        """
        Prepares the dialog so the events get processed and focus is attributed to the right
        widget.
        """
        from tank.authentication.ui.qt_abstraction import QtGui

        ld.show()
        ld.raise_()
        ld.activateWindow()

        QtGui.QApplication.processEvents()

    @contextlib.contextmanager
    def _login_dialog(self, is_session_renewal, **kwargs):
        # Import locally since login_dialog has a dependency on Qt and it might be missing
        from tank.authentication import login_dialog

        class MyLoginDialog(login_dialog.LoginDialog):
            my_result = None

            def done(self, r):
                self.my_result = r
                return super(MyLoginDialog, self).done(r)

        # Patch out the SsoSaml2Toolkit class to avoid threads being created, which cause
        # issues with tests.
        with patch("tank.authentication.login_dialog.SsoSaml2Toolkit"):
            with contextlib.closing(
                MyLoginDialog(is_session_renewal, **kwargs)
            ) as ld:
                try:
                    self._prepare_window(ld)
                    yield ld
                finally:
                    # Hook - disable exit confirmation for the tests
                    ld._confirm_exit = lambda: True

    @suppress_generated_code_qt_warnings
    def test_focus(self):
        """
        Make sure that the site and user fields are disabled when doing session renewal
        """
        with self._login_dialog(is_session_renewal=False) as ld:
            self.assertEqual(ld.ui.site.currentText(), "")

        with self._login_dialog(is_session_renewal=False, login="login") as ld:
            self.assertEqual(ld.ui.site.currentText(), "")

        # Makes sure the focus is set to the password even tough we've only specified the hostname
        # because the current os user name is the default.
        with self._login_dialog(is_session_renewal=False, hostname="host") as ld:
            # window needs to be activated to get focus.
            self.assertTrue(ld.ui.password.hasFocus())

        with self._login_dialog(
            is_session_renewal=False, hostname="host", login="login"
        ) as ld:
            self.assertTrue(ld.ui.password.hasFocus())

    def _test_login(self, console):
        self._print_message(
            "We're about to test authentication. Simply enter valid credentials.",
            console,
        )
        interactive_authentication.authenticate(
            "https://.shotgunstudio.com", "", "", fixed_host=False
        )
        self._print_message("Test successful", console)

    @interactive
    @suppress_generated_code_qt_warnings
    def test_login_ui(self):
        """
        Pops the ui and lets the user authenticate.
        :param cache_session_data_mock: Mock for the tank.util.session_cache.cache_session_data
        """
        self._test_login(console=False)

    @patch("tank.authentication.interactive_authentication._get_ui_state")
    @interactive
    @suppress_generated_code_qt_warnings
    def test_login_console(self, _get_ui_state_mock):
        """
        Pops the ui and lets the user authenticate.
        :param cache_session_data_mock: Mock for the tank.util.session_cache.cache_session_data
        """
        _get_ui_state_mock.return_value = False
        self._test_login(console=True)

    def _print_message(self, text, test_console):
        if test_console:
            print()
            print("=" * len(text))
            print(text)
            print("=" * len(text))
        else:
            from tank.authentication.ui.qt_abstraction import QtGui

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
            "re-enter your password.",
            test_console,
        )
        # Get the basic user credentials.
        (
            host,
            login,
            session_token,
            session_metadata,
        ) = interactive_authentication.authenticate(
            "https://enter_your_host_name_here.shotgunstudio.com",
            "enter_your_username_here",
            "",
            fixed_host=False,
        )
        sg_user = user_impl.SessionUser(
            host=host, login=login, session_token=session_token, http_proxy=None
        )
        self._print_message(
            "We're about to fake an expired session. Hang tight!", test_console
        )
        # Test the session renewal code.
        tank.authentication.interactive_authentication.renew_session(sg_user)
        self._print_message("Test successful", test_console)

    @interactive
    @suppress_generated_code_qt_warnings
    def test_session_renewal_ui(self):
        """
        Interactively test session renewal.
        """
        self._test_session_renewal(test_console=False)

    @patch("tank.authentication.interactive_authentication._get_ui_state")
    @interactive
    @suppress_generated_code_qt_warnings
    def test_session_renewal_console(self, _get_ui_state_mock):
        """
        Interactively test for session renewal with the GUI.
        """
        # Doing this forces the prompting code to use the console.
        _get_ui_state_mock.return_value = False
        self._test_session_renewal(test_console=True)

    @suppress_generated_code_qt_warnings
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

        from tank.authentication.ui.qt_abstraction import QtCore, QtGui

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
                        raise Exception(
                            "Invoker should be of the same thread as the QApplication."
                        )
                    if QtCore.QThread.currentThread() != self:
                        raise Exception("Current thread not self.")
                    if QtGui.QApplication.instance().thread == self:
                        raise Exception(
                            "QApplication should be in the main thread, not self."
                        )
                    invoker_obj(thrower)
                except Exception as e:
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

    @patch(
        "tank.authentication.console_authentication.input",
        side_effect=[
            "  https://test.shotgunstudio.com ",
            "  username   ",
            " 2fa code ",
        ],
    )
    @patch(
        "tank.authentication.console_authentication.ConsoleLoginHandler._get_password",
        return_value=" password ",
    )
    @suppress_generated_code_qt_warnings
    def test_console_auth_with_whitespace(self, *mocks):
        """
        Makes sure that authentication strips whitespaces on the command line.
        """
        handler = console_authentication.ConsoleLoginHandler(fixed_host=False)
        self.assertEqual(
            handler._get_sg_url(None, None),
            "https://test.shotgunstudio.com",
        )
        self.assertEqual(
            handler._get_user_credentials(None, None, None),
            (None, "username", " password "),
        )
        self.assertEqual(handler._get_2fa_code(), "2fa code")

    @patch(
        "tank.authentication.console_authentication.input",
        side_effect=["  https://test-sso.shotgunstudio.com "],
    )
    @patch(
        "tank.authentication.console_authentication.is_sso_enabled_on_site",
        return_value=True,
    )
    @patch(
        "tank.authentication.console_authentication.is_unified_login_flow2_enabled_on_site",
        return_value=False,
    )
    @suppress_generated_code_qt_warnings
    def test_sso_enabled_site_with_legacy_exception_name(self, *mocks):
        """
        Ensure that an exception is thrown should we attempt console authentication
        on an SSO-enabled site. We use the legacy exception-name to ensure backward
        compatibility with older code.
        """
        handler = console_authentication.ConsoleLoginHandler(fixed_host=False)
        with self.assertRaises(ConsoleLoginWithSSONotSupportedError):
            handler.authenticate(None, None, None)

    @patch(
        "tank.authentication.console_authentication.input",
        side_effect=["  https://test-sso.shotgunstudio.com "],
    )
    @patch(
        "tank.authentication.console_authentication.is_sso_enabled_on_site",
        return_value=True,
    )
    @patch(
        "tank.authentication.console_authentication.is_unified_login_flow2_enabled_on_site",
        return_value=False,
    )
    @suppress_generated_code_qt_warnings
    def test_sso_enabled_site(self, *mocks):
        """
        Ensure that an exception is thrown should we attempt console authentication
        on an SSO-enabled site.
        """
        handler = console_authentication.ConsoleLoginHandler(fixed_host=False)
        with self.assertRaises(ConsoleLoginNotSupportedError):
            handler.authenticate(None, None, None)

    @suppress_generated_code_qt_warnings
    def test_ui_auth_with_whitespace(self):
        """
        Makes sure that the ui strips out whitespaces.
        """
        # Import locally since login_dialog has a dependency on Qt and it might be missing
        from tank.authentication.ui.qt_abstraction import QtGui

        with self._login_dialog(is_session_renewal=False) as ld:
            # For each widget in the ui, make sure that the text is properly cleaned
            # up when widget loses focus.
            for widget in [ld.ui._2fa_code, ld.ui.backup_code, ld.ui.site, ld.ui.login]:
                # Give the focus, so that editingFinished can be triggered.
                widget.setFocus()
                if isinstance(widget, QtGui.QLineEdit):
                    widget.setText(" text ")
                else:
                    widget.lineEdit().setText(" text ")
                # Give the focus to another widget, which should trigger the editingFinished
                # signal and the dialog will clear the extra spaces in it.
                ld.ui.password.setFocus()
                if isinstance(widget, QtGui.QLineEdit):
                    # Text should be cleaned of spaces now.
                    self.assertEqual(widget.text(), "text")
                else:
                    self.assertEqual(widget.currentText(), "text")

    @suppress_generated_code_qt_warnings
    def test_login_dialog_exit_confirmation(self):
        """
        Make sure that the site and user fields are disabled when doing session renewal
        """

        from tank.authentication.ui.qt_abstraction import QtGui, QtCore

        # Test window close event
        with self._login_dialog(False) as ld:
            # First, simulate user clicks on the No button
            ld.confirm_box.exec_ = lambda: QtGui.QMessageBox.StandardButton.No

            self.assertEqual(ld.close(), False)
            self.assertIsNone(ld.my_result)
            self.assertEqual(ld.isVisible(), True)

            # Then, simulate user clicks on the Yes button
            ld.confirm_box.exec_ = lambda: QtGui.QMessageBox.StandardButton.Yes

            self.assertEqual(ld.close(), True)
            self.assertEqual(ld.my_result, QtGui.QDialog.Rejected)
            self.assertEqual(ld.isVisible(), False)

        # Test escape key event
        with self._login_dialog(False) as ld:
            event = QtGui.QKeyEvent(
                QtGui.QKeyEvent.KeyPress,
                QtCore.Qt.Key_Escape,
                QtCore.Qt.KeyboardModifiers(),
            )

            # First, simulate user clicks on the No button
            ld.confirm_box.exec_ = lambda: QtGui.QMessageBox.StandardButton.No

            self.assertIsNone(ld.keyPressEvent(event))
            self.assertIsNone(ld.my_result)
            self.assertEqual(ld.isVisible(), True)

            # Then, simulate user clicks on the Yes button
            ld.confirm_box.exec_ = lambda: QtGui.QMessageBox.StandardButton.Yes

            # Test Escape key
            self.assertIsNone(ld.keyPressEvent(event))
            self.assertEqual(ld.my_result, QtGui.QDialog.Rejected)
            self.assertEqual(ld.isVisible(), False)

    @suppress_generated_code_qt_warnings
    @patch(
        "tank.authentication.sso_saml2.utils._get_site_infos",
        return_value={
            "unified_login_flow_enabled2": True,
            "user_authentication_method": "default",
        },
    )
    @patch("tank.authentication.login_dialog.ULF2_AuthTask.start")
    @patch(
        "tank.authentication.login_dialog._is_running_in_desktop",
        return_value=True,
    )
    @patch(
        "tank.authentication.unified_login_flow2.authentication.process",
        return_value=(
            "https://host.shotgunstudio.com",
            "user_login",
            "session_token",
            None,
        ),
    )
    def test_login_dialog_unified_login_flow2(self, *unused_mocks):
        with self._login_dialog(
            True,
            hostname="https://host.shotgunstudio.com",
        ) as ld:
            self.assertTrue(ld.menu_action_legacy.isVisible())
            self.assertFalse(ld.menu_action_ulf.isVisible())
            self.assertTrue(ld.menu_action_ulf2.isVisible())

            # Ensure current method set is ufl2
            self.assertFalse(ld._use_web)
            self.assertTrue(ld._use_local_browser)

            # Trigger login credentials
            ld._menu_activated_action_login_creds()

            # Ensure current method set is lcegacy credentials
            self.assertFalse(ld._use_web)
            self.assertFalse(ld._use_local_browser)

            # Trigger ULF2 again
            ld._menu_activated_action_ulf2()

            # Trigger Sign-In
            ld._ok_pressed()

            self.assertIsNotNone(ld._ulf2_task, "ULF2 Auth has started")

            # check that UI displays the UFL2 pending screen
            self.assertEqual(ld.ui.stackedWidget.currentWidget(), ld.ui.ulf2_page)

            # Cancel the request and go back to the login screen
            ld._ulf2_back_pressed()

            # check that UI displays the login credentials
            self.assertEqual(ld.ui.stackedWidget.currentWidget(), ld.ui.login_page)
            self.assertIsNone(ld._ulf2_task)

            # Trigger Sign-In
            ld._ok_pressed()
            self.assertIsNotNone(ld._ulf2_task, "ULF2 Auth has started")

            # Simulate ULF2 Thread run
            ld._ulf2_task.run()
            ld._ulf2_task_finished()

            # check that UI displays the login credentials
            self.assertEqual(ld.ui.stackedWidget.currentWidget(), ld.ui.login_page)

            self.assertEqual(
                ld._ulf2_task.session_info,
                (
                    "https://host.shotgunstudio.com",
                    "user_login",
                    "session_token",
                    None,
                ),
            )
