# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from tank_test.tank_test_base import (
    mock,
    ShotgunTestBase,
)

from tank_test.tank_test_base import setUpModule  # noqa


from tank_vendor.shotgun_api3 import AuthenticationFault
from tank.authentication import user_impl, ShotgunAuthenticationError


class ShotgunWrapperTests(ShotgunTestBase):
    """
    Tests the user_impl module.
    """

    @mock.patch("tank_vendor.shotgun_api3.Shotgun._call_rpc")
    @mock.patch("tank_vendor.shotgun_api3.Shotgun.server_caps")
    @mock.patch("tank.authentication.interactive_authentication.renew_session")
    def test_create_connection_with_session_renewal(
        self, renew_session_mock, server_caps_mock, _call_rpc_mock
    ):
        pass
    @mock.patch("tank_vendor.shotgun_api3.Shotgun._call_rpc")
    @mock.patch("tank_vendor.shotgun_api3.Shotgun.server_caps")
    @mock.patch("tank.authentication.interactive_authentication.renew_session")
    def test_create_connection_with_session_renewal_failure(
        self, renew_session_mock, server_caps_mock, _call_rpc_mock
    ):
        pass
    @mock.patch("tank_vendor.shotgun_api3.Shotgun.server_caps")
    @mock.patch("tank.authentication.interactive_authentication.renew_session")
    @mock.patch("tank.authentication.session_cache.get_session_data")
    @mock.patch("tank_vendor.shotgun_api3.Shotgun._call_rpc")
    def test_successfull_session_cache_snooping(
        self,
        _call_rpc_mock,
        get_session_data_mock,
        renew_session_mock,
        server_caps_mock,
    ):
        pass
    @mock.patch("tank_vendor.shotgun_api3.Shotgun.server_caps")
    @mock.patch("tank.authentication.interactive_authentication.renew_session")
    @mock.patch("tank.authentication.session_cache.get_session_data")
    @mock.patch("tank_vendor.shotgun_api3.Shotgun._call_rpc")
    def test_failed_session_cache_snooping(
        self,
        _call_rpc_mock,
        get_session_data_mock,
        renew_session_mock,
        server_caps_mock,
    ):
        pass
