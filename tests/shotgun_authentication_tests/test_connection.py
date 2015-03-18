# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from __future__ import with_statement
from mock import patch
import sys

from tank_test.tank_test_base import *
import tank_test

from tank.util.core_authentication_manager import CoreAuthenticationManager
from tank_vendor.shotgun_authentication import connection
from tank_vendor.shotgun_api3 import shotgun


class AuthenticationTests(TankTestBase):
    """
    Tests the session module. Note that because how caching the session information is still
    very much in flux, we will not be unit testing cache_session_info, get_login_info and
    delete_session_data for now, since they have complicated to test and would simply slow us down.
    """

    @patch("tank_vendor.shotgun_authentication.authentication.is_script_user_authenticated")
    @patch("tank_vendor.shotgun_authentication.authentication.is_human_user_authenticated")
    def setUp(
        self,
        is_human_user_authenticated_mock,
        is_script_user_authenticated_mock,
    ):
        if not CoreAuthenticationManager.is_activated():
            CoreAuthenticationManager.activate()

        # setUp in the base class tries to configure some path-cache related stuff, which invokes
        # get_current_user. We can't want a current user, so report that nothing has been authenticated.
        is_human_user_authenticated_mock.return_value = False
        is_script_user_authenticated_mock.return_value = False

        super(AuthenticationTests, self).setUp()

    @patch("tank_vendor.shotgun_authentication.connection._validate_session_token")
    def test_create_from_valid_session(self, validate_session_token_mock):
        """
        When cache info is valid and _validate_session_token succeeds, it's return value
        is returned by create_sg_connection_from_authentication.
        """
        # The return value of the _validate_session_token is also the return value of
        # _create_sg_connection_from_session. Make sure we are getting it.
        validate_session_token_mock.return_value = "Success"
        self.assertEqual(connection.create_sg_connection_from_session(
            {"host": "abc", "login": "login", "session_token": "session_token"}
        ), "Success")

    @patch("tank_test.mockgun.Shotgun.find_one")
    @patch("tank_vendor.shotgun_authentication.connection._shotgun_instance_factory")
    def test_authentication_failure_in_validate_session_token(self, shotgun_instance_factory_mock, find_one_mock):
        """
        In _validate_session_token, if find_one throws AuthenticationFault exception, we should
        fail gracefully
        """
        shotgun_instance_factory_mock.side_effect = tank_test.mockgun.Shotgun
        # find_one should throw the AuthenticationFault, which should gracefully abort connecting
        # to Shotgun
        find_one_mock.side_effect = shotgun.AuthenticationFault
        self.assertEquals(
            connection._validate_session_token("https://a.com", "b", None), None
        )

    @patch("tank_test.mockgun.Shotgun.find_one")
    @patch("tank_vendor.shotgun_authentication.connection._shotgun_instance_factory")
    def test_unexpected_failure_in_validate_session_token(self, shotgun_instance_factory_mock, find_one_mock):
        """
        In _validate_session_token, if find_one throws anything else than AuthenticationFault, it
        should be rethrown.
        """
        shotgun_instance_factory_mock.side_effect = tank_test.mockgun.Shotgun
        # Any other error type than AuthenticationFailed is unexpected and should be rethrown
        find_one_mock.side_effect = ValueError
        with self.assertRaises(ValueError):
            connection._validate_session_token("https://a.com", "b", None)

    @patch("tank_vendor.shotgun_authentication.connection._validate_session_token")
    @patch("tank_vendor.shotgun_authentication.authentication.clear_cached_credentials")
    def test_bad_credentials_should_wipe_session_data(self, validate_session_token_mock, clear_cached_credentials_mock):
        """
        When cache info is valid and _validate_session_token succeeds, it's return value
        is returned by create_sg_connection_from_authentication.
        """
        validate_session_token_mock.return_value = None
        clear_cached_credentials_mock.return_value = None
        self.assertEqual(connection.create_sg_connection_from_session(
            {"host": "abc", "login": "login", "session_token": "session_token"}
        ), None)
        self.assertEqual(clear_cached_credentials_mock.call_count, 1)

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
                    invoker = connection._create_invoker()
                    # Make sure we have a QObject derived object and not a regular Python function.
                    if not isinstance(invoker, QtCore.QObject):
                        raise Exception("Invoker is not a QObject")
                    if invoker.thread() != QtGui.QApplication.instance().thread():
                        raise Exception("Invoker should be of the same thread as the QApplication.")
                    if QtCore.QThread.currentThread() != self:
                        raise Exception("Current thread not self.")
                    if QtGui.QApplication.instance().thread == self:
                        raise Exception("QApplication should be in the main thread, not self.")
                    invoker(thrower)
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
