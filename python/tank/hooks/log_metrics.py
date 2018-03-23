# Copyright (c) 2016 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

"""Hook that gets executed every time Toolkit logs user metrics."""

from tank import Hook


class LogMetrics(Hook):

    def execute(self, metrics):
        """
        .. warning::
            This method is deprecated and is not executed anymore.

            Please check :meth:`LogMetrics.log_metrics`.

        Called when Toolkit logs user metrics.
        
        :param list metrics: list of dictionaries with logged data.

        The metrics dictionaries will take one of two forms:

        1. A user attribute metric. These typically log the version of
           an app, engine, framework, DCC, etc.

        {
            "type": "user_attribute",
            "attr_name": <attr name>
            "attr_value": <attr value>
        }

        2. A user activity metric. These metrics are more common and
           log the usage of a particular api, hook, engine, app, framework,
           method, etc.

        {
            "type": "user_activity",
            "module": <module name>
            "action": <action name>
        }

        """
        pass

    def log_metrics(self, metrics):
        """
        Called when Toolkit logs metrics.
        
        :param list metrics: list of :attr:`~tank.util.EventMetric.data` dictionaries
        with logged data.


        .. note:: 
            This hook will be executed within one or more
            dedicated metrics logging worker threads and not in the main thread.
            Overriding this hook may require additional care to avoid issues
            related to accessing shared resources across multiple threads.

        """
        pass
