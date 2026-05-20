# Copyright (c) 2026 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from sgtk.bootstrap import ToolkitManager
from sgtk.bootstrap.errors import TankBootstrapError

from tank.authentication import flow_auth

from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import (
    mock,
    ShotgunTestBase,
    temp_env_var,
)


@mock.patch(
    "tank.authentication.ShotgunAuthenticator.get_user",
    return_value=mock.Mock(),
)
class FlowAuthHookTests(ShotgunTestBase):
    """Coverage for ToolkitManager._check_and_trigger_am_auth."""

    PROJECT_ID = 42

    def _build_manager_with_sg(self, sg_project_payload):
        """Create a ToolkitManager whose _sg_connection.find_one returns
        ``sg_project_payload`` for a Project query."""
        mgr = ToolkitManager()
        mgr._sg_connection = mock.Mock()
        mgr._sg_connection.find_one.return_value = sg_project_payload
        return mgr

    @mock.patch("tank.authentication.flow_auth.get_access_token")
    @mock.patch("tank.authentication.flow_auth.init_authentication")
    @mock.patch("tank.authentication.flow_auth.resolve_flow_auth_settings")
    def test_am_ready_project_triggers_auth(
        self, mock_resolve, mock_init, mock_get, _
    ):
        mock_resolve.return_value = mock.Mock()
        mgr = self._build_manager_with_sg(
            {flow_auth.AM_READY_PROJECT_FIELD: "abc-123"}
        )

        mgr._check_and_trigger_am_auth(self.PROJECT_ID, progress_callback=mock.Mock())

        mock_resolve.assert_called_once()
        mock_init.assert_called_once_with(mock_resolve.return_value)
        mock_get.assert_called_once()

    @mock.patch("tank.authentication.flow_auth.get_access_token")
    @mock.patch("tank.authentication.flow_auth.init_authentication")
    def test_non_am_ready_project_skips_auth(self, mock_init, mock_get, _):
        mgr = self._build_manager_with_sg(
            {flow_auth.AM_READY_PROJECT_FIELD: None}
        )

        mgr._check_and_trigger_am_auth(self.PROJECT_ID, progress_callback=None)

        mock_init.assert_not_called()
        mock_get.assert_not_called()

    @mock.patch("tank.authentication.flow_auth.get_access_token")
    @mock.patch("tank.authentication.flow_auth.init_authentication")
    def test_missing_project_entity_skips_auth(self, mock_init, mock_get, _):
        mgr = self._build_manager_with_sg(None)

        mgr._check_and_trigger_am_auth(self.PROJECT_ID, progress_callback=None)

        mock_init.assert_not_called()
        mock_get.assert_not_called()

    @mock.patch("tank.authentication.flow_auth.get_access_token")
    @mock.patch("tank.authentication.flow_auth.init_authentication")
    def test_empty_project_entity_skips_auth(self, mock_init, mock_get, _):
        mgr = self._build_manager_with_sg({})

        mgr._check_and_trigger_am_auth(self.PROJECT_ID, progress_callback=None)

        mock_init.assert_not_called()
        mock_get.assert_not_called()

    @mock.patch("tank.authentication.flow_auth.get_access_token")
    @mock.patch("tank.authentication.flow_auth.init_authentication")
    def test_none_project_id_skips_auth(self, mock_init, mock_get, _):
        mgr = self._build_manager_with_sg(
            {flow_auth.AM_READY_PROJECT_FIELD: "abc-123"}
        )

        mgr._check_and_trigger_am_auth(None, progress_callback=None)

        # find_one should not even be called when project_id is None
        mgr._sg_connection.find_one.assert_not_called()
        mock_init.assert_not_called()
        mock_get.assert_not_called()

    @mock.patch("tank.authentication.flow_auth.init_authentication")
    @mock.patch("tank.authentication.flow_auth.resolve_flow_auth_settings")
    def test_configuration_error_raises_TankBootstrapError(
        self, mock_resolve, mock_init, _
    ):
        mock_resolve.return_value = mock.Mock()
        mock_init.side_effect = flow_auth.FlowAuthConfigurationError("missing app id")
        mgr = self._build_manager_with_sg(
            {flow_auth.AM_READY_PROJECT_FIELD: "abc-123"}
        )

        with self.assertRaises(TankBootstrapError):
            mgr._check_and_trigger_am_auth(self.PROJECT_ID, progress_callback=mock.Mock())

    @mock.patch("tank.authentication.flow_auth.get_access_token")
    @mock.patch("tank.authentication.flow_auth.init_authentication")
    @mock.patch("tank.authentication.flow_auth.resolve_flow_auth_settings")
    def test_runtime_error_soft_fails_by_default(
        self, mock_resolve, mock_init, mock_get, _
    ):
        mock_resolve.return_value = mock.Mock()
        mock_get.side_effect = RuntimeError("network down")
        mgr = self._build_manager_with_sg(
            {flow_auth.AM_READY_PROJECT_FIELD: "abc-123"}
        )

        # Should not raise.
        mgr._check_and_trigger_am_auth(self.PROJECT_ID, progress_callback=mock.Mock())

    @mock.patch("tank.authentication.flow_auth.get_access_token")
    @mock.patch("tank.authentication.flow_auth.init_authentication")
    @mock.patch("tank.authentication.flow_auth.resolve_flow_auth_settings")
    def test_runtime_error_hard_fails_with_env_var(
        self, mock_resolve, mock_init, mock_get, _
    ):
        mock_resolve.return_value = mock.Mock()
        mock_get.side_effect = RuntimeError("network down")
        mgr = self._build_manager_with_sg(
            {flow_auth.AM_READY_PROJECT_FIELD: "abc-123"}
        )

        with temp_env_var(TK_FLOW_AUTH_REQUIRED="1"):
            with self.assertRaises(TankBootstrapError):
                mgr._check_and_trigger_am_auth(
                    self.PROJECT_ID, progress_callback=mock.Mock()
                )


@mock.patch(
    "tank.authentication.ShotgunAuthenticator.get_user",
    return_value=mock.Mock(),
)
class ResolveProjectIdTests(ShotgunTestBase):
    """Coverage for ToolkitManager._resolve_project_id (refactored helper)."""

    def test_none_entity_returns_none(self, _):
        mgr = ToolkitManager()
        self.assertIsNone(mgr._resolve_project_id(None))

    def test_project_entity_returns_id(self, _):
        mgr = ToolkitManager()
        self.assertEqual(
            mgr._resolve_project_id({"type": "Project", "id": 99}), 99
        )

    def test_entity_with_project_link_returns_id(self, _):
        mgr = ToolkitManager()
        self.assertEqual(
            mgr._resolve_project_id(
                {"type": "Shot", "id": 1, "project": {"type": "Project", "id": 77}}
            ),
            77,
        )

    def test_entity_without_project_link_queries_sg(self, _):
        mgr = ToolkitManager()
        mgr._sg_connection = mock.Mock()
        mgr._sg_connection.find_one.return_value = {"project": {"type": "Project", "id": 55}}

        self.assertEqual(
            mgr._resolve_project_id({"type": "Shot", "id": 1}), 55
        )

    def test_entity_with_no_project_raises(self, _):
        mgr = ToolkitManager()
        mgr._sg_connection = mock.Mock()
        mgr._sg_connection.find_one.return_value = None

        with self.assertRaises(TankBootstrapError):
            mgr._resolve_project_id({"type": "Shot", "id": 1})
