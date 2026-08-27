"""Pluggable transfer lock for per-asset cross-process exclusivity.

The abstract `TransferLock` defines the interface; `FileTransferLock`
is the default file-based implementation using TTL heartbeat lock files.

Lock files live under `$jobs_dir/.asset_locks/`. Atomic acquisition writes
content to a temp file, then publishes it via `os.link`, which fails
atomically with `FileExistsError` if the target already exists — the lock
file is never observable in a partially-written state.

**Acquisition strategy (fail fast):**

- If the lock file does not exist → create it atomically, start heartbeat.
- If the lock file exists and is live (see `_is_live` — TTL not expired, or
  TTL expired but a same-host PID confirms the holder is still running and
  hasn't been stale for longer than `_PID_REUSE_GRACE`) → another process is
  actively transferring. Raise TransferInProgressError immediately — no waiting,
  no retry.
- If the lock file exists but is not live (TTL expired, or a same-host PID
  confirmed gone even before TTL expiry) → the previous holder crashed.
  Attempt to steal the lock atomically via `os.replace`. On success proceed;
  on failure (another process stole it first) raise TransferInProgressError.

The lock holder refreshes `valid_until` every `_HEARTBEAT_INTERVAL` seconds
via a daemon thread. On process crash the daemon dies and the TTL lapses —
but on the same host, a crash is detected immediately rather than waiting out
the TTL: `_is_live` also checks whether the recorded `pid` still exists, and a
dead PID makes a lock stealable right away. This only applies when the lock
was written on the same host (`hostname` in the lock file matches
`socket.gethostname()`) — a PID recorded on a different host can't be safely
queried (it may not even mean the same thing, and `blob_storage_path` may be a
network share), so a cross-host lock falls back to TTL-only staleness, same
as before this check existed.

That same heartbeat thread doubles as a cooperative-cancel channel:
`request_cancel_asset` drops a `<name>.cancel` marker next to a live lock
file, and the holder's heartbeat notices it on its next tick and invokes the
`on_cancel_requested` callback passed to `acquire`, if any — a way for
another process to ask this lock's holder to stop before resorting to
`force_release_asset`.
"""

import contextlib
import ctypes
import ctypes.wintypes
import json
import logging
import os
import re
import socket
import sys
import threading
import time
from abc import ABC, abstractmethod
from typing import Callable, Generator, List, Optional

from adsk.flow.local.storage_manager.exceptions import TransferInProgressError
from adsk.flow.local.storage_manager.internal.fs import ensure_dir

logger = logging.getLogger(__name__)

_LOCK_TTL: float = 30.0
_HEARTBEAT_INTERVAL: float = 10.0
_ERROR_ACCESS_DENIED = 5
# Bounds same-host PID-reuse: `_is_live` distrusts a live-looking PID match once
# `valid_until` has been stale for longer than this. Without this bound, an
# unrelated process later reusing the same PID would read as live forever —
# `valid_until` alone does not protect against that on the PID-authoritative
# branch (see `_is_live`).
_PID_REUSE_GRACE: float = _LOCK_TTL


def _pid_exists(pid: int) -> bool:
    """Best-effort, conservative liveness check for pid on this host.

    Any uncertain outcome resolves to True (alive) — this must never falsely
    declare a running process dead, since that risks reclaiming a lock still
    in active use.
    """
    if sys.platform.startswith("win"):
        return _pid_exists_windows(pid)
    return _pid_exists_posix(pid)


def _pid_exists_posix(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False  # confirmed: no such process
    except PermissionError:
        return True  # exists, just owned by a different user
    except OSError:
        return True  # uncertain — never reclaim on ambiguity
    return True


def _pid_exists_windows(pid: int) -> bool:
    """Query pid without signaling it.

    `os.kill(pid, 0)` is unsafe on Windows: CPython implements it, for any
    signal other than `CTRL_C_EVENT`/`CTRL_BREAK_EVENT`, as `OpenProcess` +
    `TerminateProcess` — a liveness probe would kill the target process.
    `OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)` only queries.

    `restype`/`argtypes` are set explicitly because ctypes otherwise assumes
    a 32-bit `c_int` return — HANDLE is pointer-sized, and on 64-bit builds
    an unmarked return risks truncating a live handle to 0. The DLL is
    loaded with `use_last_error=True` so `ctypes.get_last_error()` reliably
    reflects this call's `GetLastError()` and isn't clobbered by other
    ctypes bookkeeping in between. A failed `OpenProcess` due to
    `ERROR_ACCESS_DENIED` (a protected process, or one owned by a different
    user) means the pid exists but can't be queried, so it resolves True —
    same "uncertain means alive" rule as the POSIX `PermissionError` branch
    above.

    https://autodesk.atlassian.net/browse/PLATSDK-251 to verify with
    Windows OS enabled CI pipeline.
    """
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
    kernel32.OpenProcess.restype = ctypes.wintypes.HANDLE
    kernel32.OpenProcess.argtypes = [
        ctypes.wintypes.DWORD,
        ctypes.wintypes.BOOL,
        ctypes.wintypes.DWORD,
    ]
    kernel32.CloseHandle.argtypes = [ctypes.wintypes.HANDLE]

    process_query_limited_information = 0x1000
    ctypes.set_last_error(0)  # type: ignore
    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        return ctypes.get_last_error() == _ERROR_ACCESS_DENIED  # type: ignore
    kernel32.CloseHandle(handle)
    return True


class TransferLock(ABC):
    """Pluggable exclusive lock keyed by an opaque string.

    Call `make_key` to derive a stable key from asset/revision/operation
    coordinates, then pass it to `acquire`. This separation lets concrete
    implementations customise both the key format and the locking mechanism
    independently.

    Implementations must guarantee that at most one caller holds the lock for a
    given key at any time, across threads and across processes sharing the
    same backing store.
    """

    @abstractmethod
    def make_key(self, *args, **kwargs) -> str:
        """Build a stable lock key from coordinates specific to the implementation.

        Subclasses define their own argument signature.
        """

    @abstractmethod
    def acquire(
        self, key: str, on_cancel_requested: Optional[Callable[[], None]] = None
    ) -> contextlib.AbstractContextManager[None]:
        """Return a context manager that holds the exclusive lock for `key`.

        Args:
            key: Lock key, from `make_key`.
            on_cancel_requested: Invoked (at most once per hold) if another
                process signals `request_cancel_asset` for this key while it
                is held. Implementations without a live-signal channel may
                ignore this.

        Raises:
            TransferInProgressError: Lock is already held by a live process, or
                crash-recovery steal failed.
        """


class FileTransferLock(TransferLock):
    """File-based TTL lock backed by a `.lock` file per key.

    See module docstring for the acquisition strategy.

    Args:
        locks_dir: Directory where lock files are stored. Created if absent.
    """

    def __init__(self, locks_dir: str) -> None:
        self._locks_dir = locks_dir
        ensure_dir(locks_dir)

    def make_key(
        self,
        asset_id: str,
        revision_number: Optional[int],
        operation: str,
        version_number: Optional[int] = None,
    ) -> str:
        """Build a file-safe lock key from asset coordinates.

        Args:
            asset_id: Asset identifier (URN or short key).
            revision_number: Revision being transferred, None for uploads or when version_number is given.
            operation: "download" or "upload".
            version_number: Version being synced into `vN/`. Takes precedence over revision_number when both are
                given — downloads write into a shared, version-scoped directory (and its manifest), so the lock must be
                keyed to the version being mutated, not the revision. "revision_number" alone is still used for the
                ".displaced/rN/" fallback, which has no version to key on.

        Returns:
            str: A file-safe lock key.
        """
        safe_id = asset_id.replace(":", "_").replace("/", "_").replace("\\", "_")
        if version_number is not None:
            suffix = f"_v{version_number}"
        elif revision_number is not None:
            suffix = f"_r{revision_number}"
        else:
            suffix = ""
        return f"{safe_id}{suffix}.{operation}"

    @contextlib.contextmanager
    def acquire(
        self,
        key: str,
        on_cancel_requested: Optional[Callable[[], None]] = None,
        *,
        ttl: Optional[float] = None,
        heartbeat_interval: Optional[float] = None,
    ) -> Generator[None, None, None]:
        """See `TransferLock.acquire`.

        Args:
            ttl: Override for how long a heartbeat stays fresh before this
                lock is stale-steal-eligible. Defaults to `_LOCK_TTL`, tuned
                for per-asset transfer locks — fast stale-detection matters
                mid-transfer. A holder with a much longer life expectancy and
                no urgency to reclaim quickly (e.g. a per-instance liveness
                marker held for a process's whole lifetime) could pass a
                larger value to avoid needless filesystem churn — not
                currently exercised by any caller in this codebase.
            heartbeat_interval: Override for how often the refresh thread
                runs. Defaults to `_HEARTBEAT_INTERVAL`. Must stay under ttl
                so a live holder's marker doesn't itself lapse between
                refreshes.

        Raises:
            ValueError: heartbeat_interval is not less than ttl.
        """
        ttl = _LOCK_TTL if ttl is None else ttl
        heartbeat_interval = _HEARTBEAT_INTERVAL if heartbeat_interval is None else heartbeat_interval
        if heartbeat_interval >= ttl:
            raise ValueError(f"heartbeat_interval ({heartbeat_interval}) must be less than ttl ({ttl})")
        ensure_dir(self._locks_dir)
        lock_path = os.path.join(self._locks_dir, f"{key}.lock")
        self._acquire_lock(lock_path, key, ttl)
        stop_event = threading.Event()
        heartbeat = threading.Thread(
            target=self._heartbeat_loop,
            args=(lock_path, stop_event, on_cancel_requested, ttl, heartbeat_interval),
            daemon=True,
            name=f"lock-heartbeat-{key[-20:]}",
        )
        heartbeat.start()
        try:
            yield
        finally:
            stop_event.set()
            heartbeat.join(timeout=heartbeat_interval * 2)
            lock_paths = [lock_path, self._cancel_marker_path(lock_path)]
            for path in lock_paths:
                try:
                    os.unlink(path)
                except OSError:
                    # Already gone — acceptable (e.g. stolen after a very long pause) OR
                    # No cancel was ever requested for this hold — normal case.
                    pass

    def is_asset_locked(self, storage_key: str) -> bool:
        """Return True if a live (non-expired) lock is held for `storage_key`.
        Used to determine whether an asset's cache directory is safe to delete.

        Matches a lock file for any revision, version, or operation on this
        asset. Read-only — never creates, steals, or removes a lock file,
        unlike `acquire`. A False result does not guarantee no one
        acquires a lock for this asset immediately afterward — callers doing
        something destructive based on this should re-check immediately
        before acting, and treat the remaining gap as an accepted best-effort
        race, not a hard guarantee.
        """
        pattern = self._lock_name_pattern(storage_key)
        try:
            names = os.listdir(self._locks_dir)
        except OSError:
            return False
        for name in names:
            if not pattern.search(name):
                continue
            try:
                with open(os.path.join(self._locks_dir, name), encoding="utf-8") as fh:
                    data = json.load(fh)
            except (OSError, json.JSONDecodeError):
                continue  # unreadable/corrupt — treat as not live, consistent with _acquire_lock's steal path
            if self._is_live(data):
                return True
        return False

    def is_workspace_live(self, workspace: str) -> bool:
        """Return True if a live instance-lock is held for `workspace`."""
        key = self.make_key(asset_id=workspace, revision_number=None, operation="instance")
        lock_path = os.path.join(self._locks_dir, f"{key}.lock")
        try:
            with open(lock_path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            return False
        return self._is_live(data)

    def request_cancel_asset(self, storage_key: str) -> List[str]:
        """Signal every live lock holder for `storage_key` to voluntarily stop.

        Creates a `<name>.cancel` marker next to each matching, non-expired
        lock file. A holder's heartbeat thread (see `_heartbeat_loop`) polls
        for this marker and, if it was given an `on_cancel_requested`
        callback on `acquire`, invokes it — at most once per hold. This is a
        request, not a guarantee: a holder running code that predates this
        feature, or one that never notices in time, simply never responds,
        and the marker sits there until the lock is next acquired/released
        (both clean up their own marker).

        Idempotent — signaling an already-signaled lock is a no-op.

        Returns the lock file names signaled (not the marker paths).
        """
        pattern = self._lock_name_pattern(storage_key)
        try:
            names = os.listdir(self._locks_dir)
        except OSError:
            return []
        signaled = []
        for name in names:
            if not pattern.search(name):
                continue
            lock_path = os.path.join(self._locks_dir, name)
            try:
                with open(lock_path, encoding="utf-8") as fh:
                    data = json.load(fh)
            except (OSError, json.JSONDecodeError):
                continue  # unreadable/corrupt — nothing live to signal
            if not self._is_live(data):
                continue
            try:
                fd = os.open(self._cancel_marker_path(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
            except FileExistsError:
                pass  # Already signaled — idempotent.
            signaled.append(name)
        return signaled

    def is_cancel_requested(self, key: str) -> bool:
        """True if `request_cancel_asset` has signaled the lock held for `key`."""
        lock_path = os.path.join(self._locks_dir, f"{key}.lock")
        return os.path.exists(self._cancel_marker_path(lock_path))

    def force_release_asset(self, storage_key: str) -> List[str]:
        """Unconditionally remove every lock file for `storage_key` — live or
        expired, ours or not.

        DANGER: this does not stop whatever process holds a live lock from
        continuing to write. If another process is mid-transfer, force-releasing
        its lock and then deleting the asset directory out from under it can
        cause that process's write to fail partway (its next `os.replace()`
        will find the destination directory gone). That process's own transfer
        surfaces this as a failed job it can inspect and retry — it does not
        corrupt THIS process's state — but the other process's in-flight
        operation is not protected.

        Also removes any leftover `.cancel` marker for `storage_key` — the
        holder being force-released never runs its own release code, so
        nothing else would clean it up.

        Returns the lock file names removed.
        """
        pattern = self._lock_name_pattern(storage_key)
        try:
            names = os.listdir(self._locks_dir)
        except OSError:
            return []
        removed = []
        for name in names:
            if not pattern.search(name):
                continue
            lock_path = os.path.join(self._locks_dir, name)
            try:
                os.unlink(lock_path)
                removed.append(name)
            except OSError:
                pass
            try:
                os.unlink(self._cancel_marker_path(lock_path))
            except OSError:
                pass
        return removed

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _acquire_lock(self, lock_path: str, key: str, ttl: float) -> None:
        if self._try_create(lock_path, ttl):
            logger.debug("Acquired lock for key %s", key)
            return
        # Lock file existed at the moment of our failed create — check whether
        # it's actually still there and, if so, whether it's stale.

        data: Optional[dict] = None
        file_present = True
        try:
            with open(lock_path, encoding="utf-8") as fh:
                data = json.load(fh)
        except FileNotFoundError:
            file_present = False
        except (OSError, json.JSONDecodeError):
            pass  # Present but unreadable/corrupt — treat as stale below.

        if data is not None and self._is_live(data):
            # Lock held by a live process — fail immediately.
            holder_pid = data.get("pid", "unknown")
            raise TransferInProgressError(
                f"A transfer is already in progress for lock '{key}' "
                f"(held by PID {holder_pid}). Cancel the existing transfer and retry.",
            )

        if not file_present:
            # The holder released it between our failed create and this check
            # (common under heavy contention). Retry the exclusive create —
            # unlike _try_steal's os.replace, this can't let multiple callers
            # "win" at once.
            if self._try_create(lock_path, ttl):
                logger.debug("Acquired lock for key %s (released mid-check)", key)
                return
            raise TransferInProgressError(
                f"Could not acquire lock for '{key}' — claimed by another caller. Retry the operation.",
            )

        # Lock file is present but stale (holder crashed). Attempt atomic steal.
        logger.info("Stale lock detected for key %s; attempting recovery", key)
        if self._try_steal(lock_path, ttl):
            logger.info("Recovered stale lock for key %s", key)
            return

        raise TransferInProgressError(
            f"Could not recover a stale lock for '{key}' " f"— another process claimed it first. Retry the operation.",
        )

    def _try_create(self, lock_path: str, ttl: float) -> bool:
        """Atomically create the lock file, or return False if it already exists.

        Writes content to a temp file first, then publishes it via `os.link`
        (fails atomically with FileExistsError if the target exists). Unlike
        `os.open(O_CREAT | O_EXCL)` followed by a separate `os.write`, this
        never leaves a window where the lock file exists but is still empty —
        a concurrent reader could otherwise see the empty file, fail to parse
        it as JSON, and mistake a live lock for a corrupt/stale one.
        """
        tmp = lock_path + f".{os.getpid()}.{threading.get_ident()}.create.tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(self._lock_content(ttl))
            os.link(tmp, lock_path)
            return True
        except FileExistsError:
            return False
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    def _try_steal(self, lock_path: str, ttl: float) -> bool:
        """Attempt to atomically replace an expired lock. Returns True on success.

        Uses write-to-temp + `os.replace` (atomic rename). There is a narrow
        TOCTOU window where two processes simultaneously observe expiry and both
        call this; `os.replace` is atomic, so the last writer wins. For downloads,
        both proceeding is safe (same bytes written, blob file written atomically).
        For uploads the simultaneous-steal scenario is extremely unlikely.
        """
        tmp = lock_path + f".{os.getpid()}.tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(self._lock_content(ttl))
            os.replace(tmp, lock_path)
            return True
        except OSError:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            return False

    def _refresh_lock(self, lock_path: str, ttl: float) -> None:
        """Atomically refresh valid_until in the lock file."""
        tmp = lock_path + f".{os.getpid()}.refresh"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(self._lock_content(ttl))
            os.replace(tmp, lock_path)
        except OSError as exc:
            logger.warning("Could not refresh lock %s: %s", lock_path, exc)

    @staticmethod
    def _lock_content(ttl: float) -> str:
        return json.dumps(
            {
                "pid": os.getpid(),
                "hostname": socket.gethostname(),
                "valid_until": time.time() + ttl,
            }
        )

    def _heartbeat_loop(
        self,
        lock_path: str,
        stop_event: threading.Event,
        on_cancel_requested: Optional[Callable[[], None]],
        ttl: float,
        heartbeat_interval: float,
    ) -> None:
        cancel_fired = False
        while not stop_event.wait(heartbeat_interval):
            try:
                with open(lock_path, encoding="utf-8") as fh:
                    data = json.load(fh)
                if data.get("pid") != os.getpid():
                    logger.warning(
                        "Lock %s was taken over by PID %s; stopping heartbeat",
                        lock_path,
                        data.get("pid"),
                    )
                    return
            except (OSError, json.JSONDecodeError):
                return  # Lock gone or unreadable — stop silently
            self._refresh_lock(lock_path, ttl)
            if (
                not cancel_fired
                and on_cancel_requested is not None
                and os.path.exists(self._cancel_marker_path(lock_path))
            ):
                cancel_fired = True
                try:
                    on_cancel_requested()
                except Exception:  # pylint: disable=broad-except
                    # A misbehaving callback must not take down the heartbeat
                    # thread — that would strand the lock without renewal.
                    logger.exception("on_cancel_requested callback raised for lock %s", lock_path)

    @staticmethod
    def _cancel_marker_path(lock_path: str) -> str:
        return lock_path + ".cancel"

    @staticmethod
    def _lock_name_pattern(storage_key: str) -> re.Pattern[str]:
        """Regex matching any lock filename for storage_key, any revision/version/operation.

        make_key() always produces `{safe_id}[_v{n}|_r{n}].{operation}`, and
        safe_id always ends with storage_key (see storage.storage_key() — the
        URN's last, separator-free segment). Anchoring on `(^|_)` before the
        key and requiring the `_v{n}`/`_r{n}`/operation suffix shape after it
        avoids matching a different asset whose key happens to be a substring.
        """
        return re.compile(r"(^|_)" + re.escape(storage_key) + r"(_v\d+|_r\d+)?\.(download|upload)\.lock$")

    @staticmethod
    def _is_live(data: dict) -> bool:
        """True if lock-file JSON data represents a still-live holder.

        When the recorded holder's PID can be checked (same host, `pid`
        present), that check wins over `valid_until` in the "confirmed gone"
        direction, and is grace-bounded in the "confirmed present" direction:

        - Confirmed gone → dead, even if `valid_until` is still comfortably
          in the future. This is what lets a same-host relaunch steal
          immediately after a crash instead of waiting out the TTL —
          `valid_until` can be up to `_HEARTBEAT_INTERVAL` seconds stale at
          the moment of a crash, so trusting it alone would delay recovery.
        - Confirmed present → live, provided `valid_until` hasn't been stale
          for more than `_PID_REUSE_GRACE`. This still tolerates the holder
          process being merely paused (a debugger breakpoint, a suspended VM)
          for up to that grace window without losing the lock. Beyond it, a
          PID match alone is no longer trusted: the OS may have reassigned
          that exact PID to an unrelated process well after the real holder
          crashed, and an unbounded PID-authoritative check would then read
          that lock as live forever.

        The PID check is skipped — falling back to TTL-only, exactly as
        before this check existed — whenever it can't be trusted: a different
        host (a PID from another machine is meaningless, and
        `blob_storage_path` may be a network share) or no `pid` recorded (a
        malformed or hand-edited lock file — every lock file this SDK writes
        includes `pid`, so this is not an expected shape, just a guard
        against a corrupt one — can't disprove liveness, so don't guess).
        """
        pid = data.get("pid")
        valid_until = data.get("valid_until", 0)
        if data.get("hostname") == socket.gethostname() and pid is not None:
            return _pid_exists(pid) and valid_until >= time.time() - _PID_REUSE_GRACE
        return bool(valid_until >= time.time())
