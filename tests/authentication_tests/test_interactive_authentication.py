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

import contextlib

import sys
import os

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
    site_info,
)
from tank.authentication.utils import sanitize_http_proxy
from tank.authentication.sso_saml2.core.sso_saml2_core import (
    SsoSaml2Core,
    get_renew_path,
)
from tank.authentication.sso_saml2.core.authentication_session_data import (
    AuthenticationSessionData,
)

import tank
import tank_vendor.shotgun_api3


@skip_if_pyside_missing
class InteractiveTests(ShotgunTestBase):
    """
    Tests ui and console based authentication.
    """

    def setUp(self, *args, **kwargs):
        pass
    def tearDown(self):
        pass
    @suppress_generated_code_qt_warnings
    def test_site_and_user_disabled_on_session_renewal(self):
        pass
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
                return super().done(r)

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
        pass
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
        pass
    @mock.patch("tank.authentication.interactive_authentication._get_ui_state")
    @interactive
    @suppress_generated_code_qt_warnings
    def test_login_console(self, _get_ui_state_mock):
        pass
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
        pass
    @mock.patch("tank.authentication.interactive_authentication._get_ui_state")
    @interactive
    @suppress_generated_code_qt_warnings
    def test_session_renewal_console(self, _get_ui_state_mock):
        pass
    @suppress_generated_code_qt_warnings
    def test_invoker_rethrows_exception(self):
        pass
    def test_console_auth_error(self, *mocks):
        pass
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
        pass
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
        pass
    @mock.patch(
        "tank.authentication.site_info._get_site_infos",
        return_value={
            "authentication_app_session_launcher_enabled": False,
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
        pass
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
    def test_sso_enabled_site_with_legacy_exception_name(self, *mocks):
        pass
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
    def test_sso_enabled_site(self, *mocks):
        pass
    @suppress_generated_code_qt_warnings
    def test_ui_auth_with_whitespace(self):
        pass
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
        pass
    @suppress_generated_code_qt_warnings
    def test_login_dialog_exit_confirmation(self):
        pass
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
        "tank.authentication.session_cache.get_preferred_method",
        return_value=None,
    )
    def test_initial_ui_not_basic_for_identity_site(self, *unused_mocks):
        pass
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
        pass
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
        pass
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
        pass
    @suppress_generated_code_qt_warnings
    def test_web_login_not_supported(self):
        pass
    @suppress_generated_code_qt_warnings
    def test_login_dialog_method_selected_default(self):
        pass
    @suppress_generated_code_qt_warnings
    def test_login_dialog_method_selected_session_cache(self):
        pass
    @suppress_generated_code_qt_warnings
    @mock.patch("tank.authentication.login_dialog.ASL_AuthTask.start")
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
        pass
    @mock.patch(
        "tank.authentication.site_info._get_site_infos",
        return_value={
            "authentication_app_session_launcher_enabled": True,
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
        pass
    @mock.patch(
        "tank.authentication.session_cache.get_preferred_method",
        return_value=None,
    )
    def test_console_get_auth_method(self, *unused_mocks):
        pass
    def test_asl_auth_task_errors(self):
        pass
class LoadInformationInfoTests(ShotgunTestBase):
    def test_reload_wrong_url(self, *unused_mocks):
        pass
    def test_reload_wrong_site(self, *unused_mocks):
        pass
class UtilsTests(ShotgunTestBase):
    def test_sanitize_http_proxy(self):
        pass
    def test_get_renew_path(self):
        pass
class SsoSaml2CoreTests(ShotgunTestBase):
    def setUp(self, *args, **kwargs):
        pass
    def test_on_renew_sso_session(self):
        pass
    def test_on_sso_login_attempt(self):
        pass
