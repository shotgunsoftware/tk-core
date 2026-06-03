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
Engine-related unit tests.
"""

import contextlib
import os
import random
import sys
import threading
import time
import unittest
from unittest import mock

import sgtk
import tank
from sgtk.platform import engine
from tank.errors import TankError
from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import (
    TankTestBase,
    skip_if_pyside_missing,
    suppress_generated_code_qt_warnings,
)


class TestEngineBase(TankTestBase):
    """
    Sets up and tears down engine-based unit tests.
    """

    def setUp(self):
        pass
    def tearDown(self):
        pass
class TestDialogCreation(TestEngineBase):
    """
    Tests how engines construct and show dialogs.
    """

    def setUp(self):
        pass
    @skip_if_pyside_missing
    def test_create_widget(self):
        pass
    @skip_if_pyside_missing
    def tearDown(self):
        pass
class TestStartEngine(TestEngineBase):
    """
    Tests how engines are started.
    """

    def test_get_engine_path(self):
        pass
    def test_valid_engine(self):
        pass
    def test_engine_running(self):
        pass
    def test_properties(self):
        pass
class TestLegacyStartShotgunEngine(TestEngineBase):
    """
    Tests how the tk-shotgun engine is started via the start_shotgun_engine routine.
    """

    def test_empty_environment(self):
        pass
@skip_if_pyside_missing
class TestExecuteInMainThread(TestEngineBase):
    """
    Tests the execute_in_main_thread and async_execute_in_main_thread methods.
    """

    def setUp(self):
        pass
    @unittest.skipIf(
        (
            (sys.version_info.major, sys.version_info.minor) == (3, 11)
            and sys.platform.startswith("linux")
        ),
        "Problem - SG-38851",
    )
    def test_exec_in_main_thread(self):
        pass
    def test_async_exec_in_main_thread(self):
        pass
    def _test_exec_in_main_thread(self, exec_in_main_thread_func):
        """
        Makes sure that the given functor will call user code in the main thread.

        :param exec_in_main_thread_func: Method that can send a request to the main thread.
        """
        t = threading.Thread(
            target=lambda: exec_in_main_thread_func(
                self._assert_run_in_main_thread_and_quit
            )
        )
        t.start()
        self._app.exec_()
        t.join()

    def _assert_run_in_main_thread_and_quit(self):
        from sgtk.platform.qt import QtCore

        # Make sure we are running in the main thread.
        self.assertEqual(
            QtCore.QThread.currentThread(), QtCore.QCoreApplication.instance().thread()
        )
        self._app.quit()

    @skip_if_pyside_missing
    def test_exec_in_main_thread_deadlock(self):
        pass
    @skip_if_pyside_missing
    def test_async_exec_in_main_thread_deadlock(self):
        pass
    # FIXME: Deactivating this test because it randomly freezes, but the code doesn't seem
    # to have any problem in production (which we would have heard of, since the background task
    # manager uses this feature extensively).
    #
    # The error string is:
    # python[37236] <Warning>: void CGSUpdateManager::log() const: conn 0x1fd93: spurious update.
    #
    # No amount of Googling could figure it out. Converting to QThreads doesn't fix it either.
    # Also, it seems the test only fails if it is run with all the other tests. On its own it appears to be fine.
    def _test_thead_safe_exec_in_main_thread(self):
        """
        Checks that execute_in_main_thread is itself thread-safe!  It
        runs a simple test a number of times in multiple threads and asserts the result
        returned is as expected.
        """
        from sgtk.platform.qt import QtCore

        num_test_threads = 20
        num_thread_iterations = 30

        def run_in_main_thread(v):
            """
            :param v: A value sent from the background thread.
            :returns: The value sent from the background thread.
            """
            # print "Running", v
            return v

        def threaded_work(val):
            """
            Sends as many notifications to the main thread using execute_in_main_thread
            as specified by num_thread_iterations.

            :param val: The index of the thread.
            """
            try:
                eng = sgtk.platform.current_engine()
                c_time = 0.0
                for i in range(num_thread_iterations):
                    time.sleep(random.randint(0, 10) / 10.0)
                    arg = (val, i)
                    st = time.time()
                    ret_val = eng.execute_in_main_thread(run_in_main_thread, arg)
                    e = time.time()
                    c_time += e - st
                    self.assertEqual(ret_val, arg)
            except Exception as e:
                print(e)
                raise

            # print "Cumulative time for thread %d: %0.4fs" % (val, c_time)

        threads = []
        for ti in range(num_test_threads):
            t = threading.Thread(target=lambda: threaded_work(ti))
            t.start()
            threads.append(t)

        def wait_for_threads_and_quit(threads):
            for i, t in enumerate(threads):
                t.join()
            QtCore.QCoreApplication.instance().quit()

        t = threading.Thread(target=lambda: wait_for_threads_and_quit(threads))
        t.start()
        QtCore.QCoreApplication.instance().exec_()


class TestContextChange(TestEngineBase):
    """
    Makes sure that pre and post context change events are always sent wen context changes.
    """

    def setUp(self):
        pass
    @contextlib.contextmanager
    def _assert_hooks_invoked(self, old_context, new_context):
        """
        Asserts that the change context hooks have only been invoked once and with
        the right arguments. To be invoked with the 'with' statement.

        :param old_context: Context to compare with the old context parameter in
            the hooks.
        :param new_context: Context to compare with the new context parameter in
            the hooks.
        """
        with self._pre_patch as pre_mock, self._post_patch as post_mock:
            # Invokes the code within the caller's 'with' statement. (that's really cool!)
            yield
            pre_mock.assert_called_once_with(self.tk, old_context, new_context)
            post_mock.assert_called_once_with(self.tk, old_context, new_context)

    def test_on_engine_start(self):
        pass
    def test_on_engine_destroy(self):
        pass
    def test_on_destroy_engine_and_start(self):
        pass
    def test_on_engine_restart(self):
        pass
    def test_on_engine_restart_other_context(self):
        pass
    def test_on_change_context_with_context_change_supporting_engine(self):
        pass
    def test_on_change_context_without_context_change_supporting_engine(self):
        pass
class TestRegisteredCommands(TestEngineBase):
    """
    Test functionality related to registering commands with an engine.
    """

    def _command_callback(self):
        pass

    def test_register_command(self):
        pass
    def test_duplicate_commands(self):
        pass
class TestCompatibility(TankTestBase):
    def test_backwards_compatible(self):
        pass
@skip_if_pyside_missing
class TestShowDialog(TestEngineBase):
    """
    Tests the engine.show_dialog method.
    """

    def setUp(self):
        pass
    def tearDown(self):
        pass
    @suppress_generated_code_qt_warnings
    def test_gui_app_and_close(self):
        pass
