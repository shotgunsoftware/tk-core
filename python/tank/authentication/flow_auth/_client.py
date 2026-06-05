# Copyright (c) 2026 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Flow GQL SDK client factory with authentication wired in.
"""

from ._authentication import get_flow_access_token


class FlowAuthenticationHandler:
    """Auth adapter for the Flow GQL SDK client.

    Satisfies the SDK's ``auth_handler`` interface: the client calls
    ``get_authentication_token()`` on every request so that short-lived tokens
    are transparently refreshed without recreating the client.
    """

    def get_authentication_token(self) -> str:
        return get_flow_access_token()


def get_flow_client(endpoint_url=None):
    """Return a ready-to-use Flow GQL SDK client with authentication wired in.

    Lazy-initialises APS auth if bootstrap has not already done so. Uses the
    SDK default endpoint (``tank_vendor.flow_data_sdk.config.DEFAULT_ENDPOINT``)
    when ``endpoint_url`` is not supplied.

    :param endpoint_url: Override the GraphQL endpoint. Defaults to the SDK's
        production endpoint.
    :type endpoint_url: str or None
    :returns: Initialised ``GQLClient`` instance.
    """
    from tank_vendor.flow_data_sdk import GQLClient
    from tank_vendor.flow_data_sdk.config import DEFAULT_ENDPOINT

    return GQLClient(
        endpoint=endpoint_url or DEFAULT_ENDPOINT,
        auth_handler=FlowAuthenticationHandler(),
    )
