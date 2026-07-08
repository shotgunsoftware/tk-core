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

from dataclasses import dataclass
from typing import Callable

from tank_vendor.flow_data_sdk import GQLClient
from tank_vendor.flow_data_sdk.base.client import AuthenticationHandlerBase

from . import utils
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
REFERENCE_TYPE = "component.reference"


# Component purposes
# ------------------
# Purposes are special designations that can be added to a binary component to
# differentiate it based on function/characteristic. Values are completely arbitrary.
# The purposes below are some basic defaults that are generally useful,
# but integrations can choose to use other values.

SOURCE_PURPOSE = "source"
THUMBNAIL_PURPOSE = "thumbnail"


# Component names
# ---------------
# Conventional component names for formally supported components.
# NOTE: Component names must be unique within an asset revision.

COMMENT_COMP = "Comment"
DER_SOURCE_COMP = "Derivative Source"
FILE_SEQ_COMP = "File Sequence"
SOURCE_COMP = "Source"
THUMBNAIL_COMP = "Thumbnail"
TYPE_COMP = "Type"


# MEDM GQL Client Access
# ----------------------
# Global gql client instance that is initialized per session.
# This variable is for internal use only and should be initialized
# explicitly using the init_client() function, and accessed via get_client().

_gql_client: GQLClient | None = None


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
    _gql_client = GQLClient(endpoint=endpoint_url, auth_handler=auth_handler)


def get_client() -> GQLClient:
    """Return global client if initialized, otherwise raises an error.

    Raises:
        FlowError
    """
    if _gql_client is None:
        raise FlowError("GQL client has not been initialized.")
    return _gql_client


# MEDM Session Collection
# ----------------------
# The session collection stores the MEDM collection that we are operating
# under for the current session. Tracking this helps us to query schema information
# from the right collection.

_session_collection: SessionCollection | None = None


@dataclass
class SessionCollection:
    """Data class containing relevant information for session collection.
    It tracks the collection id, and provides easy access to pertinent attributes.
    """

    #: Id of collection
    id: str
    #: Organization ID of collection
    organization_id: str
    #: Group Id of collection
    group_id: str

    def is_cpa_collection(self) -> bool:
        """Return true if session project is from a CPA provisioned collection."""
        if self.organization_id == "fstech":
            return False
        return True

    def __str__(self):
        """Stringify object info in readable way."""
        s = "SESSION COLLECTION:\n"
        s += f"\tid: {self.id}\n"
        s += f"\torganization_id: {self.organization_id}\n"
        s += f"\tgroup_id: {self.group_id}\n"
        return s


def init_session_collection(collection_id: str, organization_id: str, group_id: str):
    """Store collection info for session.

    Global SessionCollection data object can be accessed using `get_session_collection()`
    function.

    Args:
        collection_id: MEDM collection id.
        organization_id: Organization id of collection.
        group_id: Group id of collection.
    """
    global _session_collection

    logger = get_logger(__name__)
    logger.info("Setting session collection info...")
    _session_collection = SessionCollection(
        id=collection_id,
        organization_id=organization_id,
        group_id=group_id,
    )
    logger.info(_session_collection)


def get_session_collection() -> SessionCollection:
    """Return session collection if initialized, otherwise raises an error.

    Raises:
        FlowError
    """
    if _session_collection is None:
        raise FlowError("Session collection has not been initialized.")
    return _session_collection


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


# Configure logger
# ----------------
# Set a logger callback for use in the integration sdk.
# If not configured, a default python logger will be used.


def set_logger_callback(callback: Callable):
    """Set the function that returns the logger for the session."""
    utils._logger_callback = callback
