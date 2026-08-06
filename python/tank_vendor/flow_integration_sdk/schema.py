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
#

"""Utilities for querying and caching schema information."""

from __future__ import annotations  # needed for python 3.9 support

import json
import os
from functools import cache

from tank_vendor.flow_data_sdk.base import model as flow_model
from tank_vendor.flow_data_sdk.base.exceptions import GQLAPIError

from .exceptions import FlowError
from .globals import (
    BASE_COMPONENT_TYPE_ID,
    BASE_PROPERTY_TYPE_ID,
    BASE_TYPE_ID,
    BINARY_TYPE_ID,
    COMMENT_TYPE_ID,
    FOLDER_TYPE_ID,
    get_client,
    get_session_collection,
    IMAGE_TYPE_ID,
    KIND_BASE_TYPE_ID,
)
from .utils import get_logger, trace


# Schema inheritance tree cache
# -----------------------------
# Stored globally as an optimization to avoid querying/re-querying
# parent types of known schema types.
# Format:  key = schema type id, value = list of parent types
_schema_tree: dict[str, list[str]] = {}

# Hardcode some well known relationships and root types
_schema_tree[BASE_COMPONENT_TYPE_ID] = []
_schema_tree[BASE_PROPERTY_TYPE_ID] = []
_schema_tree[BASE_TYPE_ID] = []
_schema_tree[BINARY_TYPE_ID] = [BASE_COMPONENT_TYPE_ID]
_schema_tree[COMMENT_TYPE_ID] = [BASE_COMPONENT_TYPE_ID]
_schema_tree[FOLDER_TYPE_ID] = [BASE_TYPE_ID]
_schema_tree[IMAGE_TYPE_ID] = [BINARY_TYPE_ID]


# Schema type ids cache
# ---------------------
# This maps custom type names to full type ids
# Format: key = type name (e.g. "type.maya.workfile"), value = full type id
_schema_ids: dict[str, str] = {}


# Schema display name cache
# -------------------------
# Caches display data of schemas to avoid re-querying.
# Format: key = type id, value = display name
_schema_display_names: dict[str, str] = {}


def _read_schema_config(config_path: str):
    """Read the given json config file, and return raw json dictionary."""
    logger = get_logger(__name__)

    logger.info(f"Reading schema type ids config file: {config_path}")
    if not os.path.exists(config_path):
        raise RuntimeError(f"Schema config file not found: {config_path}")

    with open(config_path) as f:
        try:
            raw_config = json.loads(f.read())
        except json.decoder.JSONDecodeError as exc:
            raise ValueError("Schema config file is invalid.") from exc
    return raw_config


def _compose_schema_id(type_name: str, version: str):
    """Generate a full type id with info provided."""
    session_collection = get_session_collection()
    org_id = session_collection.organization_id
    group_id = session_collection.group_id
    namespace = f"{org_id}.{group_id}"
    return f"{namespace}:{type_name}-{version}"


@trace
def cache_schema_config(config_path: str):
    """Add types from provided schema config json file into schema cache
    to optimize queries against them.

    ..note:: `globals.init_session_collection()` must be called before
             attempting to add to schema cache.

    Args:
        config_path: Path to json schema config file.

    Raises:
        RuntimeError
        ValueError
    """
    raw_config = _read_schema_config(config_path)

    # Cache type id and display name info for configured types
    for schema in raw_config.get("schemas", {}):
        type_name = schema.get("name", "")
        type_version = schema.get("version", "")
        display_name = schema.get("display_name", "")
        if type_name and type_version:
            type_id = _compose_schema_id(type_name, type_version)
            _schema_ids[type_name] = type_id
        if display_name:
            _schema_display_names[type_id] = display_name

    # Add configured types to schema tree cache
    for schema in raw_config.get("schemas", {}):
        type_name = schema.get("name", "")
        kind = schema.get("kind")
        if not kind:
            raise ValueError(f"Schema '{type_name}' is missing required 'kind' field.")
        parent_types = schema.get("inherits", [])
        # strip "$ref:" prefix
        parent_types = [pt[5:] for pt in parent_types]
        # convert to full ids
        parent_types = [get_schema_id(pt) for pt in parent_types]
        # always include the kind-appropriate base type
        if kind not in KIND_BASE_TYPE_ID:
            raise ValueError(
                f"Unknown schema kind '{kind}' for '{type_name}'. "
                f"Must be one of: {', '.join(KIND_BASE_TYPE_ID)}"
            )
        parent_types.append(KIND_BASE_TYPE_ID[kind])
        type_id = get_schema_id(type_name)
        # store ancestral relationship
        if type_id:
            _schema_tree[type_id] = parent_types


def get_schema_id(type_name: str) -> str | None:
    """Return full type id of type name if cached.

    Args:
        type_name: Base name of schema type (e.g. "type.template").

    Returns:
        Full id of type, or None if type is not cached.
    """
    return _schema_ids.get(type_name, None)


@trace
def get_schema_display_name(type_id: str) -> str | None:
    """Return display name of schema of given its type id.

    Args:
        type_id: Schema type id to be queried.

    Returns:
        Display name of schema if set, or None if not set.

    Raises:
        FlowError
    """
    logger = get_logger(__name__)

    if type_id in _schema_display_names:
        return _schema_display_names[type_id]

    # Type is not in schema config, must query display name
    client = get_client()
    q_input = flow_model.GetSchemaDisplayDataInput(schema_type_id=type_id)
    q_schema_display = client.service_schema.schema_display_data(q_input)
    try:
        logger.info(f"Querying schema display data for type id: {type_id}.")
        r_schema_display = q_schema_display.call()
    except GQLAPIError as exc:
        msg = f"Error querying schema display data for type id: {type_id}. {exc}"
        raise FlowError(msg) from exc
    display_data = r_schema_display.schema_display_data
    if display_data.display_name == flow_model.NOT_SET:
        return None
    # Cache display name before returning
    _schema_display_names[type_id] = display_data.display_name
    return display_data.display_name


@cache
@trace
def is_sub_type(base_id: str, type_id: str) -> bool:
    """Return True if provided type is a sub class of base type.

    Args:
        base_id: String base type id.
        type_id: String type id.

    Returns:
        True if type_id derives from base_id.

    Raises:
        FlowError
    """
    logger = get_logger(__name__)

    if base_id == type_id:
        return True

    # Check schema tree cache for input type
    def match_ancestor(base_id, type_id):
        if type_id not in _schema_tree:
            raise ValueError("Unregistered type id.")
        parent_types = _schema_tree[type_id]
        for parent_type in parent_types:
            if parent_type == base_id:
                return True
            if match_ancestor(base_id, parent_type):
                return True
        return False

    try:
        return match_ancestor(base_id, type_id)
    except ValueError:
        # The type in question is not in our config cache
        # We are forced to make a query
        msg = f'Querying schema subclasses for base type "{base_id}" to find type "{type_id}".'
        logger.info(msg)
        client = get_client()
        session_collection = get_session_collection()
        q_input = flow_model.SchemasBySuperTypeInput(
            collection_id=session_collection.id,
            type_id=base_id,
            include_sub_sub_classes=True,
        )
        q_schema = client.service_schema.schemas_by_super_type(q_input)
        try:
            # NOTE: Iterator wraps q_schema.call() so no need to invoke this
            #       exlicitly.
            for subtype in q_schema.schema_types_iterator:
                if type_id == subtype:
                    return True
            return False
        except GQLAPIError as exc:
            msg = f'Error querying subtypes of base type "{base_id}": {exc}'
            raise FlowError(msg) from exc


def get_schema_config_version(config_path: str) -> str:
    """Retrieve the schema config version from a config.json file.

    Args:
        config_path: Path to the schema config json file.

    Returns:
        The schema config version, or 'unknown' if the key is not present.

    Raises:
        RuntimeError: If the config file is not found.
        ValueError: If the config file contains invalid JSON.
    """
    config = _read_schema_config(config_path)
    return config.get("version", "unknown")
