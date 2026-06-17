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
This module contains classes and utilities that facilitate the "sandbox".
This is a space on disk reserved for work in progress. Assets can be created,
or checked out in the sandbox, modified, and then published back to MEDM.

The collection of files for an asset that is in sandbox is called a "draft".
These are contained within a "draft folder" whose location is managed by this module
(though the root location is configured in `storage.set_sandbox_root()`).
Within, the draft folder, a draft info sidecar file is stored to record important
information about a new draft or checkout draft.
    * new draft = working on brand new asset
    * checkout draft = working on published asset

Draft files are by definition unpublished. Drafts are identified by either
an asset's storage key or temporary uuid for brand new assets.

Within this module, we have utilities for querying draft information from the file system.
As well, there are key utilities for manipulating drafts including
    * creating new assets as drafts
    * checking out assets as drafts
    * discarding drafts
    * publishing new assets or revisions from drafts
"""

from __future__ import annotations  # needed for python 3.9 support

import json
import os
import shutil
import uuid
from dataclasses import dataclass, asdict

from tank_vendor.flow_data_sdk.base import model as medm_model
from tank_vendor.flow_data_sdk.base.exceptions import GQLAPIError

from .fetch import fetch
from .globals import BASE_TYPE_ID, get_client
from .exceptions import (
    EntityNotFoundError,
    FlowError,
    DraftExistsError,
    InvalidDraftError,
    PublishAssetError,
    PublishConflictError,
)
from .publish import (
    CommentComponentSpec,
    ComponentSpec,
    publish_new_asset,
    publish_new_revision,
    TypeComponentSpec,
)
from .storage import (
    get_sandbox_root,
    get_storage_component_path,
    get_storage_key,
)
from .utils import (
    cleanpath,
    get_logger,
    is_sub_directory,
    relpath,
    trace,
)


@dataclass
class DraftInfo:
    """Base class for draft info dataclasses with providing common functionality."""

    #: Id that uniquely identifies a draft in local sandbox.
    draft_id: str

    @trace
    def write_file(self, file_path: str):
        """Write contents of dataclass to draft info file.

        Args:
            file_path: Full path to destination file.

        Raises:
            FlowError
        """
        try:
            with open(file_path, "w") as f:
                f.write(json.dumps(asdict(self), indent=4))
        except Exception as exc:  # pylint: disable=broad-except
            msg = f"Draft info file could not be written: {file_path}"
            raise FlowError(msg) from exc

    @classmethod
    @trace
    def read_file(cls, file_path: str) -> DraftInfo:
        """Read a draft info file and convert into draft dataclass.

        Args:
            file_path: Full path to draft info file.

        Returns:
            Sub-class of BaseDraft.

        Raises:
            FlowError
        """
        try:
            with open(file_path, "r") as f:
                json_str = f.read()
        except (IOError, OSError) as exc:
            msg = f"Draft info file could not be opened: {file_path}"
            raise FlowError(msg) from exc

        try:
            json_dict = json.loads(json_str)
        except json.JSONDecodeError as exc:
            msg = f"Draft info file format is invalid: {file_path}"
            raise FlowError(msg) from exc

        draft_type = json_dict.get("draft_type")
        if draft_type == "new":
            try:
                return NewDraftInfo(**json_dict)
            except TypeError as exc:
                msg = f"Draft info file is missing required attributes for NewDraftInfo: {file_path}"
                raise FlowError(msg) from exc
        elif draft_type == "checkout":
            try:
                return CheckoutDraftInfo(**json_dict)
            except TypeError as exc:
                msg = f"Draft info file is missing required attributes for CheckoutDraftInfo: {file_path}"
                raise FlowError(msg) from exc
        else:
            msg = f"Draft info file has invalid draft type designated: {file_path}"
            raise FlowError(msg)

    def pprint(self):
        """Print dataclass contents in readable way."""

        logger = get_logger(__name__)
        printstr = "\n-----------------------------------------\n"
        printstr += f"{self.__class__.__name__}\n"
        printstr += "-----------------------------------------\n"
        for prop, value in self.__dict__.items():
            printstr += f"    {prop}: {value}\n"
        logger.info(printstr)


@dataclass
class CheckoutDraftInfo(DraftInfo):
    """Container for info associated with a checkout draft.
    NOTE: A checkout draft is a draft that results from checking out
          a published revision.
    """

    #: Name of asset.
    name: str
    #: Id of asset.
    asset_id: str
    #: Version number of asset checked out.
    version: int
    #: Revision number of asset checked out.
    revision: int
    #: Latest published version of asset at the time of checkout.
    latest_version: int
    #: Latest published revision of asset at the time of checkout.
    latest_revision: int
    #: Source path of draft.
    source_path: str
    #: Record draft type as a constant property which makes recording to file easier.
    draft_type: str = "checkout"


@dataclass
class NewDraftInfo(DraftInfo):
    """Container for info associated with a new draft.
    NOTE: A new draft is a draft for an asset that has been created and not yet published.
    """

    #: Name of asset.
    name: str
    #: Description of new asset.
    description: str
    #: Id of parent of new asset.
    parent_id: str
    #: Type ids to be associated with new asset.
    type_ids: list[str]
    #: Source path of draft.
    source_path: str
    #: Record draft type as a constant property which makes recording to file easier.
    draft_type: str = "new"


# ------------------------------------------
# DRAFT DATA ACCESSORS
# ------------------------------------------


@trace
def get_draft_id(asset_id: str | None = None) -> str:
    """Return a local draft id for given asset.

    Args:
        asset_id: Medm asset id. If None, this is treated as a new asset -
                  return a temporary uuid.

    Returns:
        Draft id for asset.
    """
    # NOTE: For this sandbox implementation, we will use the storage key as the
    #       draft id for any published assets, and generate a uuid for new asset.
    if asset_id is None:
        return str(uuid.uuid4())
    else:
        return get_storage_key(asset_id)


def get_draft_folder(draft_id: str) -> str:
    """Return the location of the draft folder for the given draft id.

    Args:
        draft_id: Id that uniquely identifies a draft within local sandbox.

    Returns:
        Full path to draft folder on local disk.
    """
    sandbox_root = get_sandbox_root()
    return f"{sandbox_root}/{draft_id}/draft"


@trace
def read_draft_info(draft_id: str) -> DraftInfo:
    """Read the draft info sidecar file and convert into draft dataclass.

    Args:
        draft_id: Id that uniquely identifies a draft within local sandbox.

    Returns:
        Subclass of DraftInfo dataclass.

    Raises:
        InvalidDraftError
    """
    draft_folder = get_draft_folder(draft_id)
    draft_info_file = cleanpath(draft_folder, ".draft")
    if not os.path.exists(draft_info_file):
        msg = f"Draft info file not found: {draft_info_file}"
        raise InvalidDraftError(draft_id=draft_id, details=msg)
    try:
        return DraftInfo.read_file(draft_info_file)
    except FlowError as exc:
        raise InvalidDraftError(draft_id=draft_id, details=str(exc))


@trace
def is_new_asset(draft_id: str) -> bool:
    """Return True if the draft id provided points to a new asset that has
    never been published.

    Args:
        draft_id: Id that uniquely identifies a draft within local sandbox.
    """
    draft_info = read_draft_info(draft_id)
    return isinstance(draft_info, NewDraftInfo)


@trace
def is_local_draft(draft_id: str) -> bool:
    """Return True if the draft id provided points to draft in local sandbox.

    Args:
        draft_id: Id that uniquely identifies a draft within local sandbox.
    """
    draft_folder = get_draft_folder(draft_id)
    return os.path.exists(draft_folder)


@trace
def get_draft_context(draft_path: str) -> str | None:
    """Given a file path, if it is a draft path in the local sandbox,
    return the associated draft id. Otherwise return None.

    Args:
        draft_path: A file path which is potentially belonging to a draft.

    Returns:
        Draft id or None if path does not belong to a draft.

    Raises:
        ValueError
    """
    sandbox_root = get_sandbox_root()
    if not is_sub_directory(sandbox_root, draft_path):
        return None

    draft_path = relpath(sandbox_root, draft_path)
    try:
        draft_id, version, filename = draft_path.split("/")
    except ValueError:
        return None

    if version != "draft":
        return None

    return draft_id


def get_asset_drafts(asset_id: str) -> list[CheckoutDraftInfo]:
    """Return all local drafts that exist for the given asset.

    .. note:: Currently, we only support a single draft per asset,
              however this could change in the future with the introduction
              of multiple checkouts/sandboxes. Returning a list keeps this
              utility flexible.

    The returned values will be CheckoutDraftInfo objects which will contain
    detailed information about each draft.

    .. note:: This function can only be used to retrieve information about
              checkouts. Please use `get_drafts(draft_type="new")` function
              to retrieve list of brand new assets that exist in sandbox.

    Args:
        asset_id: Id of MEDM asset. This can also be a revision or version id
                  from the same asset.

    Returns:
        List of CheckoutDraftInfo objects.
    """
    # Retrieve asset's draft id
    draft_id = get_draft_id(asset_id)
    # Read draft info if it exists
    try:
        draft_info = read_draft_info(draft_id)
    except InvalidDraftError:
        return []
    return [draft_info]


def get_drafts(draft_type: str | None = None) -> list[DraftInfo]:
    """Return a list of all drafts found in local sandbox.

    Args:
        draft_type: If specified, filter by given draft type.
                    Accepted values include "new" or "checkout".

    Returns:
        List of DraftInfo objects that may be either
        CheckoutDraftInfo or NewDraftInfo types.

    Raise:
        FlowError
    """
    sandbox_root = get_sandbox_root()
    if not os.path.exists(sandbox_root):
        raise FlowError(f"Configured sandbox root does not exist: {sandbox_root}")

    drafts = []
    for item in os.listdir(sandbox_root):
        if not os.path.isdir(os.path.join(sandbox_root, item)):
            continue
        draft_id = item
        try:
            draft_info = read_draft_info(draft_id)
        except InvalidDraftError:
            continue
        if draft_type is not None and draft_type != draft_info.draft_type:
            continue  # skip if filter doesn't match
        drafts.append(draft_info)
    return drafts


# ------------------------------------------
# SANDBOX UTILITIES
# ------------------------------------------


@trace
def create_asset_in_sandbox(
    name: str,
    description: str,
    parent_id: str,
    type_ids: list[str] | None = None,
    source_path: str = "",
) -> NewDraftInfo:
    """Create a workspace for a new asset in sandbox.

    Args:
        name: String name for asset.
        description: Description of the asset.
        parent_id: Id of parent entity, which may be a project, folder or asset.
        type_ids: List of type ids to be attached to asset.
        source_path: Optionally provide a source file to be associated with new asset.

    Returns:
        NewDraftInfo object.

    Raises:
        EntityNotFoundError
    """

    # NOTE: This function will "create" an asset in the sense of creating a
    #       draft location for the asset and storing a sidecar file with
    #       relevant metadata, but not create anything on MEDM.
    #       The actual creation of the MEDM asset will be done at publish time.

    # Create unique draft id that is file safe
    draft_id = get_draft_id()

    # Create a draft folder
    draft_folder = get_draft_folder(draft_id)
    if not os.path.exists(draft_folder):
        os.makedirs(draft_folder)

    # Copy source file to draft folder if applicable
    # TODO: This is over-simplified, and makes assumptions about a single source file
    #       as well as simple types.
    #       In future, we should accept ComponentSpecs instead which must
    #       be serialized into the draft info file to be re-created at publish time.
    #       We should also allow specification of multiple "input" files.
    if source_path:
        draft_path = cleanpath(draft_folder, os.path.basename(source_path))
        shutil.copyfile(source_path, draft_path)
    else:
        draft_path = ""

    # Add a sidecar file to store metadata of new asset
    # This will ensure that when it's publish time, we have all the info we need
    # to create the appropriate asset entity.
    draft_info_file = cleanpath(draft_folder, ".draft")
    draft_info = NewDraftInfo(
        draft_id=draft_id,
        name=name,
        description=description,
        parent_id=parent_id,
        type_ids=type_ids or [],
        source_path=draft_path,
    )
    draft_info.write_file(draft_info_file)

    return draft_info


@trace
def checkout_revision(
    revision: medm_model.AssetRevision,
    component_name: str = "",
    component_purpose: str = "",
    force: bool = False,
) -> CheckoutDraftInfo:
    """Check out the given asset revision into sandbox.
    If a draft already exists, an exception will be thrown unless force=True.

    Args:
        revision: AssetRevision object.
        component_name: If provided, search for component with this name to be checked out.
                        This should be unique within the revision.
        component_purpose: If provided, search for a component with this purpose to be
                           checked out. There may be multiple components with the same purpose,
                           so the first match will be returned.
        force: If True, force a re-checkout even if an existing draft is found.

    Returns:
        A CheckoutDraftInfo object containing all pertinent information
        of new or existing checkout.

    Raises:
        DraftExistsError
        FlowError
    """
    logger = get_logger(__name__)

    draft_id = get_draft_id(revision.asset_id)
    draft_folder = get_draft_folder(draft_id)

    if os.path.exists(draft_folder):
        if not force:
            raise DraftExistsError(draft_id=draft_id, draft_folder=draft_folder)
        else:
            logger.info("Removing existing draft folder...")
            # Delete existing draft folder
            try:
                shutil.rmtree(draft_folder)
            except Exception as exc:  # pylint: disable=broad-except
                msg = f"Could not remove existing draft directory: {draft_folder}"
                raise FlowError(msg) from exc

    # Fetch necessary binaries for revision into primary storage
    # TODO: Assumption that we are retrieving a single blob every time.
    #       Need to expand this to grab all blobs, or an explicit list.
    fetch(
        revision,
        component_name=component_name,
        component_purpose=component_purpose,
    )

    # Create the draft folder so we can copy new files to it
    logger.info("Creating draft folder...")
    os.makedirs(draft_folder)

    # Copy from storage into sandbox
    # NOTE: assuming flat files in asset dir
    # NOTE: assuming only a single source file
    cached_path = get_storage_component_path(
        revision,
        component_name=component_name,
        component_purpose=component_purpose,
    )
    if cached_path is None:
        # This indicates that the specified component does not exist
        # on the revision, so raise an error
        msg = "Revision does not contain a component fitting the filter: "
        msg += f"component_name = {component_name}, component_purpose = {component_purpose}. "
        msg += "No source file(s) to copy.  Checkout cannot be completed."
        raise FlowError(msg)

    draft_path = cleanpath(draft_folder, os.path.basename(cached_path))
    msg = "Copying files to draft folder...\n"
    msg += f"{cached_path} -> {draft_path}"
    logger.info(msg)
    try:
        shutil.copy(cached_path, draft_path)
    except Exception as exc:  # pylint: disable=broad-except
        raise FlowError("Copy failed!") from exc

    # Query the asset to get it's latest info
    asset = _query_asset(revision.asset_id)

    # Write draft info
    draft_info_file = cleanpath(draft_folder, ".draft")
    draft_info = CheckoutDraftInfo(
        draft_id=draft_id,
        name=asset.name,
        asset_id=asset.id,
        revision=revision.revision_number,
        latest_revision=asset.revision_number,
        version=revision.version_number,
        latest_version=asset.version_number,
        source_path=draft_path,
    )
    draft_info.write_file(draft_info_file)
    logger.info("Draft metadata updated.")

    return draft_info


@trace
def discard_draft(draft_id: str):
    """Discard an existing draft of an asset.

    Args:
        draft_id: Unique id that identifies a draft location in local sandbox.

    Raises:
        FlowError
        InvalidDraftError
    """
    logger = get_logger(__name__)

    if not is_local_draft(draft_id):
        msg = f'The draft "{draft_id}" is not in local sandbox.'
        raise InvalidDraftError(draft_id=draft_id, details=msg)

    draft_folder = get_draft_folder(draft_id)
    parent_folder = os.path.dirname(draft_folder)
    logger.info(f"Deleting draft folder: {parent_folder}...")
    try:
        # Remove the parent directory above "draft" folder
        shutil.rmtree(parent_folder)
    except Exception as exc:  # pylint: disable=broad-except
        msg = f"Draft folder could not deleted: {parent_folder}"
        raise FlowError(msg) from exc


@trace
def publish_draft(
    draft_id: str,
    comment: str = "",
    components: list[ComponentSpec] | None = None,
    used_versions: list[str] | None = None,
    force: bool = False,
) -> medm_model.Asset:
    """Publish a new asset or new revision of existing asset from a draft.

    Args:
        draft_id: Unique local draft id.
        comment: Description of revision.
        components: List of component specifications that will be converted into components
                    to be attached to asset revision.
                    (These are used to store binaries and metadata on revisions.)
        used_versions: List of version ids of other assets used by this asset.
                       (Stored as "uses" relationships with other asset versions.)
        force: If True, publish without checking for publish conflicts.

    Returns:
        Updated MEDM asset object.

    Raises:
        EntityNotFoundError
        PublishAssetError
        PublishConflictError
    """
    logger = get_logger(__name__)

    # Retrieve draft metadata
    draft_info = read_draft_info(draft_id)

    # Add comment component to components if not already present
    components = [] if components is None else list(components)
    components.append(CommentComponentSpec(comment))

    if draft_info.draft_type == "new":
        # For new assets, we need to convert the type ids into components
        # (Names must be kept unique!)
        for i, type_id in enumerate(draft_info.type_ids):
            components.append(TypeComponentSpec(type_id=type_id, name=f"Type {i}"))

        # Publish new asset with appropriate metadata
        asset = publish_new_asset(
            name=draft_info.name,
            parent_id=draft_info.parent_id,
            description=draft_info.description,
            components=components,
            used_versions=used_versions,
        )

        # Rename the draft folder on first publish to replace the temporary draft
        # id with the asset's permanent storage key
        new_draft_id = get_storage_key(asset.id)
        new_source_path = _rename_draft_folder(draft_id, new_draft_id)
        draft_id = new_draft_id

    else:
        # Query the asset
        asset_id = draft_info.asset_id
        try:
            asset = _query_asset(asset_id)
        except FlowError as exc:
            msg = f"Invalid asset id associated with draft: {asset_id}"
            raise EntityNotFoundError(entity_id=asset_id, details=msg) from exc

        # For existing assets, we need to preserve the types already assigned
        # to the asset - add these to the component list
        for i, type_id in enumerate(_get_type_ids(asset)):
            components.append(TypeComponentSpec(type_id=type_id, name=f"Type {i}"))

        # Check for conflict before publishing
        # A conflict arises if newer revisions of the asset have been published
        # since this asset was checked out.
        if not force and _check_publish_conflict(draft_info, asset):
            checkout_revision = draft_info.revision
            checkout_version = draft_info.version
            raise PublishConflictError(
                asset=asset,
                checkout_version=checkout_version,
                checkout_revision=checkout_revision,
            )

        # Update an existing asset by publishing a new revision
        asset = publish_new_revision(
            asset_id=asset_id,
            components=components,
            used_versions=used_versions,
        )

        # For publishes of existing assets, the source path should not change
        new_source_path = draft_info.source_path

    msg = f'Successfully published version {asset.version_number} (r{asset.revision_number}) of asset "{asset.name}" to Flow AM!'
    logger.info(msg)

    # Update the draft info file to adjust for latest publish.
    # This is a sidecar file that will contain any relevant "checkout" information
    # about current draft. After a publish, we will treat the draft has being
    # checked out from the most recent published version.
    # NOTE: we can continue to use the same draft id.
    draft_folder = get_draft_folder(draft_id)
    draft_info_file = cleanpath(draft_folder, ".draft")
    draft_info = CheckoutDraftInfo(
        draft_id=draft_id,
        name=asset.name,
        asset_id=asset.id,
        revision=asset.revision_number,
        version=asset.version_number,
        latest_revision=asset.revision_number,
        latest_version=asset.version_number,
        source_path=new_source_path,
    )
    draft_info.write_file(draft_info_file)
    logger.info("Draft metadata updated.")

    return asset


@trace
def _rename_draft_folder(old_draft_id: str, new_draft_id: str) -> str:
    """Attempt to rename the draft folder to the new draft id.
    If it's not possible, create the new draft folder and copy contents over.

    Returns:
        Path of new path to source file.

    Raises:
        PublishAssetError
    """
    logger = get_logger(__name__)
    logger.info(f'Renaming draft folder from "{old_draft_id}" -> "{new_draft_id}".')
    draft_info = read_draft_info(old_draft_id)
    old_draft_folder = os.path.dirname(get_draft_folder(old_draft_id))
    new_draft_folder = os.path.dirname(get_draft_folder(new_draft_id))
    try:
        os.rename(old_draft_folder, new_draft_folder)
    except Exception:  # pylint: disable=broad-except
        msg = f"Could not rename draft folder: {old_draft_folder}. "
        msg += "Creating a copy instead..."
        logger.warning(msg)
        try:
            shutil.copytree(old_draft_folder, new_draft_folder)
        except Exception as exc:  # pylint: disable=broad-except
            msg = f"Could not create draft folder: {new_draft_folder}"
            exc_data = {"draft_folder": old_draft_folder}
            raise PublishAssetError(data=exc_data, details=msg) from exc

    # Determine new source path
    old_source_path = draft_info.source_path
    new_source_path = old_source_path.replace(old_draft_folder, new_draft_folder)
    return new_source_path


def _query_asset(asset_id: str) -> medm_model.Asset:
    """Query an asset based on id.

    Raises:
        EntityNotFoundError
        FlowError
    """
    logger = get_logger(__name__)
    client = get_client()
    q_input = medm_model.AssetsByIdsInput(ids=[asset_id])
    q_asset = client.service_asset.assets_by_ids(q_input)
    try:
        q_asset.call()
    except GQLAPIError as exc:
        msg = f"Error querying asset: {asset_id}. {exc}"
        raise FlowError(msg) from exc
    if len(q_asset.assets) == 0:
        msg = "Error retrieving MEDM asset."
        raise EntityNotFoundError(entity_id=asset_id, details=msg)
    asset = q_asset.assets[0]
    logger.info(f'Queried asset "{asset.name}".')
    return asset


def _get_type_ids(asset: medm_model.Asset):
    """Return list of type ids assigned to asset."""
    type_ids = []
    for comp in asset.components:
        if BASE_TYPE_ID in comp.parent_type_ids:
            type_ids.append(comp.type_id)
    return type_ids


def _check_publish_conflict(draft_info, asset) -> bool:
    """Check if there is a publish conflict based on current state of
    asset and checkout state of asset.
    """
    # A conflict is defined as trying to publish an asset which has had
    # new versions published against it since the asset was checked out
    #
    # NOTE: We are making the assumption that within a single "numbered" version,
    #       component and uses relationships stay the same from revision to revision!
    #       This assumption allows us to only consider conflicts with respect to versions.
    return draft_info.latest_version < asset.version_number
