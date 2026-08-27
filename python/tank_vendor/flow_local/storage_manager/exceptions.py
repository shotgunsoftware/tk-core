"""Exceptions for the storage_manager module."""

from typing import List, Optional


class StorageManagerError(Exception):
    """Base exception for all storage_manager errors."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ComponentSpecError(StorageManagerError):
    """Raised when a component spec is invalid or incompatible with the server schema."""


class CreateAssetError(StorageManagerError):
    """Raised when the creating asset call fails, before any file transfer starts."""


class UpdateAssetError(StorageManagerError):
    """Raised when the update-asset mutation fails, before any file transfer starts."""


class TransferError(StorageManagerError):
    """Base for upload/download failures. The job is recorded and may be resumable.

    urn / file_path identify what was being transferred; job_id is the
    JobStore key to pass to `StorageManager.resume_job`. retryable is True for
    transient failures (network errors, 429, 5xx) where the same request may
    succeed on a subsequent attempt.
    """

    def __init__(
        self,
        message: str,
        *,
        urn: Optional[str] = None,
        file_path: Optional[str] = None,
        job_id: Optional[str] = None,
        retryable: bool = False,
    ):
        super().__init__(message)
        self.urn = urn
        self.file_path = file_path
        self.job_id = job_id
        self.retryable = retryable


class DownloadError(TransferError):
    """Raised when a binary download fails."""


class UploadError(TransferError):
    """Raised when a multipart upload fails."""


class TransferCancelledError(TransferError):
    """Raised when a job's transfer loop notices it has been cancelled mid-flight.

    Always constructed with `retryable=False` — a cancelled transfer is never
    retried; the job is already discarded from the job store by the time this
    is raised.
    """

    def __init__(
        self,
        message: str,
        *,
        urn: Optional[str] = None,
        file_path: Optional[str] = None,
        job_id: Optional[str] = None,
    ):
        super().__init__(message, urn=urn, file_path=file_path, job_id=job_id, retryable=False)


class StorageError(StorageManagerError):
    """Raised when a local file system operation fails."""


class DependencyError(StorageManagerError):
    """Raised when the `uses`-graph traversal for dependency resolution fails."""

    def __init__(self, message: str, *, asset_id: Optional[str] = None):
        super().__init__(message)
        self.asset_id = asset_id


class ConflictError(StorageManagerError):
    """Raised when a publish would overwrite work that advanced since checkout.

    Raised by the server-side optimistic check and by the client-side draft
    conflict check (`publish_draft` when the asset advanced since checkout).
    Re-checkout to fetch the latest revision and retry.

    asset_id identifies which asset conflicted, useful in workflows that
    manage multiple assets concurrently.
    """

    def __init__(
        self,
        message: str,
        *,
        asset_id: Optional[str] = None,
    ):
        super().__init__(message)
        self.asset_id = asset_id


class NoChangeError(StorageManagerError):
    """Raised when publish_draft is a no-op: files, metadata, and `uses` are all
    unchanged since checkout.

    No `create_asset`/`update_asset` call is made and no blobs are uploaded.
    revision_number is the server revision compared against (the one checked out).
    """

    def __init__(self, message: str, *, asset_id: Optional[str] = None, revision_number: Optional[int] = None):
        super().__init__(message)
        self.asset_id = asset_id
        self.revision_number = revision_number


class DraftExistsError(StorageManagerError):
    """Raised when a draft already exists for the asset being checked out.

    Pass `discard_existing_draft=True` to `checkout_draft`, or discard the
    existing draft first (`discard_draft` with the asset's draft id).
    """

    def __init__(self, message: str, *, asset_id: Optional[str] = None, draft_path: Optional[str] = None):
        super().__init__(message)
        self.asset_id = asset_id
        self.draft_path = draft_path


class DraftError(StorageManagerError):
    """Raised when a sandbox draft is missing, invalid, or its sidecar is unreadable."""


class BinaryComponentDropError(StorageManagerError):
    """Raised when publish_draft would silently drop existing binary component(s).

    publish_draft's binary_components uses REPLACE semantics, so a name not
    re-sent is deleted. Pass force=True to publish_draft to drop intentionally.
    """

    def __init__(self, message: str, *, asset_id: Optional[str] = None, dropped: Optional[List[str]] = None):
        super().__init__(message)
        self.asset_id = asset_id
        self.dropped = dropped or []


class TransferInProgressError(StorageManagerError):
    """Raised when a transfer is already in progress for the requested asset.

    The transfer lock is fail-fast: if another process holds the lock the error
    is raised immediately rather than waiting. Cancel the in-progress job with
    `StorageManager.cancel_job` and retry.
    """

    def __init__(self, message: str, *, asset_id: Optional[str] = None, job_id: Optional[str] = None):
        super().__init__(message)
        self.asset_id = asset_id
        self.job_id = job_id


class JobOwnershipError(StorageManagerError):
    """Raised when discarding or cancelling a job manifest owned by a different, still-live instance.

    Defense in depth beyond `StorageManager.cancel_all_jobs`'s scoping to jobs
    this process created: `StorageManager.cancel_job` lets a caller target an
    arbitrary job id directly, including one it doesn't own.
    """

    def __init__(self, message: str, *, owner: Optional[str] = None, job_id: Optional[str] = None):
        super().__init__(message)
        self.owner = owner
        self.job_id = job_id
