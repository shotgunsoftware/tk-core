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
        pass
    def test_log(self, *mocks):
        pass
    @patch.object(metrics.EventMetric, "log")
    def test_log_for_coverage(self, *mocks):
        pass
    @patch.object(
        metrics.EventMetric,
        "log",
    )
    def test_consume(self, *mocks):
        pass
