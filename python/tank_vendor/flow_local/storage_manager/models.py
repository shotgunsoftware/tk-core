"""Public data models for the storage_manager package.

Models fall into four groups:

**Draft models** (`NewDraftInfo`, `CheckoutDraftInfo`):
    Represent a local editable copy of an asset.  Both carry a *draft_id*
    (opaque handle for `publish_draft` / `discard_draft`) and a
    *draft_path* (sandbox folder where the caller places binary files).

**Blob model** (`BlobRef`):
    A single binary file associated with an asset revision.

**Transfer / job models** (`DownloadJobInfo`, `UploadJobInfo`,
`TransferProgress`, `JobStatus`, `JobKind`):
    Track the state of in-flight and completed file transfers.  Poll
    `StorageManager.list_jobs` to observe progress; use `StorageManager.resume_job` and
    `StorageManager.cancel_job` to manage them.

**Async wrapper** (`AsyncTask`):
    Wraps a background transfer thread.  Use `AsyncTask.metadata` for
    data resolved synchronously before the transfer started, and
    `AsyncTask.get` to block until the transfer completes.
"""

from __future__ import annotations

from concurrent.futures import Future
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar, Union

# ---------------------------------------------------------------------------
# Draft models
# ---------------------------------------------------------------------------


@dataclass
class NewDraftInfo:
    """Draft for an asset created locally but not yet published.

    Returned by `StorageManager.create_draft`. Copy your binary files
    into *draft_path*, then call `StorageManager.publish_draft` with
    `draft_id` to create the asset on the server for the first time.

    `draft_path` is the sandbox folder where the caller edits files — the same
    handle relationship as `CheckoutDraftInfo`, so create and checkout flows are
    symmetric. `draft_id` is the handle to pass to `publish_draft` / `discard_draft`.

    Typical usage::

        draft = sm.create_draft(name="MyAsset", parent_id=project_id)
        shutil.copy(local_file, draft.draft_path)
        asset = sm.publish_draft(
            draft.draft_id,
            binary_components=[BinaryComponentSpec(name="source", files=[...])],
        ).get()

    Attributes:
        draft_id: Opaque handle that identifies this draft folder.  Pass to
            `publish_draft` or `discard_draft`.
        name: Display name the asset will receive on first publish.
        parent_id: ID of the project (or folder) that will own the new asset.
        description: Optional description written to the asset on publish.
        type_ids: Schema type URNs preserved as generic components when the
            asset is first published.
        draft_path: Absolute path to the local sandbox folder.  The folder is
            created synchronously by `create_draft`; place all binary files
            here before calling `publish_draft`.
        pending_asset_id: Set internally after the server asset is created but
            before blobs are uploaded.  If publish fails mid-flight, a retry
            reads this field to reuse the already-created asset instead of
            creating a duplicate.
    """

    draft_id: str
    name: str
    parent_id: str
    description: str = ""
    type_ids: List[str] = field(default_factory=list)
    draft_path: str = ""
    pending_asset_id: Optional[str] = None


@dataclass
class CheckoutDraftInfo:  # pylint: disable=too-many-instance-attributes
    """Draft resulting from checking out a published revision.

    This is also the value returned by `checkout_draft`: `draft_path` is the
    sandbox folder where the caller edits files and `draft_id` is the handle to
    pass to `publish_draft` / `discard_draft`.

    `version_number` / `revision_number` are what was checked out;
    `latest_version_number` / `latest_revision_number` are what was current on the
    server at checkout time and drive conflict detection on the next publish.
    Field names mirror the SDK's `Asset`/`AssetRevision` `version_number` and
    `revision_number` so the same vocabulary is used across the SDK.

    This object is available immediately as `AsyncTask.metadata` before any
    files have been downloaded.  The sandbox folder and all field values are set
    synchronously; the blobs are only guaranteed on disk after `AsyncTask.get()`
    returns.

    Typical usage::

        task = sm.checkout_draft(asset_id, project_id)
        info = task.metadata          # CheckoutDraftInfo available immediately
        print(info.draft_path)        # sandbox folder already created on disk
        draft = task.get()            # block until all blobs are on disk
        # edit files in draft.draft_path ...
        asset = sm.publish_draft(
            draft.draft_id,
            binary_components=[BinaryComponentSpec(name="source", files=[...])],
        ).get()

    If the asset was updated on the server between checkout and publish,
    `publish_draft` raises `ConflictError`.  Re-checkout the latest revision
    and re-apply changes.

    Attributes:
        draft_id: Opaque handle that identifies this draft folder.  Pass to
            `publish_draft` or `discard_draft`.
        name: Display name of the checked-out asset.
        asset_id: ID of the checked-out asset.
        version_number: Version number that was checked out, or `None` for a
            pre-release / unversioned revision.
        revision_number: Revision number that was checked out.
        latest_version_number: Server's current version number at checkout
            time.  Used by `publish_draft` for conflict detection.
        latest_revision_number: Server's current revision number at checkout
            time.  If the server has advanced past this number when
            `publish_draft` is called, `ConflictError` is raised.
        draft_path: Absolute path to the local sandbox folder.  Available
            immediately (no need to call `AsyncTask.get()` first).  The
            downloaded blobs are placed here; guaranteed populated after
            `AsyncTask.get()` completes.
        dependencies: Blobs resolved from the asset's `uses` graph at
            checkout time.  Metadata is available immediately via
            `AsyncTask.metadata`; files are on disk only after
            `AsyncTask.get()` returns.  Persisted in the `.draft` sidecar
            so dep metadata survives session restarts.  Call
            `get_dependency_paths()` to obtain the local file-system paths.
    """

    draft_id: str
    name: str
    asset_id: str
    version_number: Optional[int]
    revision_number: int
    latest_version_number: int
    latest_revision_number: int
    draft_path: str = ""
    dependencies: List[BlobRef] = field(default_factory=list)


# Union type used for annotations where either draft kind is accepted.
DraftInfo = Union[NewDraftInfo, CheckoutDraftInfo]


# ---------------------------------------------------------------------------
# Blob models
# ---------------------------------------------------------------------------


@dataclass
class BlobRef:
    """A single binary blob that needs to be present locally.

    `BlobRef` objects are produced internally during checkout and surfaced via
    `StorageManager.get_dependency_paths`.
    Metadata fields are populated synchronously at checkout time; the file
    content is only guaranteed on disk after the enclosing `AsyncTask`
    completes.

    `blob_path` is the blob's encoded relative path (the component data `path`
    field), which may include subfolders (e.g. `textures/wood.png`); it is
    reproduced verbatim under the blob cache and sandbox on download. Blob path
    collisions are rejected at publish time, so no on-download renaming is needed.

    `version_id` is the AssetVersion URN for the version this blob belongs to
    (e.g. `urn:medm:assetVersion:...:ver:<n>`). The server validates `uses`
    targets as AssetVersion URNs, so callers can pass this directly to
    `publish_draft(uses=...)`.

    To map a `BlobRef` to a local file path after checkout completes, use
    `StorageManager.get_dependency_paths`::

        dep_paths = sm.get_dependency_paths(draft.draft_id, project_id)
        for blob in draft.dependencies:
            local_path = dep_paths[blob.version_id]

    Attributes:
        asset_id: ID of the asset this blob belongs to.
        revision_number: Revision number this blob was fetched from.
        urn: Binary component resource ID (unique identifier on the server).
        blob_path: Blob's encoded relative path reproduced under the local
            cache and sandbox on download.  May include subfolders.
        version_number: Numbered version this blob's revision belongs to, or
            `None` for displaced historical revisions (where the server has
            unlinked the version pointer after a non-bump update).  Used
            internally to determine the `v{N}/` version-surface path.
        is_zipped: `True` if the blob is a ZIP archive that will be expanded
            in-place after download.  The caller sees the extracted files, not
            the archive itself.
        version_id: AssetVersion URN for the version this blob belongs to.
            Can be passed directly to `publish_draft(uses=[blob.version_id])`
            to preserve the same `uses` graph on re-publish.
    """

    asset_id: str
    revision_number: int
    urn: str
    blob_path: str
    version_number: Optional[int] = None  # None for displaced historical revisions
    is_zipped: bool = False  # blob is a zip archive → expand on checkout/download
    version_id: Optional[str] = None  # AssetVersion URN for this blob's version
    # todo:phil, component name might be useful to provide here.
    # todo:phil, job grouped by asset?


# ---------------------------------------------------------------------------
# Job models
# ---------------------------------------------------------------------------


class JobStatus(str, Enum):
    """Lifecycle states for a transfer job.

    Jobs move through states in order: `PENDING` → `RUNNING` →
    `COMPLETED` / `FAILED` / `CANCELLED`.

    All three of `COMPLETED`, `FAILED`, and `CANCELLED` are `is_terminal` —
    the job will not transition again on its own. But only `COMPLETED` and
    `CANCELLED` are `is_prunable`: they are dropped from the job store
    immediately. `FAILED` jobs are kept so callers can inspect `error`, then
    either retry via `StorageManager.resume_job` or abandon via
    `StorageManager.cancel_job`.
    """

    PENDING = "pending"
    """Registered but not yet executing."""
    RUNNING = "running"
    """Transfer is actively in progress."""
    COMPLETED = "completed"
    """Transfer finished successfully; pruned from the job store."""
    FAILED = "failed"
    """Transfer encountered an error; persisted for inspection and retry."""
    CANCELLED = "cancelled"
    """Manually cancelled; pruned from the job store."""

    @property
    def is_terminal(self) -> bool:
        return self in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED)

    @property
    def is_prunable(self) -> bool:
        """Whether a job in this status should be dropped from the store immediately."""
        return self in (JobStatus.COMPLETED, JobStatus.CANCELLED)


class JobKind(str, Enum):
    """Discriminator for transfer job types.

    Use `job.job_kind` to narrow a `TransferJobInfo` union without
    `isinstance` checks::

        for job_id, job in sm.list_jobs().items():
            if job.job_kind == JobKind.DOWNLOAD:
                ...  # DownloadJobInfo
            else:
                ...  # UploadJobInfo
    """

    DOWNLOAD = "download"
    UPLOAD = "upload"


class _TransferJobBase:
    """Base class for transfer job dataclasses.

    Declares the shared attributes so mypy understands they are always present,
    and provides the derived `is_terminal`, `is_prunable`, and
    `percent` properties. Concrete subclasses (`DownloadJobInfo`,
    `UploadJobInfo`) are `@dataclass` classes that define all fields —
    including the ones declared here — as dataclass fields with appropriate
    defaults.
    """

    # Bare class-level annotations (no defaults) declare the contract for mypy.
    # Concrete dataclass subclasses provide the actual fields with defaults.
    status: JobStatus
    bytes_done: int
    bytes_total: int
    error: Optional[str]

    @property
    def is_terminal(self) -> bool:
        return self.status.is_terminal

    @property
    def is_prunable(self) -> bool:
        return self.status.is_prunable

    @property
    def percent(self) -> float:
        """Completion fraction in [0.0, 1.0]. Returns 0.0 until bytes_total is known."""
        if self.bytes_total == 0:
            return 0.0
        return float(min(1.0, self.bytes_done / self.bytes_total))


@dataclass
class DownloadJobInfo(_TransferJobBase):
    """State for a single blob download.

    Created by `StorageManager.checkout_draft` and `StorageManager.download_asset`.  Jobs are
    pre-registered in the job store *before* the background transfer starts, so
    callers can observe them via `StorageManager.list_jobs` without waiting for
    the transfer to begin.

    An interrupted download can be resumed via `StorageManager.resume_job`; it will continue
    from a local `.part` file using HTTP Range, avoiding a full re-download.

    *urn* is the binary component's resource id; *file_path* is the local
    destination (named to match UploadJobInfo.file_path for symmetry).
    *project_id* is the MEDM project the blob's download URL is resolved
    against; it is persisted so an interrupted download can be resumed without
    re-supplying it.

    Attributes:
        job_id: Unique key for this job in the job store.
        file_path: Local destination path for the downloaded blob.
        urn: Binary component resource ID (the blob being downloaded).
        project_id: MEDM project used to resolve the blob's download URL.
            Persisted so interrupted downloads can be resumed in a later
            session without re-supplying it.
        status: Current lifecycle state (see `JobStatus`).
        bytes_done: Bytes transferred so far.
        bytes_total: Total expected bytes; `0` until the server responds
            with `Content-Length`.  Use `percent` for a safe ratio.
        error: Human-readable error message when `status` is `FAILED`,
            otherwise `None`.
    """

    job_id: str
    file_path: str
    urn: str
    project_id: str = ""
    status: JobStatus = field(default=JobStatus.PENDING)
    bytes_done: int = 0
    bytes_total: int = 0
    error: Optional[str] = None

    @property
    def job_kind(self) -> JobKind:
        return JobKind.DOWNLOAD


@dataclass
class UploadJobInfo(_TransferJobBase):
    """State for a single blob upload.

    Created by `StorageManager.publish_draft` after the server mutation returns
    blob URNs and upload slots.  Unlike download jobs, upload jobs are not
    pre-registered before the background thread starts — `publish_draft`'s
    `AsyncTask` returns an empty `job_ids` list.  Poll `StorageManager.list_jobs`
    after a short delay or wait for `AsyncTask.get()` to complete.

    An interrupted upload can be retried via `StorageManager.resume_job`; the same
    server-side upload job (`async_job_id`) is reused, and the upload resumes from
    the next unacknowledged part using the persisted `part_etags`
    instead of restarting from part 1. The in-progress server-side upload job
    from a failed attempt is deliberately left open rather than closed —
    closing it would permanently invalidate the blob slot, and the binary
    service rejects a second `open_upload_file` call for the same
    `upload_uri` once the first has registered the file, so retries must
    reuse `async_job_id` rather than reopening.

    *urn* is the binary component's resource id; `file_path` is the local source
    file. `upload_uri` is the client-generated `upload://` handle recorded with
    the component on the server, reused to reopen the upload slot on resume.

    Attributes:
        job_id: Unique key for this job in the job store.
        file_path: Local source file being uploaded.
        urn: Binary component resource ID (the blob being uploaded).
        upload_uri: Client-generated `upload://` handle recorded with the
            component on the server.  Reused to reopen the upload slot when
            resuming an interrupted transfer.
        asset_id: ID of the asset being published.  Used internally to enforce
            one-upload-per-asset exclusion; concurrent publishes for the same
            asset are rejected.
        owner: This instance's identity (`Config.workspace`) at the moment the
            job was created; never rewritten once set.
        status: Current lifecycle state (see `JobStatus`).
        bytes_done: Bytes transferred so far.
        bytes_total: Total size of the file being uploaded.
        error: Human-readable error message when `status` is `FAILED`,
            otherwise `None`.
        part_etags: ETags for parts already uploaded and acknowledged, in part
            order (index 0 is part 1). Persisted after each part so a retry or
            `StorageManager.resume_job` can continue from the next part instead
            of re-uploading the whole file.
        part_etags_size: The file's size when `part_etags` was last updated.
            Compared against the file's current size before resuming — a mismatch
            means the file changed since the etags were recorded, so they're
            discarded and the upload restarts from part 1. Doesn't detect the file
            being replaced by different content of the same size.
        async_job_id: Server-side upload job id returned by `open_upload_file`.
            Persisted as soon as the job is opened so a retry or `resume_job`
            reuses this same job instead of calling `open_upload_file` again —
            the binary service rejects a second open for the same
            `upload_uri` once a file has been registered against it.
    """

    job_id: str
    file_path: str
    urn: str
    upload_uri: str
    asset_id: str = ""
    owner: Optional[str] = None
    status: JobStatus = field(default=JobStatus.PENDING)
    bytes_done: int = 0
    bytes_total: int = 0
    error: Optional[str] = None
    part_etags: List[str] = field(default_factory=list)
    part_etags_size: int = 0
    async_job_id: Optional[str] = None

    @property
    def job_kind(self) -> JobKind:
        return JobKind.UPLOAD


# Union type used for annotations where either job kind is accepted.
TransferJobInfo = Union[DownloadJobInfo, UploadJobInfo]


@dataclass
class ClearCacheResult:
    """Outcome of `StorageManager.clear_cache`.

    Attributes:
        cleared: Storage keys (cache directory names) that were deleted.
        bytes_freed: Total bytes freed across all deleted directories.
        errors: Storage key -> error message, for a directory that could not
            be removed (e.g. a permission error, or one that became locked
            after `clear_cache()`'s upfront validation passed). Left untouched.
        force_cancelled_jobs: Job ids force-cancelled by a `force=True` call.
            Empty unless `force=True` was passed.
        force_broken_locks: Storage keys whose live transfer lock was forcibly
            removed by a `force=True` call after it did not respond to a
            cooperative cancel request — possibly held by another process.
            Empty unless `force=True` was passed.
        cooperative_stopped: Storage keys held by another process that
            released their lock on their own after a `force=True` call
            signaled a cancel request — no lock-breaking was needed. Empty
            unless `force=True` was passed.
    """

    cleared: List[str] = field(default_factory=list)
    bytes_freed: int = 0
    errors: Dict[str, str] = field(default_factory=dict)
    force_cancelled_jobs: List[str] = field(default_factory=list)
    force_broken_locks: List[str] = field(default_factory=list)
    cooperative_stopped: List[str] = field(default_factory=list)


@dataclass
class TransferProgress:
    """Transfer progress snapshot passed to a :data:`ProgressCallback`.

    Delivered repeatedly by the background worker thread as bytes are
    transferred.  The callback registered via `on_progress=` in
    `StorageManager.checkout_draft`, `StorageManager.download_asset`, or
    `StorageManager.publish_draft` is called from that worker thread and
     must be thread-safe.

    Attributes:
        bytes_done: Bytes transferred so far in the current job.
        bytes_total: Total expected bytes for the current job.  May be `0`
            until the server responds with `Content-Length` (downloads) or
            the file size is measured (uploads); `percentage` returns
            `0.0` until this is known.
    """

    bytes_done: int
    bytes_total: int

    @property
    def percentage(self) -> float:
        """Completion fraction in [0.0, 1.0]. Returns 0.0 until bytes_total is known."""
        if self.bytes_total == 0:
            return 0.0
        return min(1.0, self.bytes_done / self.bytes_total)


ProgressCallback = Callable[[TransferProgress], None]
"""Signature for a transfer progress callback.

Passed as `on_progress=` to `StorageManager.checkout_draft`, `StorageManager.download_asset`, and
`StorageManager.publish_draft`.  Called from the background worker thread on each progress update
— implementations must be thread-safe::

    def on_progress(p: TransferProgress) -> None:
        print(f"{p.bytes_done}/{p.bytes_total} ({p.percentage:.0%})")

    sm.download_asset(asset_id, project_id, on_progress=on_progress).get()
"""


_T = TypeVar("_T")


class AsyncTask(Generic[_T]):
    """A background transfer operation returned by `checkout_draft`, `download_asset`,
    `download_blob`, `publish_draft`, and `resume_job`.

    The task runs file transfers in a background thread while the calling thread
    remains unblocked. Use `metadata` for any data that was resolved
    synchronously before the transfer started (e.g. the draft folder path on a
    checkout), and `get` to block until the transfer is complete.

    **When is** `metadata` **available?**

    +---------------------------------+----------------------------------------------+
    | Returned by                     | `metadata` before `get()`?               |
    +=================================+==============================================+
    | `checkout_draft()`            | Yes — `CheckoutDraftInfo`             |
    +---------------------------------+----------------------------------------------+
    | `download_blob()`             | Yes — `BlobRef`                       |
    +---------------------------------+----------------------------------------------+
    | `download_asset()`            | No — `None` until `get()` returns        |
    +---------------------------------+----------------------------------------------+
    | `publish_draft()`             | No — `None` until `get()` returns        |
    +---------------------------------+----------------------------------------------+
    | `resume_job()`                | Yes — the pre-resume `TransferJobInfo`   |
    +---------------------------------+----------------------------------------------+

    Typical usage::

        # Checkout: inspect the sandbox folder while blobs download in background
        task = sm.checkout_draft(asset_id, project_id)
        info = task.metadata          # CheckoutDraftInfo — no blocking needed
        print(info.draft_path)        # sandbox folder already created
        draft = task.get()            # block until all blobs are on disk
        dep_paths = sm.get_dependency_paths(draft.draft_id, project_id)

        # Download: no metadata until transfer completes
        task = sm.download_asset(asset_id, project_id)
        blob_paths = task.get()       # {revision_number: local_path, ...}

        # Single blob: metadata available before transfer completes
        task = sm.download_blob(revision_id, blob_urn)
        blob = task.metadata          # BlobRef — available before transfer completes
        path = task.get()             # block until the blob is on disk

        # Publish: no metadata until mutation + uploads complete
        task = sm.publish_draft(draft.draft_id, binary_components=[...])
        asset = task.get()            # returns the published Asset

    Cancelling a running transfer:
        `cancel()` only works before the background thread has started — it
        returns `False` once running. For a transfer that is already
        running, cancel individual jobs via
        `StorageManager.cancel_job` using the IDs in `job_ids`; the running job raises
        `TransferCancelledError`, which `get` re-raises.

    Crash recovery:
        Failed jobs are persisted to disk.  On the next session, call
        `StorageManager.get_pending_jobs` to rehydrate them, then
        `StorageManager.resume_job` to retry.

    Attributes:
        job_ids: Job store keys for the in-flight transfer jobs. Populated for
            checkout and download operations so callers can poll via
            `StorageManager.list_jobs`. Empty for publish operations (upload job
            IDs are only known after the server mutation, which runs inside the
            background thread).
    """

    def __init__(
        self,
        job_ids: List[str],
        future: "Future[_T]",
        metadata: Optional[Any] = None,
    ) -> None:
        self.job_ids: List[str] = list(job_ids)
        self._future: "Future[_T]" = future
        self._metadata: Optional[Any] = metadata

    @property
    def metadata(self) -> Optional[Any]:
        """Synchronously-available data set before the background thread started.

        For `checkout_draft` this is the `CheckoutDraftInfo` (draft folder
        path, version numbers, etc.) — available immediately without calling
        `get`. For `download_blob` this is the `BlobRef` for the
        target blob — available before `get`. For `publish_draft` and
        `download_asset` this is `None` until `get` returns.

        After `get` completes, this property keeps any synchronously-set
        metadata (e.g. `CheckoutDraftInfo`, `BlobRef`). The return
        value of `get` may differ — for `download_blob` it is the cache
        path string while `metadata` remains the `BlobRef`.
        """
        return self._metadata

    @property
    def done(self) -> bool:
        """`True` if the background transfer has finished (successfully or with an error)."""
        return self._future.done()

    def get(self, timeout: Optional[float] = None) -> _T:
        """Block until the transfer completes and return the result.

        Re-raises any exception from the transfer thread (e.g. `DownloadError`,
        `UploadError`, `TransferInProgressError`).

        Args:
            timeout: Maximum seconds to wait, or `None` to wait forever.

        Raises:
            concurrent.futures.TimeoutError: timeout elapsed before completion.
            concurrent.futures.CancelledError: `cancel` succeeded before the transfer
                started.
            TransferCancelledError: A job was cancelled via `StorageManager.cancel_job`
                while the transfer was already running.
        """
        value = self._future.result(timeout=timeout)
        if self._metadata is None:
            self._metadata = value
        return value

    def cancel(self) -> bool:
        """Request cancellation of the pending transfer.

        Returns `True` if the transfer was cancelled before it started.
        Returns `False` if it is already running or complete — use
        `StorageManager.cancel_job` to stop a running transfer.
        """
        return self._future.cancel()

    def add_done_callback(self, callback: Callable[[Future[_T]], None]) -> None:
        """Register a callback on the underlying transfer future."""
        self._future.add_done_callback(callback)
