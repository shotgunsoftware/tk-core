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
This module provides utilities related to storage locations.
"""

from __future__ import annotations  # needed for python 3.9 support

import os
import json
from functools import cache
from filelock import FileLock

from tank_vendor.flow_data_sdk.base import model as medm_model

from .utils import (
    abspath,
    cleanpath,
    ensure_dir,
    get_logger,
    trace,
)
from .exceptions import (
    ConfigurationError,
    DirectoryNotCreatedError,
    FlowError,
)


# Storage roots
# -------------
# Environment variables that store key storage root paths.
# Paths should be configured via set_sandbox_root() and set_storage_root().
# They should be accessed via get_sandbox_root() and get_storage_root()

# Sandbox storage root - for draft assets/revisions (editable)
FLOW_SANDBOX_ROOT = "FLOW_SANDBOX_ROOT"

# Primary cache root - for binaries cached locally from remote storage (read-only)
FLOW_STORAGE_ROOT = "FLOW_STORAGE_ROOT"


def set_sandbox_root(sandbox_root: str, create_dir: bool = False):
    """Set sandbox root location.

    Args:
        sandbox_root: Path to top-level sandbox directory.
        create_dir: If True, create this directory if it doesn't exist.

    Raises:
        DirectoryNotCreatedError
    """
    logger = get_logger(__name__)

    # Expand user paths (e.g., ~ to /Users/username)
    sandbox_root = os.path.expanduser(sandbox_root)
    # Ensure path is absolute and real
    sandbox_root = abspath("", sandbox_root)
    logger.info(f"Setting Flow sandbox directory to: {sandbox_root}")
    if create_dir:
        try:
            # Create directory if necessary
            ensure_dir(sandbox_root)
        except DirectoryNotCreatedError as exc:
            raise ConfigurationError(
                details=f"Couldn't create directory {sandbox_root} for sandbox root."
            ) from exc

    os.environ[FLOW_SANDBOX_ROOT] = sandbox_root


def set_storage_root(storage_root: str, create_dir: bool = False):
    """Set primary cache location.

    Args:
        storage_root: Path to top-level primary cache directory.
        create_dir: If True, create this directory if it doesn't exist.

    Raises:
        DirectoryNotCreatedError
    """
    logger = get_logger(__name__)

    # Expand user paths (e.g., ~ to /Users/username)
    storage_root = os.path.expanduser(storage_root)
    # Ensure path is absolute and real
    storage_root = abspath("", storage_root)
    logger.info(f"Setting Flow storage directory to: {storage_root}")
    if create_dir:
        try:
            # Create directory if necessary
            ensure_dir(storage_root)
        except DirectoryNotCreatedError as exc:
            raise ConfigurationError(
                details=f"Couldn't create directory {storage_root} for primary storage root."
            ) from exc
    os.environ[FLOW_STORAGE_ROOT] = storage_root


def get_sandbox_root() -> str:
    """Return the root directory of sandbox location.

    Returns:
        Full path to configured sandbox root directory.
    """
    return os.getenv(FLOW_SANDBOX_ROOT, "")


def get_storage_root() -> str:
    """Return the root directory of primary cache location.

    Returns:
        Full path to configured storage root directory.
    """
    return os.getenv(FLOW_STORAGE_ROOT, "")


def get_storage_key(asset_id: str) -> str:
    """Parse storage key from asset id.
    This is a unique file-safe id that can be used in storage file paths.

    Args:
        asset_id: Medm asset id.

    Returns:
        Storage key associated with that asset.
    """
    return asset_id.rsplit(":", maxsplit=1)[-1]


def get_storage_asset_dir(asset_id: str) -> str:
    """Return the full path of asset directory in primary storage
    (whether or not the directory exists).

    Args:
        asset_id: Medm asset id.

    Returns:
        Full path to expected location of primary storage directory on local disk.
    """
    return cleanpath(get_storage_root(), get_storage_key(asset_id))


def get_storage_revision_dir(asset_id: str, revision_number: int) -> str:
    """Return the full path of asset directory in primary storage
    for the given revision of asset (whether or not the directory exists).

    Args:
        asset_id: Medm asset id.
        revision_number: Number of revision.

    Returns:
        Full path to expected location of primary storage directory on local disk.
    """
    return cleanpath(get_storage_asset_dir(asset_id), f"r{revision_number}")


@trace
def _cache_asset_info(asset_id: str):
    """Store relevant, persistent metadata about this asset to its
    storage directory. This will be very useful for certain lookups.

    In particular, we want to cache the relationship between the asset's
    storage key and asset id. We do this by saving a sidecar file to the
    asset's storage directory. Looking this up via the sidecar file will
    save a very expensive query when mapping storage key back to asset id.

    Args:
        asset_id: Id of asset whose info should be cached.

    Raises:
        FlowError
    """
    # Check if the info file already exists
    # If so, check that it is complete. File reads are cheap so doing
    # this every time an Asset object is constructed should be ok.
    storage_dir = get_storage_asset_dir(asset_id)
    file_path = cleanpath(storage_dir, ".info")
    info = {}
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            try:
                info = json.loads(f.read())
            except json.JSONDecodeError:
                # We don't care if the file is corrupted, just write a new one
                pass

    # For now we're only storing asset id
    expected_keys = ["asset_id"]
    write_file = False
    for key in expected_keys:
        if key not in info:
            # If the file is incomplete, re-write the file
            write_file = True
            break

    if not write_file:
        return

    info = {"asset_id": asset_id}
    try:
        if not os.path.exists(storage_dir):
            os.makedirs(storage_dir)
        # Lock file before writing to it
        lock = FileLock(f"{file_path}.lock")
        with lock:
            with open(file_path, "w") as f:
                f.write(json.dumps(info, indent=4))
    except Exception as exc:  # pylint: disable=broad-except
        msg = f"Asset info file could not be written: {file_path}"
        raise FlowError(msg) from exc


@cache
@trace
def storage_key_to_asset_id(storage_key: str) -> str:
    """Given an asset storage key, return the corresponding asset id.

    Args:
        storage_key: String asset storage key.

    Returns:
        Asset id.

    Raises:
        FlowError
    """
    # Check if storage key to asset id lookup is cached
    info_file = cleanpath(get_storage_root(), storage_key, ".info")
    if os.path.exists(info_file):
        with open(info_file, "r") as f:
            info = json.loads(f.read())
            asset_id = info.get("asset_id")
            if asset_id is not None:
                return asset_id

    # Fallback plan is to do a very expensive project query
    # TODO: implement query

    raise FlowError(f"Invalid storage key provided: {storage_key}")


def get_storage_component_path(
    revision: medm_model.AssetRevision,
    component_name: str = "",
    component_purpose: str = "",
    blob_index: int = 0,
) -> str | None:
    """Return the full path of the component blob file of the given asset revision
    in primary storage (whether or not the file exists).

    Args:
        revision: Revision to which component belongs.
        component_name: If provided, search for component with this name and return its storage path.
                        This should be unique within the revision.
        component_purpose: If provided, search for a component with this purpose and return
                           its storage path. There may be multiple components with the same purpose,
                           so the first match will be returned.
        blob_index: Specific blob from source component to get.

    ..note:: If both component name and purpose are provided, the first intersection
             of both criteria will be returned.

    Returns:
        Full path to expected location of cached source file on local disk, or
        None if the component does not exist on the revision.

    Raise:
        FlowError
    """
    comp = _find_component(revision, name=component_name, purpose=component_purpose)
    if not comp:
        return None
    try:
        blob_path = comp.data["data"][blob_index]["path"]
    except KeyError as exc:
        msg = f'Blob path could not be retrieved for component "{comp.name}". {exc}'
        raise FlowError(msg)
    storage_dir = get_storage_revision_dir(revision.asset_id, revision.revision_number)
    return cleanpath(storage_dir, blob_path)


def _find_component(
    revision: medm_model.AssetRevision,
    name: str = "",
    purpose: str = "",
    type_id: str = "",
) -> medm_model.Component | None:
    """Match component on given revision based on criteria.
    If multiple criteria is provided, the first intersection will be returned.

    Args:
        revision: Revision to be searched.
        name: Name of component to match.
        purpose: Purpose of component to match.
                 NOTE: this is only applicable to binary components.
        type_id: Type id of component to match.
    """
    for comp in revision.components:
        comp_purpose = comp.data.get("purpose", "")
        if name and comp.name != name:
            continue
        if purpose and comp_purpose != purpose:
            continue
        if type_id and comp.type_id != type_id:
            continue
        return comp
    return None
