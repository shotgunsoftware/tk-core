# Copyright (c) 2018 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Hook that gets executed every time Toolkit logs user metrics."""

from tank import Hook


class LogMetrics(Hook):
    def execute(self, metrics):
        """
        .. warning::
            This method is deprecated and is not executed anymore.

            Please check :meth:`LogMetrics.log_metrics`.
        """
        pass

    def log_metrics(self, metrics):
        """
        Called when Toolkit logs a list of metrics.

        A metric is a dictionary with three items:

        - **event_group** (:class:`str`) - Name of the event group.
        - **event_name** (:class:`str`) - Name of the event.
        - **event_properties** (:class:`list`) - List of properties for the event.

        The default implementation does nothing.

        :param list(dict) metrics: List of metrics.

        .. note::
            This hook will be executed within one or more dedicated metrics logging
            worker threads and not in the main thread. Overriding this hook may
            require additional care to avoid issues related to accessing shared
            resources across multiple threads.
        """
        pass
