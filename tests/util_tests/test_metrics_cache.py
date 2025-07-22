# Copyright (c) 2023 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import unittest

from unittest.mock import patch

from tank.platform import (
    engine,
)

from tank.util import (
    metrics,
    metrics_cache,
)


class MetricsCacheTests(unittest.TestCase):
    def tearDown(self):
        for k in os.environ:
            if k.startswith("sgtk_metric_cache_"):
                del os.environ[k]

        super().tearDown()

    def test_log(self, *mocks):
        # not json_serializable
        metrics_cache.log(object(), "name", log_once=True)
        self.assertEqual(
            len([k for k in os.environ if k.startswith("sgtk_metric_cache_")]),
            0,
        )

        metrics_cache.log("group", "name", log_once=object())
        self.assertEqual(
            len([k for k in os.environ if k.startswith("sgtk_metric_cache_")]),
            0,
        )

        metrics_cache.log("group", "name", properties={"k": "v"})
        self.assertEqual(
            os.environ["sgtk_metric_cache_cc567a4f3d676f29"],
            '[["group", "name"], {"properties": {"k": "v"}}]',
        )

    @patch.object(metrics.EventMetric, "log")
    def test_log_for_coverage(self, *mocks):
        engine.set_current_engine(object())
        try:
            metrics_cache.log("group", "name", bundle=object())
            self.assertFalse(
                [k for k in os.environ if k.startswith("sgtk_metric_cache_")],
            )
        finally:
            engine.set_current_engine(None)

    @patch.object(
        metrics.EventMetric,
        "log",
    )
    def test_consume(self, *mocks):
        """
        No assert, just no exception and test coverage
        """

        os.environ["sgtk_metric_cache_1"] = "test"
        metrics_cache.consume()

        os.environ["sgtk_metric_cache_1"] = '"test"'
        metrics_cache.consume()

        os.environ["sgtk_metric_cache_1"] = '["i1", "i2"]'
        metrics_cache.consume()

        os.environ["sgtk_metric_cache_1"] = '[["args"], {"kwargs": {"k": "v"}}]'
        metrics_cache.consume()

        with patch.object(
            os.environ,
            "pop",
            side_effect=KeyError("foo"),
        ):
            os.environ["sgtk_metric_cache_1"] = "test"
            metrics_cache.consume()
