"""Local blob-cache path computation, the version manifest, and the asset-info sidecar."""

import json
import logging
from dataclasses import dataclass, field
from typing import Dict, Optional

from adsk.flow.local.storage_manager.config import Config
from adsk.flow.local.storage_manager.internal.context import get_active_config
from adsk.flow.local.storage_manager.internal.fs import HASH_ALGORITHM, atomic_write_json, cleanpath, ensure_dir

logger = logging.getLogger(__name__)

# Bump manually whenever an on-disk blob/manifest change would be misread by an SDK build
# using a lower value. Decoupled from the SDK's own package version — unrelated point releases
# built from unchanged storage code share a value and therefore share cache storage; only a
# real format break gets a new value, and therefore a new, physically isolated directory.
CACHE_FORMAT_VERSION = 1


def storage_key(asset_id: str) -> str:
    """Extract the short, file-safe key from an asset URN.

    URN format: urn:medm:asset:<col_id>:<prj_id>:<asset_id>
    Returns the final segment which is safe to use as a directory name.
    """
    parts = asset_id.split(":")
    return parts[-1] if parts else asset_id


def blob_cache_root() -> str:
    """Return the top-level directory for the current cache format's blob storage tree.

    All asset dirs live under here so a CACHE_FORMAT_VERSION bump physically isolates
    old-format data instead of letting a newer SDK build misread it.
    """
    return cleanpath(get_active_config().blob_storage_path, f"cache_fmt_v{CACHE_FORMAT_VERSION}")


def storage_asset_dir_for(config: Config, asset_id_or_key: str) -> str:
    """Return the blob storage cache directory for asset_id_or_key under an explicit config.

    Accepts either a full asset URN or an already-extracted storage key — storage_key() is
    idempotent on a key it's already applied to.

    Use this instead of storage_asset_dir from code that may run outside a
    with_active_config-bound call — e.g. a lock's background heartbeat thread signalling
    cancellation for another process — since get_active_config() would raise there.
    """
    return cleanpath(config.blob_storage_path, f"cache_fmt_v{CACHE_FORMAT_VERSION}", storage_key(asset_id_or_key))


def storage_asset_dir(asset_id: str) -> str:
    """Return the blob storage cache directory for a specific asset."""
    return storage_asset_dir_for(get_active_config(), asset_id)


def storage_version_dir(asset_id: str, version_number: int) -> str:
    """Return the stable version-surface directory for a specific asset version.

    This is the path DCC tools reference, and the only physical cache copy of the version's blobs:
    they are downloaded directly here (atomic replace, see internal/remote.py), never staged through
    an intermediate revision-cache directory. Content is not deleted during normal SDK operation
    (`StorageManager.clear_cache()` is the sole, explicit exception); see the version manifest
    (`read_version_manifest`) for what's actually present.
    """
    return cleanpath(storage_asset_dir(asset_id), f"v{version_number}")


def storage_displaced_revision_dir(asset_id: str, revision_number: int) -> str:
    """Fallback cache location for a "displaced" historical revision.

    Used only by `StorageManager.download_blob` when the requested revision has no live
    version pointer (`blob.version_number is None` — the server unlinked it after a
    later non-bump update), so there is no ``vN/`` to write into.
    """
    return cleanpath(storage_asset_dir(asset_id), ".displaced", f"r{revision_number}")


# ---------------------------------------------------------------------------
# Version manifest — per-version-dir record of what's on disk in vN/
# ---------------------------------------------------------------------------


@dataclass
class ManifestEntry:
    """Record of a single blob synced into a version dir.

    Attributes:
        path: The blob's encoded relative path within the version dir (matches `BlobRef.blob_path`).
        hash: Content hash of the file at *path*, using the manifest's `hash_algorithm`.
        size: File size in bytes.
        mtime: `os.path.getmtime()` of *path* right after this SDK wrote it. Compared
            against the file's current mtime on a cache hit (see
            `StorageManager._is_manifest_entry_current`) to catch same-size corruption
            that a later in-place write would leave behind.
        revision_number: The revision this blob's bytes came from. A version dir can hold entries
            from more than one revision over time, so the staleness check compares against this,
            not the manifest's top-level revision_number.
        expanded: True if *path* is a zip archive whose contents have already been extracted
            alongside it, so re-expansion can be skipped.
    """

    path: str
    hash: str
    size: int
    mtime: float
    revision_number: int
    expanded: bool = False


@dataclass
class VersionManifest:
    """Manifest of what's on disk in a `vN/` version-surface directory.

    Describes what has been synced into `vN/`, not necessarily what the current revision contains,
    so it stays valid across a version rollback to an already-synced revision. Persisted as
    `vN/.revision`.
    """

    asset_id: str
    version_number: int
    revision_number: int  # max(entry.revision_number for entry in binaries) — informational only
    synced_at: str
    hash_algorithm: str
    binaries: Dict[str, ManifestEntry] = field(default_factory=dict)  # blob_path -> entry


def version_manifest_path(version_dir: str) -> str:
    """Return the manifest file path for *version_dir*."""
    return cleanpath(version_dir, ".revision")


def read_version_manifest(version_dir: str) -> Optional[VersionManifest]:
    """Read the manifest for *version_dir*, or None if missing/unreadable/malformed.

    Returns None (never raises) on a missing file, unparseable JSON, or a manifest with no
    `binaries` list — callers treat None as "nothing known to be current."
    """
    file_path = version_manifest_path(version_dir)
    try:
        with open(file_path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None

    raw_binaries = data.get("binaries")
    if not isinstance(raw_binaries, list):
        return None

    try:
        binaries = {
            entry["path"]: ManifestEntry(
                path=entry["path"],
                hash=entry["hash"],
                size=entry["size"],
                mtime=entry["mtime"],
                revision_number=entry["revision_number"],
                expanded=entry.get("expanded", False),
            )
            for entry in raw_binaries
        }
        return VersionManifest(
            asset_id=data["asset_id"],
            version_number=data["version_number"],
            revision_number=data["revision_number"],
            synced_at=data.get("synced_at", ""),
            hash_algorithm=data.get("hash_algorithm", HASH_ALGORITHM),
            binaries=binaries,
        )
    except (KeyError, TypeError):
        return None


def write_version_manifest(version_dir: str, manifest: VersionManifest) -> None:
    """Write *manifest* atomically to *version_dir*.

    Failures are logged and swallowed — a missed write only costs a redundant
    future re-download (the manifest entry that would have prevented it is
    simply absent), never corruption, so callers are not disrupted.
    """
    file_path = version_manifest_path(version_dir)
    data = {
        "asset_id": manifest.asset_id,
        "version_number": manifest.version_number,
        "revision_number": manifest.revision_number,
        "synced_at": manifest.synced_at,
        "hash_algorithm": manifest.hash_algorithm,
        "binaries": [
            {
                "path": entry.path,
                "revision_number": entry.revision_number,
                "hash": entry.hash,
                "size": entry.size,
                "mtime": entry.mtime,
                "expanded": entry.expanded,
            }
            for entry in manifest.binaries.values()
        ],
    }
    try:
        ensure_dir(version_dir)
        atomic_write_json(file_path, data, indent=4)
    except OSError as exc:
        logger.warning("Could not write version manifest %s: %s", file_path, exc)
