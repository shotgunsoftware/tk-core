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
from tank.util.constants import TANK_LOG_METRICS_HOOK_NAME

import tank
from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import TankTestBase, ShotgunTestBase
from tank.authentication import ShotgunAuthenticator

import os
import json
import time
import threading
import unittest2
from tank_vendor import six
from tank_vendor.six.moves import urllib


if six.PY2:
    LINUX_DISTRIBUTION_FUNCTION = "platform.linux_distribution"
else:
    LINUX_DISTRIBUTION_FUNCTION = "tank_vendor.distro.linux_distribution"


class TestEventMetric(ShotgunTestBase):
    """Cases testing tank.util.metrics.EventMetric class"""

    def test_data_property(self):
        """Object has a data dictionary that matches args."""

        obj = EventMetric("App", "Testing Data Property")
        self.assertTrue(hasattr(obj, "data"))
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
        except Exception as e:
            self.fail(
                "Creating an instance of 'EventMetric' failed unexpectedly: %s" % (e)
            )

    def test_init_with_valid_parameters(self):
        """ Simply assert that the constructor is exception free.

            Also tests the '_add_system_info_properties' method which
            gets called in constructor
            """
        try:

            EventMetric("App", "Test Log Metric without additional properties")

            EventMetric(
                "App",
                "Test Log Metric with additional properties",
                properties={
                    "IntProp": 2,
                    "BoolProp": True,
                    "StringProp": "This is a test string",
                    "DictProp": {"Key1": "value1", "Key2": "Value2"},
                },
            )

        except Exception as e:
            self.fail(
                "Creating an instance of 'EventMetric' failed unexpectedly: %s" % (e)
            )

    def test_usage_of_extra_properties(self):
        """ Simply assert usage of the properties parameter is exception free. """
        EventMetric("App", "Test add_event_properties", None)

        EventMetric(
            "App",
            "Test add_event_properties",
            properties={
                "IntProp": 2,
                "BoolProp": True,
                "StringProp": "This is a test string",
                "DictProp": {"Key1": "value1", "Key2": "Value2"},
                "ListProp": [1, 2, 3, 4, 5],
            },
        )

    def test_group_definition_exists(self):
        """
        Simply test that standard group definition havent't been deleted or renamed.
        """
        self.assertTrue(hasattr(EventMetric, "GROUP_TOOLKIT"))

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
    batch_size_too_large_failure_count = 0
    mock_calls_timestamp = []

    def _create_context(self):
        """
        Helper test init method for setting up a bogus context
        just so we can run the engine.
        """
        some_path = os.path.join(
            self.project_root, "sequences", "Seq", "shot_code", "step_name"
        )
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
        self._cur_engine = tank.platform.start_engine(
            engine_name, self.tk, self.context
        )

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
            return_value="unused_path_location",
        )
        self._get_api_core_config_location_mock.start()
        self.addCleanup(self._get_api_core_config_location_mock.stop)

        # Mocks app store script user credentials retrieval
        self._get_app_store_key_from_shotgun_mock = patch(
            "tank.descriptor.io_descriptor.appstore.IODescriptorAppStore._IODescriptorAppStore__get_app_store_key_from_shotgun",
            return_value=("abc", "123"),
        )
        self._get_app_store_key_from_shotgun_mock.start()
        self.addCleanup(self._get_app_store_key_from_shotgun_mock.stop)

        self._authenticate()
        self._create_engine()

        # Patch & Mock the `urlopen` method
        self._urlopen_mock = patch("tank_vendor.six.moves.urllib.request.urlopen")
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
            self._urlopen_mock.stop()
            self._urlopen_mock = None
            self._mocked_method = None

        self._destroy_engine()

        # Restore value as it might have been changed in tests
        MetricsDispatchWorkerThread.DISPATCH_INTERVAL = self._saved_dispatch_interval

        # important to call base class so it can clean up memory
        super(TestMetricsDispatchWorkerThread, self).tearDown()

    def _get_urllib_request_calls(self, return_only_calls_after_reset=False):
        """
        Helper test method that traverses `mock_calls` and return a list of `urllib.Request` specific calls

        :return: a list a `urllib.Request` specific calls
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

            # Quick sanity check to ensure that the mocked call includes a
            # Request call.  Don't use the full module name since it varies from
            # Python 2 to 3.  The isinstance check below will prevent any false
            # positives.
            if found_reset and "Request" in str(mocked_call):
                # TODO: find out what class type is 'something'
                for args in mocked_call:
                    for arg in args:
                        if isinstance(arg, urllib.request.Request):
                            mocked_request_calls.append(arg)

        return mocked_request_calls

    def _get_metrics(self, return_only_calls_after_reset=False):
        """

        Helper test method that traverses `mock_calls` and return a list of individual metrics.

        NOTE: The method also filters out 'engine init' that is usually present.

        :return: a list a metric dictionaries
        """
        metrics = []
        for mocked_request in self._get_urllib_request_calls(
            return_only_calls_after_reset
        ):
            # get_data was removed in Python 3.4. since we're testing against 3.6 and
            # 3.7, this should be sufficient.
            if six.PY3:
                data = mocked_request.data
            else:
                data = mocked_request.get_data()
            data = json.loads(data)
            # Now that we have request data
            # Traverse the metrics to find the one we've logged above
            if "metrics" in data:
                for metric in data["metrics"]:
                    metrics.append(metric)

        return metrics

    def _helper_test_end_to_end(self, group, name, properties, setup_shogun=True):
        """
        Helper method for the test_end_to_end_* tests. Allows a deeper and
        more complete test cycle of creating, submitting and receiving
        a mocked-server response.
        """

        if setup_shogun:
            # Setup test fixture, engine and context with newer server caps
            #
            # Define a local server caps mock locally since it only
            # applies to this particular test
            class server_capsMock:
                def __init__(self):
                    self.version = (7, 4, 0)

            self._setup_shotgun(server_capsMock())

        # Save a few values for comparing on the other side
        expected_event_name = name
        if (
            EventMetric.EVENT_NAME_FORMAT % (group, name)
            not in EventMetric.SUPPORTED_EVENTS
        ):
            expected_event_name = "Unknown Event"

        # Make at least one metric related call!
        EventMetric.log(group, name, properties)

        TIMEOUT_SECONDS = 4 * MetricsDispatchWorkerThread.DISPATCH_INTERVAL
        timeout = time.time() + TIMEOUT_SECONDS

        # Simple flag just to differenciate one of two conditions:
        # a) didn't even find a mocked request call
        # b) a + didn't find expected metric
        found_urllib_request_call = False

        while time.time() < timeout:
            time.sleep(TestMetricsDispatchWorkerThread.SLEEP_INTERVAL)

            for mocked_request in self._get_urllib_request_calls():
                found_urllib_request_call = True
                # get_data was removed in Python 3.4. since we're testing against 3.6 and
                # 3.7, this should be sufficient.
                if six.PY3:
                    data = mocked_request.data
                else:
                    data = mocked_request.get_data()
                data = json.loads(data)
                # Now that we have request data
                # Traverse the metrics to find the one we've logged above
                if "metrics" in data:
                    # At this point we found Request calls with 'metrics' data
                    # Although we've not found our particular metric
                    # We can already verify that the logged metric was made using the right URL
                    url = mocked_request.get_full_url()
                    self.assertTrue(
                        TestMetricsDispatchWorkerThread.METRIC_ENDPOINT in url,
                        "Not using the latest metric '%s' endpoint"
                        % (TestMetricsDispatchWorkerThread.METRIC_ENDPOINT),
                    )

                    for metric in data["metrics"]:
                        if ("event_name" in metric) and (
                            expected_event_name == metric["event_name"]
                        ):
                            # Nothing else FOR NOW to test, we can report success by bypassing
                            # timeout failure down below.

                            # Tests all of the received metric properties that went through two conversions
                            return metric

        if found_urllib_request_call:
            self.fail("Timed out waiting for expected metric.")
        else:
            self.fail("Timed out waiting for a mocked urlopen request call.")

    def test_end_to_end_basic(self):
        """
        Test a complete cycle using non problematic metric object.
        """
        server_received_metric = self._helper_test_end_to_end(
            EventMetric.GROUP_TOOLKIT,
            # We use an un-supported event name here which will be replaced with
            # "Unknown Event"
            "Launched Action",
            properties={
                EventMetric.KEY_HOST_APP: "Maya",
                EventMetric.KEY_HOST_APP_VERSION: "2017",
                EventMetric.KEY_APP: "tk-multi-publish2",
                EventMetric.KEY_APP_VERSION: "v0.2.3",
                "IntProp": 2,
                "BoolProp": True,
                "DictProp": {"Key1": "value1", "Key2": "Value2"},
                "ListProp": [1, 2, 3, 4, 5],
            },
        )

        # Test the metric that was encoded and transmitted to the mock server
        self.assertEqual(
            server_received_metric["event_group"], EventMetric.GROUP_TOOLKIT
        )
        self.assertEqual(server_received_metric["event_name"], "Launched Action")
        self.assertTrue("event_properties" in server_received_metric)

        self.assertTrue(
            EventMetric.KEY_HOST_APP in server_received_metric["event_properties"]
        )
        self.assertTrue(
            EventMetric.KEY_HOST_APP_VERSION
            in server_received_metric["event_properties"]
        )
        self.assertTrue(
            EventMetric.KEY_APP in server_received_metric["event_properties"]
        )
        self.assertTrue(
            EventMetric.KEY_APP_VERSION in server_received_metric["event_properties"]
        )

        self.assertTrue("IntProp" in server_received_metric["event_properties"])
        self.assertTrue("BoolProp" in server_received_metric["event_properties"])
        self.assertTrue("DictProp" in server_received_metric["event_properties"])
        self.assertTrue("ListProp" in server_received_metric["event_properties"])

        self.assertTrue(
            isinstance(server_received_metric["event_group"], six.text_type)
        )
        self.assertTrue(isinstance(server_received_metric["event_name"], six.text_type))
        self.assertTrue(isinstance(server_received_metric["event_properties"], dict))

        self.assertTrue(
            isinstance(
                server_received_metric["event_properties"][EventMetric.KEY_HOST_APP],
                six.text_type,
            )
        )
        self.assertTrue(
            isinstance(
                server_received_metric["event_properties"][
                    EventMetric.KEY_HOST_APP_VERSION
                ],
                six.text_type,
            )
        )
        self.assertTrue(
            isinstance(
                server_received_metric["event_properties"][EventMetric.KEY_APP],
                six.text_type,
            )
        )
        self.assertTrue(
            isinstance(
                server_received_metric["event_properties"][EventMetric.KEY_APP_VERSION],
                six.text_type,
            )
        )

        self.assertTrue(
            isinstance(server_received_metric["event_properties"]["IntProp"], int)
        )
        self.assertTrue(
            isinstance(server_received_metric["event_properties"]["IntProp"], int)
        )
        self.assertTrue(
            isinstance(server_received_metric["event_properties"]["BoolProp"], bool)
        )
        self.assertTrue(
            isinstance(server_received_metric["event_properties"]["DictProp"], dict)
        )
        self.assertTrue(
            isinstance(server_received_metric["event_properties"]["ListProp"], list)
        )

    def helper_test_event_whitelist(
        self, event_group, event_name, expecting_unknown=False, setup_shotgun=False
    ):
        """
        Helper method for the 'test_event_whitelist' test
        """
        server_received_metric = self._helper_test_end_to_end(
            event_group, event_name, {}, setup_shotgun
        )

        # Test the metric that was encoded and transmitted to the mock server
        self.assertTrue("event_group" in server_received_metric)
        self.assertTrue("event_name" in server_received_metric)

        if expecting_unknown:
            self.assertEqual(server_received_metric["event_name"], "Unknown Event")
            self.assertEqual(server_received_metric["event_group"], "Toolkit")
        else:
            self.assertEqual(server_received_metric["event_name"], event_name)

    def test_event_whitelist(self):
        """
        Test existence and support for the entire current metric event whitelist

        NOTE: Deliberately not using EventMetric defined GROUP_xxxx constants
        """

        # We need to init shotgun on first call
        self.helper_test_event_whitelist("App", "Logged In", setup_shotgun=True)
        self.helper_test_event_whitelist("App", "Logged Out")
        self.helper_test_event_whitelist("App", "Viewed Login Page")
        self.helper_test_event_whitelist("Media", "Created Note")
        self.helper_test_event_whitelist("Media", "Created Reply")
        self.helper_test_event_whitelist("Navigation", "Viewed Projects")
        self.helper_test_event_whitelist("Navigation", "Viewed Panel")
        self.helper_test_event_whitelist("Projects", "Viewed Project Commands")
        self.helper_test_event_whitelist("Tasks", "Created Task")
        self.helper_test_event_whitelist("Toolkit", "Launched Action")
        self.helper_test_event_whitelist("Toolkit", "Launched Command")
        self.helper_test_event_whitelist("Toolkit", "Launched Software")
        self.helper_test_event_whitelist("Toolkit", "Loaded Published File")
        self.helper_test_event_whitelist("Toolkit", "Published")
        self.helper_test_event_whitelist("Toolkit", "New Workfile")
        self.helper_test_event_whitelist("Toolkit", "Opened Workfile")
        self.helper_test_event_whitelist("Toolkit", "Saved Workfile")

        # Testing out unknown events
        self.helper_test_event_whitelist("CarAndDriver", "Reviewed New Car", True)
        self.helper_test_event_whitelist("Firmwares", "Updated Router Firmware", True)

    def test_end_to_end_unsupported_event(self):
        """
        Test a complete cycle using an unsupported event name.
        """
        properties = {
            EventMetric.KEY_HOST_APP: "Maya",
            EventMetric.KEY_HOST_APP_VERSION: "2017",
            EventMetric.KEY_APP: "tk-multi-publish2",
            EventMetric.KEY_APP_VERSION: "v0.2.3",
            "IntProp": 2,
            "BoolProp": True,
            "DictProp": {"Key1": "value1", "Key2": "Value2"},
            "ListProp": [1, 2, 3, 4, 5],
        }
        server_received_metric = self._helper_test_end_to_end(
            EventMetric.GROUP_TOOLKIT,
            # We use an un-supported event name here which will be replaced with
            # "Unknown Event"
            "Testing basic end to end functionality",
            properties=properties,
        )

        # Test the metric that was encoded and transmitted to the mock server
        self.assertTrue("event_group" in server_received_metric)
        self.assertTrue("event_name" in server_received_metric)
        # Our un-supported event name should have been changed
        self.assertEqual(server_received_metric["event_name"], "Unknown Event")
        self.assertTrue("event_properties" in server_received_metric)
        # The original un-supported event name should be available as a property
        self.assertEqual(
            server_received_metric["event_properties"]["Event Name"],
            "Testing basic end to end functionality",
        )
        for k in [
            EventMetric.KEY_HOST_APP,
            EventMetric.KEY_HOST_APP_VERSION,
            EventMetric.KEY_APP,
            EventMetric.KEY_APP_VERSION,
        ]:
            self.assertEqual(
                server_received_metric["event_properties"][k], properties[k]
            )

        preserved_properties = server_received_metric["event_properties"]["Event Data"]
        self.assertTrue("IntProp" in preserved_properties)
        self.assertTrue("BoolProp" in preserved_properties)
        self.assertTrue("DictProp" in preserved_properties)
        self.assertTrue("ListProp" in preserved_properties)

        self.assertTrue(
            isinstance(server_received_metric["event_group"], six.text_type)
        )
        self.assertTrue(isinstance(server_received_metric["event_name"], six.text_type))
        self.assertTrue(isinstance(server_received_metric["event_properties"], dict))

        self.assertTrue(
            isinstance(
                server_received_metric["event_properties"][EventMetric.KEY_HOST_APP],
                six.text_type,
            )
        )
        self.assertTrue(
            isinstance(
                server_received_metric["event_properties"][
                    EventMetric.KEY_HOST_APP_VERSION
                ],
                six.text_type,
            )
        )
        self.assertTrue(
            isinstance(
                server_received_metric["event_properties"][EventMetric.KEY_APP],
                six.text_type,
            )
        )
        self.assertTrue(
            isinstance(
                server_received_metric["event_properties"][EventMetric.KEY_APP_VERSION],
                six.text_type,
            )
        )

        self.assertTrue(isinstance(preserved_properties["IntProp"], int))
        self.assertTrue(isinstance(preserved_properties["IntProp"], int))
        self.assertTrue(isinstance(preserved_properties["BoolProp"], bool))
        self.assertTrue(isinstance(preserved_properties["DictProp"], dict))
        self.assertTrue(isinstance(preserved_properties["ListProp"], list))

    # Not currently supporting usage of non-ascii7 characters, request would need to be escaped"
    def _test_end_to_end_with_non_ascii7_chars(self):
        """
        Test a complete cycle of creating, submitting and receiving a server
        response using non-ascii-7 characaters in the request.
        """
        self._helper_test_end_to_end(
            EventMetric.GROUP_TOOLKIT,
            "Test test_end_to_end",
            properties={
                "Name with accents": "Éric Hébert",
                "String with tricky characters": "''\"\\//%%$$?&?$^^,¨¨`",
            },
        )

    def test_not_logging_older_tookit(self):
        """
        Test that logging metrics is not possible from an older version
        of toolkit as it can't even pass metric version check and therefore
        won't call urllib.urlopen mock calls
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
                self.fail(
                    "Was not expecting any request mock calls since code in metrics.py "
                    "should have been filtered out based on server caps. version."
                )

        #
        # If we get here, this is SUCCESS as we didn't receive urllib.Request calls
        #

    def test_misc_constants(self):

        # Verify that the endpoint was indeed updated
        self.assertEqual(
            TestMetricsDispatchWorkerThread.METRIC_ENDPOINT,
            MetricsDispatchWorkerThread.API_ENDPOINT,
        )
        # Verify that process interval is adequate. This is currently arbitrary but
        # 5 seconds does seems to be reasonable for now.
        # This is subject to change as we start receiving metrics again.
        #
        # Do provide a reason ( here and in modified metrics.py code
        # why either value might be changed
        #
        self.assertEqual(5, MetricsDispatchWorkerThread.DISPATCH_INTERVAL)
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
                properties={"Metric id": i},
            )

        queue = MetricsQueueSingleton()._queue
        self.assertTrue(len(queue) <= MetricsQueueSingleton.MAXIMUM_QUEUE_SIZE)

        # Test that the first item is indeed N items past the originally queued ones
        # Where N is TEST_SIZE minus size of queue
        oldest_metric = queue.popleft()
        metric_index = oldest_metric.data["event_properties"]["Metric id"]
        self.assertEqual(
            metric_index, TEST_SIZE - MetricsQueueSingleton.MAXIMUM_QUEUE_SIZE
        )

        # Finally, test that the newest item
        newest_metric = queue.pop()
        metric_index = newest_metric.data["event_properties"]["Metric id"]
        self.assertEqual(metric_index, TEST_SIZE - 1)

    @classmethod
    def _mocked_urlopen_for_test_maximum_batch_size(*args, **kwargs):
        """
        Helper method checking that batch size are limited to N elements.
        :param kwargs:
        """
        test_instance = args[0]
        millis = int(round(time.time() * 1000))
        test_instance.mock_calls_timestamp.append(millis)

        data = metrics = args[1].data
        payload = json.loads(data)
        metrics = payload["metrics"]
        batch_size = len(metrics)

        EXPECTED_MAXIMUM_SIZE = 10
        if batch_size > EXPECTED_MAXIMUM_SIZE:
            test_instance.batch_size_too_large_failure_count = (
                test_instance.batch_size_too_large_failure_count + 1
            )

    def test_maximum_batch_size(self):
        """
        Test that the dispatcher worker thread is not sending all queued metrics at once
        but rather sent in batches that can be handled by the server.
        """

        # Setup test fixture, engine and context with newer server caps
        #
        # Define a local server caps mock locally since it only
        # applies to this particular test
        class server_capsMock:
            def __init__(self):
                self.version = (7, 4, 0)

        self._setup_shotgun(server_capsMock())

        # The '_setup_shotgun' helper method is setting up an 'urlopen' mock.
        # For this test, we need to override that to something more specific.
        self._urlopen_mock.stop()
        self._urlopen_mock = None
        self._urlopen_mock = patch(
            "tank_vendor.six.moves.urllib.request.urlopen",
            side_effect=TestMetricsDispatchWorkerThread._mocked_urlopen_for_test_maximum_batch_size,
        )
        self._mocked_method = self._urlopen_mock.start()

        # We add 10 time the maximum number of events in the queue.
        TEST_SIZE = 7 + (10 * MetricsQueueSingleton.MAXIMUM_QUEUE_SIZE)
        for i in range(TEST_SIZE):
            EventMetric.log(
                "App",
                "Testing maximum queue size %d" % (i),
                properties={"Metric id": i},
            )

        queue = MetricsQueueSingleton()._queue
        TIMEOUT_SECONDS = 40 * MetricsDispatchWorkerThread.DISPATCH_INTERVAL

        # Wait for firsts events to show up in queue
        timeout = time.time() + TIMEOUT_SECONDS
        length = len(queue)
        while (length == 0) and (time.time() < timeout):
            time.sleep(TestMetricsDispatchWorkerThread.SLEEP_INTERVAL)
            length = len(queue)

        # Wait for the queue to be emptied
        length = len(queue)
        timeout = time.time() + TIMEOUT_SECONDS
        while (length > 0) and (time.time() < timeout):
            time.sleep(TestMetricsDispatchWorkerThread.SLEEP_INTERVAL)
            length = len(queue)

        self.assertEqual(self.batch_size_too_large_failure_count, 0)

    def test_batch_interval(self):
        """
        Test that the dispatcher attempts emptying the queue on each cycle
        rather than sending a single batch per cycle. The older code was s
        sending a single batch of metrics per cycle of 5 seconds, each batch
        being 10 metrics, the dispatcher could then handle only 2 metrics per
        second. A higher rate would cause metrics to accumulate in the
        dispatcher queue.

        Because we're dealing with another thread, there are timing issues and
        context switch which are difficult to account for. Because  we're using
        a very small dispatcher cycle time for some cycle we might actually go
        beyond the normal cycle period. For that reason we won't inspect
        individual cycle but the average cycle time over 10 or more cycles.
        """

        # Setup test fixture, engine and context with newer server caps
        #
        # Define a local server caps mock locally since it only
        # applies to this particular test
        class server_capsMock:
            def __init__(self):
                self.version = (7, 4, 0)

        self._setup_shotgun(server_capsMock())

        # The '_setup_shotgun' helper method is setting up an 'urlopen' mock.
        # For this test, we need to override that to something more specific.
        self._urlopen_mock.stop()
        self._urlopen_mock = None
        self._urlopen_mock = patch(
            "tank_vendor.six.moves.urllib.request.urlopen",
            side_effect=TestMetricsDispatchWorkerThread._mocked_urlopen_for_test_maximum_batch_size,
        )
        self._mocked_method = self._urlopen_mock.start()

        # We add 10 time the maximum number of events in the queue + some extra.
        TEST_SIZE = 7 + (10 * MetricsQueueSingleton.MAXIMUM_QUEUE_SIZE)
        for i in range(TEST_SIZE):
            EventMetric.log(
                EventMetric.GROUP_TOOLKIT,
                "Testing maximum queue size %d" % (i),
                properties={"Metric id": i},
            )

        queue = MetricsQueueSingleton()._queue
        TIMEOUT_SECONDS = 40 * MetricsDispatchWorkerThread.DISPATCH_INTERVAL

        # Wait for firsts events to show up in queue
        timeout = time.time() + TIMEOUT_SECONDS
        length = len(queue)
        while (length == 0) and (time.time() < timeout):
            time.sleep(TestMetricsDispatchWorkerThread.SLEEP_INTERVAL)
            length = len(queue)

        # Wait for the queue to be emptied
        length = len(queue)
        timeout = time.time() + TIMEOUT_SECONDS
        while (length > 0) and (time.time() < timeout):
            time.sleep(TestMetricsDispatchWorkerThread.SLEEP_INTERVAL)
            length = len(queue)

        # Checking overall cycle average time NOT individual cycle time
        max_interval = MetricsDispatchWorkerThread.DISPATCH_INTERVAL * 1000
        count = len(self.mock_calls_timestamp)
        first_timestamp_ms = self.mock_calls_timestamp[0]
        last_timestamp_ms = self.mock_calls_timestamp[count - 1]
        avg_time_ms = (last_timestamp_ms - first_timestamp_ms) / count
        self.assertTrue(avg_time_ms < max_interval)


class TestMetricsQueueSingleton(unittest2.TestCase):
    """Cases testing tank.util.metrics.MetricsQueueSingleton class."""

    def test_singleton(self):
        """Multiple instantiations return same instance."""

        obj1 = MetricsQueueSingleton()
        obj2 = MetricsQueueSingleton()
        obj3 = MetricsQueueSingleton()
        self.assertTrue(obj1 == obj2 == obj3)


class TestMetricsDeprecatedFunctions(ShotgunTestBase):
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
        self._metrics_queue_singleton_log_mock = patch(
            "tank.util.metrics.MetricsQueueSingleton.log"
        )
        self._mocked_method = self._metrics_queue_singleton_log_mock.start()

    def tearDown(self):
        if self._mocked_method:
            self._metrics_queue_singleton_log_mock.stop()
            self._metrics_queue_singleton_log_mock = None
            self._mocked_method.reset_mock()
            self._mocked_method = None

        super(TestMetricsDeprecatedFunctions, self).tearDown()

    def test_legacy_util_import_statement(self):
        """
        Test the presence of the import log_user_*_metric statements
        in util.__init__ to preserve retro compatibility and prevent
        exception in legacy engine code.
        """
        from tank.util import log_user_activity_metric
        from tank.util import log_user_attribute_metric

        # Bogus test call to the two legacy metric methods
        log_user_activity_metric("Test Module", "Test Action")
        log_user_attribute_metric("Attribute", "Value")

    def test_log_event_metric(self):
        # Self testing that the mock setup is correct
        # by trying out a non-deprecated method.
        EventMetric.log("App", "Testing Own Test Mock")
        self.assertTrue(
            self._mocked_method.called,
            "Was expecting a call to the "
            "`MetricsQueueSingleton.log`"
            "method from the non-deprecated "
            "`log_event_metric` method.",
        )

    def test_log_metric(self):
        # It is ok to provide an empty metric dictionary since we just want to
        # check that the `MetricsQueueSingleton.log` is called or not.
        log_metric({})
        self.assertFalse(
            self._mocked_method.called,
            "Was not expecting a call to the "
            "`MetricsQueueSingleton.log` "
            "method from the deprecated "
            "`log_metric` method.",
        )

    def test_log_user_attribute_metric(self):

        log_user_attribute_metric(
            attr_name="Some attr. name", attr_value="Some attr. value"
        )
        self.assertFalse(
            self._mocked_method.called,
            "Was not expecting a call to the "
            "`MetricsQueueSingleton.log` "
            "method from the deprecated "
            "`log_user_attribute_metric` method.",
        )

    def test_log_user_activity_metric(self):

        log_user_activity_metric(module="Some some name", action="Some action")
        self.assertFalse(
            self._mocked_method.called,
            "Was not expecting a call to the "
            "`MetricsQueueSingleton.log` "
            "method from the deprecated "
            "`log_user_activity_metric` method.",
        )


class TestMetricsFunctions(ShotgunTestBase):
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
        except Exception as e:
            self.fail("log_metric() failed unexpectedly on bad metric: %s" % (e))

    def test_log_event_metric_with_good_metrics(self):

        # make sure no exceptions on good metrics
        try:
            EventMetric.log("App", "Testing Log Metric without additional properties")
            EventMetric.log(
                "App",
                "Testing Log Metric with additional properties",
                properties={
                    "IntProp": 2,
                    "BoolProp": True,
                    "StringProp": "This is a test string",
                    "DictProp": {"Key1": "value1", "Key2": "Value2"},
                },
            )
        except Exception as e:
            self.fail("EventMetric.log() failed unexpectedly on good metric: %s" % (e))


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

        shot = {
            "type": "Shot",
            "code": "shot_name",
            "id": 2,
            "sg_sequence": seq,
            "project": self.project,
        }
        shot_path = os.path.join(seq_path, "shot_name")
        self.add_production_path(shot_path, shot)

        step = {"type": "Step", "code": "step_name", "id": 4}
        self.shot_step_path = os.path.join(shot_path, "step_name")
        self.add_production_path(self.shot_step_path, step)

        self.test_resource = os.path.join(
            self.pipeline_config_root, "config", "foo", "bar.png"
        )
        os.makedirs(os.path.dirname(self.test_resource))
        fh = open(self.test_resource, "wt")
        fh.write("test")
        fh.close()

        # Set the dispatch interval to something not too big so tests will not
        # wait for a long time.
        self._metrics_interval = MetricsDispatchWorkerThread.DISPATCH_INTERVAL
        MetricsDispatchWorkerThread.DISPATCH_INTERVAL = 2
        # Make sure we have an empty queue
        metrics_queue = MetricsQueueSingleton()
        metrics_queue.get_metrics()
        self.context = self.tk.context_from_path(self.shot_step_path)
        self._authenticate()

    def tearDown(self):
        MetricsDispatchWorkerThread.DISPATCH_INTERVAL = self._metrics_interval
        # engine is held as global, so must be destroyed.
        cur_engine = tank.platform.current_engine()
        if cur_engine:
            cur_engine.destroy()
        os.remove(self.test_resource)
        self._de_authenticate()
        # important to call base class so it can clean up memory
        super(TestBundleMetrics, self).tearDown()

    def _authenticate(self):
        # Need to set authenticated user prior to MetricDispatcher.start below
        user = ShotgunAuthenticator().create_script_user(
            "script_user", "script_key", "https://abc.shotgunstudio.com"
        )
        tank.set_authenticated_user(user)

    def _de_authenticate(self):
        tank.set_authenticated_user(None)

    @patch("tank.util.metrics.MetricsDispatcher.start")
    def test_bundle_metrics(self, patched_start):
        """
        Test metrics logged by bundles.
        """
        engine = tank.platform.start_engine("test_engine", self.tk, self.context)
        metrics_queue = MetricsQueueSingleton()
        # Make sure we don't have a dispatcher running
        if engine._metrics_dispatcher:
            self.assertFalse(engine._metrics_dispatcher.workers)

        # Log a metric and check it
        engine.log_metric("Engine test")
        metrics = metrics_queue.get_metrics()
        self.assertEqual(len(metrics), 1)
        data = metrics[0].data
        self.assertEqual(data["event_group"], EventMetric.GROUP_TOOLKIT)
        self.assertEqual(data["event_name"], "Engine test")
        self.assertEqual(data["event_properties"][EventMetric.KEY_HOST_APP], "unknown")
        self.assertEqual(
            data["event_properties"][EventMetric.KEY_HOST_APP_VERSION], "unknown"
        )
        self.assertEqual(data["event_properties"][EventMetric.KEY_ENGINE], engine.name)
        self.assertEqual(
            data["event_properties"][EventMetric.KEY_ENGINE_VERSION], engine.version
        )
        self.assertFalse(EventMetric.KEY_APP in data["event_properties"])
        self.assertFalse(EventMetric.KEY_APP_VERSION in data["event_properties"])
        self.assertFalse(EventMetric.KEY_COMMAND in data["event_properties"])
        # Make sure we have at least one app with a framework, this is checked
        # after the loops
        able_to_test_a_framework = False
        # Check metrics logged from apps
        for app in six.itervalues(engine.apps):
            app.log_metric("App test")
            metrics = metrics_queue.get_metrics()
            self.assertEqual(len(metrics), 1)
            data = metrics[0].data
            self.assertEqual(data["event_group"], EventMetric.GROUP_TOOLKIT)
            self.assertEqual(data["event_name"], "App test")
            self.assertEqual(
                data["event_properties"][EventMetric.KEY_HOST_APP], "unknown"
            )
            self.assertEqual(
                data["event_properties"][EventMetric.KEY_HOST_APP_VERSION], "unknown"
            )
            self.assertEqual(
                data["event_properties"][EventMetric.KEY_ENGINE], engine.name
            )
            self.assertEqual(
                data["event_properties"][EventMetric.KEY_ENGINE_VERSION], engine.version
            )
            self.assertEqual(data["event_properties"][EventMetric.KEY_APP], app.name)
            self.assertEqual(
                data["event_properties"][EventMetric.KEY_APP_VERSION], app.version
            )
            self.assertFalse(EventMetric.KEY_COMMAND in data["event_properties"])
            app.log_metric("App test", command_name="Blah")
            metrics = metrics_queue.get_metrics()
            self.assertEqual(len(metrics), 1)
            data = metrics[0].data
            self.assertEqual(data["event_group"], EventMetric.GROUP_TOOLKIT)
            self.assertEqual(data["event_name"], "App test")
            self.assertEqual(
                data["event_properties"][EventMetric.KEY_HOST_APP], "unknown"
            )
            self.assertEqual(
                data["event_properties"][EventMetric.KEY_HOST_APP_VERSION], "unknown"
            )
            self.assertEqual(
                data["event_properties"][EventMetric.KEY_ENGINE], engine.name
            )
            self.assertEqual(
                data["event_properties"][EventMetric.KEY_ENGINE_VERSION], engine.version
            )
            self.assertEqual(data["event_properties"][EventMetric.KEY_APP], app.name)
            self.assertEqual(
                data["event_properties"][EventMetric.KEY_APP_VERSION], app.version
            )
            self.assertEqual(data["event_properties"][EventMetric.KEY_COMMAND], "Blah")
            for fw in six.itervalues(app.frameworks):
                able_to_test_a_framework = True
                fw.log_metric("Framework test")
                metrics = metrics_queue.get_metrics()
                self.assertEqual(len(metrics), 1)
                data = metrics[0].data
                self.assertEqual(data["event_group"], EventMetric.GROUP_TOOLKIT)
                self.assertEqual(data["event_name"], "Framework test")
                self.assertEqual(
                    data["event_properties"][EventMetric.KEY_HOST_APP], "unknown"
                )
                self.assertEqual(
                    data["event_properties"][EventMetric.KEY_HOST_APP_VERSION],
                    "unknown",
                )
                self.assertEqual(
                    data["event_properties"][EventMetric.KEY_ENGINE], engine.name
                )
                self.assertEqual(
                    data["event_properties"][EventMetric.KEY_ENGINE_VERSION],
                    engine.version,
                )
                # The app is unknwown within a framework so shouldn't be part of
                # properties
                self.assertFalse(EventMetric.KEY_APP in data["event_properties"])
                self.assertFalse(
                    EventMetric.KEY_APP_VERSION in data["event_properties"]
                )
                self.assertFalse(EventMetric.KEY_COMMAND in data["event_properties"])
        # Make sure we tested at least one app with a framework
        self.assertTrue(able_to_test_a_framework)

    @patch("urllib.open")
    def test_log_metrics_hook(self, patched):
        """
        Test the log_metric hook is fired when logging metrics
        """
        engine = tank.platform.start_engine("test_engine", self.tk, self.context)
        self.assertTrue(engine.metrics_dispatch_allowed)

        # Make sure we do have a dispatcher running
        self.assertTrue(engine._metrics_dispatcher)
        self.assertTrue(engine._metrics_dispatcher.workers)

        # Check the hook is called with the right arguments
        exec_core_hook = engine.tank.execute_core_hook_method
        hook_calls = []

        def log_hook(hook_name, hook_method, **kwargs):
            if hook_name == TANK_LOG_METRICS_HOOK_NAME:
                hook_calls.append(kwargs)
            # Call the original hook
            return exec_core_hook(hook_name, hook_method, **kwargs)

        with patch("tank.api.Sgtk.execute_core_hook_method") as mocked:
            mocked.side_effect = log_hook
            engine.log_metric("Hook test")
            # Make sure the dispatcher has some time to wake up
            time.sleep(2 * MetricsDispatchWorkerThread.DISPATCH_INTERVAL)
            hook_called = False
            for hook_call in hook_calls:
                for metric in hook_call["metrics"]:
                    if metric["event_name"] == "Hook test":
                        hook_called = True
                        break
            self.assertTrue(hook_called)


from tank.util.metrics import PlatformInfo


class TestPlatformInfo(unittest2.TestCase):
    def setUp(self):
        super(TestPlatformInfo, self).setUp()
        # reset un-cache PlatformInfo cached value
        PlatformInfo._PlatformInfo__cached_platform_info = None

    @patch("platform.system", return_value="Windows")
    @patch("platform.release", return_value="XP")
    def test_as_windows(self, mocked_release, mocked_system):
        """
        Tests as a Windows XP system
        """
        platform_info = PlatformInfo.get_platform_info()
        self.assertIsNotNone(platform_info)
        self.assertEqual("Windows", platform_info["OS"])
        self.assertEqual("XP", platform_info["OS Version"])
        self.assertTrue(mocked_system.called)
        self.assertTrue(mocked_release.called)

    @patch("platform.system", return_value="Darwin")
    @patch("platform.mac_ver", return_value=("10.7.5", ("", "", ""), "i386"))
    def test_as_osx(self, mocked_mac_ver, mocked_system):
        """
        Tests as some OSX Lion system
        """
        platform_info = PlatformInfo.get_platform_info()
        self.assertIsNotNone(platform_info)
        self.assertEqual("Mac", platform_info["OS"])
        self.assertEqual("10.7", platform_info["OS Version"])
        self.assertTrue(mocked_system.called)
        self.assertTrue(mocked_mac_ver.called)

    @patch("platform.system", return_value="Linux")
    @patch(LINUX_DISTRIBUTION_FUNCTION, return_value=("debian", "7.7", ""))
    def test_as_linux(self, mocked_system, mocked_linux_distribution):
        """
        Tests as a Linux Debian system
        """
        platform_info = PlatformInfo.get_platform_info()
        self.assertIsNotNone(platform_info)
        self.assertEqual("Linux", platform_info["OS"])
        self.assertEqual("Debian 7", platform_info["OS Version"])
        self.assertTrue(mocked_system.called)
        self.assertTrue(mocked_linux_distribution.called)

    @patch("platform.system", return_value="BSD")
    @patch(LINUX_DISTRIBUTION_FUNCTION, side_effect=Exception)
    def test_as_unsupported_system(self, mocked_linux_distribution, mocked_system):
        """
        Tests a fake unsupported system
        """
        mocked_linux_distribution.reset_mock()
        platform_info = PlatformInfo.get_platform_info()
        self.assertIsNotNone(platform_info)
        self.assertEqual("Unsupported system: (BSD)", platform_info["OS"])
        self.assertEqual("Unknown", platform_info["OS Version"])
        self.assertTrue(mocked_system.called)
        self.assertFalse(mocked_linux_distribution.called)

    @patch("platform.system", return_value="Linux")
    @patch(LINUX_DISTRIBUTION_FUNCTION, side_effect=Exception)
    def test_as_linux_without_distribution(
        self, mocked_linux_distribution, mocked_system
    ):
        """
        Tests handling of an exception caused by the 'linux_distribution' method.
        """
        platform_info = PlatformInfo.get_platform_info()
        self.assertIsNotNone(platform_info)
        self.assertEqual("Linux", platform_info["OS"])
        self.assertEqual("Unknown", platform_info["OS Version"])
        self.assertTrue(mocked_system.called)
        self.assertTrue(mocked_linux_distribution.called)

    @patch("platform.system", return_value="Darwin")
    @patch("platform.mac_ver", side_effect=Exception)
    def test_as_mac_without_mac_version(self, mocked_mac_ver, mocked_system):
        """
        Tests handling of an exception caused by the 'mac_ver' method.
        """
        platform_info = PlatformInfo.get_platform_info()
        self.assertIsNotNone(platform_info)
        self.assertEqual("Mac", platform_info["OS"])
        self.assertEqual("Unknown", platform_info["OS Version"])
        self.assertTrue(mocked_system.called)
        self.assertTrue(mocked_mac_ver.called)

    @patch("platform.system", return_value="Windows")
    @patch("platform.release", side_effect=Exception)
    def test_as_mac_without_release(self, mocked_release, mocked_system):
        """
        Tests handling of an exception caused by the 'release' method.
        """
        platform_info = PlatformInfo.get_platform_info()
        self.assertIsNotNone(platform_info)
        self.assertEqual("Windows", platform_info["OS"])
        self.assertEqual("Unknown", platform_info["OS Version"])
        self.assertTrue(mocked_system.called)
        self.assertTrue(mocked_release.called)

    @patch("platform.system", side_effect=Exception)
    @patch("platform.release", side_effect=Exception)
    def test_system(self, mocked_release, mocked_system):
        """
        Tests handling of an exception caused by the 'system' method.
        """
        platform_info = PlatformInfo.get_platform_info()
        self.assertIsNotNone(platform_info)
        self.assertEqual("Unknown", platform_info["OS"])
        self.assertEqual("Unknown", platform_info["OS Version"])
        self.assertTrue(mocked_system.called)
        self.assertFalse(mocked_release.called)
