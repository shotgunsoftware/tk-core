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
    MetricsDispatchQueueSingleton,
    ToolkitMetric,
    UserAttributeMetric,
    UserActivityMetric,
    log_metric,
    log_user_activity_metric,
    log_user_attribute_metric,
)

from tank_test.tank_test_base import *

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

class TestUserAttributeMetric(TankTestBase):
    """Cases testing tank.util.metrics.UserAttributeMetric class"""

    def test_data_property(self):
        """Object has a data dictionary that matches args."""

        obj = UserAttributeMetric(
            "Test Attribute",
            "UserAttributeMetric.data property test",
        )
        self.assertTrue(hasattr(obj, 'data'))
        self.assertIsInstance(obj.data, dict)


class TestUserActivityMetric(TankTestBase):
    """Cases testing tank.util.metrics.UserActivityMetric class"""

    def test_data_property(self):
        """Object has a data dictionary that matches args."""

        obj = UserActivityMetric(
            "Tank Metrics Unit Test",
            "UserActivityMetric.data property test",
        )
        self.assertTrue(hasattr(obj, 'data'))
        self.assertIsInstance(obj.data, dict)


class TestMetricsDispatchQueueSingleton(TankTestBase):
    """Cases testing tank.util.metrics.MetricsDispatchQueueSingleton class."""

    def test_singleton(self):
        """Multiple instantiations return same instance."""

        obj1 = MetricsDispatchQueueSingleton()
        obj2 = MetricsDispatchQueueSingleton()
        obj3 = MetricsDispatchQueueSingleton()
        self.assertTrue(obj1 == obj2 == obj3)

    # TODO: figure out why server_caps not being patched as in other tests.
    #@patch("tank_vendor.shotgun_api3.Shotgun.server_caps")
    #def test_initialized(self, server_caps_mock):
    #    """Initialized/workers properties set properly when `init` is called."""
    #
    #    obj = MetricsDispatchQueueSingleton()
    #    self.assertFalse(obj.initialized)
    #    self.assertEquals(obj.workers, [])
    #    obj.init(self.tk)
    #    self.assertTrue(obj.initialized)
    #    self.assertNotEqual(obj.workers, [])


class TestMetricsFunctions(TankTestBase):
    """Cases testing tank.util.metrics functions"""

    def test_log_metric(self):
        good_metrics = [
            UserActivityMetric(
                "Tank Metrics Unit Test",
                "tk_metrics.log_metric test",
            ),
            UserAttributeMetric(
                "Test Attribute",
                "tk_metrics.log_metric test",
            ),
        ]
        bad_metrics = [
            UserActivityMetric(None, "UserActivityMetric.data property test"),
            UserActivityMetric("Tank Metrics Unit Test", None),
            UserActivityMetric(None, None),
            UserActivityMetric({}, {}),
            UserActivityMetric([], []),
            UserAttributeMetric(None, "Test Value"),
            UserAttributeMetric("Test Attribute", None),
            UserAttributeMetric(None, None),
            UserAttributeMetric({}, {}),
            UserAttributeMetric([], []),
        ]

        # make sure no exceptions on good metrics
        for metric in good_metrics:
            try:
                log_metric(metric)
            except Exception, e:
                self.fail(
                    "log_metric() failed unexpectedly on good metric (%s): %s",
                    (metric, e)
                )

        # make sure no exceptions on bad metrics
        for metric in bad_metrics:
            try:
                log_metric(metric)
            except Exception, e:
                self.fail(
                    "log_metric() failed unexpectedly on bad metric (%s): %s",
                    (metric, e)
                )

    def test_log_user_activity_metric(self):

        try:
            log_user_activity_metric(
                "Tank Metrics Unit Test",
                "tk_metrics.log_user_activity_metric test",
            )
            log_user_activity_metric(
                None, "tk_metrics.log_user_activity_metric test")
            log_user_activity_metric("Tank Metrics Unit Test", None)
            log_user_activity_metric(None, None)
            log_user_activity_metric({}, {})
            log_user_activity_metric([], [])
        except Exception, e:
            self.fail(
                "log_user_activity_metric() failed unexpectedly: %s" % (e,))

    def test_log_user_attribute_metric(self):

        try:
            log_user_attribute_metric(
                "Test Attribute",
                "tk_metrics.log_user_attribute_metric test",
            )
            log_user_attribute_metric(
                None, "tk_metrics.log_user_attribute_metric test")
            log_user_attribute_metric("Test Attribute", None)
            log_user_attribute_metric(None, None)
            log_user_attribute_metric({}, {})
            log_user_attribute_metric([], [])
        except Exception, e:
            self.fail(
                "log_user_attribute_metric() failed unexpectedly: %s" % (e,))


