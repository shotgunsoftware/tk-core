# -
# *****************************************************************************
# Copyright 2026 Autodesk, Inc. All rights reserved.
#
# These coded instructions, statements, and computer programs contain
# unpublished proprietary information written by Autodesk, Inc. and are
# protected by Federal copyright law. They may not be disclosed to third
# parties or copied or duplicated in any form, in whole or in part, without
# the prior written consent of Autodesk, Inc.
# *****************************************************************************
# +

"""
This module contains convenience constants and globally accessible
session variables relevant to MEDM access and asset management.
"""

from __future__ import annotations  # needed for python 3.9 support

from tank_vendor.flow_data_sdk import GQLClient
from tank_vendor.flow_data_sdk.base.client import AuthenticationHandlerBase
from .exceptions import FlowError
from .utils import get_logger


# Component type ids
# ------------------
# Type ids correspond to specific MEDM schemas (and versions).
# Schemas can be created in a hierarchical fashion using inheritance.
# The schemas below are official Autodesk supported types that are
# commonly relevant to asset management.

BASE_TYPE_ID = "autodesk.me:type-1.1.0"
BINARY_TYPE_ID = "autodesk.me:component.binary-1.0.0"
COMMENT_TYPE_ID = "autodesk.me:component.publishComment-1.0.0"
# NOTE: This is a temporary schema being annexed for representing derivative source
#       which should be switched for a dedicated schema later.
DER_SOURCE_TYPE_ID = "autodesk.me:component.dynamicPlaylistSource-1.0.0"
FOLDER_TYPE_ID = "autodesk.me:type.folder-1.0.0"
IMAGE_TYPE_ID = "autodesk.me:component.binary.image-1.0.0"

# Component types
# ---------------
# Component base type names without full ids.
# This should be a temporary measure, only necessary while some types
# are not yet added to the autodesk domain, and must be created per collection.
FILE_SEQ_TYPE = "type.fileSequence"

# Component names
# ---------------
# Conventional component names for formally supported components.
# NOTE: Component names must be unique within an asset revision.

COMMENT_COMP = "Comment"
DER_SOURCE_COMP = "Derivative Source"
FILE_SEQ_COMP = "File Sequence"
TYPE_COMP = "Type"


# MEDM GQL Client Access
# ----------------------
# Global gql client instance that is initialized per session.
# This variable is for internal use only and should be initialized
# explicitly using the init_client() function, and accessed via get_client().

_gql_client = None


def init_client(endpoint_url: str, auth_handler: AuthenticationHandlerBase):
    """Initialize a global client instance that can be reused for the session.
    Client object can be accessed using `get_client()` function.

    Args:
        endpoint_url: Endpoint to connect to.
        auth_handler: An instance of a subclass of AuthenticationHandlerBase
                      with required authentication interface implemented.
    """
    global _gql_client

    logger = get_logger(__name__)
    logger.info(f"Creating V2 GQL client with endpoint: {endpoint_url}")
    _gql_client = GQLClient(
        endpoint=endpoint_url, auth_handler=auth_handler
    )
    logger.info(f"_gql_client = {_gql_client}")


def get_client() -> GQLClient:
    """Return global client if initialized, otherwise raises an error.

    Raises:
        FlowError
    """
    if _gql_client is None:
        raise FlowError("GQL client has not been initialized.")
    return _gql_client


# Web App url
# -----------
# Store configured web app url as a global for the session.
# This variable is for internal use only.
# Configure this value via set_webapp_url() and access is via get_webapp_url().

_webapp_url = None


def set_webapp_url(url: str):
    """Set global variable for webapp url."""
    global _webapp_url
    logger = get_logger(__name__)
    logger.info(f"Setting Flow web app url to: {url}")
    _webapp_url = url


def get_webapp_url() -> str | None:
    """Return configured webapp url or None if it is not set."""
    return _webapp_url
