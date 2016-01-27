# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""Classes and functions for logging Toolkit metrics."""


###############################################################################
# imports

from threading import Thread
from Queue import Queue

import urllib
import urllib2


###############################################################################
# Metrics dispatch Thread and Queue classes

class MetricsDispatchWorkerThread(Thread):
    """Worker thread for dispatching metrics to sg registration endpoint.

    Given a queue where metrics are logged in the client code, once started,
    this worker will dispatch them to the shotgun api endpoint as they
    arrive. 

    This thread runs as a `daemon` in order to prevent process shutdown
    from waiting until all metrics are processed.
    
    """

    def __init__(self, tk, metrics_queue, log=None):
        """Initialize the worker thread.

        :params tk: Toolkit api instance.
        :params queue.Queue metrics_queue: FIFO queue for metrics to dispatch.
        :params logging.Logger log: Logger for debugging purposes.

        """

        super(MetricsDispatchWorkerThread, self).__init__()

        self._tk = tk
        self._log = log
        self._metrics_queue = metrics_queue

        # don't wait for this thread to exit 
        self.daemon = True


    def run(self):
        """Runs a loop to dispatch metrics as they're added to the queue."""

        # if metrics are not supported, then no reason to process the queue
        if not self._metrics_supported():
            return

        # The thread is a daemon. Let it run for the duration of the process
        while True:

            # get the next available metric and dispatch it
            try:
                metric = self._metrics_queue.get(block=True)
                self._dispatch(metric)
            except Exception as e:
                if self._log:
                    self._log.error("Error dispatching metric: %s" % (e,))
            finally:
                # success or fail, we don't want to reprocess this metric
                self._metrics_queue.task_done()


    def _dispatch(self, metric):
        """Dispatch the supplied metric to the sg api registration endpoint.

        :param Metric metric: The Toolkit metric to dispatch.

        """

        # get this thread's sg connection via tk api
        sg_connection = self._tk.shotgun

        # handle proxy setup by pulling the proxy details from the main
        # shotgun connection
        if sg_connection.config.proxy_handler:
            opener = urllib2.build_opener(
                sg_connection.config.proxy_handler)
            urllib2.install_opener(opener)

        # get the session token and add it to the metrics payload
        session_token = sg_connection.get_session_token()
        metric.data["session_token"] = session_token

        # format the url based on the sg connection and post the data
        url = "%s/%s" % (sg_connection.base_url, metric.API_ENDPOINT)
        #res = urllib2.urlopen(url, urllib.urlencode(metric.data)) # XXX uncomment

        # remove the session token so that it doesn't show up in the log
        del metric.data["session_token"]

        if self._log:
            self._log.debug("Logged metric: %s" % (metric,))


    def _metrics_supported(self):
        """Returns True if server supports the metrics api endpoint."""

        if not hasattr(self, '_metrics_ok'):

            sg_connection = self._tk.shotgun
            self._metrics_ok = (
                sg_connection.server_caps.version and 
                sg_connection.server_caps.version >= (6, 2, 0)
                # XXX update the version number once metric endpoint available
            )
            
        self._metrics_ok = True # XXX remove after tsting

        return self._metrics_ok


class MetricsDispatchQueueSingleton(object):
    """A FIFO queue for logging metrics to dispatch via worker thread(s).

    This is a singleton class, so any instantiation will return the same object
    instance within the current process.

    The `init()` method must be called in order to create and start the 
    worker threads. Metrics can be added before or after `init()` is called 
    and they will be processed in order.

    """

    # keeps track of the single instance of the class
    __instance = None


    def __new__(cls, *args, **kwargs):
        """Ensures only one instance of the metrics queue exists."""

        # create the queue instance if it hasn't been created already
        if not cls.__instance:

            # remember the instance so that no more are created
            metrics_queue = super(
                MetricsDispatchQueueSingleton, cls).__new__(
                    cls, *args, **kwargs)

            # False until init() is called
            metrics_queue._initialized = False

            # The underlying Queue.Queue instance
            metrics_queue._queue = Queue()

            cls.__instance = metrics_queue

        return cls.__instance


    def init(self, tk, workers=1, log=None):
        """Initialize the Queue by starting up the workers.

        :param tk: Toolkit api instance to use for sg connection.
            Forwarded to the worker threads.
        :param int workers: Number of worker threads to start.
        :param loggin.Logger log: Optional logger for debugging.
            Forwarded to the worker threads.

        Creates and starts worker threads for dispatching metrics. Only
        callable once. Subsequent calls are a no-op.

        """

        # Uncomment these lines to debug metrics
        import logging
        log = logging.getLogger('tk.metrics')
        log.addHandler(logging.StreamHandler())
        log.setLevel(logging.DEBUG)

        if self._initialized:
            if log:
                log.debug("Metrics queue already initialized. Doing nothing.")
            return

        # start the dispatch workers to use this queue
        for i in range(workers):
            worker = MetricsDispatchWorkerThread(tk, self._queue, log)
            worker.start()
            if log:
                log.debug("Added worker thread: %s" % (worker,))

        self._initialized = True


    def log(self, metric):
        """Add the metric to the queue for dispatching.

        :param ToolkitMetric metric: The metric to log.

        """
        self._queue.put(metric)


    @property
    def initialized(self):
        """True if the queue has been initialized."""
        return self._initialized


###############################################################################
# ToolkitMetric classes and subclasses

class ToolkitMetric(object):
    """Simple class representing tk metric data and destination endpoint."""

    API_ENDPOINT = "api3/register_metric"
    """Endpoint for registering metrics. Could be overridden by subclasses."""

    def __init__(self, data):
        """Initialize the object with a dictionary of metric data.
        
        :param dict data: A dictionary of metric data.
        
        """
        self._data = data

    def __str__(self):
        """Readable representation of the metric."""
        return "%s: %s" % (self.__class__, self._data)

    @property
    def data(self):
        """The underlying data this metric represents."""
        return self._data


class UserActivityMetric(ToolkitMetric):
    """Convenience class for a user activity metric."""

    def __init__(self, module, action):
        """Initialize the metric with the module and action information.
        
        :param str module: Name of the module in which action was performed.
        :param str action: The action that was performed.
        
        """
        super(UserActivityMetric, self).__init__({
            "mode": "user_activity",
            "module": module,
            "action": action,
        })


class UserAttributeMetric(ToolkitMetric):
    """Convenience class for a user attribute metric."""

    def __init__(self, attr_name, attr_value):
        """Initialize the metric with the attribute name and value.
        
        :param str attr_name: Name of the attribute.
        :param str attr_value: The value of the attribute.

        """
        super(UserAttributeMetric, self).__init__({
            "mode": "user_attribute",
            "attr_name": attr_name,
            "attr_value": attr_value,
        })


###############################################################################
# metrics logging convenience functions

def log_metric(metric):
    """Log a Toolkit metric.
    
    :param ToolkitMetric metric: The metric to log.

    This method simply adds the metric to the dispatch queue.
    
    """
    MetricsDispatchQueueSingleton().log(metric)


def log_user_activity_metric(module, action):
    """Convenience method for logging a user activity metric.

    :param str module: The module the activity occured in.
    :param str action: The action the user performed.

    """
    log_metric(UserActivityMetric(module, action))

    
def log_user_attribute_metric(attr_name, attr_value):
    """Convenience method for logging a user attribute metric.

    :param str attr_name: The name of the attribute.
    :param str attr_value: The value of the attribute to log.

    """
    log_metric(UserAttributeMetric(attr_name, attr_value))


