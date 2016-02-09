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

from collections import deque
from threading import Thread, Lock
import time
import urllib2
 
from ..platform import constants as platform_constants

# use api json to cover py 2.5
from tank_vendor import shotgun_api3
json = shotgun_api3.shotgun.json


###############################################################################
# Metrics dispatch Thread and Queue classes

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
            metrics_queue._lock = Lock()
            metrics_queue._workers = []

            # The underlying collections.deque instance
            metrics_queue._queue = deque()

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
        #import logging
        #log = logging.getLogger('sgtk.metrics')
        #log.addHandler(logging.StreamHandler())
        #log.setLevel(logging.DEBUG)

        if self._initialized:
            if log:
                log.debug("Metrics queue already initialized. Doing nothing.")
            return

        # if metrics are not supported, then no reason to start up any workers.
        if not self._metrics_supported(tk.shotgun):
            if log:
                log.debug("This version of SG doesn't support metrics logging.")
            return

        # start the dispatch workers to use this queue
        for i in range(workers):
            worker = _MetricsDispatchWorkerThread(tk, self, log)
            worker.start()
            if log:
                log.debug("Added worker thread: %s" % (worker,))
            self._workers.append(worker)

        self._initialized = True

    def log(self, metric):
        """Add the metric to the queue for dispatching.

        :param ToolkitMetric metric: The metric to log.

        """
        self._lock.acquire()
        self._queue.append(metric)
        self._lock.release()

    @property
    def initialized(self):
        """True if the queue has been initialized."""
        return self._initialized

    @property
    def workers(self):
        """A list of initialized workers for the queue."""
        return self._workers

    def _get_metrics(self, count=None):
        """Return `count` metrics.

        :param int count: The number of pending metrics to return.

        If `count` is not supplied, or greater than the number of pending
        metrics, returns all metrics.

        Should never raise an exception.

        """

        metrics = []

        self._lock.acquire()

        num_pending = len(self._queue)

        # there are pending metrics
        if num_pending:

            # determine how many metrics to retrieve
            if not count or count > num_pending:
                count = num_pending

            try:
                # would be nice to be able to pop N from deque. oh well.
                metrics = [self._queue.popleft() for i in range(0, count)]
            except Exception:
                pass

        self._lock.release()

        return metrics

    def _metrics_supported(self, sg_connection):
        """Returns True if server supports the metrics api endpoint."""

        # TODO: update the version number once the endpoint is available
        self._metrics_ok = (
            sg_connection.server_caps.version and
            sg_connection.server_caps.version >= (7, 0, 0)
        )

        # TODO: remove after testing
        self._metrics_ok = True
        return self._metrics_ok


class _MetricsDispatchWorkerThread(Thread):
    """Worker thread for dispatching metrics to sg logging endpoint.

    Given a queue where metrics are logged in the client code, once started,
    this worker will dispatch them to the shotgun api endpoint. The worker
    retrieves any pending metrics after the `DISPATCH_INTERVAL` and sends
    them all in a single request to sg.

    This thread runs as a `daemon` in order to prevent process shutdown
    from waiting until all metrics are processed.

    """

    API_ENDPOINT = "api3/log_metrics/"
    """SG API endpoint for logging metrics."""

    DISPATCH_INTERVAL = 5
    """Worker will wait this long between metrics dispatch attempts."""

    DISPATCH_BATCH_SIZE = 0
    """Worker will dispatch this many metrics at a time, or all if <= 0."""

    def __init__(self, tk, metrics_queue, log=None):
        """Initialize the worker thread.

        :params tk: Toolkit api instance.
        :params metrics_queue: Holds metrics to log in SG.
        :params logging.Logger log: Logger for debugging purposes.

        """

        super(_MetricsDispatchWorkerThread, self).__init__()

        self._tk = tk
        self._log = log
        self._metrics_queue = metrics_queue

        # don't wait for this thread to exit
        self.daemon = True

    def run(self):
        """Runs a loop to dispatch metrics as they're added to the queue."""

        # The thread is a daemon. Let it run for the duration of the process
        while True:

            # get the next available metric and dispatch it
            try:
                metrics = self._metrics_queue._get_metrics(
                    self.DISPATCH_BATCH_SIZE)
                if metrics:
                    self._dispatch(metrics)
            except Exception, e:
                if self._log:
                    self._log.error("Error dispatching metrics: %s" % (e,))
            finally:
                # wait before dispatching more metrics
                time.sleep(self.DISPATCH_INTERVAL)

    def _dispatch(self, metrics):
        """Dispatch the supplied metric to the sg api registration endpoint.

        :param Metric metrics: The Toolkit metric to dispatch.

        """

        # get this thread's sg connection via tk api
        sg_connection = self._tk.shotgun

        # handle proxy setup by pulling the proxy details from the main
        # shotgun connection
        if sg_connection.config.proxy_handler:
            opener = urllib2.build_opener(sg_connection.config.proxy_handler)
            urllib2.install_opener(opener)

        # build the full endpoint url with the shotgun site url
        url = "%s/%s" % (sg_connection.base_url, self.API_ENDPOINT)

        # construct the payload with the auth args and metrics data
        payload = {
            "auth_args": {
                "session_token": sg_connection.get_session_token()
            },
            "metrics": [m.data for m in metrics]
        }
        payload_json = json.dumps(payload)

        header = {'Content-Type': 'application/json'}
        request = urllib2.Request(url, payload_json, header)
        response = urllib2.urlopen(request)

        # execute the log_metrics core hook
        self._tk.execute_core_hook(
            platform_constants.TANK_LOG_METRICS_HOOK_NAME,
            tk=self._tk,
            metrics=metrics,
        )

        if self._log:
            for metric in metrics:
                self._log.debug("Logged metric: %s" % (metric,))


###############################################################################
# ToolkitMetric classes and subclasses

class ToolkitMetric(object):
    """Simple class representing tk metric data."""

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
            "type": "user_activity",
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
            "type": "user_attribute",
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

