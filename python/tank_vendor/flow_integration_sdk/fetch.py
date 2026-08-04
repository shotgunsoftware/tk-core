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
This module provides asset download/fetching utilities.
"""

from __future__ import annotations  # needed for python 3.9 support

import fileseq
import os
import zipfile
from collections.abc import Iterator
from functools import cache

from tank_vendor.flow_data_sdk.base import model as medm_model
from tank_vendor.flow_data_sdk.base.exceptions import GQLAPIError

from .exceptions import FlowError, ThumbnailError
from .globals import (
    get_client,
    FILE_SEQ_TYPE,
    THUMBNAIL_PURPOSE,
)
from .schema import get_schema_id
from .storage import (
    _cache_asset_info,
    _find_component,
    get_storage_component_path,
    get_storage_revision_dir,
)
from .utils import cleanpath, download_file, get_logger, trace


# urn to url cache - optimization to avoid re-querying urls that are fixed
# Format: key = urn, value = url
_urn_to_url = {}


@trace
def fetch_blob_urls(project_id: str, urns: list[str]) -> list[str]:
    """Query list of urls for given blob urns that can be used for
    downloading. Order should be preserved.

    Args:
        project_id: Id of project to which binary components belong.
        urns: List of blob urns to be converted to urls.

    Returns:
        List of urls from which blobs can be downloaded.

    Raises:
        FlowError
    """
    query_urns = []  # urns to be queried
    result_urls = []  # final url list to be returned

    # Add any cached urls to the return result first
    # Leave spaces in the list for values that must be queried
    for urn in urns:
        if urn in _urn_to_url:
            result_urls.append(_urn_to_url[urn])
        else:
            result_urls.append(None)
            query_urns.append(urn)

    # Query the download URLs from the API
    if query_urns:
        client = get_client()
        q_input = medm_model.BinaryComponentUrlsByUrnsInput(
            project_id=project_id,
            urns=query_urns,
        )
        q_urls = client.service_binary.binary_component_urls_by_urns(q_input)
        try:
            q_urls.call()
        except GQLAPIError as exc:
            msg = f"Error fetching binary component urls: {exc}"
            raise FlowError(msg) from exc

        queried_urls = [bin_comp_url.url for bin_comp_url in q_urls.urls]

        # Cache the urls we just queried
        for i, urn in enumerate(query_urns):
            _urn_to_url[urn] = queried_urls[i]

        # Merge quered urls with result by filling in the None spaces
        # (this should preserve the input order)
        for i, url in enumerate(result_urls):
            if url is None:
                result_urls[i] = queried_urls.pop(0)

    return result_urls


@trace
def download(
    component: medm_model.Component,
    project_id: str,
    directory: str,
    file_sequence: bool = False,
    skip_download: bool = False,
) -> dict[int, str]:
    """Download all binary blobs in component to given directory.
    Directory must exist, and component must be a binary component.

    Args:
        component: Component to be downloaded.
        project_id: Project that component belongs to.
        directory: Existing folder location to be downloaded to.
        file_sequence: If True, expect the component to contain a
                       zipped file sequence, and automatically expand it.
        skip_download: Only relevant for file sequences. Used when
                       the source zip file has already been downloaded, but
                       the files haven't been extracted.

    Returns:
        Dictionary of blob index to full path of downloaded file.

    Raises:
        FlowError
    """
    # Get list of urls for each component blob
    urns = [blob["uri"] for blob in component.data.get("data", [])]
    urls = fetch_blob_urls(project_id, urns)

    result = {}
    for i, url in enumerate(urls):
        # Determine destination path
        # NOTE: this blob index is guaranteed to exist because we retrieved its url
        blob_path = component.data["data"][i]["path"]
        file_path = cleanpath(directory, blob_path)

        # Finally download the file and save to disk
        try:
            if not skip_download:
                download_file(url, file_path)
        except Exception as exc:  # pylint: disable=broad-except
            raise FlowError(
                f'Failed to download blob {i} with url "{url}". {exc}'
            ) from exc
        result[i] = file_path

    if file_sequence:
        # NOTE: This is a temporary solution. When we cease to zip
        #       up file sequences, this code block and parameter can be removed!
        zip_file_path = result[0]
        with zipfile.ZipFile(zip_file_path, "r") as zip_file:
            # Update result dictionary to reflect frames extracted
            # (Do this to mimic the future behaviour where each frame
            #  will be stored as its own blob)
            result = {}
            blob_index = 0
            for file_name in zip_file.namelist():
                result[blob_index] = cleanpath(directory, file_name)
                blob_index += 1
                # Check for unsafe file paths within zip
                # We don't want to allow extracting outside of download directory
                if file_name.startswith("/") or ".." in file_name:
                    msg = f"Unsafe file path detected in zip file: {file_name} - aborting extraction."
                    raise FlowError(msg)
            # Extract the files
            zip_file.extractall(directory)

    return result


@trace
def fetch(
    revision: medm_model.AssetRevision,
    component_name: str = "",
    component_purpose: str = "",
    fetch_dependencies: bool = False,
):
    """Fetch the given component of a revision if not already on disk.
    If the specified component does not exist, nothing will happen.

    Args:
        revision: Revision whose component should be fetched.
        component_name: If provided, search for component with this name to be fetched.
                        This should be unique within the revision.
        component_purpose: If provided, search for a component with this purpose to be fetched.
                           There may be multiple components with the same purpose,
                           so the first match will be returned.
        fetch_dependencies: If True, also fetch the full dependency tree of the revision
                            using the same component criteria.

    ..note:: If both component name and purpose are provided, the first intersection
             of both criteria will be returned.
    """
    logger = get_logger(__name__)

    # Get project id
    project_id = _get_project_id(revision.id)

    # List of revisions to be fetched
    rev_list = [revision]
    if fetch_dependencies:
        # Add any dependencies (this will include entire dependency tree)
        # NOTE: the uses query will return the input revision itself so this
        #       item will be duplicated in the list, however that should not cause
        #       a problem.
        rev_list.extend(list(_iterate_uses(revision.numbered_version_id)))

    def missing_seq_files(file_seq_comp):
        # Return True if any files from the file seq are missing
        file_list = _get_file_list(file_seq_comp)
        # Convert to absolute paths
        storage_dir = get_storage_revision_dir(rev.asset_id, rev.revision_number)
        file_list = [cleanpath(storage_dir, f) for f in file_list]
        missing_files = False
        for f in file_list:
            if not os.path.exists(f):
                missing_files = True
                break
        return missing_files

    for rev in rev_list:
        # Check that revision has the specified component
        # NOTE: making the assumption here that we only have a single blob
        comp = _find_component(rev, name=component_name, purpose=component_purpose)
        if comp is None:
            # If the component doesn't exist, we will log a warning
            # but not consider it a failure. The purpose of this function
            # is to fetch stored binaries, so if there are no stored
            # binaries, the point is moot.
            msg = "No component of "
            msg += f'name "{component_name}" ' if component_name else ""
            msg += f'purpose "{component_purpose}" found in revision "{rev.name}".'
            msg += "Skipping fetch for this revision..."
            logger.warning(msg)
            continue
        # NOTE: the component is guaranteed to exist because we already found
        #       it - can assume this path will not be None
        cache_source_path = get_storage_component_path(rev, component_name=comp.name)
        file_seq_comp = _find_component(rev, type_id=get_schema_id(FILE_SEQ_TYPE))
        # Check primary storage for source path before fetching
        if file_seq_comp and not missing_seq_files(file_seq_comp):
            # For file sequences, it's not good enough to check for just
            # the source zip file, but we should also make sure its been unzipped
            continue
        elif not file_seq_comp and os.path.exists(cache_source_path):
            continue

        msg = f"Fetching binaries for revision {rev.name} - r{rev.revision_number}"
        msg += f', component "{comp.name}".'
        logger.info(msg)

        # Fetch the component (indicate if it's a file sequence)
        download(
            comp,
            project_id,
            get_storage_revision_dir(rev.asset_id, rev.revision_number),
            file_sequence=file_seq_comp is not None,
            # NOTE: we may be in a situation where the source file already exists
            # but its a file seq that needs to be unzipped. In this case,
            # indicate that the download step can be skipped.
            skip_download=os.path.exists(cache_source_path),
        )

        # Once fetched, cache asset info in storage dir if necessary
        _cache_asset_info(rev.asset_id)


@trace
def get_thumbnail_file(revision: medm_model.AssetRevision) -> str:
    """Return the path to the thumbnail file on disk. Fetch the file if necessary.

    Args:
        revision: Revision whose thumbnail should be fetched.

    Returns:
        File path to thumbnail.

    Raises:
        ThumbnailError
    """
    # Check that thumbnail component exists and
    # get path to thumbnail path of revision in local storage
    thumbnail_comp = _find_component(revision, purpose=THUMBNAIL_PURPOSE)
    if thumbnail_comp is None:
        msg = "Revision does not have a thumbnail component."
        raise ThumbnailError(revision_id=revision.id, details=msg)

    # Fetch thumbnail component of revision
    fetch(revision, component_purpose=THUMBNAIL_PURPOSE)

    # Verify that fetch was successful
    file_path = get_storage_component_path(revision, component_name=thumbnail_comp.name)
    if not os.path.exists(file_path):
        msg = f"Thumbnail file does not exist in storage: {file_path}"
        raise ThumbnailError(revision_id=revision.id, details=msg)

    return file_path


@trace
def get_thumbnail_url(revision: medm_model.AssetRevision) -> str:
    """Return a signed url of the thumbnail for given revision.

    Args:
        revision: Revision whose thumbnail should be fetched.

    Returns:
        Url of thumbnail.

    Raises:
        ThumbnailError
    """
    # Get project id
    project_id = _get_project_id(revision.id)

    # Check that thumbnail component exists
    thumbnail_comp = _find_component(revision, purpose=THUMBNAIL_PURPOSE)
    if thumbnail_comp is None:
        msg = "Revision has no thumbnail component."
        raise ThumbnailError(revision_id=revision.id, details=msg)

    # Fetch the thumbnail's url (assume single blob)
    try:
        urn = thumbnail_comp.data.get("data", [])[0]["uri"]
        return fetch_blob_urls(project_id, [urn])[0]
    except (FlowError, IndexError) as exc:
        msg = "Could not fetch thumbnail url."
        raise ThumbnailError(revision_id=revision.id, details=msg) from exc


@cache
@trace
def _iterate_uses(version_id: str) -> Iterator[medm_model.AssetRevision]:
    """Query uses relationships in this asset/revision.
    Pagination is handled internally within this call via the V2 sdk.
    If this query has already been performed, the cached result will be returned.
    If refresh=True, do a fresh query.

    NOTE: This implementation grabs the entire uses tree because in practice
          this is usually what we need (to fetch dependencies).

    Args:
        version_id: Query "uses" dependency tree starting from this version id.

    Returns:
        Iterator which handles the paginated response of the query containing
        medm_model.AssetRevision objects.

    Raises:
        FlowError
    """
    client = get_client()
    q_input = medm_model.AssetVersionsByTraversalInput(
        start_at_id=version_id,  # type: ignore[attr-defined]
        depth=0,  # retrieve entire tree
        direction=medm_model.TraverseDirectionEnum.OUTGOING.value,
    )
    q_uses = client.service_asset.asset_versions_by_traversal(q_input)

    # Wrap existing iterator in V2 sdk
    # NOTE: The iterator function makes the actual query calls so no need to
    #       explicitly invoke call() here.
    try:
        # NOTE: We are getting revisions for now because this is most useful to us
        #       as the primary use case for getting uses information is to fetch
        #       dependencies.
        #
        #       This is fetched through the versions iterator and not the revisions
        #       iterator. Since we are querying outgoing edges, the response gives us
        #       a list of edges like
        #           Rx -> Vy
        #           Rx -> Vz
        #           Rw -> Vu
        #           ...
        #       where R = revision, V = version
        #       The revisions iterator gives us the revision objects associated with
        #       the source of those edges. The versions iterator gives us the version
        #       objects associated with the destination of those edges.
        for ver in q_uses.versions_iterator:
            revision = ver.revision
            yield revision
    except GQLAPIError as exc:
        msg = f"Error querying uses relationships. {exc}"
        raise FlowError(msg) from exc


def _get_file_list(fileseq_comp: medm_model.Component) -> list[str]:
    """Return list of file names described by a file sequence type component."""
    frame_set = fileseq.FrameSet(fileseq_comp.data["frameSet"])
    file_format = fileseq_comp.data["fileFormat"]
    file_list = [file_format % i for i in list(frame_set)]
    return file_list


def _get_project_id(input_id: str) -> str:
    """Convert a medm asset/revision/version id into a project id."""
    parts = input_id.split(":")
    project_id = f"urn:medm:project:{parts[3]}:{parts[4]}"
    return project_id
