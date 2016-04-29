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

from __future__ import with_statement

import os
import sys
import threading
import random
import time

from tank_test.tank_test_base import TankTestBase, setUpModule, skip_if_pyside_missing

import contextlib
import tank
import sgtk
from sgtk.platform import engine
from tank.errors import TankError
import mock


class TestEngineBase(TankTestBase):
    """
    Sets up and tears down engine-based unit tests.
    """

    def setUp(self):
        """
        Sets up a few entities so we can create a vaid context.
        """
        super(TestEngineBase, self).setUp()

        self.setup_fixtures()

        # setup shot
        seq = {"type":"Sequence", "name":"seq_name", "id":3}
        seq_path = os.path.join(self.project_root, "sequences/Seq")
        self.add_production_path(seq_path, seq)
        shot = {"type":"Shot",
                "name": "shot_name",
                "id":2,
                "project": self.project}
        shot_path = os.path.join(seq_path, "shot_code")
        self.add_production_path(shot_path, shot)
        step = {"type":"Step", "name":"step_name", "id":4}
        self.shot_step_path = os.path.join(shot_path, "step_name")
        self.add_production_path(self.shot_step_path, step)

        self.test_resource = os.path.join(self.pipeline_config_root, "config", "foo", "bar.png")
        os.makedirs(os.path.dirname(self.test_resource))
        fh = open(self.test_resource, "wt")
        fh.write("test")
        fh.close()

        self.context = self.tk.context_from_path(self.shot_step_path)

    def tearDown(self):
        """
        Tears down the current engine.
        """
        cur_engine = tank.platform.current_engine()
        if cur_engine:
            cur_engine.destroy()
        os.remove(self.test_resource)

        # important to call base class so it can clean up memory
        super(TestEngineBase, self).tearDown()


class TestStartEngine(TestEngineBase):
    """
    Tests how engines are started.
    """

    def test_get_engine_path(self):
        """
        Makes sure the engine is loaded from the right location.
        """
        engine_path = tank.platform.get_engine_path("test_engine", self.tk, self.context)
        expected_engine_path = os.path.join(self.pipeline_config_root, "config", "bundles", "test_engine")
        self.assertEquals(engine_path, expected_engine_path)

    def test_valid_engine(self):
        """
        Makes sure the engine that is started is actually an sgtk engine.
        """
        cur_engine = tank.platform.start_engine("test_engine", self.tk, self.context)
        self.assertIsInstance(cur_engine, tank.platform.engine.Engine)

    def test_engine_running(self):
        """
        Makes sure starting an engine twice will fail.
        """
        engine_name = "test_engine"
        tank.platform.start_engine(engine_name, self.tk, self.context)
        self.assertRaises(TankError, tank.platform.start_engine, engine_name, self.tk, self.context)

    def test_properties(self):
        """
        Test engine properties
        """
        cur_engine = tank.platform.start_engine("test_engine", self.tk, self.context)
        self.assertEqual(cur_engine.name, "test_engine")
        self.assertEqual(cur_engine.display_name, "test_engine")
        self.assertEqual(cur_engine.version, "Undefined")
        self.assertEqual(cur_engine.documentation_url, None)
        self.assertEqual(cur_engine.instance_name, "test_engine")
        self.assertEqual(cur_engine.context, self.context)


class TestExecuteInMainThread(TestEngineBase):
    """
    Tests the execute_in_main_thread and async_execute_in_main_thread methods.
    """

    @skip_if_pyside_missing
    def setUp(self):
        """
        Starts up an engine and makes sure Qt is ready to be used.
        """
        super(TestExecuteInMainThread, self).setUp()
        tank.platform.start_engine("test_engine", self.tk, self.context)
        if sgtk.platform.qt.QtGui.qApp is None:
            sgtk.platform.qt.QtGui.QApplication(sys.argv)

    @skip_if_pyside_missing
    def test_exec_in_main_thread(self):
        """
        Checks that execute in main thread actually executes in the main thread.
        """
        self._test_exec_in_main_thread(sgtk.platform.current_engine().execute_in_main_thread)

    @skip_if_pyside_missing
    def test_async_exec_in_main_thread(self):
        """
        Checks that execute in main thread actually executes in the main thread.
        """
        self._test_exec_in_main_thread(sgtk.platform.current_engine().async_execute_in_main_thread)

    def _test_exec_in_main_thread(self, exec_in_main_thread_func):
        """
        Makes sure that the given functor will call user code in the main thread.

        :param exec_in_main_thread_func: Method that can send a request to the main thread.
        """
        t = threading.Thread(target=lambda: exec_in_main_thread_func(self._assert_run_in_main_thread_and_quit))
        t.start()
        sgtk.platform.qt.QtCore.QCoreApplication.instance().exec_()
        t.join()

    def _assert_run_in_main_thread_and_quit(self):
        from sgtk.platform.qt import QtCore
        # Make sure we are running in the main thread.
        self.assertEqual(QtCore.QThread.currentThread(), QtCore.QCoreApplication.instance().thread())
        QtCore.QCoreApplication.instance().quit()

    @skip_if_pyside_missing
    def test_exec_in_main_thread_deadlock(self):
        """
        Makes sure the main thread invoker doesn't deadlock when called from the main thread.
        """
        sgtk.platform.current_engine().execute_in_main_thread(self._assert_run_in_main_thread_and_quit)

    @skip_if_pyside_missing
    def test_async_exec_in_main_thread_deadlock(self):
        """
        Makes sure the main thread async invoker doesn't deadlock when called from the main thread.
        """
        sgtk.platform.current_engine().async_execute_in_main_thread(self._assert_run_in_main_thread_and_quit)

    @skip_if_pyside_missing
    def test_thead_safe_exec_in_main_thread(self):
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
                    c_time += (e - st)
                    self.assertEqual(ret_val, arg)
            except Exception, e:
                print e
                raise

            # print "Cumulative time for thread %d: %0.4fs" % (val, c_time)

        threads = []
        for ti in range(num_test_threads):
            t = threading.Thread(target=lambda:threaded_work(ti))
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
        """
        Prepares a mocker that will count how many times a method is called with certain parameters.
        """
        TestEngineBase.setUp(self)

        # Create pass-through patches for methods that should be invoked
        # when switching context.
        self._pre_patch = mock.patch(
            "sgtk.platform.engine._emit_core_pre_context_change",
            wraps=engine._emit_core_pre_context_change
        )
        self._post_patch = mock.patch(
            "sgtk.platform.engine._emit_core_post_context_change",
            wraps=engine._emit_core_post_context_change
        )

    @contextlib.contextmanager
    def _assert_hooks_invoked(self, old_context, new_context):
        """
        Asserts that the change context hooks have only been invoked once and with
        the right arguments. To be invoked with the 'with' statement.
        """
        with self._pre_patch as pre_mock:
            with self._post_patch as post_mock:
                # Invokes the code within the caller's 'with' statement. (that's really cool!)
                yield
                pre_mock.assert_called_once_with(self.tk, old_context, new_context)
                post_mock.assert_called_once_with(self.tk, old_context, new_context)

    def test_on_engine_start(self):
        """
        Checks if the context change hooks are invoked when an engine starts.
        """
        # Start the engine.
        with self._assert_hooks_invoked(None, self.context):
            sgtk.platform.start_engine("test_engine", self.tk, self.context),

    def test_on_engine_restart(self):
        """
        Checks if the context change hooks are invoked when an engine restarts with
        the same context.
        """
        sgtk.platform.start_engine("test_engine", self.tk, self.context)

        # Restart toolkit
        with self._assert_hooks_invoked(self.context, self.context):
            tank.platform.restart()

    def test_on_engine_restart_other_context(self):
        """
        Checks if the context change hooks are invoked when an engine restarts with
        a different context.
        """
        sgtk.platform.start_engine("test_engine", self.tk, self.context)

        new_context = self.tk.context_from_entity(
            self.context.entity["type"], self.context.entity["id"]
        )
        # Restart toolkit with the a different context.
        with self._assert_hooks_invoked(self.context, new_context):
            tank.platform.restart(new_context)

    def test_on_change_context(self):
        """
        Checks that the context change event are sent when the context is changed.
        """
        # Start the engine.
        cur_engine = sgtk.platform.start_engine("test_engine", self.tk, self.context)

        # Create another context we can switch to.
        new_context = self.tk.context_from_entity(
            self.context.entity["type"], self.context.entity["id"]
        )

        # Now trigger a context change.
        with self._assert_hooks_invoked(self.context, new_context):
            sgtk.platform.change_context(new_context)

        # Make sure the engine wasn't destroyed and recreated.
        self.assertEqual(id(cur_engine), id(sgtk.platform.current_engine()))
