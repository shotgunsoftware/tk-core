# coding: latin-1
#
# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.


from mock import patch

from tank.util.metrics import (
    MetricsQueueSingleton,
    MetricsDispatchWorkerThread,
    ToolkitMetric,
    EventMetric,
    log_metric,
    log_event_metric,
    log_user_activity_metric,
    log_user_attribute_metric,
)

from tank_test.tank_test_base import *
from tank.authentication import ShotgunAuthenticator

import os
import json
import time
import threading
import urllib2


class TestToolkitMetric(TankTestBase):
    """Cases testing tank.util.metrics.ToolkitMetric class"""

    def test_data_property(self):
        """Object has a data dictionary that matches args."""

        in_data = {
            "type": "user_activity",
            "module": "Tank Metrics Unit Test",
            "action": "ToolkitMetric.data property test",
        }
        obj = ToolkitMetric(in_data)
        self.assertTrue(hasattr(obj, 'data'))
        self.assertIsInstance(obj.data, type(in_data))


class TestEventMetric(TankTestBase):
    """Cases testing tank.util.metrics.EventMetric class"""

    def test_data_property(self):
        """Object has a data dictionary that matches args."""

        obj = EventMetric("App", "Testing Data Property")
        self.assertTrue(hasattr(obj, 'data'))
        self.assertIsInstance(obj.data, dict)
        metric = obj.data
        self.assertTrue("event_group" in metric)
        self.assertTrue("event_name" in metric)
        self.assertTrue("event_property" in metric)

    def test_init_with_invalid_parameters(self):
        """ Simply assert that the constructor is exception free and is
            able to deal with invalid parameters and various type of extra
            properties.

            Also tests the '_add_system_info_properties' method which
            gets called in constructor
            """

        try:
            EventMetric(None, "Testing No event group"),
            EventMetric("No event name", None),
            EventMetric("No event name", None, None),
            EventMetric("No event name", None, {}),
            EventMetric(None, None),
            EventMetric({}, {}),
            EventMetric([], []),
        except Exception, e:
            self.fail(
                "Creating an instance of 'EventMetric' failed unexpectedly: %s", (e)
            )

    def test_init_with_valid_parameters(self):
        """ Simply assert that the constructor is exception free.

            Also tests the '_add_system_info_properties' method which
            gets called in constructor
            """
        try:

            EventMetric("App", "Test Log Metric without additional properties")

            EventMetric("App", "Test Log Metric with additional properties",
                properties={
                    "IntProp": 2,
                    "BoolProp": True,
                    "StringProp": "This is a test string",
                    "DictProp": {"Key1": "value1", "Key2": "Value2"}
                }
            )

        except Exception, e:
            self.fail(
                "Creating an instance of 'EventMetric' failed unexpectedly: %s" % (e)
            )

    def test_usage_of_extra_properties(self):
        """ Simply assert usage of the properties parameter is exception free. """
        EventMetric("App", "Test add_event_property", None)

        EventMetric("App", "Test add_event_property",
            properties={
                "IntProp": 2,
                "BoolProp": True,
                "StringProp": "This is a test string",
                "DictProp": {"Key1": "value1", "Key2": "Value2"},
                "ListProp": [1, 2, 3, 4, 5]
            }
        )

class TestMetricsDispatchWorkerThread(TankTestBase):

    METRIC_ENDPOINT = "api3/track_metrics/"
    SLEEP_INTERVAL = 0.25

    def _create_context(self):
        """
        Helper test init method for setting up a bogus context
        just so we can run the engine.
        """
        some_path = os.path.join(self.project_root, "sequences", "Seq", "shot_code", "step_name")
        self.context = self.tk.context_from_path(some_path)

    def _authenticate(self):
        # Need to set authenticated user prior to MetricDispatcher.start below
        user = ShotgunAuthenticator().create_script_user(
            "script_user", "script_key", "https://abc.shotgunstudio.com"
        )
        tank.set_authenticated_user(user)
        self.addCleanup(self._de_authenticate)

    def _de_authenticate(self):
        tank.util.shotgun.connection._g_sg_cached_connections = threading.local()
        tank.set_authenticated_user(None)

    def _create_engine(self):

        # Reduce the interval time constant to speed up the test
        # This is fine since we're actually NOT posting to any real website.
        MetricsDispatchWorkerThread.DISPATCH_INTERVAL = 0.25

        # The environment is defined <tk-core>/tests/fixtures/config/env/test.yml
        engine_name = "test_engine"
        self._cur_engine = tank.platform.start_engine(engine_name, self.tk, self.context)

        self.addCleanup(self._destroy_engine)

    def _destroy_engine(self):
        cur_engine = tank.platform.current_engine()
        if cur_engine:
            cur_engine.destroy()

    def _setup_shotgun(self, server_caps):

        # Override what's in TestTantBase with 'older' server caps
        self.mockgun.server_caps = server_caps

        self.setup_fixtures()

        self._create_context()

        self._shotgun = tank.util.shotgun
        tank.util.shotgun.connection._g_sg_cached_connections = threading.local()

        # Clear cached appstore connection
        tank.set_authenticated_user(None)

        # Prevents an actual connection to a Shotgun site.
        self._server_caps_mock = patch("tank_vendor.shotgun_api3.Shotgun.server_caps")
        self._server_caps_mock.start()
        self.addCleanup(self._server_caps_mock.stop)

        # Avoids crash because we're not in a pipeline configuration.
        self._get_api_core_config_location_mock = patch(
            "tank.util.shotgun.connection.__get_api_core_config_location",
            return_value="unused_path_location"
        )
        self._get_api_core_config_location_mock.start()
        self.addCleanup(self._get_api_core_config_location_mock.stop)

        # Mocks app store script user credentials retrieval
        self._get_app_store_key_from_shotgun_mock = patch(
            "tank.descriptor.io_descriptor.appstore.IODescriptorAppStore._IODescriptorAppStore__get_app_store_key_from_shotgun",
            return_value=("abc", "123")
        )
        self._get_app_store_key_from_shotgun_mock.start()
        self.addCleanup(self._get_app_store_key_from_shotgun_mock.stop)

        self._authenticate()
        self._create_engine()

        # Patch & Mock the `urlopen` method
        self._urlopen_mock = patch('urllib2.urlopen')
        self._mocked_method = self._urlopen_mock.start()

    def setUp(self):
        super(TestMetricsDispatchWorkerThread, self).setUp()

        # Storing the value as it might have be changed in tests
        self._saved_dispatch_interval = MetricsDispatchWorkerThread.DISPATCH_INTERVAL

        self._urlopen_mock = None
        self._mocked_method = None

    def tearDown(self):

        # Unpatch the `urlopen` method
        if self._mocked_method:
            # If `_mocked_method` we did started `_urlopen_mock
            self._urlopen_mock.stop()
            self._urlopen_mock = None
            self._mocked_method = None

        self._destroy_engine()

        # Restore value as it might have been changed in tests
        MetricsDispatchWorkerThread.DISPATCH_INTERVAL = self._saved_dispatch_interval

        # important to call base class so it can clean up memory
        super(TestMetricsDispatchWorkerThread, self).tearDown()

    def _get_urllib2_request_calls(self, return_only_calls_after_reset=False):
        """
        Helper test method that traverses `mock_calls` and return a list of `urllib2.Request` specific calls

        :return: a list a `urllib2.Request` specific calls
        """

        mocked_request_calls = []

        if return_only_calls_after_reset:
            # Filtering, only calls after reset will be included.
            found_reset = False
        else:
            # No filter, causes all calls to be included
            found_reset = True

        # Traverse mocked_calls to find the user activity logged above
        for mocked_call in self._mocked_method.mock_calls:
            if not found_reset:
                if "call.reset()" in str(mocked_call):
                    found_reset = True

            if found_reset and "urllib2.Request" in str(mocked_call):
                # TODO: find out what class type is 'something'
                for something in mocked_call:
                    for instance in something:
                        if isinstance(instance, urllib2.Request):
                            mocked_request_calls.append(instance)

        return mocked_request_calls

    def _get_metrics(self, return_only_calls_after_reset=False):
        """

        Helper test method that traverses `mock_calls` and return a list of individual metrics.

        NOTE: The method also filters out 'engine init' that is usually present.

        :return: a list a metric dictionaries
        """
        metrics = []
        for mocked_request in self._get_urllib2_request_calls(return_only_calls_after_reset):
            data = json.loads(mocked_request.get_data())
            # Now that we have request data
            # Traverse the metrics to find the one we've logged above
            if 'metrics' in data:
                for metric in data['metrics']:
                    metrics.append(metric)

        return metrics

    def _helper_test_end_to_end(self, metric):
        """
        Helper method for the test_end_to_end_* tests. Allows a deeper and
        more complete test cycle of creating, submitting and receiving
        a mocked-server response.
        """

        # Setup test fixture, engine and context with newer server caps
        #
        # Define a local server caps mock locally since it only
        # applies to this particular test
        class server_capsMock:
            def __init__(self):
                self.version = (7, 4, 0)

        self._setup_shotgun(server_capsMock())

        # Save a few values for comparing on the other side
        METRIC_EVENT_NAME = metric.data["event_name"]

        # Make at least one metric related call!
        log_event_metric(metric)

        TIMEOUT_SECONDS = 4 * MetricsDispatchWorkerThread.DISPATCH_INTERVAL
        timeout = time.time() + TIMEOUT_SECONDS

        # Simple flag just to differenciate one of two conditions:
        # a) didn't even find a mocked request call
        # b) a + didn't find expected metric
        found_urllib2_request_call = False

        while time.time() < timeout:
            time.sleep(TestMetricsDispatchWorkerThread.SLEEP_INTERVAL)

            for mocked_request in self._get_urllib2_request_calls():
                found_urllib2_request_call = True
                data = json.loads(mocked_request.get_data())
                # Now that we have request data
                # Traverse the metrics to find the one we've logged above
                if 'metrics' in data:
                    # At this point we found Request calls with 'metrics' data
                    # Although we've not found our particular metric
                    # We can already verify that the logged metric was made using the right URL
                    url = mocked_request.get_full_url()
                    self.assertTrue(TestMetricsDispatchWorkerThread.METRIC_ENDPOINT in url,
                                    "Not using the latest metric '%s' endpoint" % (
                                        TestMetricsDispatchWorkerThread.METRIC_ENDPOINT))

                    for metric in data['metrics']:
                        if ("event_name" in metric) and (METRIC_EVENT_NAME == metric['event_name']):
                            # Nothing else FOR NOW to test, we can report success by bypassing
                            # timeout failure down below.

                            # Tests all of the received metric properties that went through two conversions
                            return metric

        if(found_urllib2_request_call):
            self.fail("Timed out waiting for expected metric.")
        else:
            self.fail("Timed out waiting for a mocked urlopen request call.")

    def test_end_to_end_basic(self):
        """
        Test a complete cycle using non proplemtic metric object.

        """
        metric = EventMetric("App", "Test test_end_to_end",
            properties={
                "IntProp": 2,
                "BoolProp": True,
                "StringProp": "This is a test string",
                "DictProp": {"Key1": "value1", "Key2": "Value2"},
                "ListProp": [1, 2, 3, 4, 5]
            }
        )
        server_received_metric = self._helper_test_end_to_end(metric)

        # Test the metric that was encoded and transmitted to the mock server
        self.assertTrue("event_group" in server_received_metric)
        self.assertTrue("event_name" in server_received_metric)
        self.assertTrue("event_property" in server_received_metric)
        self.assertTrue("IntProp" in server_received_metric["event_property"])
        self.assertTrue("BoolProp" in server_received_metric["event_property"])
        self.assertTrue("StringProp" in server_received_metric["event_property"])
        self.assertTrue("DictProp" in server_received_metric["event_property"])
        self.assertTrue("ListProp" in server_received_metric["event_property"])

        self.assertTrue(isinstance(server_received_metric["event_group"], unicode))
        self.assertTrue(isinstance(server_received_metric["event_name"], unicode))
        self.assertTrue(isinstance(server_received_metric["event_property"], dict))
        self.assertTrue(isinstance(server_received_metric["event_property"]["IntProp"], int))
        self.assertTrue(isinstance(server_received_metric["event_property"]["IntProp"], int))
        self.assertTrue(isinstance(server_received_metric["event_property"]["BoolProp"], bool))
        self.assertTrue(isinstance(server_received_metric["event_property"]["StringProp"], unicode))
        self.assertTrue(isinstance(server_received_metric["event_property"]["DictProp"], dict))
        self.assertTrue(isinstance(server_received_metric["event_property"]["ListProp"], list))

    # Not currently supporting usage of non-ascii7 charcaters, request would need to be escaped"
    def test_end_to_end_with_non_ascii7_chars(self):
        """
        Test a complete cycle of creating, submitting and receiving a server
        response using non-ascii-7 characaters in the request.
        """
        metric = EventMetric("App", "Test test_end_to_end",
            properties={
                "Name with accents": "Éric Hébert",
                "String with tricky characters": "''\"\\//%%$$?&?$^^,¨¨`"
            }
        )
        self._helper_test_end_to_end(metric)

    def test_not_logging_older_tookit(self):
        """
        Test that logging metrics is not possible from an older version
        of toolkit as it can't even pass metric version check and therefore
        won't call urllib2.urlopen mock calls
        """

        # Define a local server caps mock locally since it only
        # applies to this particular test
        class server_capsMock:
            def __init__(self):
                self.version = (6, 3, 11)

        metric = EventMetric("App", "Test Log Metric with old server")
        log_event_metric(metric)

        # Setup test fixture, engine and context with newer server caps
        self._setup_shotgun(server_capsMock())

        # Make at least one metric related call
        log_event_metric(metric)

        # Because we are testing for the absence of a Request
        # we do have to wait longer for the test to be valid.
        TIMEOUT_SECONDS = 4 * MetricsDispatchWorkerThread.DISPATCH_INTERVAL
        timeout = time.time() + TIMEOUT_SECONDS

        while time.time() < timeout:
            time.sleep(TestMetricsDispatchWorkerThread.SLEEP_INTERVAL)

            for metric in self._get_metrics():
                self.fail("Was not expecting any request mock calls since code in metrics.py "
                          "should have been filtered out based on server caps. version.")

        #
        # If we get here, this is SUCCESS as we didn't receive urllib2.Request calls
        #

    def test_misc_constants(self):

        # Verify that the endpoint was indeed updated
        self.assertEqual(TestMetricsDispatchWorkerThread.METRIC_ENDPOINT, MetricsDispatchWorkerThread.API_ENDPOINT)
        # Verify that process interval is adequate. This is currently arbitrary but
        # 5 seconds does seems to be reasonable for now.
        # This is subject to change as we start receiving metrics again.
        #
        # Do provide a reason ( here and in modified metrics.py code
        # why either value might be changed
        #
        self.assertEquals(5, MetricsDispatchWorkerThread.DISPATCH_INTERVAL)
        # NOTE: that current SG server code reject batches larger than 10.
        self.assertEqual(10, MetricsDispatchWorkerThread.DISPATCH_BATCH_SIZE)


class TestMetricsQueueSingleton(TankTestBase):
    """Cases testing tank.util.metrics.MetricsQueueSingleton class."""

    def test_singleton(self):
        """Multiple instantiations return same instance."""

        obj1 = MetricsQueueSingleton()
        obj2 = MetricsQueueSingleton()
        obj3 = MetricsQueueSingleton()
        self.assertTrue(obj1 == obj2 == obj3)


class TestMetricsDepricatedFunctions(TankTestBase):
    """ Cases testing tank.util.metrics of depricated functions

        Test that the `log_metric`, `log_user_activity_metric` and
        `log_user_attribute_metric` methods are depricated by creating a
        mock of the `MetricsQueueSingleton.log` method and then
        verifiying whether or not it was called.

        Also test that method still exist for retro-compatibility although
        there're basically empty no-op methods.
    """

    def setUp(self):
        super(TestMetricsDepricatedFunctions, self).setUp()

        # Setting up the mocked method
        self._metrics_queue_singleton_log_mock = patch("tank.util.metrics.MetricsQueueSingleton.log")
        self._mocked_method = self._metrics_queue_singleton_log_mock.start()

    def tearDown(self):
        if self._mocked_method:
            self._metrics_queue_singleton_log_mock.stop()
            self._metrics_queue_singleton_log_mock = None
            self._mocked_method.reset_mock()
            self._mocked_method = None

        super(TestMetricsDepricatedFunctions, self).tearDown()

    def test_log_event_metric(self):
        # Self testing that the mock setup is correct
        # by trying out a non-depricated method.
        log_event_metric(EventMetric("App", "Testing Own Test Mock"))
        self.assertTrue(self._mocked_method.called, "Was expecting a call to the "
                                                    "`MetricsQueueSingleton.log`"
                                                    "method from the non-depricated "
                                                    "`log_event_metric` method.")

    def test_log_metric(self):
        # It is ok to provide an empty metric dictionary since we just want to
        # check that the `MetricsQueueSingleton.log` is called or not.
        log_metric({})
        self.assertFalse(self._mocked_method.called, "Was not expecting a call to the "
                                                     "`MetricsQueueSingleton.log` "
                                                     "method from the depricated "
                                                     "`log_metric` method.")

    def test_log_user_attribute_metric(self):

        log_user_attribute_metric(attr_name="Some attr. name", attr_value="Some attr. value")
        self.assertFalse(self._mocked_method.called, "Was not expecting a call to the "
                                                     "`MetricsQueueSingleton.log` "
                                                     "method from the depricated "
                                                     "`log_user_attribute_metric` method.")

    def test_log_user_activity_metric(self):

        log_user_activity_metric(module="Some some name", action="Some action")
        self.assertFalse(self._mocked_method.called, "Was not expecting a call to the "
                                                     "`MetricsQueueSingleton.log` "
                                                     "method from the depricated "
                                                     "`log_user_activity_metric` method.")


class TestMetricsFunctions(TankTestBase):
    """Cases testing tank.util.metrics functions"""

    def test_log_event_metric_with_bad_metrics(self):

        bad_metrics = [
            EventMetric(None, "No event group"),
            EventMetric("No event name", None),
            EventMetric(None, None),
            EventMetric({}, {}),
            EventMetric([], []),
        ]

        # make sure no exceptions on bad metrics
        for metric in bad_metrics:
            try:
                log_event_metric(metric)
            except Exception, e:
                self.fail(
                    "log_metric() failed unexpectedly on bad metric (%s): %s",
                    (metric, e)
                )

    def test_log_event_metric_with_good_metrics(self):

        m1 = EventMetric("App", "Testing Log Metric without additional properties")
        m2 = EventMetric("App", "Testing Log Metric with additional properties",
            properties={
                "IntProp": 2,
                "BoolProp": True,
                "StringProp": "This is a test string",
                "DictProp": {"Key1": "value1", "Key2": "Value2"}
            }
        )

        good_metrics = [m1, m2]

        # make sure no exceptions on good metrics
        for metric in good_metrics:
            try:
                log_event_metric(metric)
            except Exception, e:
                self.fail(
                    "log_metric() failed unexpectedly on good metric (%s): %s",
                    (metric, e)
                )

    def test_log_event_metric_with_invalid_params(self):

        # Expecting an exception from a non EventMetric parameter

        with self.assertRaises(TypeError):
            log_event_metric(None)

        with self.assertRaises(TypeError):
            log_event_metric([], event_name=None)

        with self.assertRaises(TypeError):
            log_event_metric({})

        with self.assertRaises(TypeError):
            log_event_metric("String Parameter")

