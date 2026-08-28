"""Job store for tracking and resuming interrupted file transfers."""

import dataclasses
import glob
import hashlib
import json
import logging
import os
import threading
from typing import Callable, Dict, Optional, Set

from ..exceptions import JobOwnershipError
from .fs import atomic_write_json, ensure_dir
from ..models import DownloadJobInfo, JobKind, JobStatus, TransferJobInfo, UploadJobInfo

logger = logging.getLogger(__name__)


def make_job_key(kind: JobKind, identifier: str) -> str:
    """Build a stable job store key from a job kind and its URN/URI identifier."""
    return f"{kind.value}:{identifier}"


def write_job_info(path: str, job: TransferJobInfo) -> None:
    """Atomically write job to `path` as JSON.

    Advisory — never raises; logs a warning on I/O failure so the transfer
    continues even when the manifest cannot be persisted.
    """
    try:
        data = {k: v for k, v in dataclasses.asdict(job).items() if v is not None}
        data["job_kind"] = job.job_kind
        atomic_write_json(path, data)
    except OSError as exc:
        logger.warning("Could not persist job manifest %s: %s", path, exc)


def read_job_info(path: str) -> Optional[TransferJobInfo]:
    """Read and return a DownloadJobInfo or UploadJobInfo from `path`.

    Returns None if the file is missing, unreadable, malformed, or has an
    unknown `job_kind`.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Skipping unreadable job manifest %s: %s", path, exc)
        return None

    # Coerce status string → enum at the deserialization boundary.
    try:
        data["status"] = JobStatus(data.get("status", JobStatus.PENDING.value))
    except ValueError:
        logger.warning("Unknown status value in job manifest %s", path)
        return None

    try:
        kind = JobKind(data.get("job_kind"))
    except ValueError:
        logger.warning("Unknown job_kind %r in %s", data.get("job_kind"), path)
        return None

    try:
        if kind == JobKind.DOWNLOAD:
            known = {field.name for field in dataclasses.fields(DownloadJobInfo)}
            return DownloadJobInfo(**{k: v for k, v in data.items() if k in known})
        if kind == JobKind.UPLOAD:
            known = {field.name for field in dataclasses.fields(UploadJobInfo)}
            return UploadJobInfo(**{k: v for k, v in data.items() if k in known})
    except (TypeError, ValueError) as exc:
        logger.warning("Malformed job manifest %s: %s", path, exc)
        return None

    return None


class JobStore:
    """Registry of transfer jobs with optional JSON-file persistence.

    When `jobs_dir` is provided, each non-prunable job is written to a
    `<jobs_dir>/<hash>.job.json` file on creation and status change. Prunable
    jobs (completed, cancelled — see `JobStatus.is_prunable`) are dropped
    from both memory and disk the moment they finish. `FAILED` jobs are
    terminal but not prunable: they stick around in memory and on disk until a
    caller explicitly resumes (`StorageManager.resume_job`) or abandons
    (`cancel`) them, so the store can hold work still in flight,
    interrupted by a crash, or failed-and-awaiting-inspection. All of these are
    reloaded on init (a job left RUNNING by a crash is reset to PENDING; a
    FAILED job stays FAILED). A failed download's resume point is its on-disk
    `.part` file, not the manifest, so simply re-requesting the blob also
    picks up where it left off. Uploads have no local partial artifact, so the
    manifest's `part_etags` field is the resume point — see `UploadJobInfo`.

    Each job key also has an associated cancellation `threading.Event`
    (see `get_cancel_event`), checked by the in-progress transfer between
    chunks/parts so `cancel` can interrupt a `RUNNING` job, not just a
    `PENDING` one. The Event is installed at the same two places a job enters
    `_jobs` — `create` and `_load` — so every live job always has
    exactly one; `get_cancel_event` is a strict lookup, never a lazy
    create. The one exception is a kept `FAILED` job: its Event is removed
    once its run finishes (nothing is executing for it to cancel), and
    `get_live` installs a fresh one if it is later reused or resumed.
    """

    def __init__(
        self,
        jobs_dir: Optional[str] = None,
        owner: Optional[str] = None,
        is_owner_live: Optional[Callable[[str], bool]] = None,
    ) -> None:
        self._jobs: Dict[str, TransferJobInfo] = {}
        self._cancel_events: Dict[str, threading.Event] = {}
        self._jobs_dir = jobs_dir
        self._lock = threading.Lock()
        self._owner = owner
        # Does file I/O — always resolved before self._lock is acquired
        # (see _resolve_owner_live), never while holding it. update()/cancel()
        # peek the relevant job's owner without the lock for exactly this
        # reason.
        self._is_owner_live = is_owner_live or (lambda _owner: False)
        self._local_session_keys: Set[str] = set()
        if jobs_dir:
            self._ensure_jobs_dir()
            self._load()

    def create(self, key: str, job: TransferJobInfo) -> TransferJobInfo:
        """Register job under key and flush its manifest to disk.

        Installs a fresh cancellation Event for key (see `_admit`),
        overwriting any stale leftover from a previous job that used the same
        key — a key is only ever reused once the previous job for it is terminal.
        Marks key as part of this instance's local session (see
        `local_session_ids`) — unlike a job recovered by `_load`, this
        instance is authoritatively the one that started it.
        """
        with self._lock:
            self._admit(key, job)
            self._local_session_keys.add(key)
            self._flush(job)
        return job

    def local_session_ids(self) -> Set[str]:
        """Return the ids of jobs this instance created (via `create` or `get_live`), not loaded from disk."""
        with self._lock:
            return set(self._local_session_keys)

    def get_cancel_event(self, key: str) -> threading.Event:
        """Return the cancellation Event for key.

        Every job present in the store has an Event installed at the moment it
        enters `_jobs` — by `create` or, for a crash-recovered job, by
        `_load`. This is a strict lookup, not a lazy create: calling it
        for a key with no registered job is a caller bug.

        Raises:
            KeyError: no job is registered under key.
        """
        with self._lock:
            event = self._cancel_events.get(key)
            if event is None:
                raise KeyError(f"No job registered for key {key!r}")
            return event

    def remove_cancel_event(self, key: str, event: threading.Event) -> None:
        """Drop the cancellation Event for key if it is still event.

        Called once by the transfer runner after a job reaches a terminal
        state. The identity check (compare-and-delete) ensures a fresh Event
        installed by a subsequent `create` for a reused key is never
        clobbered by a late cleanup call from a previous job's run.
        """
        with self._lock:
            if self._cancel_events.get(key) is event:
                del self._cancel_events[key]

    def get_live(self, key: str) -> Optional[TransferJobInfo]:
        """Return key's job if it can be run in place, installing a fresh
        cancellation Event first if it is `FAILED`.

        A `PENDING`/`RUNNING` job is returned as-is. A `FAILED` job is
        also returned, but only after a fresh Event is installed — its
        previous run already removed the exhausted one via
        `remove_cancel_event`, so callers that pass the returned job
        straight to `StorageManager._run_job` need a working one. Returns
        `None` for an unknown key or a prunable one (completed/cancelled —
        see `JobStatus.is_prunable`), signalling the caller to
        `create` a fresh job under the key instead.

        The lookup and event installation happen under a single lock
        acquisition so a concurrent `cancel` can't discard the job
        between the two — which would otherwise leave a dangling Event
        installed for a key no longer in `_jobs`.

        Also marks key as part of this instance's local session (see
        `local_session_ids`): a caller resuming a job it fetched via
        `get_live` is claiming it as its own from this point forward,
        whether it was originally created here or recovered from disk by
        `_load`.
        """
        with self._lock:
            job = self._jobs.get(key)
            if job is None or job.is_prunable:
                return None
            if job.status == JobStatus.FAILED:
                self._cancel_events[key] = threading.Event()
            self._local_session_keys.add(key)
            return job

    def update(self, key: str, **fields) -> None:
        """Update job fields in-place; persist non-prunable jobs, discard prunable ones.

        Once a job reaches a prunable state (completed or cancelled — see
        `JobStatus.is_prunable`) it is dropped from both memory and disk
        so the store never accumulates finished work. A FAILED job is not
        prunable — it is re-persisted like any other live job so its `error`
        stays available for inspection.

        Raises:
            JobOwnershipError: fields would move a foreign, still-live
                owner's upload job into a prunable state. Checked before any
                field is applied, so a rejected update leaves the job
                untouched rather than mutating it and then refusing to
                discard the now-inconsistent result.
        """
        incoming_status = fields.get("status")
        status_enum = None
        if incoming_status is not None:
            status_enum = incoming_status if isinstance(incoming_status, JobStatus) else JobStatus(incoming_status)
        owner_live = False
        if status_enum is not None and status_enum.is_prunable:
            owner_live = self._resolve_owner_live(key)

        with self._lock:
            job = self._jobs.get(key)
            if job is None:
                return
            if status_enum is not None and status_enum.is_prunable:
                self._check_discardable(key, job, owner_live)
            for attr, value in fields.items():
                if attr == "status" and not isinstance(value, JobStatus):
                    value = JobStatus(value)
                setattr(job, attr, value)
            if job.is_prunable:
                self._discard(key, owner_live)
            else:
                self._flush(job)

    def get(self, key: str) -> Optional[TransferJobInfo]:
        """Return the job for key, or None if not found."""
        with self._lock:
            return self._jobs.get(key)

    def all(self) -> Dict[str, TransferJobInfo]:
        """Return a shallow copy of all known jobs keyed by id."""
        with self._lock:
            return dict(self._jobs)

    def pending(self) -> Dict[str, TransferJobInfo]:
        """Return jobs in `PENDING` or `RUNNING` state.

        `FAILED` is terminal, so it's excluded here even though such jobs
        are kept in the store (unlike `COMPLETED`/`CANCELLED`, which are
        pruned and would never appear anyway). Use `all` to see FAILED
        jobs too.
        """
        with self._lock:
            return {k: v for k, v in self._jobs.items() if not v.is_terminal}

    def cancel(self, key: str) -> None:
        """Cancel a live job, or discard a FAILED one outright (abandon it).

        For a `PENDING`/`RUNNING` job, signals its cancellation Event and
        transitions it to `CANCELLED` (which prunes it). For a `FAILED`
        job there is nothing running to signal, so it is discarded directly.
        No-op if the job is unknown or already prunable (completed/cancelled).
        """
        owner_live = self._resolve_owner_live(key)
        with self._lock:
            job = self._jobs.get(key)
            if job is None or job.is_prunable:
                return
            if job.status == JobStatus.FAILED:
                self._discard(key, owner_live)
                return
            event = self._cancel_events[key]  # invariant: always present for a live job
        event.set()
        self.update(key, status=JobStatus.CANCELLED)

    def _admit(self, key: str, job: TransferJobInfo) -> None:
        """Register job under key together with a fresh cancellation Event.

        The only place a key enters both `_jobs` and `_cancel_events` —
        `create` and `_load` both call this instead of writing to
        either dict directly, so the two can never drift out of sync.
        `create()` calls this under `self._lock`; `_load()` calls it
        during `__init__` before the store is visible to any other thread,
        so no lock is needed there.
        """
        self._jobs[key] = job
        self._cancel_events[key] = threading.Event()

    def _ensure_jobs_dir(self) -> None:
        """Create the jobs directory if it was removed (e.g. cache cleared mid-session)."""
        if self._jobs_dir:
            ensure_dir(self._jobs_dir)

    def _flush(self, job: TransferJobInfo) -> None:
        if not self._jobs_dir:
            return
        self._ensure_jobs_dir()
        write_job_info(self._manifest_path(job.job_id), job)

    def _load(self) -> None:
        assert self._jobs_dir
        for path in glob.glob(os.path.join(self._jobs_dir, "*.job.json")):
            job = read_job_info(path)
            if job is None or job.is_prunable:
                continue
            if job.status == JobStatus.RUNNING:
                job.status = JobStatus.PENDING  # reset RUNNING → PENDING on recovery
            self._admit(job.job_id, job)

    def _resolve_owner_live(self, key: str) -> bool:
        """Resolve whether key's current job (if any) has a live foreign owner.

        Must be called before acquiring `self._lock` — `is_owner_live` does
        file I/O, which must never run while the lock is held (both `update`
        and `cancel`'s FAILED path reach `_discard`/`_check_discardable` while
        holding it). This is an unsynchronized peek at `_jobs`, immediately
        followed by re-fetching the same key under the lock — `owner` is set
        once at creation and never mutated after, so this is racy only in the
        sense that `key` could in principle be discarded and reused for an
        unrelated job in between; per `create`'s contract a key is only ever
        reused once its previous job is terminal, so genuine concurrent reuse
        isn't a real scenario this needs to defend against.
        """
        job = self._jobs.get(key)
        return isinstance(job, UploadJobInfo) and job.owner is not None and self._is_owner_live(job.owner)

    def _check_discardable(self, key: str, job: TransferJobInfo, owner_live: bool) -> None:
        """Raise if job is a foreign, still-live owner's upload manifest.

        `owner_live` must come from `_resolve_owner_live`, called before the lock
        was acquired — see that method's docstring. Unowned jobs, this instance's
        own jobs, and jobs whose owner is no longer live are always discardable.
        """
        if isinstance(job, UploadJobInfo) and job.owner is not None and job.owner != self._owner and owner_live:
            raise JobOwnershipError(
                f"Refusing to discard job '{key}' — owned by '{job.owner}', which is still live.",
                owner=job.owner,
                job_id=key,
            )

    def _discard(self, key: str, owner_live: bool) -> None:
        """Drop a job from memory and delete its on-disk manifest.

        Deliberately leaves `_cancel_events` untouched — see
        `remove_cancel_event` for why removing it here would race a
        running job's own first `get_cancel_event` lookup.

        Args:
            owner_live: See `_check_discardable` — must come from
                `_resolve_owner_live`, resolved before the lock was acquired.

        Raises:
            JobOwnershipError: see `_check_discardable`.
        """
        job = self._jobs.get(key)
        if job is not None:
            self._check_discardable(key, job, owner_live)
        self._jobs.pop(key, None)
        self._local_session_keys.discard(key)
        self._remove(key)

    def _remove(self, key: str) -> None:
        if not self._jobs_dir:
            return
        try:
            os.remove(self._manifest_path(key))
        except OSError as exc:
            logger.debug("Could not remove job manifest for %s: %s", key, exc)

    def _manifest_path(self, key: str) -> str:
        assert self._jobs_dir
        safe = hashlib.md5(key.encode(), usedforsecurity=False).hexdigest()
        return os.path.join(self._jobs_dir, f"{safe}.job.json")
