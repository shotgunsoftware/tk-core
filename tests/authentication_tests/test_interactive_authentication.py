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
    mock,
    suppress_generated_code_qt_warnings,
)
from tank.authentication import (
    console_authentication,
    ConsoleLoginNotSupportedError,
    ConsoleLoginWithSSONotSupportedError,
    constants as auth_constants,
    errors,
    interactive_authentication,
    invoker,
    user_impl,
)

import tank
import tank_vendor.shotgun_api3


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
    def _login_dialog(self, is_session_renewal=False, **kwargs):
        # Import locally since login_dialog has a dependency on Qt and it might be missing
        from tank.authentication import login_dialog

        class MyLoginDialog(login_dialog.LoginDialog):
            my_result = None

            def done(self, r):
                self.my_result = r
                return super(MyLoginDialog, self).done(r)

        # Patch out the SsoSaml2Toolkit class to avoid threads being created, which cause
        # issues with tests.
        with mock.patch("tank.authentication.login_dialog.SsoSaml2Toolkit"):
            with contextlib.closing(MyLoginDialog(is_session_renewal, **kwargs)) as ld:
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
        with self._login_dialog() as ld:
            self.assertEqual(ld.ui.site.currentText(), "")

        with self._login_dialog(login="login") as ld:
            self.assertEqual(ld.ui.site.currentText(), "")

        # Makes sure the focus is set to the password even tough we've only specified the hostname
        # because the current os user name is the default.
        with self._login_dialog(hostname="host") as ld:
            # window needs to be activated to get focus.
            self.assertTrue(ld.ui.password.hasFocus())

        with self._login_dialog(
            hostname="host", login="login"
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

    @mock.patch("tank.authentication.interactive_authentication._get_ui_state")
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

    @mock.patch("tank.authentication.interactive_authentication._get_ui_state")
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

    @mock.patch(
        "tank.authentication.console_authentication.input",
        side_effect=[
            "  https://test.shotgunstudio.com ",
            "  username   ",
            " 2fa code ",
        ],
    )
    @mock.patch(
        "tank.authentication.console_authentication.ConsoleLoginHandler._get_password",
        return_value=" password ",
    )
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

    @mock.patch(
        "tank.authentication.site_info._get_site_infos",
        return_value={},
    )
    @mock.patch(
        "tank.authentication.session_cache.generate_session_token",
        side_effect=[
            tank_vendor.shotgun_api3.MissingTwoFactorAuthenticationFault(),
            "my_session_token_39",
        ],
    )
    @mock.patch(
        "tank.authentication.console_authentication.input",
        side_effect=[
            "",  # Select default login
            "2fa code",
        ],
    )
    @mock.patch(
        "tank.authentication.console_authentication.ConsoleLoginHandler._get_password",
        return_value="password",
    )
    def test_console_auth_2fa(self, *mocks):
        handler = console_authentication.ConsoleLoginHandler(fixed_host=True)
        self.assertEqual(
            handler.authenticate("https://test.shotgunstudio.com", "username", None),
            ("https://test.shotgunstudio.com", "username", "my_session_token_39", None),
        )

    @mock.patch(
        "tank.authentication.site_info._get_site_infos",
        return_value={
            "app_session_launcher_enabled": False,
        },
    )
    @mock.patch(
        "tank.authentication.console_authentication.ConsoleRenewSessionHandler._get_password",
        side_effect=[
            "password",
            EOFError(),  # Simulate an error
        ],
    )
    @mock.patch(
        "tank.authentication.session_cache.generate_session_token",
        return_value="my_session_token_97",
    )
    def test_console_renewal(self, *mocks):
        handler = console_authentication.ConsoleRenewSessionHandler()
        self.assertEqual(
            handler.authenticate("https://test.shotgunstudio.com", "username", None),
            ("https://test.shotgunstudio.com", "username", "my_session_token_97", None),
        )

        # Then repeat the operation with an exception for password
        with self.assertRaises(errors.AuthenticationCancelled):
            handler.authenticate("https://test.shotgunstudio.com", "username", None)

    @mock.patch(
        "tank.authentication.console_authentication.input",
        side_effect=["  https://test-sso.shotgunstudio.com "],
    )
    @mock.patch(
        "tank.authentication.site_info._get_site_infos",
        return_value={
            "user_authentication_method": "saml2",
        },
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

    def test_sso_enabled_site(self, *mocks):
        """
        Ensure that an exception is thrown should we attempt console authentication
        on an SSO-enabled site.
        """
        handler = console_authentication.ConsoleLoginHandler(fixed_host=True)
        for option in ["oxygen", "saml2"]:
            with mock.patch(
                "tank.authentication.site_info._get_site_infos",
                return_value={
                    "user_authentication_method": option,
                },
            ):
                with self.assertRaises(ConsoleLoginNotSupportedError):
                    handler.authenticate(
                        "https://test-sso.shotgunstudio.com", None, None
                    )

    @suppress_generated_code_qt_warnings
    def test_ui_auth_with_whitespace(self):
        """
        Makes sure that the ui strips out whitespaces.
        """
        # Import locally since login_dialog has a dependency on Qt and it might be missing
        from tank.authentication.ui.qt_abstraction import QtGui

        with self._login_dialog() as ld:
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
    @mock.patch(
        "tank.authentication.site_info._get_site_infos",
        return_value={},
    )
    @mock.patch(
        "tank.authentication.login_dialog._is_running_in_desktop",
        return_value=True,
    )
    def test_ui_error_management(self, *unused_mocks):
        # Empty of invalid site
        with self._login_dialog() as ld:
            ld.ERROR_MSG_FORMAT = "[Error135]%s"

            # Trigger Sign-In
            ld._ok_pressed()

            self.assertEqual(
                ld.ui.message.text(),
                "[Error135]Please enter the address of the site to connect to.",
            )

        # Empty login
        with self._login_dialog(
            hostname="https://host.shotgunstudio.com",
        ) as ld:
            ld.ERROR_MSG_FORMAT = "[Error357]%s"
            ld._get_current_user = lambda: ""

            # Trigger Sign-In
            ld._ok_pressed()

            self.assertEqual(
                ld.ui.message.text(),
                "[Error357]Please enter your login name.",
            )

        # Empty password
        with self._login_dialog(
            hostname="https://host.shotgunstudio.com", login="john"
        ) as ld:
            ld.ERROR_MSG_FORMAT = "[Error579]%s"

            # Trigger Sign-In
            ld._ok_pressed()

            self.assertEqual(
                ld.ui.message.text(),
                "[Error579]Please enter your password.",
            )

        # Link Activated - browser error - mainly for coverage
        with mock.patch(
            "tank.authentication.login_dialog.QtGui.QDesktopServices.openUrl",
            return_value=False,
        ), self._login_dialog(
            hostname="https://host.shotgunstudio.com",
        ) as ld:
            ld.ERROR_MSG_FORMAT = "[Error246]%s"

            # Trigger forgot password
            ld._link_activated()

            self.assertEqual(
                ld.ui.message.text(),
                "[Error246]Can't open 'https://host.shotgunstudio.com/user/forgot_password'.",
            )

    @suppress_generated_code_qt_warnings
    def test_login_dialog_exit_confirmation(self):
        """
        Make sure that the site and user fields are disabled when doing session renewal
        """

        from tank.authentication.ui.qt_abstraction import QtGui, QtCore

        # Test window close event
        with self._login_dialog() as ld:
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
        with mock.patch(
            "tank.authentication.login_dialog.ULF2_AuthTask.start",
            return_value=False,
        ), self._login_dialog() as ld:
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

            # Initialize the ULF2 process - mostly for coverage
            ld._asl_process("https://host.shotgunstudio.com")

            # Test Escape key
            self.assertIsNone(ld.keyPressEvent(event))
            self.assertEqual(ld.my_result, QtGui.QDialog.Rejected)
            self.assertEqual(ld.isVisible(), False)

    @suppress_generated_code_qt_warnings
    @mock.patch(
        "tank.authentication.login_dialog._is_running_in_desktop",
        return_value=True,
    )
    @mock.patch(
        "tank.authentication.web_login_support.get_shotgun_authenticator_support_web_login",
        return_value=True,
    )
    @mock.patch(
        "tank.authentication.session_cache.get_preferred_method",
        return_value=None,
    )
    def test_login_dialog_method_selected(self, *unused_mocks):
        # First - basic
        with mock.patch(
            "tank.authentication.site_info._get_site_infos",
            return_value={},
        ), self._login_dialog(
            is_session_renewal=True,
            hostname="https://host.shotgunstudio.com",
        ) as ld:
            # Ensure current method set is lcegacy credentials
            self.assertEqual(ld.method_selected, auth_constants.METHOD_BASIC)

        # Then Web login
        with mock.patch(
            "tank.authentication.site_info._get_site_infos",
            return_value={
                "user_authentication_method": "oxygen",
                "unified_login_flow_enabled": True,
            },
        ), self._login_dialog(
            is_session_renewal=True, hostname="https://host.shotgunstudio.com",
        ) as ld:
            # Ensure current method set is web login
            self.assertEqual(ld.method_selected, auth_constants.METHOD_WEB_LOGIN)

        # Then Web login but env override
        with mock.patch.dict(
            "os.environ", {"SGTK_FORCE_STANDARD_LOGIN_DIALOG": "1"}
        ), mock.patch(
            "tank.authentication.site_info._get_site_infos",
            return_value={
                "user_authentication_method": "oxygen",
                "unified_login_flow_enabled": True,
            },
        ), self._login_dialog(
            is_session_renewal=True, hostname="https://host.shotgunstudio.com",
        ) as ld:
            # Ensure current method set is web login
            self.assertEqual(ld.method_selected, auth_constants.METHOD_BASIC)

    @suppress_generated_code_qt_warnings
    @mock.patch(
        "tank.authentication.site_info._get_site_infos",
        return_value={},
    )
    @mock.patch(
        "tank.authentication.session_cache.get_recent_users",
        return_value=["john"],
    )
    @mock.patch(
        "tank.authentication.session_cache.generate_session_token",
        side_effect=[
            tank_vendor.shotgun_api3.MissingTwoFactorAuthenticationFault(),
            tank_vendor.shotgun_api3.MissingTwoFactorAuthenticationFault(),
            "my_session_token_39",
        ],
    )
    def test_ui_auth_2fa(self, *mocks):
        from tank.authentication.ui.qt_abstraction import QtGui

        with mock.patch.object(
            QtGui.QDialog,
            "exec_",
            return_value=QtGui.QDialog.Accepted,
        ), self._login_dialog(
            is_session_renewal=True,
            hostname="https://host.shotgunstudio.com",
        ) as ld:
            # Fill password field
            ld.ui.password.setText("password")

            # Trigger Sign-In
            ld._ok_pressed()

            # check that UI displays the 2FA screen
            self.assertEqual(
                ld.ui.stackedWidget.currentWidget(),
                ld.ui._2fa_page,
            )

            ld._use_app_pressed()  # Only for coverage since already there

            ld.ERROR_MSG_FORMAT = "[Error688]%s"

            # Hit the button without filling the 2fa field
            ld._verify_2fa_pressed()

            self.assertEqual(
                ld.ui.invalid_code.text(),
                "[Error688]Please enter your code.",
            )

            # Fill the 2fa field
            ld.ui._2fa_code.setText("123456")

            ld._verify_2fa_pressed()
            # This is supposed to fails (see patch)

            # check that UI displays the 2FA screen
            self.assertEqual(
                ld.ui.stackedWidget.currentWidget(),
                ld.ui._2fa_page,
            )

            # Select backup code method
            ld._use_backup_pressed()

            # Fill the backup code field
            ld.ui.backup_code.setText("1a2b3c4d5e6f7g8h9i0j")

            ld._verify_backup_pressed()

            # This is supposed to work
            self.assertEqual(
                QtGui.QDialog.result(ld),
                QtGui.QDialog.Accepted,
            )

            self.assertEqual(
                ld.result(),
                (
                    "https://host.shotgunstudio.com",
                    "john",
                    "my_session_token_39",
                    None,
                ),
            )

    @suppress_generated_code_qt_warnings
    @mock.patch(
        "tank.authentication.login_dialog._is_running_in_desktop",
        return_value=True,
    )
    @mock.patch(
        "tank.authentication.login_dialog.get_shotgun_authenticator_support_web_login",
        return_value=True,
    )
    @mock.patch(
        "tank.authentication.site_info._get_site_infos",
        return_value={
            "user_authentication_method": "oxygen",
            "unified_login_flow_enabled": True,
        },
    )
    @mock.patch(
        "tank.authentication.session_cache.get_recent_users",
        return_value=["john"],
    )
    @mock.patch(
        "tank.authentication.sso_saml2.sso_saml2.SsoSaml2.login_attempt",
        return_value=False,
    )
    def test_ui_auth_web_login(self, *mocks):
        """
        Not doing much at the moment. Just try to increase code coverage
        """

        from tank.authentication.ui.qt_abstraction import QtGui

        with mock.patch.object(
            QtGui.QDialog,
            "exec_",
            return_value=QtGui.QDialog.Accepted,
        ), self._login_dialog(
            is_session_renewal=True,
            hostname="https://host.shotgunstudio.com",
        ) as ld:
            # Ensure current method set is web login
            self.assertEqual(ld.method_selected, auth_constants.METHOD_WEB_LOGIN)

            # Trigger Sign-In
            ld._ok_pressed()

            # tweak
            ld._session_metadata = "fake"

            self.assertIsNone(ld.result())

    @suppress_generated_code_qt_warnings
    def test_web_login_not_supported(self):
        # Ensure that Web Login methos is not selected in UI when config is set
        # to web login but client does not support it

        with mock.patch(
            "tank.authentication.login_dialog.ULF2_AuthTask.start"
        ), mock.patch(
            "tank.authentication.login_dialog._is_running_in_desktop",
            return_value=True,
        ), mock.patch(
            "tank.authentication.login_dialog.get_shotgun_authenticator_support_web_login",
            return_value=False,
        ), mock.patch(
            "tank.authentication.session_cache.get_preferred_method",
            return_value=auth_constants.METHOD_WEB_LOGIN,
        ), mock.patch(
            "tank.authentication.site_info._get_site_infos",
            return_value={
                "app_session_launcher_enabled": True,
            },
        ), self._login_dialog(
            is_session_renewal=True,
            hostname="https://host.shotgunstudio.com",
        ) as ld:
            self.assertEqual(ld.method_selected, auth_constants.METHOD_BASIC)

    @suppress_generated_code_qt_warnings
    def test_login_dialog_method_selected_default(self):
        with mock.patch(
            "tank.authentication.login_dialog.ULF2_AuthTask.start"
        ), mock.patch(
            "tank.authentication.login_dialog._is_running_in_desktop",
            return_value=True,
        ), mock.patch(
            "tank.authentication.login_dialog.get_shotgun_authenticator_support_web_login",
            return_value=True,
        ), mock.patch(
            "tank.authentication.session_cache.get_preferred_method",
            return_value=None,
        ), mock.patch(
            "tank.authentication.site_info._get_site_infos",
            return_value={
                "user_authentication_method": "oxygen",
                "unified_login_flow_enabled": True,
                "app_session_launcher_enabled": True,
            },
        ):
            with self._login_dialog(
                hostname="https://host.shotgunstudio.com",
            ) as ld:
                self.assertEqual(ld.method_selected, auth_constants.METHOD_WEB_LOGIN)

            with mock.patch.dict("os.environ", {
                "SGTK_DEFAULT_AUTH_METHOD": "app_session_launcher",
            }), self._login_dialog(
                hostname="https://host.shotgunstudio.com",
            ) as ld:
                self.assertEqual(ld.method_selected, auth_constants.METHOD_ASL)

            with mock.patch(
                "tank.authentication.login_dialog._is_running_in_desktop",
                return_value=False,
            ), mock.patch(
                "tank.authentication.login_dialog.get_shotgun_authenticator_support_web_login",
                return_value=False,
            ), mock.patch.dict("os.environ", {
                "SGTK_DEFAULT_AUTH_METHOD": "credentials",
            }), self._login_dialog(
                hostname="https://host.shotgunstudio.com",
            ) as ld:
                self.assertEqual(ld.method_selected, auth_constants.METHOD_BASIC)

            with mock.patch.dict("os.environ", {
                "SGTK_DEFAULT_AUTH_METHOD": "test_me", # Invalid value
            }), self._login_dialog(
                hostname="https://host.shotgunstudio.com",
            ) as ld:
                self.assertEqual(ld.method_selected, auth_constants.METHOD_WEB_LOGIN)

            with mock.patch(
                "tank.authentication.session_cache.get_preferred_method",
                return_value=auth_constants.METHOD_WEB_LOGIN,
            ), mock.patch.dict("os.environ", {
                "SGTK_DEFAULT_AUTH_METHOD": "app_session_launcher",
            }), self._login_dialog(
                hostname="https://host.shotgunstudio.com",
            ) as ld:
                self.assertEqual(ld.method_selected, auth_constants.METHOD_WEB_LOGIN)

            # Test valid SGTK_DEFAULT_AUTH_METHOD values but support for these
            # are disabled

            # credentials but web login is available
            with mock.patch.dict("os.environ", {
                "SGTK_DEFAULT_AUTH_METHOD": "credentials",
            }), self._login_dialog(
                hostname="https://host.shotgunstudio.com",
            ) as ld:
                self.assertEqual(ld.method_selected, auth_constants.METHOD_WEB_LOGIN)

            # qt_web_login but method not available
            with mock.patch.dict("os.environ", {
                "SGTK_DEFAULT_AUTH_METHOD": "qt_web_login",
            }), mock.patch(
                "tank.authentication.login_dialog._is_running_in_desktop",
                return_value=False,
            ), mock.patch(
                "tank.authentication.login_dialog.get_shotgun_authenticator_support_web_login",
                return_value=False,
            ), self._login_dialog(
                hostname="https://host.shotgunstudio.com",
            ) as ld:
                self.assertEqual(ld.method_selected, auth_constants.METHOD_BASIC)

            # app_session_launcher but method ULF2 not available
            with mock.patch.dict("os.environ", {
                "SGTK_DEFAULT_AUTH_METHOD": "app_session_launcher",
            }), mock.patch(
                "tank.authentication.site_info._get_site_infos",
                return_value={
                    "user_authentication_method": "oxygen",
                    "unified_login_flow_enabled": True,
                    "app_session_launcher_enabled": False,
                },
            ), self._login_dialog(
                hostname="https://host.shotgunstudio.com",
            ) as ld:
                self.assertEqual(ld.method_selected, auth_constants.METHOD_WEB_LOGIN)

    @suppress_generated_code_qt_warnings
    def test_login_dialog_method_selected_session_cache(self):
        with mock.patch(
            "tank.authentication.login_dialog.ULF2_AuthTask.start"
        ), mock.patch(
                "tank.authentication.login_dialog._is_running_in_desktop",
                return_value=True,
        ), mock.patch(
            "tank.authentication.login_dialog.get_shotgun_authenticator_support_web_login",
            return_value=True,
        ), mock.patch(
            "tank.authentication.site_info._get_site_infos",
            return_value={
                "user_authentication_method": "oxygen",
                "unified_login_flow_enabled": True,
                "app_session_launcher_enabled": True,
            },
        ):
            # credentials but web login is available
            with mock.patch(
                "tank.authentication.session_cache.get_preferred_method",
                return_value=auth_constants.METHOD_BASIC,
            ), mock.patch.dict("os.environ", {
                "SGTK_DEFAULT_AUTH_METHOD": "app_session_launcher",
            }), self._login_dialog(
                hostname="https://host.shotgunstudio.com",
            ) as ld:
                self.assertEqual(ld.method_selected, auth_constants.METHOD_ULF2)

            # qt_web_login but method is not available
            with mock.patch(
                "tank.authentication.login_dialog._is_running_in_desktop",
                return_value=False,
            ), mock.patch(
                "tank.authentication.login_dialog.get_shotgun_authenticator_support_web_login",
                return_value=False,
            ), mock.patch(
                "tank.authentication.session_cache.get_preferred_method",
                return_value=auth_constants.METHOD_WEB_LOGIN,
            ), mock.patch.dict("os.environ", {
                "SGTK_DEFAULT_AUTH_METHOD": "app_session_launcher",
            }), self._login_dialog(
                hostname="https://host.shotgunstudio.com",
            ) as ld:
                self.assertEqual(ld.method_selected, auth_constants.METHOD_ULF2)

    @suppress_generated_code_qt_warnings
    @mock.patch("tank.authentication.login_dialog.ULF2_AuthTask.start")
    @mock.patch(
        "tank.authentication.login_dialog._is_running_in_desktop",
        return_value=True,
    )
    @mock.patch(
        "tank.authentication.login_dialog.get_shotgun_authenticator_support_web_login",
        return_value=True,
    )
    @mock.patch(
        "tank.authentication.app_session_launcher.process",
        return_value=(
            "https://host.shotgunstudio.com",
            "user_login",
            "session_token",
            None,
        ),
    )
    @mock.patch(
        "tank.authentication.session_cache.get_preferred_method",
        return_value=None,
    )
    @mock.patch(  # Only for coverage purposes
        "tank.authentication.session_cache.get_recent_users",
        return_value=["john", "bob"],
    )
    def test_login_dialog_app_session_launcher(self, *unused_mocks):
        from tank.authentication.ui.qt_abstraction import QtGui

        # First basic and ULF2 methods
        with mock.patch(
            "tank.authentication.site_info._get_site_infos",
            return_value={
                "app_session_launcher_enabled": True,
            },
        ), mock.patch.object(
            QtGui.QDialog,
            "exec_",
            return_value=QtGui.QDialog.Accepted,
        ), self._login_dialog(
            is_session_renewal=True,
            hostname="http://host.shotgunstudio.com",  # HTTP only for code coverage
            fixed_host=True,  # Only for coverage purposes
        ) as ld:
            ld._query_task.run()  # Call outside thread for code coverage

            self.assertTrue(ld.menu_action_legacy.isVisible())
            self.assertFalse(ld.menu_action_ulf.isVisible())
            self.assertTrue(ld.menu_action_asl.isVisible())

            # Ensure current method set is legacy credentials
            self.assertEqual(ld.method_selected, auth_constants.METHOD_BASIC)

            # Trigger ULF2 again
            ld._menu_activated_action_asl()

            # Ensure current method set is ufl2
            self.assertEqual(ld.method_selected, auth_constants.METHOD_ASL)

            # Trigger Sign-In
            ld._ok_pressed()

            self.assertIsNotNone(ld._asl_task, "ULF2 Auth has started")

            # check that UI displays the UFL2 pending screen
            self.assertEqual(ld.ui.stackedWidget.currentWidget(), ld.ui.asl_page)

            # Cancel the request and go back to the login screen
            ld._asl_back_pressed()

            # check that UI displays the login credentials
            self.assertEqual(ld.ui.stackedWidget.currentWidget(), ld.ui.login_page)
            self.assertIsNone(ld._asl_task)

            # Trigger Sign-In
            ld._ok_pressed()
            self.assertIsNotNone(ld._asl_task, "ULF2 Auth has started")

            # Simulate ULF2 Thread run
            ld._asl_task.run()
            ld._asl_task_finished()

            # check that UI displays the login credentials
            self.assertEqual(ld.ui.stackedWidget.currentWidget(), ld.ui.login_page)

            # Verify that the dialog succeeded
            self.assertEqual(
                QtGui.QDialog.result(ld),
                QtGui.QDialog.Accepted,
            )

            self.assertEqual(
                ld.result(),
                (
                    "https://host.shotgunstudio.com",
                    "user_login",
                    "session_token",
                    None,
                ),
            )

        # Test SGTK_FORCE_STANDARD_LOGIN_DIALOG override
        with mock.patch(
            "tank.authentication.site_info._get_site_infos",
            return_value={
                "app_session_launcher_enabled": True,
            },
        ), mock.patch.dict(
            "os.environ", {"SGTK_FORCE_STANDARD_LOGIN_DIALOG": "1"}
        ), self._login_dialog(
            is_session_renewal=True,
            hostname="https://host.shotgunstudio.com",
        ) as ld:
            # Ensure current method set is lcegacy credentials
            self.assertEqual(ld.method_selected, auth_constants.METHOD_BASIC)

        # Then Web login vs ULF2
        with mock.patch(
            "tank.authentication.site_info._get_site_infos",
            return_value={
                "user_authentication_method": "oxygen",
                "unified_login_flow_enabled": True,
                "app_session_launcher_enabled": True,
            },
        ), self._login_dialog(
            is_session_renewal=True,
            hostname="https://host.shotgunstudio.com",
        ) as ld:
            self.assertFalse(ld.menu_action_legacy.isVisible())
            self.assertTrue(ld.menu_action_ulf.isVisible())
            self.assertTrue(ld.menu_action_asl.isVisible())

            # Ensure current method set is web login
            self.assertEqual(ld.method_selected, auth_constants.METHOD_WEB_LOGIN)

            # Trigger ULF2 again
            ld._menu_activated_action_asl()

            # Ensure current method set is ufl2
            self.assertEqual(ld.method_selected, auth_constants.METHOD_ASL)

            # Trigger Sign-In
            ld._ok_pressed()

            self.assertIsNotNone(ld._asl_task, "ULF2 Auth has started")

            # check that UI displays the UFL2 pending screen
            self.assertEqual(ld.ui.stackedWidget.currentWidget(), ld.ui.asl_page)

            # Cancel the request and go back to the login screen
            ld._asl_back_pressed()

            # check that UI displays the login credentials
            self.assertEqual(ld.ui.stackedWidget.currentWidget(), ld.ui.login_page)
            self.assertIsNone(ld._asl_task)

            # Trigger Sign-In
            ld._ok_pressed()
            self.assertIsNotNone(ld._asl_task, "ULF2 Auth has started")

            # Simulate ULF2 Thread run
            ld._asl_task.run()
            ld._asl_task_finished()

            # check that UI displays the login credentials
            self.assertEqual(ld.ui.stackedWidget.currentWidget(), ld.ui.login_page)

            self.assertEqual(
                ld._asl_task.session_info,
                (
                    "https://host.shotgunstudio.com",
                    "user_login",
                    "session_token",
                    None,
                ),
            )

    @mock.patch(
        "tank.authentication.site_info._get_site_infos",
        return_value={
            "app_session_launcher_enabled": True,
        },
    )
    @mock.patch(
        "tank.authentication.session_cache.generate_session_token", return_value=None
    )
    @mock.patch(
        "tank.authentication.session_cache.get_recent_hosts",
        return_value=[
            "https://site1.shotgunstudio.com",
            "https://site2.shotgunstudio.com",
            "https://site3.shotgunstudio.com",
        ],
    )
    def test_console_app_session_launcher(self, *unused_mocks):
        handler = console_authentication.ConsoleLoginHandler(fixed_host=False)

        # First select the legacy method
        with mock.patch(
            "tank.authentication.console_authentication.input",
            side_effect=[
                "\n",  # Select default SG site (site1)
                "1",  # Select "legacy" auth method
                "username",
            ],
        ), mock.patch(
            "tank.authentication.console_authentication.ConsoleLoginHandler._get_password",
            return_value="password",
        ):
            self.assertEqual(
                handler.authenticate("https://site3.shotgunstudio.com", None, None),
                ("https://site3.shotgunstudio.com", "username", None, None),
            )

        # Then repeat the operation but select the ULF2 method
        with mock.patch(
            "tank.authentication.console_authentication.input",
            side_effect=[
                "",  # Select default site -> site4
                "2",  # Select "ULF2" auth method
                "",  # OK to continue
            ],
        ), mock.patch(
            "tank.authentication.app_session_launcher.process",
            return_value=("https://site4.shotgunstudio.com", "ULF2!", None, None),
        ):
            self.assertEqual(
                handler.authenticate("https://site4.shotgunstudio.com", None, None),
                ("https://site4.shotgunstudio.com", "ULF2!", None, None),
            )

        # Alternate fixed_host value for code coverage
        handler = console_authentication.ConsoleLoginHandler(fixed_host=True)

        # Then repeat the operation having the site configured with Oxygen
        with mock.patch(
            "tank.authentication.site_info._get_site_infos",
            return_value={
                "user_authentication_method": "oxygen",
                "app_session_launcher_enabled": True,
            },
        ), mock.patch(
            "tank.authentication.console_authentication.input",
            side_effect=[
                # No method to select as there is only one option
                "",  # OK to continue
            ],
        ), mock.patch(
            "tank.authentication.app_session_launcher.process",
            return_value="ULF2 result 9867",
        ):
            self.assertEqual(
                handler.authenticate("https://site4.shotgunstudio.com", None, None),
                "ULF2 result 9867",
            )

        # Then, one more small test for coverage
        with mock.patch(
            "tank.authentication.site_info._get_site_infos",
            return_value={
                "user_authentication_method": "oxygen",
                "app_session_launcher_enabled": True,
            },
        ), mock.patch(
            "tank.authentication.console_authentication.input",
            side_effect=[
                "",  # OK to continue
            ],
        ), mock.patch(
            "tank.authentication.app_session_launcher.process",
            return_value=None,  # Simulate an authentication error
        ):
            with self.assertRaises(errors.AuthenticationError):
                handler._authenticate_app_session_launcher(
                    "https://site4.shotgunstudio.com", None, None
                )

        # Finally, disable ULF2 method and ensure legacy cred methods is
        # automatically selected
        with mock.patch(
            "tank.authentication.site_info._get_site_infos",
            return_value={},
        ), mock.patch(
            "tank.authentication.console_authentication.input",
            side_effect=[
                # No method to select as there is only one option
                "username",
            ],
        ), mock.patch(
            "tank.authentication.console_authentication.ConsoleLoginHandler._get_password",
            return_value="password",
        ):
            self.assertEqual(
                handler.authenticate("https://site3.shotgunstudio.com", None, None),
                ("https://site3.shotgunstudio.com", "username", None, None),
            )

    @mock.patch(
        "tank.authentication.session_cache.get_preferred_method",
        return_value=None,
    )
    def test_console_get_auth_method(self, *unused_mocks):
        from tank.authentication.site_info import SiteInfo

        with mock.patch.object(
            tank_vendor.shotgun_api3.Shotgun,
            "info",
            return_value={
                "app_session_launcher_enabled": True,
            },
        ):
            site_i = SiteInfo()
            # Call the reload with info hooked for code coverage
            site_i.reload(
                "https://host.shotgunstudio.com",
                http_proxy="http://proxy.local:3128",
            )

            handler = console_authentication.ConsoleLoginHandler(fixed_host=True)

            with mock.patch(
                "tank.authentication.console_authentication.input",
                return_value="1",
            ):
                self.assertEqual(
                    handler._get_auth_method("https://host.shotgunstudio.com", site_i),
                    auth_constants.METHOD_BASIC,
                )

            with mock.patch(
                "tank.authentication.console_authentication.input",
                return_value="2",
            ):
                self.assertEqual(
                    handler._get_auth_method("https://host.shotgunstudio.com", site_i),
                    auth_constants.METHOD_ASL,
                )

            for option in [
                auth_constants.METHOD_BASIC,
                auth_constants.METHOD_ASL,
            ]:
                with mock.patch(
                    "tank.authentication.session_cache.get_preferred_method",
                    return_value=option,
                ), mock.patch(
                    "tank.authentication.console_authentication.input",
                    return_value="",
                ):
                    self.assertEqual(
                        handler._get_auth_method("https://host.shotgunstudio.com", site_i),
                        option,
                    )

            for wrong_value in ["0", "3", "-1", "42", "wrong"]:
                with mock.patch(
                    "tank.authentication.console_authentication.input",
                    return_value=wrong_value,
                ):
                    with self.assertRaises(errors.AuthenticationError):
                        handler._get_auth_method(
                            "https://host.shotgunstudio.com", site_i
                        )

    def test_ulf2_auth_task_errors(self):
        # Mainly for code coverage

        from tank.authentication import login_dialog
        ulf2_task = login_dialog.ULF2_AuthTask(None, "https://host.shotgunstudio.com")

        with mock.patch(
            "tank.authentication.app_session_launcher.http_request",
            side_effect=Exception("My Error 45!"),
        ), self.assertLogs(
            login_dialog.logger.name, level="DEBUG",
        ) as cm:
            ulf2_task.run()

        self.assertIn("Unknown error from the App Session Launcher", cm.output[0])
        self.assertIn("My Error 45!", cm.output[0])

        self.assertIsInstance(ulf2_task.exception, errors.AuthenticationError)
        self.assertEqual(ulf2_task.exception.args[0], "Unknown authentication error")
