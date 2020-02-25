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

from __future__ import with_statement, print_function

import os
import sys
import threading
import random
import time

from tank_test.tank_test_base import (
    TankTestBase,
    skip_if_pyside_missing,
    suppress_generated_code_qt_warnings,
)
from tank_test.tank_test_base import setUpModule  # noqa

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
        seq = {"type": "Sequence", "name": "seq_name", "id": 3}
        seq_path = os.path.join(self.project_root, "sequences/Seq")
        self.add_production_path(seq_path, seq)
        shot = {"type": "Shot", "name": "shot_name", "id": 2, "project": self.project}
        shot_path = os.path.join(seq_path, "shot_code")
        self.add_production_path(shot_path, shot)
        step = {"type": "Step", "name": "step_name", "id": 4}
        self.shot_step_path = os.path.join(shot_path, "step_name")
        self.add_production_path(self.shot_step_path, step)

        self.test_resource = os.path.join(
            self.pipeline_config_root, "config", "foo", "bar.png"
        )
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


class TestDialogCreation(TestEngineBase):
    """
    Tests how engines construct and show dialogs.
    """

    def setUp(self):
        """
        We need a QApplication to run these tests.
        """
        super(TestDialogCreation, self).setUp()

        # Engine is not started yet, so can't rely on sgtk.platform.qt for imports.
        from tank.authentication.ui.qt_abstraction import QtGui

        if QtGui.QApplication.instance() is None:
            QtGui.QApplication([])

        sgtk.platform.start_engine("test_engine", self.tk, self.context)

    @skip_if_pyside_missing
    def test_create_widget(self):
        """
        Ensures that the _create_widget method is exception safe.
        """
        # Engine is not started yet, so can't rely on sgtk.platform.qt for imports.
        from tank.authentication.ui.qt_abstraction import QtGui

        class _test_widget(QtGui.QWidget):
            def __init__(self, *args, **kwargs):
                raise Exception("Testing...")

        # Ensure we don't bubble up an exception.
        sgtk.platform.current_engine()._create_widget(_test_widget)

    @skip_if_pyside_missing
    def tearDown(self):
        """
        Tears down the current engine.
        """
        cur_engine = sgtk.platform.current_engine()
        if cur_engine:
            cur_engine.destroy()

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
        engine_path = tank.platform.get_engine_path(
            "test_engine", self.tk, self.context
        )
        expected_engine_path = os.path.join(
            self.project_config, "bundles", "test_engine"
        )
        self.assertEqual(engine_path, expected_engine_path)

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
        self.assertRaises(
            TankError, tank.platform.start_engine, engine_name, self.tk, self.context
        )

    def test_properties(self):
        """
        Test engine properties
        """
        engine = tank.platform.start_engine("test_engine", self.tk, self.context)
        expected_doc_url = "https://support.shotgunsoftware.com/hc/en-us/articles/115000068574-User-Guide"
        self.assertEqual(engine.name, "test_engine")
        self.assertEqual(engine.display_name, "test_engine")
        self.assertEqual(engine.version, "Undefined")
        self.assertEqual(engine.documentation_url, expected_doc_url)
        self.assertEqual(engine.instance_name, "test_engine")
        self.assertEqual(engine.context, self.context)


class TestLegacyStartShotgunEngine(TestEngineBase):
    """
    Tests how the tk-shotgun engine is started via the start_shotgun_engine routine.
    """

    def test_empty_environment(self):
        """
        In the case of an empty shotgun environment file, a TankError
        should be raised rather than some unhandled exception where we
        try to use the None as a dict.
        """
        self.assertRaises(
            TankError,
            tank.platform.engine.start_shotgun_engine,
            self.tk,
            "empty",  # This corresponds to shotgun_empty.yml in the fixture.
            self.context,
        )


@skip_if_pyside_missing
class TestExecuteInMainThread(TestEngineBase):
    """
    Tests the execute_in_main_thread and async_execute_in_main_thread methods.
    """

    def setUp(self):
        """
        Starts up an engine and makes sure Qt is ready to be used.
        """
        super(TestExecuteInMainThread, self).setUp()

        # Engine is not started yet, so can't rely on sgtk.platform.qt for imports.
        from tank.authentication.ui.qt_abstraction import QtGui

        # See if a QApplication instance exists, and if not create one.  Use the
        # QApplication.instance() method, since qApp can contain a non-None
        # value even if no QApplication has been constructed on PySide2.
        if not QtGui.QApplication.instance():
            self._app = QtGui.QApplication(sys.argv)
        else:
            self._app = QtGui.QApplication.instance()

        tank.platform.start_engine("test_engine", self.tk, self.context)

    def test_exec_in_main_thread(self):
        """
        Checks that execute in main thread actually executes in the main thread.
        """
        self._test_exec_in_main_thread(
            sgtk.platform.current_engine().execute_in_main_thread
        )

    def test_async_exec_in_main_thread(self):
        """
        Checks that execute in main thread actually executes in the main thread.
        """
        self._test_exec_in_main_thread(
            sgtk.platform.current_engine().async_execute_in_main_thread
        )

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
        """
        Makes sure the main thread invoker doesn't deadlock when called from the main thread.
        """
        sgtk.platform.current_engine().execute_in_main_thread(
            self._assert_run_in_main_thread_and_quit
        )

    @skip_if_pyside_missing
    def test_async_exec_in_main_thread_deadlock(self):
        """
        Makes sure the main thread async invoker doesn't deadlock when called from the main thread.
        """
        sgtk.platform.current_engine().async_execute_in_main_thread(
            self._assert_run_in_main_thread_and_quit
        )

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
        """
        Prepares a mocker that will count how many times a method is called with certain parameters.
        """
        TestEngineBase.setUp(self)

        # Create pass-through patches for methods that should be invoked
        # when switching context. We'll use them layer to count how many times
        # they have been invoked and with what parameters.
        self._pre_patch = mock.patch(
            "sgtk.platform.engine._CoreContextChangeHookGuard._execute_pre_context_change",
            wraps=engine._CoreContextChangeHookGuard._execute_pre_context_change,
        )
        self._post_patch = mock.patch(
            "sgtk.platform.engine._CoreContextChangeHookGuard._execute_post_context_change",
            wraps=engine._CoreContextChangeHookGuard._execute_post_context_change,
        )

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
        # Multi item "with"s are not supported in Python 2.5, so do one after
        # the other.
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
            sgtk.platform.start_engine("test_engine", self.tk, self.context)

    def test_on_engine_destroy(self):
        """
        Checks if the context change hooks are invoked when an engine is destroyed.
        """
        sgtk.platform.start_engine("test_engine", self.tk, self.context)
        with self._assert_hooks_invoked(self.context, None):
            sgtk.platform.current_engine().destroy()

    def test_on_destroy_engine_and_start(self):
        """
        Checks if the way workfiles currently switches context will give the appropriate event
        sequence.
        """
        sgtk.platform.start_engine("test_engine", self.tk, self.context)

        with self._assert_hooks_invoked(self.context, None):
            sgtk.platform.current_engine().destroy()

        with self._assert_hooks_invoked(None, self.context):
            sgtk.platform.start_engine("test_engine", self.tk, self.context)

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

    def test_on_change_context_with_context_change_supporting_engine(self):
        """
        Checks that the context change event are sent when the context is changed.
        """
        # Start the engine.
        cur_engine = sgtk.platform.start_engine("test_engine", self.tk, self.context)

        # Create another context we can switch to.
        new_context = self.tk.context_from_entity(
            self.context.entity["type"], self.context.entity["id"]
        )

        # Enables the test engine to support context change.
        cur_engine.enable_context_change()

        # Cache the current engine settings and then set them to a bogus
        # dict of settings. This will allow us to test whether those
        # settings are recached during the context change.
        previous_settings = cur_engine.settings
        cur_engine._set_settings(dict(foo="bar"))

        # Now trigger a context change.
        with self._assert_hooks_invoked(self.context, new_context):
            sgtk.platform.change_context(new_context)

        # Make sure the engine wasn't destroyed and recreated.
        self.assertEqual(id(cur_engine), id(sgtk.platform.current_engine()))

        # Make sure that engine settings were recached.
        try:
            self.assertEqual(
                cur_engine.settings,
                cur_engine.get_env().get_engine_settings(cur_engine.instance_name),
            )
        except AssertionError:
            # Just to be safe, we'll set the settings back to what they
            # were previously if the recache didn't happen. It might be
            # that forthcoming tests need valid settings cached.
            cur_engine._set_settings(previous_settings)
            raise

    def test_on_change_context_without_context_change_supporting_engine(self):
        """
        Checks that the context change event are sent when the context is changed
        even if the engine doesn't support context change.
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

        # Make sure the engine was destroyed and recreated.
        self.assertNotEqual(id(cur_engine), id(sgtk.platform.current_engine()))


class TestRegisteredCommands(TestEngineBase):
    """
    Test functionality related to registering commands with an engine.
    """

    def _command_callback(self):
        pass

    def test_register_command(self):
        """
        Test the command registration process. Validate the input properties
        dictionary is set correctly and no unique prefix is set.
        """
        engine = sgtk.platform.current_engine()
        if engine is None:
            engine = sgtk.platform.start_engine("test_engine", self.tk, self.context)

        test_app = engine.apps["test_app"]

        register_properties = {
            "short_name": "cmd1_sn",
            "title": "Command One",
            "description": "This is test command one.",
            "app": test_app,
            "group": "Group One",
        }
        engine.register_command(
            "test_command", self._command_callback, register_properties
        )
        # Verify a command was registered with the engine
        self.assertIsInstance(engine.commands, dict)
        self.assertIsInstance(engine.commands.get("test_command"), dict)

        command_properties = engine.commands["test_command"].get("properties")
        self.assertIsInstance(command_properties, dict)

        for property, reg_value in register_properties.items():
            self.assertEqual(command_properties[property], reg_value)
        self.assertIsNone(command_properties["prefix"])

    def test_duplicate_commands(self):
        """
        Register duplicate command names to verify the correct unique prefix is being
        created to distinguish them.
        """
        engine = sgtk.platform.current_engine()
        if engine is None:
            engine = sgtk.platform.start_engine("test_engine", self.tk, self.context)

        # For the purposes of this test, the engine itself can be considered
        # an app because it also has an `instance_name` property.
        test_app_1 = engine
        test_app_2 = engine.apps["test_app"]

        # Define four commands to register. In the end, we should have the following
        # keys in the `engine.commands` dictionary:
        #   "test_engine:Group One:test_command"
        #   "test_engine:Group Two:test_command"
        #   "test_app:Group One:test_command"
        #   "test_app:test_command"
        register_properties = [
            {
                "short_name": "cmd1_sn",
                "title": "Command One",
                "description": "This is test command one.",
                "app": test_app_1,
                "group": "Group One",
            },
            {
                "short_name": "cmd2_sn",
                "title": "Command Two",
                "description": "This is test command two.",
                "app": test_app_1,
                "group": "Group Two",
            },
            {
                "short_name": "cmd3_sn",
                "title": "Command Three",
                "description": "This is test command three.",
                "app": test_app_2,
                "group": "Group One",
            },
            {
                "short_name": "cmd4_sn",
                "title": "Command Four",
                "description": "This is test command four.",
                "app": test_app_2,
            },
            {
                "short_name": "cmd5_sn",
                "title": "Command Five",
                "description": "This is test command five.",
                "group": "Group One",
            },
        ]

        # Register the first command and verify the command name key is
        # what we expect. Later we will verify this key has been deleted.
        engine.register_command(
            "test_command", self._command_callback, register_properties[0]
        )
        self.assertIsInstance(engine.commands.get("test_command"), dict)

        # Now register the duplicate commands.
        for command_properties in register_properties[1:]:
            engine.register_command(
                "test_command", self._command_callback, command_properties
            )

        # Verify command prefixes and property values for each of the duplicate
        # commands after everything has been registered.
        for command_properties in register_properties:
            # The command_prefix should take the form app.instance_name:group
            prefix_parts = []
            if command_properties.get("app"):
                prefix_parts.append(command_properties["app"].instance_name)
            if command_properties.get("group"):
                prefix_parts.append(command_properties["group"])
            command_prefix = ":".join(prefix_parts)
            command_key = ":".join(prefix_parts + ["test_command"])

            self.assertIsInstance(engine.commands[command_key], dict)
            engine_command_properties = engine.commands[command_key]["properties"]
            for property, reg_value in command_properties.items():
                self.assertEqual(engine_command_properties[property], reg_value)
            self.assertEqual(engine_command_properties["prefix"], command_prefix)

        # Validate the original 'test_command' first registered has been deleted.
        self.assertIsNone(engine.commands.get("test_command"))


class TestCompatibility(TankTestBase):
    def test_backwards_compatible(self):
        """
        Ensures the API is backwards compatible as we've moved TankEngineInitErrorto a new location.
        """
        self.assertEqual(sgtk.platform.TankEngineInitError, sgtk.TankEngineInitError)


@skip_if_pyside_missing
class TestShowDialog(TestEngineBase):
    """
    Tests the engine.show_dialog method.
    """

    def setUp(self):
        """
        Prepares the engine and makes sure Qt is ready.
        """
        super(TestShowDialog, self).setUp()
        self.setup_fixtures()

        self.engine = sgtk.platform.start_engine("test_engine", self.tk, self.context)

        # Engine is not started yet, so can't rely on sgtk.platform.qt for imports.
        from tank.authentication.ui.qt_abstraction import QtGui

        # Create an application instance so we can take control of the execution
        # of the dialog.
        if QtGui.QApplication.instance() is None:
            self._app = QtGui.QApplication(sys.argv)
        else:
            self._app = QtGui.QApplication.instance()

        self._dialog_dimissed = False

    def tearDown(self):
        self.engine.destroy()
        super(TestShowDialog, self).tearDown()

    @suppress_generated_code_qt_warnings
    def test_gui_app_and_close(self):
        # Show the dialog
        self.engine.commands["test_app"]["callback"]()
        # Process events
        self._app.processEvents()
        # Click the dismiss button
        self.engine.apps["test_app"].dismiss_button.click()
        # Process the remaining events.
        self._app.processEvents()
