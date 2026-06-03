# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os

import sgtk

from sgtk.bootstrap import ToolkitManager

from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import (
    mock,
    ShotgunTestBase,
    TankTestBase,
    temp_env_var,
)


class TestErrorHandling(ShotgunTestBase):
    def test_get_pipeline_configurations_by_id(self):
        pass
class TestFunctionality(ShotgunTestBase):
    @mock.patch(
        "tank.authentication.ShotgunAuthenticator.get_user",
        return_value=mock.Mock(),
    )
    def test_pipeline_config_id_env_var(self, _):
        pass
    @mock.patch(
        "tank.authentication.ShotgunAuthenticator.get_user", return_value=mock.Mock()
    )
    def test_get_entity_from_environment(self, _):
        pass
    @mock.patch(
        "tank.authentication.ShotgunAuthenticator.get_user", return_value=mock.Mock()
    )
    def test_shotgun_bundle_cache(self, _):
        pass
    @mock.patch(
        "tank.authentication.ShotgunAuthenticator.get_user", return_value=mock.Mock()
    )
    def test_serialization(self, _):
        pass
class _MockedShotgunUser(object):
    """
    A fake shotgun user object that we can pass to the manager.
    """

    def __init__(self, mockgun, login):
        self._mockgun = mockgun
        self._login = login

    @property
    def login(self):
        """
        Current User Login
        """
        return self._login

    def create_sg_connection(self):
        """
        Returns the associated mockgun connection
        """
        return self._mockgun


class TestPrepareEngine(ShotgunTestBase):
    def setUp(self):
        pass
    def test_prepare_engine(self):
        pass
class TestGetPipelineConfigs(TankTestBase):
    def setUp(self):
        pass
    def test_basic_execution(self):
        pass
    def test_user_filters(self):
        pass
    @mock.patch(
        "tank.bootstrap.resolver.ConfigurationResolver._create_config_descriptor",
        return_value=mock.Mock(),
    )
    def test_latest_tracking_descriptor(self, _):
        pass
    def test_override_logic(self):
        pass
