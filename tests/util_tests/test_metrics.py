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
    EventMetric,
    log_metric,
    log_user_activity_metric,
    log_user_attribute_metric,
)

import tank
from tank_test.tank_test_base import setUpModule # noqa
from tank_test.tank_test_base import TankTestBase
from tank.authentication import ShotgunAuthenticator

import os
import json
import time
import threading
import urllib2


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
        self.assertTrue("event_properties" in metric)

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
        EventMetric("App", "Test add_event_properties", None)

        EventMetric("App", "Test add_event_properties",
            properties={
                "IntProp": 2,
                "BoolProp": True,
                "StringProp": "This is a test string",
                "DictProp": {"Key1": "value1", "Key2": "Value2"},
                "ListProp": [1, 2, 3, 4, 5]
            }
        )

    def test_group_definition_exists(self):
        """
        Simply test that standard group definitions havent't been deleted or renamed.
        """
        self.assertTrue(hasattr(EventMetric, "GROUP_APP"))
        self.assertTrue(hasattr(EventMetric, "GROUP_TASKS"))
        self.assertTrue(hasattr(EventMetric, "GROUP_MEDIA"))
        self.assertTrue(hasattr(EventMetric, "GROUP_TOOLKIT"))
        self.assertTrue(hasattr(EventMetric, "GROUP_NAVIGATION"))
        self.assertTrue(hasattr(EventMetric, "GROUP_PROJECTS"))

    def test_key_definition_exist(self):
        """
        Simply test that standard key definitions havent't been deleted or renamed.
        """
        self.assertTrue(hasattr(EventMetric, "KEY_ACTION_TITLE"))
        self.assertTrue(hasattr(EventMetric, "KEY_APP"))
        self.assertTrue(hasattr(EventMetric, "KEY_APP_VERSION"))
        self.assertTrue(hasattr(EventMetric, "KEY_COMMAND"))
        self.assertTrue(hasattr(EventMetric, "KEY_ENGINE"))
        self.assertTrue(hasattr(EventMetric, "KEY_ENGINE_VERSION"))
        self.assertTrue(hasattr(EventMetric, "KEY_ENTITY_TYPE"))
        self.assertTrue(hasattr(EventMetric, "KEY_HOST_APP"))
        self.assertTrue(hasattr(EventMetric, "KEY_HOST_APP_VERSION"))
        self.assertTrue(hasattr(EventMetric, "KEY_PUBLISH_TYPE"))


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
        self._urlopen_mock = patch("urllib2.urlopen")
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
            if "metrics" in data:
                for metric in data["metrics"]:
                    metrics.append(metric)

        return metrics

    def _helper_test_end_to_end(self, group, name, properties):
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
        METRIC_EVENT_NAME = name

        # Make at least one metric related call!
        EventMetric.log(group, name, properties)

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
                if "metrics" in data:
                    # At this point we found Request calls with 'metrics' data
                    # Although we've not found our particular metric
                    # We can already verify that the logged metric was made using the right URL
                    url = mocked_request.get_full_url()
                    self.assertTrue(TestMetricsDispatchWorkerThread.METRIC_ENDPOINT in url,
                                    "Not using the latest metric '%s' endpoint" % (
                                        TestMetricsDispatchWorkerThread.METRIC_ENDPOINT))

                    for metric in data["metrics"]:
                        if ("event_name" in metric) and (METRIC_EVENT_NAME == metric["event_name"]):
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
        Test a complete cycle using non problematic metric object.
        """
        server_received_metric = self._helper_test_end_to_end(
            EventMetric.GROUP_TOOLKIT,
            "Testing basic end to end functionality",
            properties={
                EventMetric.KEY_HOST_APP: "Maya",
                EventMetric.KEY_HOST_APP_VERSION: "2017",
                EventMetric.KEY_APP: "tk-multi-publish2",
                EventMetric.KEY_APP_VERSION: "v0.2.3",
                "IntProp": 2,
                "BoolProp": True,
                "DictProp": {"Key1": "value1", "Key2": "Value2"},
                "ListProp": [1, 2, 3, 4, 5]
            }
        )

        # Test the metric that was encoded and transmitted to the mock server
        self.assertTrue("event_group" in server_received_metric)
        self.assertTrue("event_name" in server_received_metric)
        self.assertTrue("event_properties" in server_received_metric)

        self.assertTrue(EventMetric.KEY_HOST_APP in server_received_metric["event_properties"])
        self.assertTrue(EventMetric.KEY_HOST_APP_VERSION in server_received_metric["event_properties"])
        self.assertTrue(EventMetric.KEY_APP in server_received_metric["event_properties"])
        self.assertTrue(EventMetric.KEY_APP_VERSION in server_received_metric["event_properties"])

        self.assertTrue("IntProp" in server_received_metric["event_properties"])
        self.assertTrue("BoolProp" in server_received_metric["event_properties"])
        self.assertTrue("DictProp" in server_received_metric["event_properties"])
        self.assertTrue("ListProp" in server_received_metric["event_properties"])

        self.assertTrue(isinstance(server_received_metric["event_group"], unicode))
        self.assertTrue(isinstance(server_received_metric["event_name"], unicode))
        self.assertTrue(isinstance(server_received_metric["event_properties"], dict))

        self.assertTrue(isinstance(server_received_metric["event_properties"][EventMetric.KEY_HOST_APP], unicode))
        self.assertTrue(isinstance(server_received_metric["event_properties"][EventMetric.KEY_HOST_APP_VERSION], unicode))
        self.assertTrue(isinstance(server_received_metric["event_properties"][EventMetric.KEY_APP], unicode))
        self.assertTrue(isinstance(server_received_metric["event_properties"][EventMetric.KEY_APP_VERSION], unicode))

        self.assertTrue(isinstance(server_received_metric["event_properties"]["IntProp"], int))
        self.assertTrue(isinstance(server_received_metric["event_properties"]["IntProp"], int))
        self.assertTrue(isinstance(server_received_metric["event_properties"]["BoolProp"], bool))
        self.assertTrue(isinstance(server_received_metric["event_properties"]["DictProp"], dict))
        self.assertTrue(isinstance(server_received_metric["event_properties"]["ListProp"], list))

    # Not currently supporting usage of non-ascii7 charcaters, request would need to be escaped"
    def _test_end_to_end_with_non_ascii7_chars(self):
        """
        Test a complete cycle of creating, submitting and receiving a server
        response using non-ascii-7 characaters in the request.
        """
        self._helper_test_end_to_end(
            "App",
            "Test test_end_to_end",
            properties={
                "Name with accents": "�ric H�bert",
                "String with tricky characters": "''\"\\//%%$$?&?$^^,��`"
            }
        )

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

        # Setup test fixture, engine and context with newer server caps
        self._setup_shotgun(server_capsMock())

        # Make at least one metric related call
        EventMetric.log("App", "Test Log Metric with old server")

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

    def test_maximum_queue_size(self):
        """
        Test that the dispatcher has a maximum queue size to prevent memory leak
        if the worker thread is not started. This test requires overriding what's
        being done in class setUp and deliberatly stopping the dispatcher worker tread.

        """

        # Stop the dispatcher worker thread

        self._destroy_engine()

        TEST_SIZE = 10 * MetricsQueueSingleton.MAXIMUM_QUEUE_SIZE
        for i in range(TEST_SIZE):
            EventMetric.log(
                "App",
                "Testing maximum queue size %d" % (i),
                properties={"Metric id": i}
            )

        queue = MetricsQueueSingleton()._queue
        self.assertTrue(len(queue) <= MetricsQueueSingleton.MAXIMUM_QUEUE_SIZE)

        # Test that the first item is indeed N items past the originally queued ones
        # Where N is TEST_SIZE minus size of queue
        oldest_metric = queue.popleft()
        metric_index = oldest_metric.data["event_properties"]["Metric id"]
        self.assertEqual(metric_index, TEST_SIZE - MetricsQueueSingleton.MAXIMUM_QUEUE_SIZE)

        # Finally, test that the newest item
        newest_metric = queue.pop()
        metric_index = newest_metric.data["event_properties"]["Metric id"]
        self.assertEqual(metric_index, TEST_SIZE - 1)


class TestMetricsQueueSingleton(TankTestBase):
    """Cases testing tank.util.metrics.MetricsQueueSingleton class."""

    def test_singleton(self):
        """Multiple instantiations return same instance."""

        obj1 = MetricsQueueSingleton()
        obj2 = MetricsQueueSingleton()
        obj3 = MetricsQueueSingleton()
        self.assertTrue(obj1 == obj2 == obj3)


class TestMetricsDeprecatedFunctions(TankTestBase):
    """ Cases testing tank.util.metrics of deprecated functions

        Test that the `log_metric`, `log_user_activity_metric` and
        `log_user_attribute_metric` methods are deprecated by creating a
        mock of the `MetricsQueueSingleton.log` method and then
        verifiying whether or not it was called.

        Also test that method still exist for retro-compatibility although
        there're basically empty no-op methods.
    """

    def setUp(self):
        super(TestMetricsDeprecatedFunctions, self).setUp()

        # Setting up the mocked method
        self._metrics_queue_singleton_log_mock = patch("tank.util.metrics.MetricsQueueSingleton.log")
        self._mocked_method = self._metrics_queue_singleton_log_mock.start()

    def tearDown(self):
        if self._mocked_method:
            self._metrics_queue_singleton_log_mock.stop()
            self._metrics_queue_singleton_log_mock = None
            self._mocked_method.reset_mock()
            self._mocked_method = None

        super(TestMetricsDeprecatedFunctions, self).tearDown()

    def test_log_event_metric(self):
        # Self testing that the mock setup is correct
        # by trying out a non-deprecated method.
        EventMetric.log("App", "Testing Own Test Mock")
        self.assertTrue(self._mocked_method.called, "Was expecting a call to the "
                                                    "`MetricsQueueSingleton.log`"
                                                    "method from the non-deprecated "
                                                    "`log_event_metric` method.")

    def test_log_metric(self):
        # It is ok to provide an empty metric dictionary since we just want to
        # check that the `MetricsQueueSingleton.log` is called or not.
        log_metric({})
        self.assertFalse(self._mocked_method.called, "Was not expecting a call to the "
                                                     "`MetricsQueueSingleton.log` "
                                                     "method from the deprecated "
                                                     "`log_metric` method.")

    def test_log_user_attribute_metric(self):

        log_user_attribute_metric(attr_name="Some attr. name", attr_value="Some attr. value")
        self.assertFalse(self._mocked_method.called, "Was not expecting a call to the "
                                                     "`MetricsQueueSingleton.log` "
                                                     "method from the deprecated "
                                                     "`log_user_attribute_metric` method.")

    def test_log_user_activity_metric(self):

        log_user_activity_metric(module="Some some name", action="Some action")
        self.assertFalse(self._mocked_method.called, "Was not expecting a call to the "
                                                     "`MetricsQueueSingleton.log` "
                                                     "method from the deprecated "
                                                     "`log_user_activity_metric` method.")


class TestMetricsFunctions(TankTestBase):
    """Cases testing tank.util.metrics functions"""

    def test_log_event_metric_with_bad_metrics(self):

        # make sure no exceptions on bad metrics
        try:
            EventMetric.log(None, "No event group"),
            EventMetric.log("No event name", None),
            EventMetric.log("No event name", "Using should causes test to fail"),
            EventMetric.log(None, None),
            EventMetric.log({}, {}),
            EventMetric.log([], []),
        except Exception, e:
            self.fail("log_metric() failed unexpectedly on bad metric: %s", (e))

    def test_log_event_metric_with_good_metrics(self):

        # make sure no exceptions on good metrics
        try:
            EventMetric.log("App", "Testing Log Metric without additional properties")
            EventMetric.log("App", "Testing Log Metric with additional properties",
                properties={
                     "IntProp": 2,
                     "BoolProp": True,
                     "StringProp": "This is a test string",
                     "DictProp": {"Key1": "value1", "Key2": "Value2"}
                 }
            )

        except Exception, e:
            self.fail("EventMetric.log() failed unexpectedly on good metric: %s", (e))


class TestHookLogMetrics(TankTestBase):
    """
    Tests general usage of the `tk-core/hook/log_metrics.py` hook
    """

    def test_log_metrics_hook_general_usage(self):
        """
        Tests general usage of the `tk-core/hook/log_metrics.py` hook

        TODO: Implement!
        """
        pass


class TestBundleMetrics(TankTestBase):
    """
    Class for testing metrics at Bundle level.
    """

    def setUp(self):
        super(TestBundleMetrics, self).setUp()
        self.setup_fixtures()
        
        # setup shot
        seq = {"type": "Sequence", "code": "seq_name", "id": 3}
        seq_path = os.path.join(self.project_root, "sequences", "seq_name")
        self.add_production_path(seq_path, seq)
        
        shot = {"type": "Shot", "code": "shot_name", "id": 2, "sg_sequence": seq, "project": self.project}
        shot_path = os.path.join(seq_path, "shot_name")
        self.add_production_path(shot_path, shot)
        
        step = {"type":"Step", "code": "step_name", "id": 4}
        self.shot_step_path = os.path.join(shot_path, "step_name")
        self.add_production_path(self.shot_step_path, step)

        self.test_resource = os.path.join(self.pipeline_config_root, "config", "foo", "bar.png")
        os.makedirs(os.path.dirname(self.test_resource))
        fh = open(self.test_resource, "wt")
        fh.write("test")
        fh.close()
        
        # Make sure we have an empty queue
        metrics_queue = MetricsQueueSingleton()
        metrics_queue.get_metrics()
        context = self.tk.context_from_path(self.shot_step_path)
        self.engine = tank.platform.start_engine("test_engine", self.tk, context)

    def tearDown(self):
        # engine is held as global, so must be destroyed.
        cur_engine = tank.platform.current_engine()
        if cur_engine:
            cur_engine.destroy()
        os.remove(self.test_resource)

        # important to call base class so it can clean up memory
        super(TestBundleMetrics, self).tearDown()

    @patch("tank.util.metrics.MetricsDispatcher.start")
    def test_bundle_metrics(self, mocked_start):
        """
        Test metrics logged by bundles.
        """
        engine = self.engine
        metrics_queue = MetricsQueueSingleton()
        # Make sure we don't have a dispatcher running
        if engine._metrics_dispatcher:
            self.assertFalse(engine._metrics_dispatcher.workers)
        metrics = metrics_queue.get_metrics()
        self.assertEqual(len(metrics), 1)
        # We should have a "Launched Software" metric, check it is right
        data = metrics[0].data
        self.assertEqual(data["event_group"], EventMetric.GROUP_TOOLKIT)
        self.assertEqual(data["event_name"], "Launched Software")
        self.assertEqual(data["event_properties"][EventMetric.KEY_HOST_APP], "unknown")
        self.assertEqual(data["event_properties"][EventMetric.KEY_HOST_APP_VERSION], "unknown")
        self.assertEqual(data["event_properties"][EventMetric.KEY_ENGINE], engine.name)
        self.assertEqual(data["event_properties"][EventMetric.KEY_ENGINE_VERSION], engine.version)
        self.assertFalse(EventMetric.KEY_APP in data["event_properties"])
        self.assertFalse(EventMetric.KEY_APP_VERSION in data["event_properties"])
        self.assertFalse(EventMetric.KEY_COMMAND in data["event_properties"])
        # Log a metric and check it
        engine.log_metric("Engine test")
        metrics = metrics_queue.get_metrics()
        self.assertEqual(len(metrics), 1)
        data = metrics[0].data
        self.assertEqual(data["event_group"], EventMetric.GROUP_TOOLKIT)
        self.assertEqual(data["event_name"], "Engine test")
        self.assertEqual(data["event_properties"][EventMetric.KEY_HOST_APP], "unknown")
        self.assertEqual(data["event_properties"][EventMetric.KEY_HOST_APP_VERSION], "unknown")
        self.assertEqual(data["event_properties"][EventMetric.KEY_ENGINE], engine.name)
        self.assertEqual(data["event_properties"][EventMetric.KEY_ENGINE_VERSION], engine.version)
        self.assertFalse(EventMetric.KEY_APP in data["event_properties"])
        self.assertFalse(EventMetric.KEY_APP_VERSION in data["event_properties"])
        self.assertFalse(EventMetric.KEY_COMMAND in data["event_properties"])
        # Make sure we have at least one app with a framework, this is checked
        # after the loops
        able_to_test_a_framework = False
        # Check metrics logged from apps
        for app in engine.apps.itervalues():
            app.log_metric("App test")
            metrics = metrics_queue.get_metrics()
            self.assertEqual(len(metrics), 1)
            data = metrics[0].data
            self.assertEqual(data["event_group"], EventMetric.GROUP_TOOLKIT)
            self.assertEqual(data["event_name"], "App test")
            self.assertEqual(data["event_properties"][EventMetric.KEY_HOST_APP], "unknown")
            self.assertEqual(data["event_properties"][EventMetric.KEY_HOST_APP_VERSION], "unknown")
            self.assertEqual(data["event_properties"][EventMetric.KEY_ENGINE], engine.name)
            self.assertEqual(data["event_properties"][EventMetric.KEY_ENGINE_VERSION], engine.version)
            self.assertEqual(data["event_properties"][EventMetric.KEY_APP], app.name)
            self.assertEqual(data["event_properties"][EventMetric.KEY_APP_VERSION], app.version)
            self.assertFalse(EventMetric.KEY_COMMAND in data["event_properties"])
            app.log_metric("App test", command_name="Blah")
            metrics = metrics_queue.get_metrics()
            self.assertEqual(len(metrics), 1)
            data = metrics[0].data
            self.assertEqual(data["event_group"], EventMetric.GROUP_TOOLKIT)
            self.assertEqual(data["event_name"], "App test")
            self.assertEqual(data["event_properties"][EventMetric.KEY_HOST_APP], "unknown")
            self.assertEqual(data["event_properties"][EventMetric.KEY_HOST_APP_VERSION], "unknown")
            self.assertEqual(data["event_properties"][EventMetric.KEY_ENGINE], engine.name)
            self.assertEqual(data["event_properties"][EventMetric.KEY_ENGINE_VERSION], engine.version)
            self.assertEqual(data["event_properties"][EventMetric.KEY_APP], app.name)
            self.assertEqual(data["event_properties"][EventMetric.KEY_APP_VERSION], app.version)
            self.assertEqual(data["event_properties"][EventMetric.KEY_COMMAND], "Blah")
            for fw in app.frameworks.itervalues():
                able_to_test_a_framework = True
                fw.log_metric("Framework test")
                metrics = metrics_queue.get_metrics()
                self.assertEqual(len(metrics), 1)
                data = metrics[0].data
                self.assertEqual(data["event_group"], EventMetric.GROUP_TOOLKIT)
                self.assertEqual(data["event_name"], "Framework test")
                self.assertEqual(data["event_properties"][EventMetric.KEY_HOST_APP], "unknown")
                self.assertEqual(data["event_properties"][EventMetric.KEY_HOST_APP_VERSION], "unknown")
                self.assertEqual(data["event_properties"][EventMetric.KEY_ENGINE], engine.name)
                self.assertEqual(data["event_properties"][EventMetric.KEY_ENGINE_VERSION], engine.version)
                # The app is unknwown within a framework so shouldn't be part of
                # properties
                self.assertFalse(EventMetric.KEY_APP in data["event_properties"])
                self.assertFalse(EventMetric.KEY_APP_VERSION in data["event_properties"])
                self.assertFalse(EventMetric.KEY_COMMAND in data["event_properties"])
        # Make sure we tested at least one app with a framework
        self.assertTrue(able_to_test_a_framework)
