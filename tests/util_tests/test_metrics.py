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


import json
import os
import threading
import time
import unittest
import urllib.request

import tank
from tank.authentication import ShotgunAuthenticator
from tank.util.constants import TANK_LOG_METRICS_HOOK_NAME
from tank.util.metrics import (EventMetric, MetricsDispatchWorkerThread,
                               MetricsQueueSingleton, log_metric,
                               log_user_activity_metric,
                               log_user_attribute_metric)
from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import ShotgunTestBase, TankTestBase, mock

LINUX_DISTRIBUTION_FUNCTION = "tank_vendor.distro.linux_distribution"


class TestEventMetric(ShotgunTestBase):
    """Cases testing tank.util.metrics.EventMetric class"""

    def test_data_property(self):
        pass
    def test_init_with_invalid_parameters(self):
        pass
    def test_init_with_valid_parameters(self):
        pass
    def test_usage_of_extra_properties(self):
        pass
    def test_group_definition_exists(self):
        pass
    def test_key_definition_exist(self):
        pass
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
        self._server_caps_mock = mock.patch(
            "tank_vendor.shotgun_api3.Shotgun.server_caps"
        )
        self._server_caps_mock.start()
        self.addCleanup(self._server_caps_mock.stop)

        # Avoids crash because we're not in a pipeline configuration.
        self._get_api_core_config_location_mock = mock.patch(
            "tank.util.shotgun.connection.__get_api_core_config_location",
            return_value="unused_path_location",
        )
        self._get_api_core_config_location_mock.start()
        self.addCleanup(self._get_api_core_config_location_mock.stop)

        # Mocks app store script user credentials retrieval
        self._get_app_store_key_from_shotgun_mock = mock.patch(
            "tank.descriptor.io_descriptor.appstore.IODescriptorAppStore._IODescriptorAppStore__get_app_store_key_from_shotgun",
            return_value=("abc", "123"),
        )
        self._get_app_store_key_from_shotgun_mock.start()
        self.addCleanup(self._get_app_store_key_from_shotgun_mock.stop)

        self._authenticate()
        self._create_engine()

        # Patch & Mock the `urlopen` method
        self._urlopen_mock = mock.patch("urllib.request.urlopen")
        self._mocked_method = self._urlopen_mock.start()

    def setUp(self):
        pass
    def tearDown(self):
        pass
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
            # Request call. The isinstance check below will prevent any false
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
            data = mocked_request.data
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
        props = properties.copy()
        EventMetric.log(group, name, properties)
        # Recover overwritten properties
        properties.update(props)

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
                data = mocked_request.data
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
        pass
    def helper_test_event_whitelist(
        self,
        event_group,
        event_name,
        properties=None,
        expecting_unknown=False,
        setup_shotgun=False,
    ):
        """
        Helper method for the 'test_event_whitelist' test
        """
        props = properties or {}
        server_received_metric = self._helper_test_end_to_end(
            event_group, event_name, props, setup_shotgun
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
        pass
    def test_end_to_end_unsupported_event(self):
        pass
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
        pass
    def test_misc_constants(self):
        pass
    def test_maximum_queue_size(self):
        pass
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
        pass
    def test_batch_interval(self):
        pass
class TestMetricsQueueSingleton(unittest.TestCase):
    """Cases testing tank.util.metrics.MetricsQueueSingleton class."""

    def test_singleton(self):
        pass
class TestMetricsDeprecatedFunctions(ShotgunTestBase):
    """Cases testing tank.util.metrics of deprecated functions

    Test that the `log_metric`, `log_user_activity_metric` and
    `log_user_attribute_metric` methods are deprecated by creating a
    mock of the `MetricsQueueSingleton.log` method and then
    verifiying whether or not it was called.

    Also test that method still exist for retro-compatibility although
    there're basically empty no-op methods.
    """

    def setUp(self):
        pass
    def tearDown(self):
        pass
    def test_legacy_util_import_statement(self):
        pass
    def test_log_event_metric(self):
        pass
    def test_log_metric(self):
        pass
    def test_log_user_attribute_metric(self):
        pass
    def test_log_user_activity_metric(self):
        pass
class TestMetricsFunctions(ShotgunTestBase):
    """Cases testing tank.util.metrics functions"""

    def test_log_event_metric_with_bad_metrics(self):
        pass
    def test_log_event_metric_with_good_metrics(self):
        pass
class TestBundleMetrics(TankTestBase):
    """
    Class for testing metrics at Bundle level.
    """

    def setUp(self):
        pass
    def tearDown(self):
        pass
    def _authenticate(self):
        # Need to set authenticated user prior to MetricDispatcher.start below
        user = ShotgunAuthenticator().create_script_user(
            "script_user", "script_key", "https://abc.shotgunstudio.com"
        )
        tank.set_authenticated_user(user)

    def _de_authenticate(self):
        tank.set_authenticated_user(None)

    @mock.patch("tank.util.metrics.MetricsDispatcher.start")
    def test_bundle_metrics(self, patched_start):
        pass
    @mock.patch("urllib.open")
    def test_log_metrics_hook(self, patched):
        pass
from tank.util.metrics import PlatformInfo


class TestPlatformInfo(unittest.TestCase):
    def setUp(self):
        pass
    @mock.patch("platform.system", return_value="Windows")
    @mock.patch("platform.release", return_value="XP")
    def test_as_windows(self, mocked_release, mocked_system):
        pass
    @mock.patch("platform.system", return_value="Darwin")
    @mock.patch("platform.mac_ver", return_value=("10.7.5", ("", "", ""), "i386"))
    def test_as_osx(self, mocked_mac_ver, mocked_system):
        pass
    @mock.patch("platform.system", return_value="Linux")
    @mock.patch(LINUX_DISTRIBUTION_FUNCTION, return_value=("debian", "7.7", ""))
    def test_as_linux(self, mocked_system, mocked_linux_distribution):
        pass
    @mock.patch("platform.system", return_value="BSD")
    @mock.patch(LINUX_DISTRIBUTION_FUNCTION, side_effect=Exception)
    def test_as_unsupported_system(self, mocked_linux_distribution, mocked_system):
        pass
    @mock.patch("platform.system", return_value="Linux")
    @mock.patch(LINUX_DISTRIBUTION_FUNCTION, side_effect=Exception)
    def test_as_linux_without_distribution(
        pass
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

    @mock.patch("platform.system", return_value="Darwin")
    @mock.patch("platform.mac_ver", side_effect=Exception)
    def test_as_mac_without_mac_version(self, mocked_mac_ver, mocked_system):
        pass
    @mock.patch("platform.system", return_value="Windows")
    @mock.patch("platform.release", side_effect=Exception)
    def test_as_mac_without_release(self, mocked_release, mocked_system):
        pass
    @mock.patch("platform.system", side_effect=Exception)
    @mock.patch("platform.release", side_effect=Exception)
    def test_system(self, mocked_release, mocked_system):
        pass
