"""Configuration dataclass for the storage_manager module."""

from dataclasses import dataclass, fields
from typing import Optional


@dataclass
class Config:
    """Runtime configuration for the storage manager.

    Attributes:
        blob_storage_path: Read-only local cache of MEDM binaries.
        sandbox_path: Editable working copies ("drafts") prior to commit.
        workspace: Sandbox isolation key — a sub-folder under sandbox_path so two
            DCC instances never contend for the same draft folder. Also this
            instance's identity for upload-ownership and crash-recovery
            attribution (see StorageManager) — for that, it must be stable
            across restarts of one integrator instance and distinct between
            concurrently live instances. If two live instances share a
            workspace, StorageManager.__init__ raises TransferInProgressError.
            No default: pick a value stable across restarts of this integrator
            instance (e.g. app name + user id, or a per-launch machine/session
            id) and distinct from any other instance that may run concurrently.
        download_chunk_size: Bytes per read() call when streaming downloads.
        upload_timeout: Seconds per PUT request for upload parts.
        download_timeout: Seconds for the initial download connection.
        jobs_dir: Where transfer manifests live. Defaults to
            ``<blob_storage_path>/.jobs``.
        upload_staging_path: Staging snapshot root for upload blobs. Defaults to
            ``<blob_storage_path>/.staging``.
        max_transfer_threads: Maximum background transfer threads. Each active
            download or upload occupies one thread.
    """

    blob_storage_path: str
    sandbox_path: str
    workspace: str
    download_chunk_size: int = 1024 * 1024  # 1 MB
    upload_timeout: int = 120
    download_timeout: int = 60
    jobs_dir: Optional[str] = None  # defaults to <blob_storage_path>/.jobs when None
    upload_staging_path: Optional[str] = None  # defaults to <blob_storage_path>/.staging when None
    max_transfer_threads: int = 4

    @classmethod
    def from_dict(cls, d: dict) -> "Config":
        """Construct a Config from a dict, ignoring unrecognised keys."""
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in known})
