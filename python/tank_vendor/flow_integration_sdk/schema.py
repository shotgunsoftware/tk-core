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
from tank_vendor.flow_data_sdk.base.exceptions import (
    FlowConnectionError,
    GQLAPIError,
    GQLErrorCode,
    ValidationError,
)

from .exceptions import FlowError
from .globals import (
    BASE_COMPONENT_V1_TYPE_ID,
    BASE_COMPONENT_V2_TYPE_ID,
    BASE_PROPERTY_TYPE_ID,
    BASE_TYPE_ID,
    BINARY_TYPE_ID,
    COMMENT_TYPE_ID,
    FLOW_TOOLKIT_LIBRARY_ID,
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
_schema_tree[BASE_PROPERTY_TYPE_ID] = []
_schema_tree[BASE_TYPE_ID] = []
_schema_tree[BINARY_TYPE_ID] = [BASE_COMPONENT_V1_TYPE_ID]
_schema_tree[COMMENT_TYPE_ID] = [BASE_COMPONENT_V2_TYPE_ID]
_schema_tree[FOLDER_TYPE_ID] = [BASE_TYPE_ID]
_schema_tree[IMAGE_TYPE_ID] = [BINARY_TYPE_ID]


# Schema type ids cache
# ---------------------
# This maps custom type names to the full type ids of all their versions.
# The first id is always the version configured in the schema config file
# (see `cache_schema_config()`), followed by any other version found in the
# Flow Toolkit schema library (see `cache_existing_schema_ids()`).
# Format: key = type name (e.g. "type.maya.workfile"), value = list of full type ids
_schema_ids: dict[str, list[str]] = {}


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
            _schema_ids[type_name] = [type_id]
        if display_name:
            _schema_display_names[type_id] = display_name

    # Add configured types to schema tree cache
    for schema in raw_config.get("schemas", {}):
        type_name = schema.get("name", "")
        kind = schema.get("kind")
        if not kind:
            raise ValueError(f"Schema '{type_name}' is missing required 'kind' field.")
        # resolve "$ref:" entries to full ids, pass full type ids through as-is
        parent_types = [
            get_schema_id(pt[5:]) if pt.startswith("$ref:") else pt
            for pt in schema.get("inherits", [])
        ]
        if kind not in KIND_BASE_TYPE_ID:
            raise ValueError(
                f"Unknown schema kind '{kind}' for '{type_name}'. "
                f"Must be one of: {', '.join(KIND_BASE_TYPE_ID)}"
            )
        # mirror SchemaBuilder.build(): the kind base type is only sent when
        # inherits is omitted, otherwise it is reached through the inherited types
        if not parent_types:
            parent_types.append(KIND_BASE_TYPE_ID[kind])
        type_id = get_schema_id(type_name)
        # store ancestral relationship
        if type_id:
            _schema_tree[type_id] = parent_types


def get_schema_id(type_name: str) -> str | None:
    """Return full type id of the configured version of type name if cached.

    Use this when creating schemas or data, which must use the configured
    version.

    Args:
        type_name: Base name of schema type (e.g. "type.template").

    Returns:
        Full id of type, or None if type is not cached.
    """
    type_ids = _schema_ids.get(type_name)
    return type_ids[0] if type_ids else None


def get_schema_ids(type_name: str) -> list[str]:
    """Return the full type ids of every version of type name if cached.

    Use this rather than `get_schema_id()` when searching for existing data,
    which may have been created with another version of the schema (e.g. one
    created before its base type was updated).

    Args:
        type_name: Base name of schema type (e.g. "component.layer").

    Returns:
        List of full type ids, the configured version first. Empty if type is
        not cached.
    """
    return list(_schema_ids.get(type_name, []))


@trace
def cache_existing_schema_ids(project_id: str) -> set[str]:
    """Query every schema in the Flow Toolkit schema library, and add the other
    versions of each configured type to the schema type ids cache.

    Previously added versions are replaced, the configured version is kept
    first. A library that does not exist yet is treated as containing no
    schemas.

    ..note:: `cache_schema_config()` must be called first, only types it
             cached are updated.

    Args:
        project_id: Flow AM project ID.

    Returns:
        Set of full type ids of every schema in the library.

    Raises:
        FlowError
    """
    logger = get_logger(__name__)
    client = get_client()

    q_input = flow_model.SchemasByLibraryIdInput(
        library_id=FLOW_TOOLKIT_LIBRARY_ID,
        project_id=project_id,
    )
    try:
        q_schemas = client.service_schema.schemas_by_library_id(variables=q_input)
        type_ids = {s.type_id for s in q_schemas.schemas_iterator}
    except GQLAPIError as exc:
        if exc.error_code != GQLErrorCode.NOT_FOUND.value:
            msg = f'Failed to retrieve schemas in "{FLOW_TOOLKIT_LIBRARY_ID}": {exc}'
            raise FlowError(msg) from exc
        logger.info(f'Schema library "{FLOW_TOOLKIT_LIBRARY_ID}" not found.')
        type_ids = set()
    except (FlowConnectionError, ValidationError) as exc:
        msg = f'Failed to retrieve schemas in "{FLOW_TOOLKIT_LIBRARY_ID}": {exc}'
        raise FlowError(msg) from exc

    for type_name, cached_ids in _schema_ids.items():
        configured_id = cached_ids[0]
        # type ids are "<namespace>:<type name>-<version>"
        prefix = f"{configured_id.rsplit('-', 1)[0]}-"
        other_ids = sorted(
            type_id
            for type_id in type_ids
            if type_id.startswith(prefix) and type_id != configured_id
        )
        _schema_ids[type_name] = [configured_id] + other_ids

    logger.info(f'Found {len(type_ids)} schemas in "{FLOW_TOOLKIT_LIBRARY_ID}".')
    return type_ids


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
