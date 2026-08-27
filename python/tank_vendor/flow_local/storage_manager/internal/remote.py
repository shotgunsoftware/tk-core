"""MEDM server operations.

Two cohesive halves of "talking to the server":
- Asset & revision metadata over GraphQL (create/update/fetch, `uses` traversal).
- Binary blob transfer over HTTP (streaming download with resume, multipart
  upload), plus the GraphQL binary-service calls that presign and manage those
  transfers.
"""

import base64
import hashlib
import logging
import math
import os
import ssl
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import BinaryIO, Callable, List, Optional, TypeVar, cast

import certifi
from adsk.flow.data import FlowConnectionError, GQLAPIError, GQLClient
from adsk.flow.data.base.exceptions import GQLErrorCode
from adsk.flow.data.base.model_g import (
    Asset,
    AssetRevision,
    AssetRevisionsByAssetIdInput,
    AssetRevisionsByIdsInput,
    AssetsByIdsInput,
    AssetVersionsByIdsInput,
    AssetVersionsByTraversalInput,
    BinaryComponentUrlsByUrnsInput,
    CloseUploadFileInput,
    ComponentDataInput,
    CreateAssetInput,
    GetUploadFilePartInput,
    GetUploadFilePartResponse,
    ListAction,
    NamedAssetVersion,
    NamedVersionChangeEnum,
    NumberedAssetVersion,
    OpenUploadFileInput,
    PaginationInput,
    TraverseDirectionEnum,
    UpdateAssetInput,
    UploadFileJob,
    UsesTargetInput,
)
from adsk.flow.local.storage_manager.exceptions import (
    ConflictError,
    CreateAssetError,
    DependencyError,
    DownloadError,
    StorageManagerError,
    TransferCancelledError,
    UpdateAssetError,
    UploadError,
)
from adsk.flow.local.storage_manager.internal.discovery import extract_blobs_from_revision
from adsk.flow.local.storage_manager.internal.fs import HASH_ALGORITHM, ensure_dir, new_hasher
from adsk.flow.local.storage_manager.internal.urn import compose_revision_urn, compose_version_urn
from adsk.flow.local.storage_manager.models import BlobRef

_MIN_PART_SIZE = 5 * 1024 * 1024  # 5 MB — S3 multipart minimum
# 10,000 parts is the binary service's real ceiling (schema.graphql's GetUploadFilePartInput
# docstring: "Maximum number of chunks: 10,000 parts")
_MAX_PARTS = 10_000
_DEFAULT_CHUNK = 8192  # bytes per read() call for streaming downloads/uploads
_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

_GQL_MAX_RETRIES = 3
_GQL_RETRY_BACKOFF = 1.0  # seconds; doubles each attempt
_GQL_RETRYABLE_ERROR_CODES = frozenset(
    {
        GQLErrorCode.QUOTA_LIMIT_REACHED.value,  # 429
        # Blob upload finished but the binary service is still processing it
        # server-side (e.g. media duplication); the data becomes available shortly.
        GQLErrorCode.DATA_NOT_READY.value,
    }
)

logger = logging.getLogger(__name__)

_R = TypeVar("_R")


def _gql_call_with_retry(call_fn: Callable[[], _R]) -> _R:
    """Call call_fn() with retry on transient server errors.

    Pass a bound `op.call` method: `_gql_call_with_retry(op.call)`.
    Retries on FlowConnectionError (5xx, network failures) and GQLAPIError with
    an error_code in `_GQL_RETRYABLE_ERROR_CODES` (QUOTA_LIMIT_REACHED, 429;
    DATA_NOT_READY, a blob still being processed server-side after upload).
    Permanent errors (4xx auth, not-found, conflict) are raised immediately
    without retry.
    """
    last_exc: Exception = RuntimeError("unreachable")
    for attempt in range(_GQL_MAX_RETRIES):
        try:
            return call_fn()
        except FlowConnectionError as exc:
            last_exc = exc
        except GQLAPIError as exc:
            if exc.error_code not in _GQL_RETRYABLE_ERROR_CODES:
                raise
            last_exc = exc
        if attempt < _GQL_MAX_RETRIES - 1:
            delay = _GQL_RETRY_BACKOFF * (2**attempt)
            logger.warning(
                "GQL call transient error (attempt %d/%d), retrying in %.1fs", attempt + 1, _GQL_MAX_RETRIES, delay
            )
            time.sleep(delay)
    raise last_exc


def _http_retryable(code: int) -> bool:
    """Return True for HTTP status codes that represent transient, retryable failures.

    404 — presigned URL not yet served by the CDN (eventual consistency after upload).
    429 — rate limited.
    5xx — server-side error.
    All other codes (401, 403, 400, …) are permanent failures that retrying won't fix.
    """
    return code == 404 or code == 429 or code >= 500


# ---------------------------------------------------------------------------
# Asset & revision metadata (GraphQL)
# ---------------------------------------------------------------------------
def create_asset(
    client: GQLClient,
    name: str,
    parent_id: str,
    comps: List[ComponentDataInput],
    uses: Optional[List[str]] = None,
    description: Optional[str] = None,
) -> Asset:
    """Create a new asset on the server and return it.

    description is an optional asset-level description set on the create mutation;
    when None it is omitted from the request (the server's default applies).
    """
    uses_input = [UsesTargetInput(to_version_id=version_id) for version_id in uses] if uses else None
    asset_input = CreateAssetInput(name=name, parent_id=parent_id, components=comps, uses=uses_input)
    # Only send description when provided — a literal None serializes as null.
    if description is not None:
        asset_input.description = description
    op = client.service_asset.create_asset(asset_input)
    try:
        op.call()
    except GQLAPIError as exc:
        logger.error("Failed to create asset %r under parent %s: %s", name, parent_id, exc)
        raise CreateAssetError(f'Error creating asset "{name}" on remote. {exc}. Request id: {exc.request_id}') from exc
    return op.asset


def update_asset(
    client: GQLClient,
    asset_id: str,
    comps: List[ComponentDataInput],
    uses: Optional[List[str]] = None,
    name: Optional[str] = None,
    description: Optional[str] = None,
    bump_version: bool = False,
) -> Asset:
    """Publish a new revision of an existing asset, replacing its component set.

    name / description optionally update the asset's name and description on
    the same mutation; pass None (the default) to leave them unchanged. They are
    omitted from the request when None — a literal None would serialize as null
    and wipe the server value.

    When bump_version is False (the default) only the revision number increments
    (the server's UPDATES_LATEST behaviour). Pass True to also create a new
    numbered version (CREATE_NEW) — e.g. for a deliberate milestone publish.
    """
    uses_input = [UsesTargetInput(to_version_id=version_id) for version_id in uses] if uses else None
    asset_input = UpdateAssetInput(
        id=asset_id,
        components=comps,
        components_action=ListAction.REPLACE,
        uses=uses_input,
    )
    if bump_version:
        asset_input.named_version_change = NamedVersionChangeEnum.CREATE_NEW
    # When bump_version is False, named_version_change is left as NOT_SET so the
    # server defaults to UPDATES_LATEST: new revision only, version number unchanged.
    # Only send name/description when provided — a literal None serializes as null.
    if name is not None:
        asset_input.name = name
    if description is not None:
        asset_input.description = description
    op = client.service_asset.update_asset(asset_input)
    try:
        op.call()
    except GQLAPIError as exc:
        if exc.error_code == GQLErrorCode.CONFLICT.value:
            logger.warning("Concurrent-modification conflict updating asset %s", asset_id)
            raise ConflictError(
                f"Asset '{asset_id}' was modified by another client before this update. "
                f"Fetch the latest revision and retry.",
                asset_id=asset_id,
            ) from exc
        logger.error("Failed to update asset %s: %s", asset_id, exc)
        raise UpdateAssetError(
            f'Error updating asset "{asset_id}" on remote. {exc}. Request id: {exc.request_id}'
        ) from exc
    return op.asset


def fetch_asset(client: GQLClient, asset_id: str) -> Asset:
    """Fetch a single asset by id. Raises StorageManagerError if not found."""
    result = _gql_call_with_retry(client.service_asset.assets_by_ids(AssetsByIdsInput(ids=[asset_id])).call)
    if not result.assets:
        raise StorageManagerError(f"Asset '{asset_id}' not found.")
    asset = result.assets[0]
    if not (isinstance(asset.version_number, int) and isinstance(asset.revision_number, int)):
        raise StorageManagerError(
            f"Server returned unexpected version/revision type for asset '{asset_id}': "
            f"version_number={asset.version_number!r}, revision_number={asset.revision_number!r}"
        )
    return asset


def fetch_revision(
    client: GQLClient,
    asset_id: str,
    revision_number: Optional[int] = None,
) -> Optional[AssetRevision]:
    """Fetch an asset revision by number, or the latest revision if number is None."""
    revision: Optional[AssetRevision]
    if revision_number is None:
        latest = _gql_call_with_retry(
            client.service_asset_revision.asset_revisions_by_asset_id(
                variables=AssetRevisionsByAssetIdInput(asset_id=asset_id, pagination=PaginationInput(limit=1))
            ).call
        )
        revision = latest.asset_revisions[0] if latest.asset_revisions else None
    else:
        # Compose the revision URN directly and look it up by id — avoids paging
        # through every revision of the asset just to match one number.
        revision_urn = compose_revision_urn(asset_id, revision_number)
        try:
            by_ids = _gql_call_with_retry(
                client.service_asset_revision.asset_revisions_by_ids(
                    variables=AssetRevisionsByIdsInput(ids=[revision_urn])
                ).call
            )
        except GQLAPIError as exc:
            if exc.error_code == GQLErrorCode.NOT_FOUND.value:
                return None
            raise
        revision = by_ids.revisions[0] if by_ids.revisions else None

    if revision is None:
        return None
    if not isinstance(revision.revision_number, int):
        raise StorageManagerError(
            f"Server returned unexpected revision/version type for asset '{asset_id}': "
            f"revision_number={revision.revision_number!r}, version_number={revision.version_number!r}"
        )
    return cast(AssetRevision, revision)


def fetch_revision_by_id(client: GQLClient, revision_id: str) -> AssetRevision:
    """Fetch a single asset revision by its revision URN. Raises if not found."""
    result = _gql_call_with_retry(
        client.service_asset_revision.asset_revisions_by_ids(variables=AssetRevisionsByIdsInput(ids=[revision_id])).call
    )
    if not result.revisions:
        raise StorageManagerError(f"Revision '{revision_id}' not found.")
    return cast(AssetRevision, result.revisions[0])


def fetch_revision_for_version(
    client: GQLClient,
    asset_id: str,
    version_number: int,
) -> Optional[AssetRevision]:
    """Fetch the revision associated with a specific numbered version of an asset.

    Composes the numbered-version URN and fetches it in one GQL call; the
    ASSET_VERSIONS_BY_IDS selection already embeds the revision and its
    component data so no extra round-trip is needed.

    Returns None if the version does not exist.
    """
    version_urn = compose_version_urn(asset_id, version_number)
    try:
        result = _gql_call_with_retry(
            client.service_asset.asset_versions_by_ids(variables=AssetVersionsByIdsInput(ids=[version_urn])).call
        )
    except GQLAPIError as exc:
        if exc.error_code == GQLErrorCode.NOT_FOUND.value:
            return None
        raise
    for version in result.versions or []:
        if isinstance(version, NumberedAssetVersion):
            rev = version.revision
            if isinstance(rev, AssetRevision) and isinstance(rev.revision_number, int):
                return cast(AssetRevision, rev)
    return None


def _revision_from_version(version) -> Optional[AssetRevision]:
    """Return the AssetRevision carried by a traversal version node, if present.

    NumberedAssetVersion holds the revision directly; NamedAssetVersion points to
    it through its numbered version. Returns None when no revision is selected.
    """
    if isinstance(version, NumberedAssetVersion):
        rev = version.revision
    elif isinstance(version, NamedAssetVersion) and isinstance(version.numbered_version, NumberedAssetVersion):
        rev = version.numbered_version.revision
    else:
        return None
    return rev if isinstance(rev, AssetRevision) else None


def resolve_dependent_blobs_from_revision(client: GQLClient, revision: AssetRevision) -> List[BlobRef]:
    """Resolve blobs for all assets reachable via the `uses` graph from revision.

    The `uses` traversal already returns each reachable version together with its
    revision and component data, so blobs are read straight from the traversal —
    no extra per-dependency revision query is needed.
    """
    start_version_id = revision.numbered_version_id
    if not start_version_id:
        return []

    op = client.service_asset.asset_versions_by_traversal(
        variables=AssetVersionsByTraversalInput(
            start_at_id=start_version_id,
            direction=TraverseDirectionEnum.OUTGOING,
            depth=0,  # 0 = unlimited depth
        )
    )

    blobs: List[BlobRef] = []
    seen_revision_ids: set = set()
    try:
        for version in op.versions_iterator:
            dep_revision = _revision_from_version(version)
            if dep_revision is None:
                continue
            # Skip the starting version — the root revision's own blobs are handled
            # by the caller; the traversal includes the start node.
            if dep_revision.numbered_version_id == start_version_id:
                continue
            if dep_revision.id in seen_revision_ids:
                continue
            seen_revision_ids.add(dep_revision.id)
            dep_blobs = extract_blobs_from_revision(dep_revision)
            for b in dep_blobs:
                b.version_id = dep_revision.numbered_version_id
            blobs.extend(dep_blobs)
    except GQLAPIError as exc:
        raise DependencyError(f"Failed to resolve dependent versions for version_id {start_version_id}: {exc}") from exc

    return blobs


def fetch_direct_uses(client: GQLClient, numbered_version_id: Optional[str]) -> List[str]:
    """Return the numbered_version_id of each direct `uses` target of numbered_version_id.

    Same traversal as resolve_dependent_blobs_from_revision but depth=1 (direct
    edges only, not the full transitive closure) and returning target version
    ids instead of blobs. Used to diff a publish's `uses` argument against what
    the server currently has, without pulling in transitively-reachable versions.
    """
    if not numbered_version_id:
        return []

    op = client.service_asset.asset_versions_by_traversal(
        variables=AssetVersionsByTraversalInput(
            start_at_id=numbered_version_id,
            direction=TraverseDirectionEnum.OUTGOING,
            depth=1,
        )
    )

    targets: List[str] = []
    try:
        for version in op.versions_iterator:
            dep_revision = _revision_from_version(version)
            if dep_revision is None:
                continue
            target_id = dep_revision.numbered_version_id
            if not target_id or target_id == numbered_version_id:
                continue
            targets.append(target_id)
    except GQLAPIError as exc:
        raise DependencyError(f"Failed to resolve direct uses for version_id {numbered_version_id}: {exc}") from exc

    return targets


# ---------------------------------------------------------------------------
# Binary blob transfer (HTTP)
# ---------------------------------------------------------------------------
def _resolve_blob_urls(client: GQLClient, project_id: str, urns: List[str]) -> List[str]:
    """Return a presigned download URL for each URN (order preserved)."""
    response = _gql_call_with_retry(
        client.service_binary.binary_component_urls_by_urns(
            variables=BinaryComponentUrlsByUrnsInput(project_id=project_id, urns=urns)
        ).call
    )
    return [entry.url for entry in response.urls]


@dataclass
class DownloadedBlob:
    """Result of a completed :func:`download_blob` call."""

    path: str
    size: int
    hash: str


def part_path_for(dest: str, urn: str) -> str:
    """Return the resume-file path for urn landing at dest.

    The token is derived from the blob's URN, not from dest, so two blobs
    that happen to share a destination path (e.g. two revisions of the same
    version, both downloading into "v{N}/<blob_path>") never share a
    ".part" file — resuming one would otherwise silently splice bytes from
    two different sources into one file.
    """
    token = hashlib.md5(urn.encode(), usedforsecurity=False).hexdigest()[:8]
    return f"{dest}.{token}.part"


def download_blob(
    client: GQLClient,
    project_id: str,
    urn: str,
    dest: str,
    *,
    on_progress: Optional[Callable[[int, int], None]] = None,
    chunk_size: int = _DEFAULT_CHUNK,
    timeout: int = 60,
    cancel_event: Optional[threading.Event] = None,
    hash_algorithm: str = HASH_ALGORITHM,
) -> DownloadedBlob:
    """Download one blob to dest and return its `DownloadedBlob`.

    Streams in chunk_size chunks, hashing each chunk as it's written so the
    digest costs no extra read pass. Writes to :func:`part_path_for`\\ 's path
    and atomically renames on success so dest is never left
    partially-written. If that `.part` file already exists, resumes via an
    HTTP `Range` request — the hasher is seeded from the existing bytes on
    disk first so the final digest still covers the whole file, not just the
    resumed tail.

    If cancel_event is set, raises `TransferCancelledError` at the next
    chunk boundary; the partial `.part` file is left on disk for a later resume.
    """
    urls = _resolve_blob_urls(client, project_id, [urn])
    if not urls:
        raise DownloadError(f"No download URL resolved for URN: {urn}", urn=urn)

    part_path = part_path_for(dest, urn)
    ensure_dir(os.path.dirname(dest))

    resume_bytes = os.path.getsize(part_path) if os.path.exists(part_path) else 0
    hasher = new_hasher(hash_algorithm)

    req = urllib.request.Request(urls[0])
    if resume_bytes:
        logger.debug("Resuming download of URN %s from byte %d", urn, resume_bytes)
        req.add_header("Range", f"bytes={resume_bytes}-")
    else:
        logger.debug("Downloading URN %s to %s", urn, dest)

    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CONTEXT) as response:  # noqa: S310
            http_status = response.getcode()
            content_length = int(response.headers.get("Content-Length") or 0)

            if http_status == 206:
                file_mode = "ab"
                done = resume_bytes
                total = resume_bytes + content_length
                # Seed the hasher with the bytes a prior attempt already wrote so the
                # final digest covers the whole file, not just this attempt's tail.
                with open(part_path, "rb") as seed_fh:
                    while True:
                        seed_chunk = seed_fh.read(chunk_size)
                        if not seed_chunk:
                            break
                        hasher.update(seed_chunk)
            else:
                file_mode = "wb"
                done = 0
                total = content_length

            with open(part_path, file_mode) as fh:
                while True:
                    if cancel_event is not None and cancel_event.is_set():
                        raise TransferCancelledError(f"Download of URN {urn} cancelled.", urn=urn, file_path=dest)
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    fh.write(chunk)
                    hasher.update(chunk)
                    done += len(chunk)
                    if on_progress:
                        on_progress(done, total)

        os.replace(part_path, dest)
    except urllib.error.HTTPError as exc:
        retryable = _http_retryable(exc.code)
        log = logger.warning if retryable else logger.error
        log("HTTP %s downloading URN %s", exc.code, urn)
        raise DownloadError(f"HTTP {exc.code} downloading URN {urn}", urn=urn, retryable=retryable) from exc
    except urllib.error.URLError as exc:
        logger.error("Network error downloading URN %s: %s", urn, exc)
        raise DownloadError(f"Network error downloading URN {urn}: {exc}", urn=urn, retryable=True) from exc
    except OSError as exc:
        logger.error("File I/O error writing %s for URN %s: %s", dest, urn, exc)
        raise DownloadError(f"File I/O error writing {dest}: {exc}", urn=urn, retryable=False) from exc

    # `done` is the exact count of bytes actually written (accumulated per chunk as
    # they're read), never derived from the possibly-lying Content-Length header —
    # avoids an extra stat() call for the same accuracy os.path.getsize(dest) would give.
    return DownloadedBlob(path=dest, size=done, hash=hasher.hexdigest())


def _md5_hash_range(fh: BinaryIO, length: int) -> str:
    """Compute the base64 Content-MD5 for the next length bytes of already-seeked fh.

    Reads in small fixed-size chunks so it never buffers more than one chunk of a
    part in memory, decoupling peak memory from part size.
    """
    hasher = hashlib.md5(usedforsecurity=False)
    remaining = length
    while remaining > 0:
        chunk = fh.read(min(_DEFAULT_CHUNK, remaining))
        if not chunk:
            break
        hasher.update(chunk)
        remaining -= len(chunk)
    return base64.b64encode(hasher.digest()).decode("utf-8")


class _BoundedReader:
    """File-like wrapper limiting reads to length bytes from fh's current position.

    Passed as the PUT body to urllib.request so http.client streams it in small blocks
    instead of urllib needing a full in-memory buffer for the part.
    Paired with an explicit Content-Length header so urllib skips its own auto-length
    computation (which would otherwise call `memoryview()` on this, or fall back to
    chunked transfer encoding) and hands the body straight through.
    """

    def __init__(self, fh: BinaryIO, length: int) -> None:
        self._fh = fh
        self._remaining = length

    def read(self, size: int = -1) -> bytes:
        if self._remaining <= 0:
            return b""
        if size is None or size < 0:
            size = self._remaining
        chunk = self._fh.read(min(size, self._remaining))
        self._remaining -= len(chunk)
        return chunk


def upload_blob(
    client: GQLClient,
    file_path: str,
    urn_id: str,
    upload_uri: str,
    upload_timeout: int,
    on_progress: Optional[Callable[[int, int], None]] = None,
    *,
    cancel_event: Optional[threading.Event] = None,
    resume_etags: Optional[List[str]] = None,
    resume_size: Optional[int] = None,
    resume_job_id: Optional[str] = None,
    on_part_uploaded: Optional[Callable[[List[str], int], None]] = None,
    on_job_opened: Optional[Callable[[str], None]] = None,
) -> None:
    """Upload a single blob via 3-step multipart upload (open → upload parts → close).

    urn_id and upload_uri keep the names of the SDK's `OpenUploadFileInput`
    fields they feed (the download path calls the same resource id `urn`, matching
    its own SDK input — the asymmetry mirrors the underlying service).

    resume_etags, if given, are ETags for parts already uploaded and acknowledged in
    an earlier attempt (index 0 = part 1); the upload resumes from the next part
    instead of re-uploading them. resume_size is the file size recorded alongside
    those etags; if it no longer matches the file's current size, the etags are
    discarded and the upload restarts from part 1, since the part boundaries they
    refer to are no longer valid. As a fallback when resume_size isn't given,
    resume_etags longer than the file's current part count is discarded on the
    same reasoning. Note this can't detect the file being replaced by different
    content of the same size — there's no cheap way to verify that without
    re-hashing the whole file, so that case is a known limitation: the stale parts
    would be silently reused. on_part_uploaded, if given, is called with the full,
    growing ETags list and the file's total size after every part succeeds, so the
    caller can persist progress for a later retry or resume.

    resume_job_id, if given, is a server-side upload job id from an earlier
    `open_upload_file` call for this same upload_uri; it is reused as-is instead
    of opening a new job. Required for retries: the binary service rejects a
    second `open_upload_file` for the same upload_uri once the first has
    registered the file, so the very open that "left the job open on the
    server" for a retryable failure must be reused, not repeated. on_job_opened,
    if given, is called once with the async_job_id right after a fresh
    `open_upload_file` (i.e. when resume_job_id was not given), so the caller
    can persist it before the first part is attempted.

    If cancel_event is set, raises `TransferCancelledError` at the next
    part boundary; the multipart upload job is still closed with state `FAILED` —
    cancellation is a deliberate, permanent abandonment (unlike a retryable failure),
    so invalidating the blob slot is the intended outcome.

    On any other failure, the multipart upload job is closed `FAILED` only when the
    failure is not retryable. A retryable failure leaves the job open on the server —
    closing it would permanently invalidate the blob slot (confirmed against the live
    MEDM binary service: a `FAILED` close means any later `open_upload_file` for the
    same slot fails with "no associated asset found") — so the next attempt must reuse
    async_job_id (via resume_job_id) and continue from resume_etags.
    """
    if resume_job_id:
        async_job_id = resume_job_id
    else:
        upload_job = _open_upload_file(client, urn_id, upload_uri)
        async_job_id = upload_job.id
        if on_job_opened:
            on_job_opened(async_job_id)

    etags: List[str] = list(resume_etags) if resume_etags else []

    total_size = os.path.getsize(file_path)
    part_size = max(_MIN_PART_SIZE, math.ceil(total_size / _MAX_PARTS))
    total_parts = math.ceil(total_size / part_size)

    stale = (resume_size is not None and resume_size != total_size) or len(etags) > total_parts
    if etags and stale:
        logger.warning(
            "Discarding %d stale part etag(s) for %s: file size changed since the last attempt.",
            len(etags),
            file_path,
        )
        etags = []

    start_part = len(etags) + 1

    logger.debug(
        "Uploading %s (%d bytes in %d part(s), starting at part %d) for URN %s",
        file_path,
        total_size,
        total_parts,
        start_part,
        urn_id,
    )

    upload_state = "SUCCEEDED"
    should_close = True
    # Exact for every skipped part except the last (which may be shorter than
    # part_size) — only wrong when start_part - 1 == total_parts (all parts already
    # done), and in that case the loop below never runs, so bytes_done is never
    # surfaced via on_progress; the slight overstatement is inert.
    bytes_done = (start_part - 1) * part_size
    part_num = start_part - 1

    try:
        with open(file_path, "rb") as source_file:
            for part_num in range(start_part, total_parts + 1):
                if cancel_event is not None and cancel_event.is_set():
                    raise TransferCancelledError(f"Upload of {file_path} cancelled.", urn=urn_id, file_path=file_path)

                offset = (part_num - 1) * part_size
                length = min(part_size, total_size - offset)

                # Pass 1: hash the part without buffering it (see _md5_hash_range).
                source_file.seek(offset)
                md5_hash = _md5_hash_range(source_file, length)

                part_info = _get_upload_file_part(
                    client=client,
                    async_job_id=async_job_id,
                    part_num=part_num,
                    md5_hash=md5_hash,
                )
                upload_url = part_info.send_url
                if not upload_url.startswith("http"):
                    raise RuntimeError(f"Suspicious url returned: {upload_url}. Aborting upload...")

                headers = {
                    "Content-MD5": md5_hash,
                    "Content-Type": "application/octet-stream",
                    "Content-Length": str(length),
                }
                # Pass 2: re-seek and stream the same range to the PUT socket instead of
                # handing urllib a full in-memory buffer (see _BoundedReader).
                source_file.seek(offset)
                req = urllib.request.Request(
                    upload_url, data=_BoundedReader(source_file, length), headers=headers, method="PUT"
                )
                with urllib.request.urlopen(req, timeout=upload_timeout, context=_SSL_CONTEXT) as response:
                    if response.status not in (200, 201):
                        raise ValueError(f"Failed to upload part {part_num}: HTTP {response.status}")
                    etag = response.headers.get("ETag")
                    if not etag:
                        raise ValueError(f"ETag not found in response for part {part_num}")
                    etags.append(etag)

                bytes_done += length
                if on_progress:
                    on_progress(bytes_done, total_size)
                # Persisted after bytes_done/on_progress so a crash between the two
                # can't leave the job store with a new etag but stale bytes_done.
                if on_part_uploaded:
                    on_part_uploaded(list(etags), total_size)
    except TransferCancelledError:
        # Cancellation is a deliberate, permanent abandonment (unlike a retryable
        # failure) — should_close stays True so the blob slot is invalidated.
        upload_state = "FAILED"
        raise
    except Exception as exc:
        upload_state = "FAILED"
        part_desc = f"part {part_num}" if part_num > 0 else "file open"
        if isinstance(exc, urllib.error.HTTPError):
            retryable = _http_retryable(exc.code)
        elif isinstance(exc, urllib.error.URLError):
            retryable = True
        else:
            retryable = False
        # A retryable failure leaves the job open for the next attempt to continue —
        # closing FAILED here would permanently invalidate the blob slot.
        should_close = not retryable
        log = logger.warning if retryable else logger.error
        log("Upload of %s failed during %s for URN %s: %s", file_path, part_desc, urn_id, exc)
        raise UploadError(
            f'Upload of "{file_path}" failed during {part_desc}. {exc}',
            urn=urn_id,
            file_path=file_path,
            retryable=retryable,
        ) from exc
    finally:
        if should_close:
            _close_upload_file(client, async_job_id, upload_state, etags)


def _open_upload_file(client: GQLClient, urn_id: str, upload_uri: str) -> UploadFileJob:
    op = client.service_binary.open_upload_file(variables=OpenUploadFileInput(upload_uri=upload_uri, urn_id=urn_id))
    try:
        op.call()
    except GQLAPIError as exc:
        raise UploadError(f'Failed to open upload job for URN "{urn_id}". {exc}', urn=urn_id) from exc
    return op.job


def _close_upload_file(client: GQLClient, async_job_id: str, state: str, etags: list) -> None:
    if state not in ("SUCCEEDED", "FAILED"):
        raise ValueError(f'Invalid state "{state}" for closing upload job {async_job_id}.')
    op = client.service_binary.close_upload_file(
        variables=CloseUploadFileInput(async_job_id=async_job_id, state=state, etags=etags)
    )
    try:
        op.call()
    except GQLAPIError as exc:
        raise UploadError(f"Failed to close upload job {async_job_id}. {exc}", urn=None) from exc


def _get_upload_file_part(
    client: GQLClient, async_job_id: str, part_num: int, md5_hash: str
) -> GetUploadFilePartResponse:
    op = client.service_binary.get_upload_file_part(
        variables=GetUploadFilePartInput(async_job_id=async_job_id, part_num=part_num, hash=md5_hash)
    )
    try:
        return op.call()
    except GQLAPIError as exc:
        raise UploadError(
            f"Failed to get upload URL for part {part_num} of upload job {async_job_id}. {exc}", urn=None
        ) from exc
