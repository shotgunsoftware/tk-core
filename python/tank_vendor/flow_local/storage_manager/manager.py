import contextlib
import contextvars
import dataclasses
import functools
import logging
import os
import shutil
import stat
import threading
import time
import uuid
from collections import Counter
from concurrent.futures import Future, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, cast

from adsk.flow.data import GQLClient
from adsk.flow.data.base.model_g import Asset, ComponentDataInput
from adsk.flow.local.storage_manager.component import BinaryComponentSpec, ComponentSpec, GenericComponentSpec
from adsk.flow.local.storage_manager.config import Config
from adsk.flow.local.storage_manager.exceptions import (
    BinaryComponentDropError,
    ConflictError,
    DraftExistsError,
    JobOwnershipError,
    NoChangeError,
    StorageError,
    StorageManagerError,
    TransferCancelledError,
    TransferError,
    TransferInProgressError,
    UploadError,
)
from adsk.flow.local.storage_manager.internal.context import with_active_config
from adsk.flow.local.storage_manager.internal.discovery import (
    blob_path_from_component_item,
    extract_blobs_from_revision,
    group_blobs_by_version,
    parse_component_data,
)
from adsk.flow.local.storage_manager.internal.draft import discard_asset_draft as _discard_asset_draft
from adsk.flow.local.storage_manager.internal.draft import (
    draft_dir,
    read_draft_info,
    rename_draft_folder,
    sandbox_draft_dir,
    write_draft_info,
)
from adsk.flow.local.storage_manager.internal.fs import (
    HASH_ALGORITHM,
    cleanpath,
    copy_file,
    copy_file_with_hash,
    ensure_dir,
    hash_file,
    is_non_empty_dir,
    is_zip_path,
    path_is_within,
    unzip_into,
    zip_entry_paths,
)
from adsk.flow.local.storage_manager.internal.jobs import JobStore, make_job_key
from adsk.flow.local.storage_manager.internal.lock import FileTransferLock
from adsk.flow.local.storage_manager.internal.remote import (
    DownloadedBlob,
    create_asset,
    download_blob,
    fetch_asset,
    fetch_direct_uses,
    fetch_revision,
    fetch_revision_by_id,
    fetch_revision_for_version,
    resolve_dependent_blobs_from_revision,
    update_asset,
    upload_blob,
)
from adsk.flow.local.storage_manager.internal.storage import (
    ManifestEntry,
    VersionManifest,
    blob_cache_root,
    read_version_manifest,
    storage_asset_dir_for,
    storage_displaced_revision_dir,
    storage_key,
    storage_version_dir,
    write_version_manifest,
)
from adsk.flow.local.storage_manager.internal.urn import compose_revision_urn, project_id_from_revision_urn
from adsk.flow.local.storage_manager.models import (
    AsyncTask,
    BlobRef,
    CheckoutDraftInfo,
    ClearCacheResult,
    DownloadJobInfo,
    JobKind,
    JobStatus,
    NewDraftInfo,
    ProgressCallback,
    TransferJobInfo,
    TransferProgress,
    UploadJobInfo,
)

logger = logging.getLogger(__name__)

_FORCE_JOB_STOP_TIMEOUT = 60.0  # seconds to wait for a cancelled local job's thread to exit
_COOPERATIVE_CANCEL_POLL_INTERVAL = 1.0  # seconds between is_asset_locked() polls after signaling a foreign lock
_COOPERATIVE_CANCEL_TIMEOUT = 20.0  # seconds to wait for a foreign lock to clear before force-breaking it;
# covers one FileTransferLock heartbeat tick (10s) plus margin for the holder to unwind and release.
_MAX_RETRIES = 3
_PROGRESS_FLUSH_INTERVAL = 2.0  # seconds between JobStore progress-bytes flushes
_RETRY_BACKOFF_BASE = 1.0  # seconds; doubles each attempt
_CANCEL_ALL_JOBS_MAX_PASSES = 100  # backstop for cancel_all_jobs()'s re-snapshot loop; see its docstring


class StorageManager:
    """Fully managed file operations on top of a class `adsk.flow.data.GQLClient`

    Wraps asset create/update, binary upload/download, and a local draft
    (checkout → edit → publish) workflow. All local state — the read-only blob
    cache, editable sandbox drafts, transfer-job manifests, and upload staging —
    lives under the paths given by class `Config`.

    Transfers run in a background class `concurrent.futures.ThreadPoolExecutor`
    and are surfaced as class `AsyncTask` objects so the caller's thread is never
    blocked by I/O.

    Multiple `StorageManager` instances may share the same local storage folders
    safely — cross-process locking prevents concurrent writes from corrupting the
    blob cache or the job store. Each concurrently live instance must be given
    a distinct `Config.workspace` — this instance's identity for upload-ownership
    and crash-recovery attribution (see `get_pending_jobs`, `resume_job`,
    `cancel_all_jobs`). Two live instances sharing a `workspace` fail
    construction with `TransferInProgressError`.

    Call `clear_cache` to reclaim local disk space by deleting the blob
    cache. A DCC session holding an open reference into a `v{n}/` directory
    removed by `clear_cache()` must re-fetch it (via `download_asset`,
    `checkout_draft`, or `download_blob`) — see that method's docstring for
    the exact behavior and its `force` option.

    **Workflow: publish a new asset**::

        draft = sm.create_draft(name="MyAsset", parent_id=project_id)
        shutil.copy(my_file, draft.draft_path)
        asset = sm.publish_draft(
            draft.draft_id,
            binary_components=[BinaryComponentSpec(name="source", files=[my_file])],
        ).get()

    **Workflow: checkout → edit → publish a new revision**::

        task = sm.checkout_draft(asset_id, project_id)
        info = task.metadata          # CheckoutDraftInfo — available immediately
        draft = task.get()            # blocks until blobs are on disk
        # edit files in draft.draft_path ...
        asset = sm.publish_draft(
            draft.draft_id,
            binary_components=[BinaryComponentSpec(name="source", files=[...])],
        ).get()

    **Workflow: read-only download**::

        blob_paths = sm.download_asset(asset_id, project_id).get()
        # {0: "/cache/path/file.png", 1: "/cache/path/other.png", ...}

    **Workflow: single-blob download**::

        task = sm.download_blob(revision_id, blob_urn)
        blob = task.metadata          # BlobRef — available immediately
        path = task.get()             # blocks until the blob is on disk

    Example::

        from adsk.flow.data import GQLClient
        from adsk.flow.local.storage_manager import Config, StorageManager

        sm = StorageManager(
            client=GQLClient(...),
            config=Config(blob_storage_path="/data/blobs", sandbox_path="/data/sandbox", workspace="my_dcc_app"),
        )

    Holds a lock file and a background executor for its lifetime — call
    `close()` explicitly on shutdown (e.g. a DCC's uninitialize callback).
    Call `cancel_all_jobs()` first if in-flight uploads should be abandoned
    rather than resumed on next launch::

        sm = StorageManager(client=GQLClient(...), config=config)
        sm.publish_draft(draft.draft_id, binary_components=[...]).get()
        sm.close()
    """

    def __init__(
        self,
        client: GQLClient,
        config: Config,
    ):
        """Initialise the storage manager.

        Args:
            client: An authenticated `adsk.flow.data.GQLClient`. The SDK
                never creates or refreshes tokens — authentication is the caller's
                responsibility.
            config: Storage paths and transfer-tuning parameters. See
                `adsk.flow.local.storage_manager.Config`.
        """
        self._client = client
        self._config = config
        jobs_dir = config.jobs_dir or os.path.join(config.blob_storage_path, ".jobs")
        ensure_dir(jobs_dir)
        locks_dir = os.path.join(jobs_dir, ".asset_locks")
        ensure_dir(locks_dir)
        self._transfer_lock = FileTransferLock(locks_dir=locks_dir)
        self._owner = config.workspace
        # Held for this process's lifetime (released in close()), not a bounded
        # `with` block — proves this instance is the live claimant of `workspace`
        # for as long as it runs. A live conflict (two instances given the same
        # workspace) raises TransferInProgressError out of __init__: pre-release,
        # so failing loudly now is better than a silently-inert ownership feature.
        instance_key = self._transfer_lock.make_key(asset_id=self._owner, revision_number=None, operation="instance")
        self._instance_lock_cm: Optional[contextlib.AbstractContextManager] = None
        cm = self._transfer_lock.acquire(instance_key)
        cm.__enter__()  # raises TransferInProgressError on a live conflict; cm stays unset above if so
        self._instance_lock_cm = cm
        self._job_store = JobStore(
            jobs_dir=jobs_dir,
            owner=self._owner,
            is_owner_live=self._transfer_lock.is_workspace_live,
        )
        self._upload_staging_path = config.upload_staging_path or os.path.join(config.blob_storage_path, ".staging")
        self._executor = ThreadPoolExecutor(max_workers=config.max_transfer_threads)
        # Lets clear_cache(force=True) block on a specific download job's actual
        # background thread (via its Future) rather than just its cancel flag —
        # cancel_job() only signals, it doesn't wait for the thread to exit. Also
        # backs close(timeout=...)'s bounded wait, which snapshots every value in
        # this dict; publish_draft registers under a synthetic (non-job-id) key
        # since its upload job ids aren't known until the mutation returns.
        self._active_futures: Dict[str, Future] = {}
        self._active_futures_lock = threading.Lock()
        self._prune_stale_upload_staging()

    def close(self, *, timeout: Optional[float] = None) -> bool:
        """Release this instance's held resources: the background executor and its instance-lock.

        Call this on shutdown (e.g. a DCC's uninitialize callback). Three modes:

        - Graceful (`timeout=None`, default): blocks until every transfer this
          instance started has actually stopped, then releases the
          instance-lock. Call `cancel_all_jobs()` first so in-flight transfers
          unwind quickly (bounded by one chunk/part) instead of blocking until
          natural completion.
        - Bounded (`timeout=N`, `N > 0`): waits up to `N` seconds for every
          transfer this instance started to stop. Returns whether everything
          actually drained in time. The instance-lock is only released if it
          did — never while a transfer might still be writing — so a caller
          that gets `False` back can retry with `close(timeout=...)` again,
          or escalate to `timeout=0`. Build a "still uploading… [Force Quit]"
          prompt around this.
        - Force (`timeout=0`): returns immediately, without waiting for any
          still-running transfer, and releases the instance-lock unconditionally.
          A relaunching instance sharing this workspace may then reset that
          transfer's job to PENDING and prune its staged bytes out from under
          the still-writing thread — the same exposure as an actual crash, now
          an explicit, caller-owned choice instead of an accidental race.

        Returns:
            True if every transfer this instance started had stopped by the
            time this call returned; False otherwise (only possible with a
            bounded `timeout`).

        Raises:
            ValueError: `timeout` is negative. `concurrent.futures.wait`
                silently treats a negative timeout as an immediate check
                rather than an error, which would otherwise leave `drained`
                False and the instance-lock stuck held with no way to tell
                this apart from a real bounded-wait failure.

        Idempotent. Safe to call even if `__init__` raised partway through
        (e.g. a live workspace conflict) — only tears down what was actually
        set up.
        """
        if timeout is not None and timeout < 0:
            raise ValueError(f"timeout must be >= 0 or None, got {timeout}")
        executor = getattr(self, "_executor", None)
        drained = True
        if executor is not None:
            if timeout is None:
                executor.shutdown(wait=True)
            else:
                futures_lock = getattr(self, "_active_futures_lock", None)
                futures = set()
                if futures_lock is not None:
                    with futures_lock:
                        futures = set(self._active_futures.values())
                # cancel_futures only drops not-yet-started queued work; a
                # future already running is never affected by it.
                executor.shutdown(wait=False, cancel_futures=True)
                _, not_done = wait(futures, timeout=timeout)
                drained = not not_done
        if drained or timeout == 0:
            cm = getattr(self, "_instance_lock_cm", None)
            if cm is not None:
                cm.__exit__(None, None, None)
                self._instance_lock_cm = None
        return drained

    def __del__(self) -> None:
        # Garbage-collection-time teardown must never block interpreter
        # shutdown — this reopens close(timeout=0)'s abandon race by design;
        # relying on GC instead of an explicit close() is not a graceful quit.
        self.close(timeout=0)

    @with_active_config
    def create_draft(
        self,
        name: str,
        parent_id: str,
        description: str = "",
        type_ids: Optional[List[str]] = None,
        source_paths: Optional[List[str]] = None,
    ) -> NewDraftInfo:
        """Create a sandbox draft for a brand-new (unpublished) asset.

        Copies any source_paths into the draft folder and writes a NewDraftInfo
        sidecar; nothing is created on the server until `publish_draft()`. Both the
        folder creation and file copy happen synchronously — the returned
        `adsk.flow.local.storage_manager.NewDraftInfo` is ready to use immediately.

        Args:
            name: Name for the eventual asset.
            parent_id: Parent folder/project id the asset will be published into.
            description: Optional description carried through to first publish.
            type_ids: Schema type ids to attach as components on publish.
            source_paths: Files copied into the draft folder synchronously before
                this method returns.  Useful for seeding a draft from existing
                local files without a manual `shutil.copy` step.

        Returns:
            The `NewDraftInfo` describing the new draft (incl. draft_path).
        """
        new_id = f"new_{uuid.uuid4().hex}"
        draft_path = draft_dir(new_id)
        ensure_dir(draft_path)

        for src in source_paths or []:
            copy_file(src, cleanpath(draft_path, os.path.basename(src)))

        draft_info = NewDraftInfo(
            draft_id=new_id,
            name=name,
            parent_id=parent_id,
            description=description,
            type_ids=list(type_ids or []),
            draft_path=draft_path,
        )
        write_draft_info(draft_info)
        logger.info("Created draft %s for new asset %r (parent %s)", new_id, name, parent_id)
        return draft_info

    @with_active_config
    def publish_draft(
        self,
        draft_id: str,
        *,
        binary_components: Optional[List[BinaryComponentSpec]] = None,
        extra_components: Optional[List[ComponentSpec]] = None,
        uses: Optional[List[str]] = None,
        on_progress: Optional[ProgressCallback] = None,
        bump_version: bool = False,
        force: bool = False,
    ) -> AsyncTask[Asset]:
        """Publish a sandbox draft as a new asset or a new revision of one.

        For a draft created by `create_draft` this creates the asset on first
        publish (and renames the draft folder to the asset's permanent key). For a
        draft from `checkout_draft` this publishes a new revision, raising
        ConflictError if the asset advanced on the server since checkout.

        By default, only the revision number is incremented. Pass `bump_version=True`
        to also create a new numbered version — use this for deliberate milestones
        rather than routine saves.

        The publish — including the server mutation and all blob uploads — runs in a
        background thread. Call `AsyncTask.get` to block until the
        `Asset` is ready, or to re-raise any error from the thread.

        Args:
            draft_id: Handle returned by `create_draft` / `checkout_draft`.
            binary_components: Components to upload (REPLACE semantics — list all to
                keep; omitting one that exists on the current revision raises
                BinaryComponentDropError unless `force=True`).
            extra_components: Non-binary components to attach.
            uses: Dependency version ids.
            on_progress: Progress callback (called from the worker thread).
            bump_version: When True, also create a new numbered version (default False).
            force: Allow `binary_components` to drop an existing binary component
                instead of raising (default False).

        Returns:
            An `AsyncTask`; call `AsyncTask.get` to block until the server mutation and
            all uploads complete and to receive the published `Asset`. The `job_ids`
            list on the returned task is empty — upload jobs are created inside the
            background thread after the server mutation returns.

        Raises:
            StorageManagerError: The draft is missing or malformed (raised synchronously).
            ConflictError: A new revision was published since checkout (raised on `AsyncTask.get`).
            BinaryComponentDropError: `binary_components` omits a binary component present
                on the current revision and `force` is False (raised on `AsyncTask.get`).
            TransferInProgressError: An upload is already in progress for this asset
                (raised on `AsyncTask.get`).
        """
        # Validate draft exists synchronously so callers get an immediate error on bad input.
        if not os.path.exists(draft_dir(draft_id)):
            raise StorageManagerError(f"No draft found with id '{draft_id}'.")

        # Capture the current context (including the ContextVar set by @with_active_config)
        # so the worker thread runs with the same active Config. ctx.run(fn) executes fn
        # inside the captured context — this is the documented Python 3.7+ propagation pattern.
        ctx = contextvars.copy_context()

        def _publish() -> Asset:
            return self._do_publish_draft(
                draft_id,
                binary_components=binary_components,
                extra_components=extra_components,
                uses=uses,
                on_progress=on_progress,
                bump_version=bump_version,
                force=force,
            )

        logger.info("Submitting publish of draft %s to background thread", draft_id)
        future: Future[Asset] = self._executor.submit(ctx.run, _publish)
        # No upload job ids exist yet (created inside the thread after the
        # mutation returns), so track under a synthetic key purely so
        # close(timeout=...) waits for this publish too.
        self._track_future([f"publish:{draft_id}:{uuid.uuid4().hex[:8]}"], future)
        return AsyncTask(job_ids=[], future=future)

    def _do_publish_draft(
        self,
        draft_id: str,
        *,
        binary_components: Optional[List[BinaryComponentSpec]] = None,
        extra_components: Optional[List[ComponentSpec]] = None,
        uses: Optional[List[str]] = None,
        on_progress: Optional[ProgressCallback] = None,
        bump_version: bool = False,
        force: bool = False,
    ) -> Asset:
        """Execute the publish synchronously. Called from the background thread."""
        logger.info("Publishing draft %s", draft_id)

        # Acquire the per-draft lock before any mutation to prevent concurrent
        # publish for the same draft from creating an orphaned revision.
        lock_key = self._transfer_lock.make_key(asset_id=draft_id, revision_number=None, operation="upload")
        with self._transfer_lock.acquire(lock_key):
            draft_path = draft_dir(draft_id)
            draft_info = read_draft_info(draft_path)
            extra_comps = list(extra_components or [])
            current_asset: Optional[Asset] = None

            # draft-type setup: extend extra_comps and validate pre-conditions.
            if isinstance(draft_info, NewDraftInfo):
                # For new assets, convert type_ids into generic components.
                for i, type_id in enumerate(draft_info.type_ids):
                    extra_comps.append(GenericComponentSpec(name=f"Type {i}", type_id=type_id))
            else:  # CheckoutDraftInfo
                # Query current asset to get latest state for conflict check and type preservation.
                current_asset = fetch_asset(self._client, draft_info.asset_id)

                # Conflict = the asset has a newer revision on the server than the one checked out.
                # This catches both routine revisions (UPDATES_LATEST) and version bumps (CREATE_NEW),
                # since every publish always increments the revision number.
                if current_asset.revision_number > draft_info.latest_revision_number:
                    logger.warning(
                        "Publish conflict for asset %s: checked out at revision %s, server now at revision %s",
                        draft_info.asset_id,
                        draft_info.latest_revision_number,
                        current_asset.revision_number,
                    )
                    raise ConflictError(
                        f"Asset '{draft_info.asset_id}' has been updated since checkout. "
                        f"Re-checkout to fetch the latest revision and retry.",
                        asset_id=draft_info.asset_id,
                    )

                # Preserve existing type components — since publish uses ListAction.REPLACE,
                # any component not re-sent will be wiped. Skip any type_ids the caller
                # already supplied to avoid duplicate name/type_id conflicts.
                caller_type_ids = {getattr(c, "type_id", None) for c in extra_comps} - {None}
                name_offset = len(extra_comps)
                for type_id in current_asset.asset_type_ids or []:
                    if type_id not in caller_type_ids:
                        extra_comps.append(GenericComponentSpec(name=f"Type {name_offset}", type_id=type_id))
                        name_offset += 1

            # build and validate components (common to both draft types).
            # Defensive copies so caller's lists are never mutated.
            bin_comps: List[BinaryComponentSpec] = list(binary_components or [])
            all_comps: List[ComponentSpec] = bin_comps + extra_comps
            comps = [comp.create() for comp in all_comps]
            self._validate_asset_components(bin_comps, all_comps)

            # Runs before the no-op check below, but never masks a legitimate no-op: dropping a
            # binary component always removes its name from `comps`, so _is_no_op_publish's own
            # name-set comparison against current_asset.components would already return False.
            if isinstance(draft_info, CheckoutDraftInfo) and current_asset is not None and not force:
                dropped = sorted(self._asset_binary_component_names(current_asset) - {bc.name for bc in bin_comps})
                if dropped:
                    raise BinaryComponentDropError(
                        f"publish_draft would drop existing binary component(s) {', '.join(dropped)} from asset "
                        f"'{draft_info.asset_id}' (binary_components uses REPLACE semantics). "
                        "Re-list them to keep, or pass force=True to drop intentionally.",
                        asset_id=draft_info.asset_id,
                        dropped=dropped,
                    )

            if (
                isinstance(draft_info, CheckoutDraftInfo)
                and current_asset is not None
                and self._is_no_op_publish(draft_info, current_asset, bin_comps, comps, uses)
            ):
                raise NoChangeError(
                    f"Asset '{draft_info.asset_id}' is unchanged since checkout; nothing to publish.",
                    asset_id=draft_info.asset_id,
                    revision_number=current_asset.revision_number,
                )

            # server mutation: create or update the asset.
            if isinstance(draft_info, NewDraftInfo):
                if draft_info.pending_asset_id:
                    # A previous attempt created the asset on the server but crashed before
                    # blobs were uploaded. Reuse the existing asset id to avoid a duplicate
                    # top-level asset; update_asset() creates a new revision instead.
                    logger.info(
                        "Resuming publish: reusing pre-created asset %s for draft %s",
                        draft_info.pending_asset_id,
                        draft_id,
                    )
                    asset = update_asset(
                        self._client,
                        draft_info.pending_asset_id,
                        comps,
                        uses,
                        description=draft_info.description,
                        bump_version=bump_version,
                    )
                else:
                    logger.info("Creating new asset %r under parent %s", draft_info.name, draft_info.parent_id)
                    asset = create_asset(
                        self._client, draft_info.name, draft_info.parent_id, comps, uses, draft_info.description
                    )
                    # Persist the asset id immediately so a retry reuses it instead of creating a duplicate.
                    write_draft_info(dataclasses.replace(draft_info, pending_asset_id=asset.id))
            else:  # CheckoutDraftInfo
                logger.info("Publishing new revision of asset %s", draft_info.asset_id)
                asset = update_asset(
                    self._client,
                    draft_info.asset_id,
                    comps,
                    uses,
                    bump_version=bump_version,
                )

            # post-mutation (common to both draft types).
            logger.info(
                "Published asset %s (version %s, revision %s)",
                asset.id,
                asset.version_number,
                asset.revision_number,
            )

            if bin_comps:
                self._upload_blobs(bin_comps, asset, on_progress)

            # Rename the draft folder on first publish to replace the temporary draft id
            # with the asset's permanent storage key.
            if isinstance(draft_info, NewDraftInfo):
                new_draft_id = storage_key(asset.id)
                rename_draft_folder(draft_id, new_draft_id)
                draft_id = new_draft_id

            # Update draft info file to reflect the just-published state.
            draft_path = draft_dir(draft_id)
            write_draft_info(
                CheckoutDraftInfo(
                    draft_id=draft_id,
                    name=asset.name,
                    asset_id=asset.id,
                    revision_number=asset.revision_number,
                    version_number=asset.version_number,
                    latest_revision_number=asset.revision_number,
                    latest_version_number=asset.version_number,
                    draft_path=draft_path,
                ),
            )

            return asset

    @with_active_config
    def checkout_draft(
        self,
        asset_id: str,
        project_id: str,
        version_number: Optional[int] = None,
        *,
        discard_existing_draft: bool = False,
        on_progress: Optional[ProgressCallback] = None,
    ) -> AsyncTask[CheckoutDraftInfo]:
        """Download an asset version into an editable sandbox draft.

        The main asset's files and all of its `uses` dependencies are fetched
        into the read-only blob cache. Only the main asset's files are copied
        into the sandbox draft folder (dependencies stay in the cache). Blobs are
        written to their exact encoded paths, recreating any subfolders.

        Always checks out the latest revision of the requested version so the
        local copy is never behind the server's current state for that version.

        Args:
            asset_id: Asset to check out.
            project_id: MEDM project the asset's blob download URLs resolve against.
            version_number: Specific version to check out, or None for the latest.
            discard_existing_draft: Overwrite an existing draft (unsaved edits lost).
            on_progress: Transfer progress callback.

        Returns:
            An `AsyncTask` whose result is the `CheckoutDraftInfo`.
            The `AsyncTask.metadata` property is populated immediately
            (metadata resolved synchronously before the transfer starts); call
            `AsyncTask.get` to block until the files are on disk.

        Raises:
            DraftExistsError: A draft exists and `discard_existing_draft` is False.
            StorageManagerError: The version is not found.
        """
        # --- Metadata phase (synchronous on calling thread) ---
        draft_path = sandbox_draft_dir(asset_id)
        if is_non_empty_dir(draft_path):
            if not discard_existing_draft:
                raise DraftExistsError(
                    f"Draft folder already exists for asset '{asset_id}' at {draft_path}. "
                    f"To avoid overwriting existing work, the checkout operation was cancelled. "
                    f"Delete or move the existing draft folder and retry, or set "
                    f"discard_existing_draft=True to automatically remove it.",
                )
            _discard_asset_draft(asset_id)

        logger.info("Checking out asset %s (version %s)", asset_id, version_number if version_number else "latest")

        if version_number is not None:
            asset_revision = fetch_revision_for_version(self._client, asset_id, version_number)
        else:
            asset_revision = fetch_revision(self._client, asset_id)
        if asset_revision is None:
            raise StorageManagerError(
                f"Version {version_number} not found for asset '{asset_id}'."
                if version_number is not None
                else f"No revision found for asset '{asset_id}'."
            )
        if asset_revision.version_number is None:
            raise StorageManagerError(
                f"Revision {asset_revision.revision_number} of asset '{asset_id}' has no version_number "
                f"(a displaced historical revision) — checkout_draft requires a live version pointer."
            )
        version_number = cast(int, asset_revision.version_number)

        revision_blobs = extract_blobs_from_revision(asset_revision)
        dep_blobs = resolve_dependent_blobs_from_revision(self._client, asset_revision)

        ensure_dir(draft_path)
        asset = fetch_asset(self._client, asset_id)

        # Persist the dependency blobs (with their version_number) so the
        # in-progress guard in get_dependency_paths() can watch their version
        # dirs for pending downloads too, not just the root asset's own.
        info = CheckoutDraftInfo(
            draft_id=storage_key(asset_id),
            name=asset.name,
            asset_id=asset_id,
            version_number=version_number,
            revision_number=cast(int, asset_revision.revision_number),
            latest_version_number=cast(int, asset.version_number),
            latest_revision_number=cast(int, asset.revision_number),
            draft_path=draft_path,
            dependencies=list(dep_blobs),
        )
        write_draft_info(info)

        # Pre-register jobs so the caller can poll them before the transfer starts.
        job_keys: List[str] = []
        for (group_asset_id, group_version_number), group_blobs in group_blobs_by_version(
            dep_blobs + revision_blobs
        ).items():
            version_dir = storage_version_dir(group_asset_id, group_version_number)
            manifest = read_version_manifest(version_dir)
            entries = manifest.binaries if manifest else {}
            for blob in group_blobs:
                dest = cleanpath(version_dir, blob.blob_path)
                if self._is_manifest_entry_current(entries.get(blob.blob_path), blob, dest):
                    continue
                job_key = make_job_key(JobKind.DOWNLOAD, blob.urn)
                existing = self._job_store.get(job_key)
                if existing is None or existing.is_prunable:
                    self._job_store.create(
                        job_key,
                        DownloadJobInfo(job_id=job_key, urn=blob.urn, file_path=dest, project_id=project_id),
                    )
                job_keys.append(job_key)

        # --- Transfer phase (background thread) ---
        # Capture the current context (including the ContextVar set by @with_active_config)
        # so the worker thread runs with the same active Config. ctx.run(fn) executes fn
        # inside the captured context — this is the documented Python 3.7+ propagation pattern.
        ctx = contextvars.copy_context()

        def _transfer() -> CheckoutDraftInfo:
            own_group_key = (asset_id, version_number)
            dep_groups = group_blobs_by_version(dep_blobs)

            # Dependencies are cached only — never copied into the sandbox. Each
            # dependency (asset, version) group takes its own lock rather than
            # holding every dependency's lock for the whole call, so an
            # already-current dependency only blocks concurrent writers for as
            # long as its manifest read takes.
            for (dep_asset_id, dep_version_number), group in dep_groups.items():
                if (dep_asset_id, dep_version_number) == own_group_key:
                    continue  # covered below, under the root lock (locks aren't reentrant)
                with self._transfer_lock.acquire(
                    self._transfer_lock.make_key(
                        asset_id=dep_asset_id,
                        revision_number=None,
                        operation="download",
                        version_number=dep_version_number,
                    ),
                    on_cancel_requested=functools.partial(self._on_cancel_requested_for, dep_asset_id),
                ):
                    self._sync_blobs_into_version_dir(dep_asset_id, dep_version_number, group, project_id, on_progress)

            with self._transfer_lock.acquire(
                self._transfer_lock.make_key(
                    asset_id=asset_id, revision_number=None, operation="download", version_number=version_number
                ),
                on_cancel_requested=functools.partial(self._on_cancel_requested_for, asset_id),
            ):
                # A dependency on this same (asset, version) — e.g. an asset using an
                # older version of itself — is folded into the root lock instead of
                # being skipped outright.
                if own_group_key in dep_groups:
                    self._sync_blobs_into_version_dir(
                        asset_id, version_number, dep_groups[own_group_key], project_id, on_progress
                    )

                # The main asset's blobs are synced into vN, then copied into the
                # sandbox draft, preserving any subfolder structure encoded in the
                # blob path (or, for an already-expanded zip, the frame's path
                # relative to vN).
                version_dir = storage_version_dir(asset_id, version_number)
                synced = self._sync_blobs_into_version_dir(
                    asset_id, version_number, revision_blobs, project_id, on_progress
                )
                for blob in revision_blobs:
                    synced_blob = synced[blob.blob_path]
                    if blob.is_zipped:
                        for frame_path in synced_blob.files:
                            dest = cleanpath(draft_path, os.path.relpath(frame_path, version_dir))
                            ensure_dir(os.path.dirname(dest))
                            copy_file(frame_path, dest)
                    else:
                        dest = cleanpath(draft_path, blob.blob_path)
                        ensure_dir(os.path.dirname(dest))
                        copy_file(synced_blob.path, dest)

            logger.info("Checked out asset %s into draft %s at %s", asset_id, info.draft_id, draft_path)
            return info

        future: Future[CheckoutDraftInfo] = self._executor.submit(ctx.run, _transfer)
        self._track_future(job_keys, future)
        return AsyncTask(job_ids=job_keys, future=future, metadata=info)

    def _resolve_blob(self, revision_id: str, blob_urn: str) -> BlobRef:
        """Resolve `blob_urn` on revision `revision_id` to a `BlobRef`."""
        revision = fetch_revision_by_id(self._client, revision_id)
        for blob in extract_blobs_from_revision(revision):
            if blob.urn == blob_urn:
                return blob

        raise StorageManagerError(f"Blob URN {blob_urn} not found on revision {revision_id}.")

    @with_active_config
    def download_blob(
        self,
        revision_id: str,
        blob_urn: str,
        *,
        on_progress: Optional[ProgressCallback] = None,
    ) -> AsyncTask[str]:
        """Download one blob from a revision.

        Resolves `blob_urn` on `revision_id` synchronously, starts the transfer in a
        background thread, and returns an `AsyncTask` whose `metadata`
        is the `BlobRef` — available before `AsyncTask.get` returns.
        The job store key is in `AsyncTask.job_ids`; call `AsyncTask.get`
        for the local path once the transfer completes (or immediately on a cache hit).
        While a download is in flight, `get_job` on the task's job id exposes
        the target path via `DownloadJobInfo.file_path`.

        For the common case — revision_id has a live version pointer — the blob
        lands directly under the same `vN/` version-surface path everything else
        uses, and updates that version's manifest, so this warms the same surface a
        checkout would. Only a "displaced" historical revision (one the server has
        unlinked from any version after a later non-bump update) falls back to a
        narrow, version-less cache location that nothing else in the SDK reads.

        Args:
            revision_id: MEDM revision whose components contain blob_urn.
            blob_urn: URN of the binary blob to download.
            on_progress: Transfer progress callback. Called from the worker thread.

        Returns:
            An `AsyncTask`; call `AsyncTask.get` to block until the blob
            is on disk and receive its local path.

        Raises:
            StorageManagerError: The revision or blob URN is invalid (raised synchronously).
            DownloadError: The blob download fails (raised on `AsyncTask.get`).
            TransferInProgressError: A version-scoped download/sync is already in
                progress for this blob's (asset, version) elsewhere.
        """
        blob = self._resolve_blob(revision_id, blob_urn)
        project_id = project_id_from_revision_urn(revision_id)
        job_key = make_job_key(JobKind.DOWNLOAD, blob.urn)

        if blob.version_number is not None:
            version_dir = storage_version_dir(blob.asset_id, blob.version_number)
            dest = cleanpath(version_dir, blob.blob_path)
            manifest = read_version_manifest(version_dir)
            entry = manifest.binaries.get(blob.blob_path) if manifest else None
            is_current = self._is_manifest_entry_current(entry, blob, dest)
        else:
            dest = cleanpath(storage_displaced_revision_dir(blob.asset_id, blob.revision_number), blob.blob_path)
            is_current = os.path.isfile(dest)

        if is_current:
            logger.debug("Blob already current at %s; skipping download of URN %s", dest, blob.urn)
            future: Future[str] = Future()
            future.set_result(dest)
            return AsyncTask(job_ids=[job_key], future=future, metadata=blob)

        existing = self._job_store.get(job_key)
        if existing is None or existing.is_prunable:
            self._job_store.create(
                job_key,
                DownloadJobInfo(
                    job_id=job_key,
                    urn=blob.urn,
                    file_path=dest,
                    project_id=project_id,
                ),
            )

        ctx = contextvars.copy_context()

        def _transfer() -> str:
            if blob.version_number is not None:
                with self._transfer_lock.acquire(
                    self._transfer_lock.make_key(
                        asset_id=blob.asset_id,
                        revision_number=None,
                        operation="download",
                        version_number=blob.version_number,
                    ),
                    on_cancel_requested=functools.partial(self._on_cancel_requested_for, blob.asset_id),
                ):
                    self._sync_blobs_into_version_dir(
                        blob.asset_id, blob.version_number, [blob], project_id, on_progress
                    )
            else:
                with self._transfer_lock.acquire(
                    self._transfer_lock.make_key(
                        asset_id=blob.asset_id,
                        revision_number=blob.revision_number,
                        operation="download",
                    ),
                    on_cancel_requested=functools.partial(self._on_cancel_requested_for, blob.asset_id),
                ):
                    self._run_download(blob, dest, project_id, on_progress)
            logger.info("Downloaded blob %s to %s", blob.urn, dest)
            return dest

        future = cast(Future[str], self._executor.submit(ctx.run, _transfer))
        self._track_future([job_key], future)
        return AsyncTask(job_ids=[job_key], future=future, metadata=blob)

    @with_active_config
    def download_asset(
        self,
        asset_id: str,
        project_id: str,
        *,
        version_number: Optional[int] = None,
        on_progress: Optional[ProgressCallback] = None,
    ) -> AsyncTask[Dict[int, str]]:
        """Fetch an asset version's blobs into the blob cache (read-only).

        Unlike checkout_draft, this creates no sandbox draft — use it to consume
        files without intending to edit and re-publish. Blobs are written to their
        exact encoded paths under the cache, recreating any subfolders. File
        sequences (zipped blobs) are expanded in place, and each extracted frame is
        surfaced as its own entry.

        Always fetches the latest revision of the requested version.

        Args:
            asset_id: Asset whose blobs to fetch.
            project_id: MEDM project the blob download URLs resolve against.
            version_number: Specific version to fetch, or `None` for the latest.
            on_progress: Transfer progress callback. Called from the worker thread.

        Returns:
            `adsk.flow.local.storage_manager.AsyncTask`; call `AsyncTask.get`
            to block until downloads finish and receive a `{index: local_path}` mapping
            over all downloaded files (sequences are expanded and surfaced individually).

        Raises:
            StorageManagerError: The requested version does not exist (raised synchronously).
            DownloadError: A blob download fails (raised on `AsyncTask.get`).
        """
        logger.info("Downloading asset %s (version %s)", asset_id, version_number if version_number else "latest")

        if version_number is not None:
            revision = fetch_revision_for_version(self._client, asset_id, version_number)
        else:
            revision = fetch_revision(self._client, asset_id)
        if revision is None:
            raise StorageManagerError(
                f"Version {version_number} not found for asset '{asset_id}'."
                if version_number is not None
                else f"No revision found for asset '{asset_id}'."
            )

        if revision.version_number is None:
            raise StorageManagerError(
                f"Revision {revision.revision_number} of asset '{asset_id}' has no version_number "
                f"(a displaced historical revision) — download_asset requires a live version pointer."
            )
        blobs = extract_blobs_from_revision(revision)
        resolved_version_number = cast(int, revision.version_number)
        version_dir = storage_version_dir(asset_id, resolved_version_number)

        # Pre-register jobs.
        manifest = read_version_manifest(version_dir)
        entries = manifest.binaries if manifest else {}
        job_keys: List[str] = []
        for blob in blobs:
            dest = cleanpath(version_dir, blob.blob_path)
            if self._is_manifest_entry_current(entries.get(blob.blob_path), blob, dest):
                continue
            job_key = make_job_key(JobKind.DOWNLOAD, blob.urn)
            existing = self._job_store.get(job_key)
            if existing is None or existing.is_prunable:
                self._job_store.create(
                    job_key,
                    DownloadJobInfo(job_id=job_key, urn=blob.urn, file_path=dest, project_id=project_id),
                )
            job_keys.append(job_key)

        # Capture the current context (including the ContextVar set by @with_active_config)
        # so the worker thread runs with the same active Config. ctx.run(fn) executes fn
        # inside the captured context — this is the documented Python 3.7+ propagation pattern.
        ctx = contextvars.copy_context()

        def _transfer() -> Dict[int, str]:
            result: Dict[int, str] = {}
            index = 0
            with self._transfer_lock.acquire(
                self._transfer_lock.make_key(
                    asset_id=asset_id,
                    revision_number=None,
                    operation="download",
                    version_number=resolved_version_number,
                ),
                on_cancel_requested=functools.partial(self._on_cancel_requested_for, asset_id),
            ):
                synced = self._sync_blobs_into_version_dir(
                    asset_id, resolved_version_number, blobs, project_id, on_progress
                )
                for blob in blobs:
                    # A sequence blob's extracted frames are each surfaced as their
                    # own indexed entry; a plain blob surfaces as a single entry.
                    for file_path in synced[blob.blob_path].files:
                        result[index] = file_path
                        index += 1
            logger.info("Downloaded asset %s (%d path(s))", asset_id, len(result))
            return result

        future: Future[Dict[int, str]] = self._executor.submit(ctx.run, _transfer)
        self._track_future(job_keys, future)
        return AsyncTask(job_ids=job_keys, future=future)

    @with_active_config
    def get_cached_path(self, asset_id: str, version_number: int) -> Optional[str]:
        """Return the version-surface directory for `asset_id`/`version_number` if fully cached, else None.

        Local and synchronous — checks the on-disk version manifest and the files
        it records, reusing the same file-presence/size check `download_asset`
        and `checkout_draft` use internally to skip re-downloading blobs that
        are already current (though unlike them, this also re-verifies an
        expanded zip's extracted frames on disk, since this method may be
        called long after the sync that wrote them). Never makes a network
        call, so this is safe to call for many assets in a hot path (e.g.
        deciding which of a scene's references need a download at all)
        without incurring a round trip per asset, and never raises — any
        on-disk surprise (missing file, unreadable/corrupt zip, a file
        deleted out from under it) is reported as `None`, the same as a
        plain cache miss.

        Because of that, this reflects the cache's state as of its last local
        sync only. It does **not** verify the cached copy against the server's
        latest revision — a version can receive further non-bump revisions
        after being synced, which this has no way to detect without a network
        call. If a guaranteed-fresh copy is required, call `download_asset` or
        `checkout_draft` instead — both already skip re-downloading blobs this
        method would report as cached, so there is no extra transfer cost for
        the common case, only the fetch of the latest revision pointer.

        Args:
            asset_id: Asset to look up.
            version_number: Specific version whose cache state to check.

        Returns:
            The `vN/` directory path if every blob recorded in the version's
            manifest is present on disk with the expected size — and, for a
            zip-expanded entry, its extracted frames are present too. `None` if
            there is no manifest, the manifest records no blobs, any recorded
            blob is missing or its size no longer matches, or an expanded
            zip's archive is unreadable/corrupt or missing an extracted frame.
        """
        version_dir = storage_version_dir(asset_id, version_number)
        manifest = read_version_manifest(version_dir)
        if manifest is None or not manifest.binaries:
            return None

        for blob_path, entry in manifest.binaries.items():
            dest = cleanpath(version_dir, blob_path)
            if not self._blob_size_current(dest, entry):
                return None
            if entry.expanded:
                try:
                    frames = zip_entry_paths(dest, version_dir)
                except (StorageError, OSError):
                    return None
                if not all(os.path.isfile(f) for f in frames):
                    return None

        return version_dir

    @with_active_config
    def get_draft_folder(self, draft_id: str) -> str:
        """Return the sandbox folder backing `draft_id` (where files are edited).

        If you still hold the `NewDraftInfo` or `CheckoutDraftInfo` returned at draft
        creation time, prefer reading `draft_info.draft_path` directly — this
        method is for callers who only have the draft_id string (e.g. after
        restoring state from disk).

        Args:
            draft_id: Handle returned by `create_draft` or `checkout_draft`.

        Returns:
            Absolute path to the editable draft directory.
        """
        return draft_dir(draft_id)

    @with_active_config
    def get_draft_id_for_asset(self, asset_id: str) -> Optional[str]:
        """Return the draft handle for a checked-out asset_id, or None.

        Drafts are addressed by draft_id everywhere (publish_draft, discard_draft,
        get_draft_folder). Use this to recover that handle when you only hold the
        asset id — e.g. to discard a stale draft::

            did = sm.get_draft_id_for_asset(asset_id)
            if did:
                sm.discard_draft(did)
        """
        draft_id = storage_key(asset_id)
        return draft_id if os.path.isdir(draft_dir(draft_id)) else None

    @with_active_config
    def get_dependency_paths(
        self,
        draft_id: str,
        project_id: str,
        *,
        on_progress: Optional[ProgressCallback] = None,
    ) -> Dict[str, str]:
        """Resolve and download dependency blobs for a draft.

        Returns a mapping of version URN → version-surface directory (`vN/`) for each
        dependency of the draft's current revision. Keys are AssetVersion URNs and can be
        passed directly to `publish_draft(uses=...)`. The blobs are downloaded into the
        same `vN/` surface everything else uses (not the sandbox). Calling this
        after `publish_draft` reflects the newly published revision's dependencies.

        Returns an empty dict for drafts created via `create_draft` (new assets
        have no published revision to resolve dependencies from).

        If a zipped dependency blob was already downloaded and expanded by a prior
        call (from this method or `checkout_draft`), the version manifest records
        that, so this method skips both the download and the re-expansion.

        Args:
            draft_id: Handle returned by create_draft / checkout_draft.
            project_id: MEDM project the blob download URLs resolve against.
            on_progress: Transfer progress callback.

        Returns:
            Mapping of version URN → local cache directory path.

        Raises:
            StorageManagerError: The draft is missing, malformed, or a checkout
                download is still in progress for this draft.
        """
        draft_path = draft_dir(draft_id)
        draft_info = read_draft_info(draft_path)

        if isinstance(draft_info, NewDraftInfo):
            return {}

        # Guard: if a checkout download is still in progress, dependency blobs
        # may not be fully cached yet. Raise a clear error rather than returning
        # unreliable paths. The caller should await the AsyncTask from
        # checkout_draft() before calling this method.
        # Check both the root asset's version dir and all dep version dirs so
        # a dep-only in-progress download isn't missed when root blobs are cached.
        watched_dirs = {
            storage_version_dir(blob.asset_id, blob.version_number)
            for blob in draft_info.dependencies
            if blob.version_number is not None
        }
        if draft_info.version_number is not None:
            watched_dirs.add(storage_version_dir(draft_info.asset_id, draft_info.version_number))
        if any(
            isinstance(j, DownloadJobInfo) and any(path_is_within(j.file_path, d) for d in watched_dirs)
            for j in self._job_store.pending().values()
        ):
            raise StorageManagerError(
                f"A checkout download is still in progress for draft '{draft_id}'. "
                f"Call get_dependency_paths() after the AsyncTask from checkout_draft() completes."
            )

        asset_revision = fetch_revision(self._client, draft_info.asset_id, draft_info.revision_number)
        if asset_revision is None:
            raise StorageManagerError(
                f"Revision {draft_info.revision_number} not found for asset '{draft_info.asset_id}'."
            )

        dep_blobs = resolve_dependent_blobs_from_revision(self._client, asset_revision)
        logger.debug("Caching %d dependency blob(s) for draft %s", len(dep_blobs), draft_id)

        # `uses` dependency resolution always pins to a numbered version, so every
        # dep blob here has a version_number — group_blobs_by_version raises loudly
        # if that assumption is ever violated, rather than silently mis-resolving.
        dependency_paths: Dict[str, str] = {}
        for (dep_asset_id, dep_version_number), group in group_blobs_by_version(dep_blobs).items():
            with self._transfer_lock.acquire(
                self._transfer_lock.make_key(
                    asset_id=dep_asset_id, revision_number=None, operation="download", version_number=dep_version_number
                ),
                on_cancel_requested=functools.partial(self._on_cancel_requested_for, dep_asset_id),
            ):
                self._sync_blobs_into_version_dir(dep_asset_id, dep_version_number, group, project_id, on_progress)
            version_dir = storage_version_dir(dep_asset_id, dep_version_number)
            for blob in group:
                dep_key = blob.version_id or compose_revision_urn(blob.asset_id, blob.revision_number)
                dependency_paths[dep_key] = version_dir

        return dependency_paths

    @with_active_config
    def discard_draft(self, draft_id: str) -> None:
        """Discard the draft identified by `draft_id`, removing local state only.

        No server state is modified. Use `get_draft_id_for_asset` to recover
        the draft handle when you only have the asset id.

        Args:
            draft_id: Handle returned by `create_draft` or `checkout_draft`.

        Raises:
            StorageManagerError: No draft with `draft_id` exists.
        """
        folder = draft_dir(draft_id)
        if not os.path.exists(folder):
            raise StorageManagerError(f"No draft found with id '{draft_id}'.")
        # Remove the <draft_id>/ parent, not just the draft/ leaf, so no empty
        # directory is left behind in the sandbox.
        shutil.rmtree(os.path.dirname(folder))
        logger.info("Discarded draft %s", draft_id)

    @with_active_config
    def clear_cache(self, force: bool = False) -> ClearCacheResult:
        """Delete cached blobs under `blob_storage_path` to reclaim local disk space.

        Deletes every asset's cache directory, including `v{n}/` version
        content. Never touches `.jobs`, `.staging`, or `sandbox_path`
        (drafts). Any local path got earlier from `download_asset`,
        `checkout_draft`, or `download_blob` may no longer exist afterward —
        call again to re-fetch it.

        By default (`force=False`), this is all-or-nothing: if any asset is
        busy — an active transfer, yours or another process's sharing this
        cache — nothing is deleted and `TransferInProgressError` is raised.

        `force=True` clears busy assets too. It stops your own in-flight
        transfers, and asks any other process using this cache to stop as
        well, giving it a brief window to finish gracefully. A process that
        doesn't respond in time has its lock broken instead — its transfer
        may then fail partway (surfacing as a failed job it can retry; this
        process's own state is unaffected). `ClearCacheResult` reports which
        assets cleared gracefully (`cooperative_stopped`) versus which needed
        a forced break (`force_broken_locks`).

        Args:
            force: Clear busy assets too, instead of raising. See above for
                what this can do to another in-flight transfer.

        Returns:
            ClearCacheResult: what was deleted, bytes freed, and any errors.

        Raises:
            TransferInProgressError: `force=False` and at least one asset is
                busy. Nothing was deleted.
        """
        result = ClearCacheResult()
        cache_root = blob_cache_root()
        if not os.path.isdir(cache_root):
            # Nothing written under the current cache format yet — never reach into another
            # cache_fmt_v*/ directory left behind by a different SDK build.
            return result

        reserved = self._reserved_top_level_dirs(cache_root)
        asset_dirs = [entry for entry in os.scandir(cache_root) if entry.is_dir() and entry.name not in reserved]

        if not force:
            busy = self._find_busy_assets(asset_dirs)
            if busy:
                raise TransferInProgressError(
                    f"clear_cache: {len(busy)} asset(s) busy: {sorted(busy)}. "
                    "Pass force=True to cancel in-flight transfers and clear anyway, or retry later."
                )
        else:
            self._force_stop_local_jobs(result)

        for entry in asset_dirs:
            key = entry.name
            if self._transfer_lock.is_asset_locked(key):
                if not force:
                    # Became busy after the upfront validation passed (narrow
                    # TOCTOU window) — record and skip this one dir rather than
                    # aborting a deletion pass already under way for others.
                    result.errors[key] = "became locked after validation; skipped"
                    continue
                self._resolve_foreign_lock(key, result)

            size = self._dir_size(entry.path)
            try:
                shutil.rmtree(entry.path)
            except OSError as exc:
                logger.warning("clear_cache: could not remove %s: %s", entry.path, exc)
                result.errors[key] = str(exc)
                continue
            result.cleared.append(key)
            result.bytes_freed += size

        logger.info(
            "clear_cache(force=%s): freed %d bytes across %d asset dir(s); %d error(s)",
            force,
            result.bytes_freed,
            len(result.cleared),
            len(result.errors),
        )
        return result

    def _reserved_top_level_dirs(self, cache_root: str) -> Set[str]:
        """Directory names directly under cache_root excluded from clear_cache's scan.

        By default .jobs/.staging live outside cache_root entirely (siblings of the current
        cache-format directory) and are never scanned regardless of this method. This only
        matters when Config.jobs_dir, Config.upload_staging_path, or sandbox_path has been
        (unusually) configured to nest inside cache_root — resolving the actual configured/
        derived paths, rather than assuming the literal names ".jobs"/".staging", catches that
        case. Also handles any of these living more than one level deep under cache_root — the
        whole top-level directory containing them is reserved, since clear_cache only ever
        deletes whole top-level entries.
        """
        cache_root = os.path.abspath(cache_root)
        jobs_dir = os.path.abspath(self._config.jobs_dir or os.path.join(self._config.blob_storage_path, ".jobs"))
        staging_dir = os.path.abspath(self._upload_staging_path)
        sandbox_dir = os.path.abspath(self._config.sandbox_path)
        reserved: Set[str] = set()
        for d in (jobs_dir, staging_dir, sandbox_dir):
            rel = os.path.relpath(d, cache_root)
            if rel != os.curdir and not rel.startswith(os.pardir + os.sep) and rel != os.pardir:
                reserved.add(rel.split(os.sep)[0])
        return reserved

    def _find_busy_assets(self, asset_dirs: List[os.DirEntry]) -> Set[str]:
        """Storage keys that are locked or referenced by a local pending/running job.

        Deliberately uses the unscoped `JobStore.pending()`, not
        `get_pending_jobs()` — clear_cache must never treat a live foreign
        instance's upload as safe to delete just because it's not this
        instance's own job.
        """
        pending = self._job_store.pending()
        busy_assets: Set[str] = set()
        for entry in asset_dirs:
            key = entry.name
            if self._transfer_lock.is_asset_locked(key):
                busy_assets.add(key)
                continue
            if self._asset_has_pending_job(key, entry.path, pending):
                busy_assets.add(key)
        return busy_assets

    @staticmethod
    def _asset_has_pending_job(storage_key_name: str, asset_dir: str, pending: Dict[str, TransferJobInfo]) -> bool:
        for job in pending.values():
            if isinstance(job, DownloadJobInfo):
                if path_is_within(job.file_path, asset_dir):
                    return True
            elif isinstance(job, UploadJobInfo):
                if job.asset_id and storage_key(job.asset_id) == storage_key_name:
                    return True
        return False

    @staticmethod
    def _dir_size(path: str) -> int:
        """Total size in bytes of all files under path, recursively."""
        total = 0
        for root, _dirs, files in os.walk(path):
            for name in files:
                try:
                    total += os.path.getsize(os.path.join(root, name))
                except OSError:
                    pass
        return total

    def _force_stop_local_jobs(self, result: ClearCacheResult) -> None:
        """Cancel every locally-known pending/running job and wait (bounded) for
        its background thread to actually exit before the caller proceeds to
        delete files that thread might still be writing.

        Only affects jobs this process's JobStore knows about — a foreign
        process's job is invisible here; its lock is handled separately in
        clear_cache's per-asset loop via force_release_asset. A job with no
        tracked Future (e.g. an upload job — see _track_future's callers) is
        still cancelled so its thread notices and unwinds promptly, just not
        waited on directly; any lock it still holds afterward is caught by the
        same per-asset force_release_asset step.
        """
        pending = self._job_store.pending()
        with self._active_futures_lock:
            futures = [self._active_futures.get(job_id) for job_id in pending]
        for job_id in pending:
            self.cancel_job(job_id)
            result.force_cancelled_jobs.append(job_id)
        for future in futures:
            if future is None:
                continue
            try:
                future.result(timeout=_FORCE_JOB_STOP_TIMEOUT)
            except Exception as exc:  # pylint: disable=broad-except
                # Cancellation itself raises (TransferCancelledError) — any outcome here is
                # just logged, not fatal to the rest of clear_cache.
                logger.warning("clear_cache(force=True): job thread did not exit cleanly: %s", exc)

    def _resolve_foreign_lock(self, key: str, result: ClearCacheResult) -> None:
        """Get a live lock for asset `key` out of the way before its directory
        is deleted, preferring a graceful stop over an abrupt one.

        Signals `request_cancel_asset` first — if the lock is held by another
        process running this same SDK version, that process's `acquire()`
        heartbeat notices within one tick and cancels its own jobs for this
        asset (see the `on_cancel_requested` callback wired at every
        download-scoped `acquire()` call site), which releases the lock on
        its own. Polls for that, bounded by `_COOPERATIVE_CANCEL_TIMEOUT`.

        Only escalates to `force_release_asset` — breaking the lock outright,
        with the corruption risk documented on `clear_cache` — if the holder
        never responds in time (older client, or genuinely stuck).
        """
        self._transfer_lock.request_cancel_asset(key)
        deadline = time.time() + _COOPERATIVE_CANCEL_TIMEOUT
        while time.time() < deadline:
            if not self._transfer_lock.is_asset_locked(key):
                result.cooperative_stopped.append(key)
                logger.info("clear_cache(force=True): %s released its lock after a cooperative cancel request", key)
                return
            time.sleep(_COOPERATIVE_CANCEL_POLL_INTERVAL)

        removed = self._transfer_lock.force_release_asset(key)
        if removed:
            result.force_broken_locks.append(key)
            logger.warning(
                "clear_cache(force=True): %s did not respond to a cooperative cancel request; "
                "force-released lock(s): %s",
                key,
                removed,
            )

    def _on_cancel_requested_for(self, asset_id: str) -> None:
        """`on_cancel_requested` callback bound to a specific asset via
        `functools.partial` at each download-scoped `acquire()` call site.

        `acquire()`'s callback contract is a bare `Callable[[], None]` — this
        adapts `_cancel_jobs_for_asset`'s return value away, since a heartbeat
        thread invoking it has no use for (and shouldn't need to know about)
        which job ids were cancelled.
        """
        self._cancel_jobs_for_asset(storage_key(asset_id))

    def _cancel_jobs_for_asset(self, storage_key_name: str) -> List[str]:
        """Signal cancellation for this process's own pending/running jobs
        against `storage_key_name` and return their job ids, without waiting
        for them to actually exit.

        Invoked (via `_on_cancel_requested_for`) from another process's
        `clear_cache(force=True)`, running inside *this* process's own lock
        heartbeat thread — not the requesting process's thread. Deliberately
        does not await a `Future` here the way `_force_stop_local_jobs` does:
        for a version-scoped lock, the job thread this signals is the same
        thread sitting inside `acquire()`'s `finally`, waiting on
        `heartbeat.join(...)` for this very heartbeat thread to exit. Blocking
        here on that job's `Future` would be a circular wait — this thread on
        the job thread, the job thread on this thread — broken only by
        `heartbeat.join`'s timeout, which would burn most of the requesting
        process's `_COOPERATIVE_CANCEL_TIMEOUT` budget before the lock is even
        released. Confirming the job actually stopped is the requesting
        process's job: `_resolve_foreign_lock` already polls
        `is_asset_locked()` for exactly that.
        """
        pending = self._job_store.pending()
        asset_dir = storage_asset_dir_for(self._config, storage_key_name)
        job_ids = [
            job_id
            for job_id, job in pending.items()
            if self._asset_has_pending_job(storage_key_name, asset_dir, {job_id: job})
        ]
        for job_id in job_ids:
            self.cancel_job(job_id)
        return job_ids

    def _track_future(self, job_ids: List[str], future: Future) -> None:
        """Record `future` so clear_cache(force=True) and close(timeout=...) can
        wait for these jobs' background threads to actually exit, not just
        their cancel flag. `job_ids` need not be real JobStore ids — a
        synthetic, unique key is fine when the caller only needs this future
        included in close()'s wait-set (e.g. publish_draft, which has no
        upload job ids yet at submit time).
        """
        if not job_ids:
            return
        ids = list(job_ids)
        with self._active_futures_lock:
            for jid in ids:
                self._active_futures[jid] = future

        def _on_done(_future: Future) -> None:
            self._discard_futures(ids)

        future.add_done_callback(_on_done)

    def _discard_futures(self, job_ids: List[str]) -> None:
        with self._active_futures_lock:
            for jid in job_ids:
                self._active_futures.pop(jid, None)

    @with_active_config
    def get_pending_jobs(self) -> Dict[str, TransferJobInfo]:
        """Return non-terminal jobs from prior or current sessions that this instance may act on.

        Unlike `list_jobs`, this is the intended entry point for crash
        recovery: it surfaces only `PENDING` / `RUNNING` jobs (i.e. work
        that was interrupted and can be retried), omitting jobs that are still
        actively transferring in the current session.

        When a cache is shared by multiple instances (see `Config.workspace`),
        this is also scoped by ownership so recovering one instance's crash
        doesn't surface another live instance's in-flight uploads: it
        includes every pending download (downloads are never owned), every
        upload this instance itself created, and every upload that is either
        unowned (a legacy manifest, or written before this instance's owner
        was known) or owned by this same instance. An upload owned by a
        different, still-live instance is omitted — that instance's own
        relaunch (or `get_pending_jobs` call) will find it instead.

        Typical crash-recovery pattern::

            for job_id, job in sm.get_pending_jobs().items():
                sm.resume_job(job_id)

        Returns:
            Mapping of job-id → `TransferJobInfo`
            (either `DownloadJobInfo` or `UploadJobInfo`) for every job in a
            non-terminal state (`PENDING` or `RUNNING`) this instance may act on.
        """
        pending = self._job_store.pending()
        local_session_ids = self._job_store.local_session_ids()
        # `job_id in local_session_ids` short-circuits past the owner check
        # below, but that's provably safe, not just "safe in practice": the
        # only way a job with a foreign owner ends up in local_session_ids is
        # resume_job()'s get_live() call, which itself now refuses to resume a
        # job owned by a different, still-live instance (JobOwnershipError).
        # So by the time a job is in this session, either it's unowned/ours,
        # or its owner is confirmed no longer live.
        return {
            job_id: job
            for job_id, job in pending.items()
            if isinstance(job, DownloadJobInfo)
            or job_id in local_session_ids
            or job.owner is None
            or job.owner == self._owner
        }

    @with_active_config
    def resume_job(
        self, job_id: str, *, on_progress: Optional[ProgressCallback] = None
    ) -> AsyncTask[Optional[DownloadedBlob]]:
        """Re-execute a pending transfer interrupted by a crash or network failure.

        Downloads resume via HTTP `Range` from any existing `.part` file.
        Uploads resume from the next unacknowledged part using the persisted
        `upload_uri` slot and `part_etags`.

        Starts the transfer in a background thread and returns immediately

        A `FAILED` job can be resumed here — it re-enters the same retry loop
        as the original attempt, starting from its `.part` file (download) or
        the next unacknowledged part via part_etags (upload).

        Args:
            job_id: Job store key from `get_pending_jobs`, `list_jobs`
                (for a `FAILED` job), or `AsyncTask.job_ids`.
            on_progress: Transfer progress callback. Called from the worker thread.

        Returns:
            `AsyncTask`; call `AsyncTask.get` to block until the transfer completes
            and receive the completed `DownloadedBlob` for a download job, or `None`
            for an upload job.

        Raises:
            StorageManagerError: `job_id` is unknown or the job is already completed
                or cancelled (raised synchronously); also raised on `AsyncTask.get`
                if a concurrent `cancel_job` discards the job between submission and
                the worker thread starting.
            JobOwnershipError: `job_id` is an upload owned by a different
                instance that is still live — only the owning instance may
                resume it. Without this check, `get_live()` would mark it into
                this instance's own session, letting `get_pending_jobs()` and
                `cancel_all_jobs()` act on a job they don't own. Raised synchronously.
            TransferInProgressError: `job_id` is an upload and its asset's
                transfer lock is currently held live by another process —
                resuming would race that process's own transfer rather than
                recovering from a genuine crash. Raised synchronously.
        """
        job = self._job_store.get(job_id)
        if job is None:
            raise StorageManagerError(f"No job found with id '{job_id}'")
        if job.is_prunable:
            raise StorageManagerError(f"Job '{job_id}' is already in terminal state '{job.status}'")
        if (
            isinstance(job, UploadJobInfo)
            and job.owner is not None
            and job.owner != self._owner
            and self._transfer_lock.is_workspace_live(job.owner)
        ):
            raise JobOwnershipError(
                f"Cannot resume upload job '{job_id}' — owned by '{job.owner}', which is still live. "
                "Only the owning instance may resume it.",
                owner=job.owner,
                job_id=job_id,
            )
        if isinstance(job, UploadJobInfo) and self._transfer_lock.is_asset_locked(storage_key(job.asset_id)):
            raise TransferInProgressError(
                f"Cannot resume upload job '{job_id}' — asset '{job.asset_id}' has a live transfer "
                "lock held by another process. Wait for it to finish, or inspect with list_jobs().",
                asset_id=job.asset_id,
                job_id=job_id,
            )

        ctx = contextvars.copy_context()

        def _resume() -> Optional[DownloadedBlob]:
            # Re-fetch atomically right before running, on the worker thread —
            # keeps this race window tight regardless of executor queueing
            # delay: a concurrent cancel_job() between the checks above and
            # here could otherwise discard the job while a separate
            # event-reset call still installs a now-dangling Event.
            live_job = self._job_store.get_live(job_id)
            if live_job is None:
                raise StorageManagerError(f"No job found with id '{job_id}'")
            logger.info("Resuming job %s", job_id)
            return self._run_job(live_job, on_progress)

        future = cast(Future[Optional[DownloadedBlob]], self._executor.submit(ctx.run, _resume))
        self._track_future([job_id], future)
        return AsyncTask(job_ids=[job_id], future=future, metadata=job)

    @with_active_config
    def list_jobs(self) -> Dict[str, TransferJobInfo]:
        """Return all currently tracked jobs (in-flight or crash-interrupted).

        Includes jobs in every state (`PENDING`, `RUNNING`, `FAILED`).
        Completed and cancelled jobs are pruned from the store as they finish,
        so this never accumulates finished work.

        Use this for live progress monitoring.  For crash recovery use
        `get_pending_jobs` instead, which filters to only retryable jobs.

        Returns:
            Mapping of job-id → `adsk.flow.local.storage_manager.TransferJobInfo`
            for every job currently in the store, regardless of status.
        """
        return self._job_store.all()

    @with_active_config
    def get_job(self, job_id: str) -> Optional[TransferJobInfo]:
        """Return the tracked job for `job_id`, or `None` if it is not active."""
        return self._job_store.get(job_id)

    @with_active_config
    def cancel_job(self, job_id: str) -> None:
        """Mark a job as cancelled, or abandon a FAILED job. No-op if already completed or cancelled.

        Immediately effective for a `PENDING` job — it is skipped on any
        future `resume_job` call. For a `RUNNING` job, signals its
        background transfer thread to stop at the next chunk (download) or
        part (upload) boundary — interruption latency is bounded by one
        `download_chunk_size` read or one multipart-upload part, not the
        whole transfer. The transfer thread then raises
        `adsk.flow.local.storage_manager.TransferCancelledError`, which
        propagates through the owning `adsk.flow.local.storage_manager.AsyncTask`'s
        `adsk.flow.local.storage_manager.AsyncTask.get`.

        After cancellation the job's status becomes `CANCELLED` and it is
        immediately pruned from the store. A `FAILED` job has nothing
        running to signal, so it is discarded directly — this is how you
        abandon a failed transfer you don't intend to retry via `resume_job`.


        Args:
            job_id: Job store key from `list_jobs` or
                `adsk.flow.local.storage_manager.AsyncTask.job_ids`.

        Raises:
            JobOwnershipError: `job_id` names an upload owned by a different
                instance that is still live — cancelling it here would
                destroy that instance's own ability to resume it after a
                crash. Use `cancel_all_jobs()` to only ever touch this
                instance's own jobs.
        """
        logger.info("Cancelling job %s", job_id)
        self._job_store.cancel(job_id)

    @with_active_config
    def has_active_transfers(self) -> bool:
        """True if this instance has a PENDING or RUNNING job it created this session.

        Scoped to jobs created by this process (see `Config.workspace`),
        not the shared cache as a whole — intended for a quit-time check
        ("do I need to warn the user before exiting?"), where another live
        instance's unrelated transfers are irrelevant.
        """
        local_session_ids = self._job_store.local_session_ids()
        return any(not job.is_terminal for job_id, job in self._job_store.all().items() if job_id in local_session_ids)

    @with_active_config
    def cancel_all_jobs(self) -> List[str]:
        """Cancel every non-terminal, non-FAILED job this instance created this session, and return their ids.

        Scoped to jobs created by this process, not by `Config.workspace` —
        a legacy/unowned job this instance is actively resuming is included; a
        live job another instance created is never touched, even if that
        instance happens to share this one's `workspace` (which
        `StorageManager.__init__` otherwise prevents — see `Config.workspace`).
        Intended for a graceful-quit sequence, called before `close()`.

        Matches `has_active_transfers()`'s `not job.is_terminal` filter —
        `FAILED` jobs are deliberately left alone: they're already stopped, so
        there's nothing to cancel, and `JobStore.cancel()` would otherwise
        discard a FAILED job outright, destroying its `part_etags` — the only
        resume point a failed upload has. Killing exactly the state crash
        recovery depends on, right before `close()`, would defeat this
        feature's own purpose.

        Loops re-snapshotting `local_session_ids()` until a full pass finds
        nothing new to cancel, so a job this instance is still in the middle
        of creating concurrently is not silently missed by a single fixed
        snapshot. Converges as long as this instance eventually stops
        creating new jobs — callers on a genuine quit path already satisfy
        that, since nothing should be starting new transfers past this point.
        Capped at `_CANCEL_ALL_JOBS_MAX_PASSES` passes as a backstop: a caller
        that keeps creating jobs from another thread throughout could
        otherwise loop forever; hitting the cap logs a warning and returns
        whatever was cancelled, rather than hanging silently.
        """
        cancelled: Set[str] = set()
        for _pass in range(_CANCEL_ALL_JOBS_MAX_PASSES):
            local_session_ids = self._job_store.local_session_ids()
            newly_found = [
                job_id
                for job_id, job in self._job_store.all().items()
                if job_id in local_session_ids and not job.is_terminal and job_id not in cancelled
            ]
            if not newly_found:
                return list(cancelled)
            for job_id in newly_found:
                self.cancel_job(job_id)
                cancelled.add(job_id)
        logger.warning(
            "cancel_all_jobs() stopped after %d passes with new jobs still appearing; "
            "returning %d cancelled so far. Stop creating new jobs before calling this.",
            _CANCEL_ALL_JOBS_MAX_PASSES,
            len(cancelled),
        )
        return list(cancelled)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @dataclasses.dataclass
    class _SyncedBlob:
        """Result of syncing one blob into a version dir."""

        path: str  # v{N}/<blob_path> — the archive itself for zipped blobs
        files: List[str]  # materialized files: extracted frame paths for a zip, or [path]
        downloaded: bool  # False if the manifest already showed this blob current

    @staticmethod
    def _blob_size_current(dest: str, entry: ManifestEntry) -> bool:
        """Whether *dest* exists on disk with exactly *entry*'s recorded size and mtime.

        No re-hash — that would defeat the I/O savings this check exists to
        deliver. Existence + size catches deletion and truncation; mtime additionally
        catches an in-place rewrite that happens to preserve size (e.g. some other
        process touching the file), at no extra I/O cost beyond the single `os.stat()`
        call this already needs.

        Swallows `OSError` (e.g. a concurrent `clear_cache` deleting *dest*
        between the existence check and the size read) as "not current" —
        callers treat this as a plain currency probe, not a hard failure.
        """
        try:
            st = os.stat(dest)
        except OSError:
            return False
        return stat.S_ISREG(st.st_mode) and st.st_size == entry.size and st.st_mtime == entry.mtime

    @staticmethod
    def _is_manifest_entry_current(entry: Optional[ManifestEntry], blob: BlobRef, dest: str) -> bool:
        """Whether `entry` (if any) means `dest` already holds `blob`'s current bytes."""
        return (
            entry is not None
            and entry.revision_number == blob.revision_number
            and StorageManager._blob_size_current(dest, entry)
            and (entry.expanded or not blob.is_zipped)
        )

    @staticmethod
    def _asset_binary_component_names(target_asset: Asset) -> Set[str]:
        """Names of components on `target_asset` whose data carries a blob list.

        Same shape check as `extract_blobs_from_revision` — there is no explicit
        binary/generic flag on `ComponentData` to check instead.
        """
        names = set()
        for c in target_asset.components or []:
            parsed = parse_component_data(c.data)
            if parsed is not None and isinstance(parsed.get("data"), list):
                names.add(c.name)
        return names

    @staticmethod
    def _validate_asset_components(bin_comps: List[BinaryComponentSpec], all_comps: List[ComponentSpec]) -> None:
        """Raise StorageManagerError if components violate uniqueness constraints."""
        # Component names are the only key we can match server components on later
        # (ComponentData has no id), so they must be unique within a publish.
        names = [c.name for c in all_comps]
        dupes = sorted(name for name, count in Counter(names).items() if count > 1)
        if dupes:
            raise StorageManagerError(
                f"Duplicate component name(s): {dupes}. Component names must be unique within a publish."
            )

        # Blob paths must not collide so downloads can use them verbatim (no renaming).
        paths = [blob.blob_path for bc in bin_comps for blob in bc.upload_blobs]
        dupes = sorted(path for path, count in Counter(paths).items() if count > 1)
        if dupes:
            raise StorageManagerError(
                f"Colliding blob path(s): {dupes}. Give each blob a unique path "
                f"(e.g. pass base_dir to BinaryComponentSpec to preserve subfolders)."
            )

    def _is_no_op_publish(
        self,
        draft_info: CheckoutDraftInfo,
        current_asset: Asset,
        bin_comps: List[BinaryComponentSpec],
        comps: List[ComponentDataInput],
        uses: Optional[List[str]],
    ) -> bool:
        """True if publishing `comps`/`uses` would produce a byte-identical revision.

        Only called for CheckoutDraftInfo publishes. Checks run cheapest-first —
        component name set, then generic component payloads, then `uses` (one
        extra GraphQL call), then binary content hashes (file I/O) last — so any
        difference short-circuits before the expensive work.
        """
        if draft_info.version_number is None:
            return False  # unknown local cache surface — can't confirm binaries are unchanged

        current_by_name = {c.name: c for c in (current_asset.components or [])}
        if {c.name for c in comps} != set(current_by_name):
            return False

        bin_names = {bc.name for bc in bin_comps}
        for comp in comps:
            if comp.name in bin_names:
                continue  # binary components are diffed by content hash below
            current = current_by_name[comp.name]
            if current.type_id != comp.type_id or parse_component_data(current.data) != comp.data:
                return False

        if set(uses or []) != set(fetch_direct_uses(self._client, current_asset.numbered_version_id)):
            return False

        version_dir = storage_version_dir(draft_info.asset_id, draft_info.version_number)
        manifest = read_version_manifest(version_dir)
        manifest_entries = manifest.binaries if manifest else {}
        for bin_comp in bin_comps:
            current_data = parse_component_data(current_by_name[bin_comp.name].data) or {}
            try:
                current_paths = {
                    blob_path_from_component_item(item)
                    for item in current_data.get("data", [])
                    if isinstance(item, dict)
                }
            except ValueError:
                return False

            local_blobs = bin_comp.upload_blobs
            if current_paths != {b.blob_path for b in local_blobs}:
                return False
            for blob in local_blobs:
                entry = manifest_entries.get(blob.blob_path)
                if entry is None or entry.hash != hash_file(blob.full_path):
                    return False

        return True

    def _upload_blobs(
        self,
        bin_comps: List[BinaryComponentSpec],
        medm_asset: Asset,
        on_progress: Optional[ProgressCallback],
    ) -> None:
        """Fetch blob upload URIs, stage local files, and run upload jobs.

        Fetches the exact revision that was just created (its component data carries
        the server-assigned blob URIs). Staging copies source files to a crash-safe
        location before upload begins so the source can be re-read on resume.
        """
        # Match blob components on the exact revision we just created: its component
        # data carries the server-assigned blob uris to upload to. The mutation
        # returns only the Asset (a pointer to its latest revision), so fetch the
        # revision by the returned revision_id rather than trusting Asset.components.
        medm_revision = fetch_revision_by_id(self._client, medm_asset.revision_id)

        # When staging is enabled, each blob is copied to a persistent staging location
        # before upload so the source file can be re-read on resume after a crash.
        staged_paths = self._stage_upload_blobs(bin_comps)

        self._run_upload_jobs(bin_comps, medm_asset, medm_revision, staged_paths, on_progress)

    def _stage_upload_blobs(self, bin_comps: List[BinaryComponentSpec]) -> Dict[str, str]:
        """Snapshot each upload blob to a stable staging location before upload.

        Returns a mapping of blob.upload_uri → local path to upload from.
        When staging is disabled, maps directly to the original file paths.
        """
        batch_id = uuid.uuid4().hex
        staged_paths: Dict[str, str] = {}  # blob.upload_uri -> path to upload from
        for bin_comp in bin_comps:
            for blob in bin_comp.upload_blobs:
                staged_path = os.path.join(self._upload_staging_path, batch_id, blob.blob_path)
                ensure_dir(os.path.dirname(staged_path))
                try:
                    shutil.copyfile(blob.full_path, staged_path)
                except OSError as exc:
                    raise TransferError(f'Failed to copy "{blob.full_path}" to staging "{staged_path}". {exc}') from exc
                staged_paths[blob.upload_uri] = staged_path
        return staged_paths

    def _run_download(
        self,
        blob: BlobRef,
        dest: str,
        project_id: str,
        on_progress: Optional[ProgressCallback],
    ) -> DownloadedBlob:
        """Create-or-reuse the download job for `blob` targeting `dest` and run it."""
        ensure_dir(os.path.dirname(dest))
        job_key = make_job_key(JobKind.DOWNLOAD, blob.urn)
        job = self._job_store.get_live(job_key)
        if job is None:
            job = self._job_store.create(
                job_key,
                DownloadJobInfo(job_id=job_key, urn=blob.urn, file_path=dest, project_id=project_id),
            )
        return cast(DownloadedBlob, self._run_job(job, on_progress))

    def _sync_blobs_into_version_dir(
        self,
        asset_id: str,
        version_number: int,
        blobs: List[BlobRef],
        project_id: str,
        on_progress: Optional[ProgressCallback],
    ) -> "Dict[str, StorageManager._SyncedBlob]":
        """Ensure every blob in `blobs` is present under v{version_number}/.

        Downloads, expands, and hashes only what the manifest doesn't already
        show as current; writes one manifest update covering the whole batch.
        All of `blobs` must share `asset_id`/`version_number` — group blobs with
        `group_blobs_by_version` before calling this per group.

        The caller must hold the download lock for (asset_id, version_number) —
        this merges the existing manifest with new entries (read-modify-write),
        which is unsafe under concurrent writers to the same version dir.

        Returns a mapping of blob_path -> `_SyncedBlob`.
        """
        version_dir = storage_version_dir(asset_id, version_number)
        manifest = read_version_manifest(version_dir)
        entries: Dict[str, ManifestEntry] = dict(manifest.binaries) if manifest else {}
        synced: "Dict[str, StorageManager._SyncedBlob]" = {}
        changed = False

        for blob in blobs:
            dest = cleanpath(version_dir, blob.blob_path)
            entry = entries.get(blob.blob_path)
            if self._is_manifest_entry_current(entry, blob, dest):
                files = zip_entry_paths(dest, version_dir) if blob.is_zipped else [dest]
                # zip_entry_paths only computes where extraction would have landed;
                # a frame deleted independently of the archive would otherwise be
                # handed back as a path to a file that doesn't exist.
                if all(os.path.isfile(f) for f in files):
                    synced[blob.blob_path] = self._SyncedBlob(path=dest, files=files, downloaded=False)
                    continue

            outcome = self._run_download(blob, dest, project_id, on_progress)
            files = unzip_into(dest, version_dir) if blob.is_zipped else [dest]
            entries[blob.blob_path] = ManifestEntry(
                path=blob.blob_path,
                hash=outcome.hash,
                size=outcome.size,
                mtime=os.path.getmtime(dest),
                revision_number=blob.revision_number,
                expanded=blob.is_zipped,
            )
            changed = True
            synced[blob.blob_path] = self._SyncedBlob(path=dest, files=files, downloaded=True)

        if changed:
            write_version_manifest(
                version_dir,
                VersionManifest(
                    asset_id=asset_id,
                    version_number=version_number,
                    revision_number=max(entry.revision_number for entry in entries.values()),
                    synced_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    hash_algorithm=HASH_ALGORITHM,
                    binaries=entries,
                ),
            )

        return synced

    def _run_upload_jobs(
        self,
        bin_comps: List[BinaryComponentSpec],
        medm_asset,  # type: Asset
        medm_revision,
        staged_paths: Dict[str, str],
        on_progress: Optional[ProgressCallback],
    ) -> None:
        """Upload all blobs for `bin_comps` and cache them locally.

        Must be called while holding the upload asset lock for `medm_asset.id`.
        """
        logger.debug("Uploading binaries for %d component(s) of asset %s", len(bin_comps), medm_asset.id)
        for bin_comp in bin_comps:
            # Names are unique within the revision (validated above). The i-th
            # upload_blob maps by index to the i-th entry in medm_comp.data["data"]
            # — the server preserves blob order.
            medm_comp = next(
                (c for c in (medm_revision.components or []) if c.name == bin_comp.name),
                None,
            )
            if medm_comp is None:
                raise UploadError(f'Component "{bin_comp.name}" missing on revision after publish.')

            upload_blobs = bin_comp.upload_blobs
            comp_blobs = medm_comp.data.get("data", [])
            if len(comp_blobs) != len(upload_blobs):
                raise UploadError(
                    f'Component "{medm_comp.name}" blob count mismatch: expected {len(upload_blobs)}, '
                    f"got {len(comp_blobs)}."
                )
            for i, upload_blob_item in enumerate(upload_blobs):
                job_key = make_job_key(JobKind.UPLOAD, comp_blobs[i]["uri"])
                job = self._job_store.get_live(job_key)
                if job is None:
                    job = self._job_store.create(
                        job_key,
                        UploadJobInfo(
                            job_id=job_key,
                            file_path=staged_paths[upload_blob_item.upload_uri],
                            urn=comp_blobs[i]["uri"],
                            upload_uri=upload_blob_item.upload_uri,
                            asset_id=medm_asset.id,
                            owner=self._owner,
                        ),
                    )
                self._run_job(job, on_progress)

        # Warm the local version-surface cache with what was just uploaded (non-critical:
        # the originals are already uploaded regardless of whether this succeeds).
        #
        # Use medm_revision's revision_number/version_number, not medm_asset's: the
        # mutation response (medm_asset) is a pointer fetched before this revision was
        # necessarily fully materialized (the same reason _upload_blobs() re-fetches
        # medm_revision by id instead of trusting medm_asset.components). checkout_draft
        # later resolves blob.revision_number/version_number from the same kind of
        # AssetRevision fetch (fetch_revision), so matching against medm_revision here
        # (not medm_asset) is what makes the manifest entries actually line up.
        upload_revision_number = medm_revision.revision_number
        upload_version_number = medm_revision.version_number if isinstance(medm_revision.version_number, int) else None
        if upload_version_number is None:
            logger.debug("Asset %s has no version_number after publish; skipping local cache warm.", medm_asset.id)
            return

        version_dir = storage_version_dir(medm_asset.id, upload_version_number)
        try:
            with self._transfer_lock.acquire(
                self._transfer_lock.make_key(
                    asset_id=medm_asset.id,
                    revision_number=None,
                    operation="download",
                    version_number=upload_version_number,
                ),
                on_cancel_requested=functools.partial(self._on_cancel_requested_for, medm_asset.id),
            ):
                manifest = read_version_manifest(version_dir)
                entries: Dict[str, ManifestEntry] = dict(manifest.binaries) if manifest else {}
                for bin_comp in bin_comps:
                    for upload_blob_item in bin_comp.upload_blobs:
                        dest = cleanpath(version_dir, upload_blob_item.blob_path)
                        is_zipped = is_zip_path(upload_blob_item.blob_path)
                        try:
                            ensure_dir(os.path.dirname(dest))
                            digest, size = copy_file_with_hash(upload_blob_item.full_path, dest)
                            # Match _sync_blobs_into_version_dir: a zip blob must be
                            # expanded here too, or _is_manifest_entry_current() never
                            # considers it current and the next checkout re-downloads it.
                            if is_zipped:
                                unzip_into(dest, version_dir)
                            entries[upload_blob_item.blob_path] = ManifestEntry(
                                path=upload_blob_item.blob_path,
                                hash=digest,
                                size=size,
                                mtime=os.path.getmtime(dest),
                                revision_number=upload_revision_number,
                                expanded=is_zipped,
                            )
                        except Exception as exc:  # pylint: disable=broad-except
                            # non-critical; originals are already uploaded
                            logger.debug("Could not cache uploaded blob locally at %s: %s", dest, exc)
                write_version_manifest(
                    version_dir,
                    VersionManifest(
                        asset_id=medm_asset.id,
                        version_number=upload_version_number,
                        revision_number=max(
                            (entry.revision_number for entry in entries.values()), default=upload_revision_number
                        ),
                        synced_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        hash_algorithm=HASH_ALGORITHM,
                        binaries=entries,
                    ),
                )
        except (TransferInProgressError, OSError) as exc:
            # A version-scoped download/sync already in progress elsewhere, or a lock/disk
            # error acquiring it — skip the cache warm rather than fail an otherwise
            # successful publish. The uploaded bytes are safely on the server either way.
            logger.debug(
                "Skipping local cache warm for asset %s, version %s: %s",
                medm_asset.id,
                upload_version_number,
                exc,
            )

    def _run_job(self, job: TransferJobInfo, on_progress: Optional[ProgressCallback]) -> Optional[DownloadedBlob]:
        """Drive job from its current state to completed or failed, with retry.

        Transient errors (`adsk.flow.local.storage_manager.TransferError.retryable` is True
        — network errors, 429, 5xx) are retried up to `_MAX_RETRIES` times with
        exponential back-off. Semantic failures (4xx auth/not-found, disk full, bad URN)
        are raised immediately without retry.

        Downloads resume from the existing `.part` file on each attempt (HTTP Range).
        Uploads resume from the next unacknowledged part using the persisted
        `upload_uri` and `part_etags` — a retryable failure leaves the server-side
        upload job open rather than closing it, since closing would permanently
        invalidate the blob slot.

        If `StorageManager.cancel_job` is called for job while this is
        running, the transfer is interrupted at the next chunk/part boundary and
        `adsk.flow.local.storage_manager.TransferCancelledError` is raised
        (no retry).

        Returns the completed `adsk.flow.local.storage_manager.DownloadedBlob` for a download job, or
        `None` for an upload job.
        """
        logger.debug("Running %s job %s", job.job_kind.value, job.job_id)
        cancel_event = self._job_store.get_cancel_event(job.job_id)

        _last_flush = 0.0

        def _track(done: int, total: int) -> None:
            nonlocal _last_flush
            # Always update the UI progress for smooth reporting.
            if on_progress:
                on_progress(TransferProgress(bytes_done=done, bytes_total=total))
            # Throttle disk writes — bytes_done is for UI only; crash recovery
            # uses the .part file, so per-chunk persistence has no correctness value.
            now = time.time()
            if now - _last_flush >= _PROGRESS_FLUSH_INTERVAL:
                self._job_store.update(job.job_id, bytes_done=done, bytes_total=total)
                _last_flush = now

        def _persist_parts(part_etags: List[str], total_size: int) -> None:
            self._job_store.update(job.job_id, part_etags=part_etags, part_etags_size=total_size)

        def _persist_async_job_id(async_job_id: str) -> None:
            self._job_store.update(job.job_id, async_job_id=async_job_id)

        def _execute() -> Optional[DownloadedBlob]:
            if isinstance(job, DownloadJobInfo):
                return download_blob(
                    client=self._client,
                    project_id=job.project_id,
                    urn=job.urn,
                    dest=job.file_path,
                    on_progress=_track,
                    chunk_size=self._config.download_chunk_size,
                    timeout=self._config.download_timeout,
                    cancel_event=cancel_event,
                )
            if isinstance(job, UploadJobInfo):
                upload_blob(
                    client=self._client,
                    file_path=job.file_path,
                    urn_id=job.urn,
                    upload_uri=job.upload_uri,
                    upload_timeout=self._config.upload_timeout,
                    on_progress=_track,
                    cancel_event=cancel_event,
                    resume_etags=job.part_etags,
                    resume_size=job.part_etags_size or None,
                    resume_job_id=job.async_job_id,
                    on_part_uploaded=_persist_parts,
                    on_job_opened=_persist_async_job_id,
                )
            return None

        try:
            for attempt in range(_MAX_RETRIES):
                # Catches cancellation that arrives during the inter-retry backoff
                # sleep below, which the in-loop chunk/part checks can't observe.
                if cancel_event.is_set():
                    self._job_store.update(job.job_id, status=JobStatus.CANCELLED)
                    logger.info("%s job %s cancelled", job.job_kind.value, job.job_id)
                    raise TransferCancelledError(f"{job.job_kind.value} job {job.job_id} cancelled.", job_id=job.job_id)
                self._job_store.update(job.job_id, status=JobStatus.RUNNING)
                try:
                    result = _execute()
                    self._job_store.update(job.job_id, status=JobStatus.COMPLETED)
                    logger.debug("Completed %s job %s", job.job_kind.value, job.job_id)
                    if isinstance(job, UploadJobInfo):
                        self._cleanup_staged_upload(job.file_path)
                    return result
                except TransferCancelledError as exc:
                    self._job_store.update(job.job_id, status=JobStatus.CANCELLED)
                    logger.info("%s job %s cancelled: %s", job.job_kind.value, job.job_id, exc)
                    raise
                except TransferError as exc:
                    if exc.retryable and attempt < _MAX_RETRIES - 1:
                        delay = _RETRY_BACKOFF_BASE * (2**attempt)
                        logger.warning(
                            "%s job %s: transient error (attempt %d/%d), retrying in %.1fs: %s",
                            job.job_kind.value,
                            job.job_id,
                            attempt + 1,
                            _MAX_RETRIES,
                            delay,
                            exc,
                        )
                        self._job_store.update(job.job_id, status=JobStatus.PENDING)
                        time.sleep(delay)
                    else:
                        self._job_store.update(job.job_id, status=JobStatus.FAILED, error=str(exc))
                        logger.error(
                            "%s job %s failed after %d attempts: %s", job.job_kind.value, job.job_id, _MAX_RETRIES, exc
                        )
                        raise
                except Exception as exc:
                    self._job_store.update(job.job_id, status=JobStatus.FAILED, error=str(exc))
                    logger.error("%s job %s failed: %s", job.job_kind.value, job.job_id, exc)
                    raise
            raise AssertionError("unreachable: _MAX_RETRIES must be >= 1")
        finally:
            self._job_store.remove_cancel_event(job.job_id, cancel_event)

    def _cleanup_staged_upload(self, file_path: Optional[str]) -> None:
        """Remove a staged upload snapshot (and its now-empty parent dir)."""
        if not file_path:
            return
        base = os.path.abspath(self._upload_staging_path)
        if os.path.abspath(file_path).startswith(base + os.sep):
            try:
                os.remove(file_path)
                os.rmdir(os.path.dirname(file_path))
            except OSError as exc:
                logger.debug("Could not remove staged upload %s: %s", file_path, exc)  # non-fatal

    def _prune_stale_upload_staging(self) -> None:
        """Remove staging batch dirs not referenced by any active job.

        Prevents orphaned staging files from accumulating when a session crashes
        after staging but before upload completes.

        Deliberately uses the unscoped `JobStore.pending()`, not
        `get_pending_jobs()` — narrowing this to this instance's own jobs
        would make it delete a live foreign instance's staged upload bytes,
        which is strictly worse than the bug this method exists to fix: it
        would destroy the data a resume actually depends on, not just the
        record of it.
        """
        if not os.path.isdir(self._upload_staging_path):
            return
        active_paths = {job.file_path for job in self._job_store.pending().values() if isinstance(job, UploadJobInfo)}
        for entry in os.scandir(self._upload_staging_path):
            if not entry.is_dir():
                continue
            # Keep batch dir if any active job's staged file lives inside it.
            # Use startswith rather than os.scandir so nested blob paths
            # (e.g. textures/wood.png) are matched at any depth.
            if any(p.startswith(entry.path + os.sep) for p in active_paths):
                continue
            logger.debug("Pruning stale staging dir %s", entry.path)
            shutil.rmtree(entry.path, ignore_errors=True)
