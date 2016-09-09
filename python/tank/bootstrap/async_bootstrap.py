# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

# Import Qt without having to worry about the version to use.
from ..util.qt_importer import QtImporter
importer = QtImporter()
if importer.wrapper is None:
    # Raise an exception when Qt is not available.
    raise ImportError
QtCore = importer.QtCore
QtGui = importer.QtGui

from ..api import Sgtk


class AsyncBootstrapWrapper(QtCore.QObject):
    """
    Wrapper class that can bootstrap an :class:`~sgtk.Sgtk` instance
    asynchronously in a background thread, followed by the synchronous launching
    of an :class:`~sgtk.platform.Engine` instance in the main application thread.
    """

    def __init__(self, toolkit_manager, engine_name, entity):
        """
        Initializes an instance of the asynchronous bootstrap wrapper.

        This method retrieves the toolkit manager progress reporting callback to use it later.

        :param toolkit_manager: :class:`~sgtk.bootstrap.ToolkitManager` instance bootstrapping the engine.
        :param engine_name: Name of the engine to launch.
        :param entity: Shotgun entity used to resolve a project context.
        """

        super(AsyncBootstrapWrapper, self).__init__()

        self._toolkit_manager = toolkit_manager
        self._engine_name = engine_name
        self._entity = entity

        # Retrieve the toolkit manager progress reporting callback.
        self._progress_callback = self._toolkit_manager._progress_cb

        self._completed_callback = None
        self._failed_callback = None

        # Create a worker that can bootstrap the toolkit asynchronously in a background thread.
        self._worker = _BootstrapToolkitWorker(self._toolkit_manager, engine_name, entity)

        # This QThread object will live in the main thread, not in the new thread it will manage.
        self._thread = QtCore.QThread()

        # Make the worker operate with the new thread affinity and use the QThread object event loop.
        self._worker.moveToThread(self._thread)

        # Start to work when the QThread object will have started its event loop in its new thread context.
        self._thread.started.connect(self._worker.work)

        # Make the worker report on the toolkit bootstrap progress.
        self._worker.progressing.connect(self._progress_bootstrap)

        # Handle completion of the toolkit bootstrap by the worker.
        self._worker.completed.connect(self._complete_bootstrap)

        # Handle failure of the toolkit bootstrap by the worker.
        self._worker.failed.connect(self._fail_bootstrap)

    def set_callbacks(self, completed_callback, failed_callback):
        """
        Sets the callback functions used to signify the completion and the failure of the bootstrap.

        These functions must have the following signatures:

            ``completed_callback(engine)``

            where:
            - ``engine`` is the launched :class:`~sgtk.platform.Engine` instance.

            ``failed_callback(phase, exception)``

            where:
            - ``phase`` is the bootstrap phase that raised the exception,
                        ``ToolkitManager.TOOLKIT_BOOTSTRAP_PHASE`` or ``ToolkitManager.ENGINE_STARTUP_PHASE``.
                        Using this phase, the callback can decide if the toolkit core needs
                        to be re-imported to ensure usage of a swapped in version.
            - ``exception`` is the python exception raised while bootstrapping.

        :param completed_callback: Callback function that handles cleanup after successful completion of the bootstrap.
        :param failed_callback: Callback function that handles cleanup after failed completion of the bootstrap.
        """

        self._completed_callback = completed_callback
        self._failed_callback = failed_callback

    def bootstrap(self):
        """
        Starts the asynchronous bootstrap logic.
        """

        # Start the QThread object event loop in its new thread context.
        self._thread.start()

    @QtCore.Slot(float, str, int, int)
    def _progress_bootstrap(self, progress_value, message, current_index, maximum_index):
        """
        Callback slot that reports back on the toolkit and engine bootstrap progress.

        :param progress_value: Current progress value, ranging from 0.0 to 1.0.
        :param message: Progress message to report.
        :param current_index: Optional current item number being looped over, or None.
        :param maximum_index: Optional maximum item number being looped over, or None.
        """

        if self._progress_callback:
            self._progress_callback(progress_value, message, current_index, maximum_index)

    @QtCore.Slot(Sgtk)
    def _complete_bootstrap(self, toolkit):
        """
        Callback slot that handles cleanup after successful completion of the toolkit bootstrap.

        :param toolkit: Bootstrapped :class:`~sgtk.Sgtk` instance.
        """

        # Make the QThread object exit its event loop.
        self._thread.quit()

        # Make the worker operate with the main thread affinity
        # where the main event loop can handle its deletion.
        self._worker.moveToThread(self.thread())

        try:

            # Ladies and Gentlemen, start your engines!
            engine = self._toolkit_manager._start_engine(toolkit, self._engine_name, self._entity)

        except Exception, exception:

            if self._failed_callback:
                # Handle cleanup after failed completion of the engine startup.
                self._failed_callback(self._toolkit_manager.ENGINE_STARTUP_PHASE, exception)

            return

        if self._completed_callback:
            # Handle cleanup after successful completion of the engine startup.
            self._completed_callback(engine)

    @QtCore.Slot(Exception)
    def _fail_bootstrap(self, exception):
        """
        Callback slot that handles cleanup after failed completion of the toolkit bootstrap.

        :param exception: Exception raised while bootstrapping the toolkit.
        """

        # Make the QThread object exit its event loop.
        self._thread.quit()

        # Make the worker operate with the main thread affinity
        # where the main event loop can handle its deletion.
        self._worker.moveToThread(self.thread())

        if self._failed_callback:
            # Handle cleanup after failed completion of the toolkit bootstrap.
            self._failed_callback(self._toolkit_manager.TOOLKIT_BOOTSTRAP_PHASE, exception)


class _BootstrapToolkitWorker(QtCore.QObject):
    """
    Bootstrap worker that can bootstrap an :class:`~sgtk.Sgtk` instance asynchronously in a background thread.

    This class defines 3 Qt signals:
    - ``progressing`` with signature ``(float, str, int, int)``
      emitted while the bootstrap toolkit worker is progressing in its work in the background,
      where ``float, str, int, int``are the current progress value, the progress message to report,
      the current item number being looped over and the maximum item number being looped over.
    - ``completed`` with signature ``(Sgtk)``
      emitted when the bootstrap toolkit worker successfully completes its work in the background,
      where ``Sgtk`` is the bootstrapped :class:`~sgtk.Sgtk` instance.
    - ``failed`` with signature ``(Exception)``
      emitted when the bootstrap toolkit worker fails to complete its work in the background,
      where ``Exception`` is the python exception raised while bootstrapping.
    """

    # Qt signal emitted while the bootstrap toolkit worker is progressing in its work in the background.
    progressing = QtCore.Signal(float, str, int, int)

    # Qt signal emitted when the bootstrap toolkit worker successfully completes its work in the background.
    completed = QtCore.Signal(Sgtk)

    # Qt signal emitted when the bootstrap toolkit worker fails to complete its work in the background.
    failed = QtCore.Signal(Exception)

    def __init__(self, toolkit_manager, engine_name, entity):
        """
        Initializes an instance of the bootstrap toolkit worker.

        :param toolkit_manager: :class:`~sgtk.bootstrap.ToolkitManager` instance bootstrapping the engine.
        :param engine_name: Name of the engine used to resolve a configuration.
        :param entity: Shotgun entity used to resolve a project context.
        """

        super(_BootstrapToolkitWorker, self).__init__()

        self._toolkit_manager = toolkit_manager
        self._engine_name = engine_name
        self._entity = entity

    @QtCore.Slot()
    def work(self):
        """
        Bootstraps a toolkit instance for the given engine and entity and
        signal the progress, and the completion or the failure of this work.
        """

        # Preserve the original toolkit manager progress reporting callback.
        original_progress_callback = self._toolkit_manager._progress_cb

        try:

            # Install a local thread-safe progress reporting callback.
            self._toolkit_manager.set_progress_callback(self._report_progress)

            # Bootstrap a toolkit instance for the given engine and entity.
            toolkit = self._toolkit_manager._bootstrap_sgtk(self._engine_name, self._entity)

            # Restore the original toolkit manager progress reporting callback.
            self._toolkit_manager.set_progress_callback(original_progress_callback)

            # Signal completion of the toolkit bootstrap.
            self.completed.emit(toolkit)

        except Exception, exception:

            # Restore the original toolkit manager progress reporting callback.
            self._toolkit_manager.set_progress_callback(original_progress_callback)

            # Signal failure of the toolkit bootstrap.
            self.failed.emit(exception)

    def _report_progress(self, progress_value, message, current_index, maximum_index):
        """
        Callback function that reports back on the toolkit bootstrap progress.

        :param progress_value: Current progress value, ranging from 0.0 to 1.0.
        :param message: Progress message to report.
        :param current_index: Optional current item number being looped over.
        :param maximum_index: Optional maximum item number being looped over.
        """

        # Signal the toolkit bootstrap progress.
        self.progressing.emit(progress_value, message, current_index, maximum_index)


def _get_thread_info_msg(caller):
    """
    Debugging function that generates a message about the thread the calling process is running in.

    :param caller: Name of the calling process to include in the information message.
    :return: Generated information message.
    """

    if QtGui.QApplication.instance():
        if QtCore.QThread.currentThread() == QtGui.QApplication.instance().thread():
            msg = "%s is running in main Qt thread."
        else:
            msg = "%s is running in background Qt thread."
    else:
        msg = "%s in not running in a Qt thread!"

    return msg % caller
