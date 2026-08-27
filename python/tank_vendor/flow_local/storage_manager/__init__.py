"""Managed file operations for Autodesk Flow assets.

The **Platform Local SDK** provides a high-level layer on top of
`adsk.flow.data.GQLClient` that handles uploads, downloads, and a local
draft (checkout → edit → publish) lifecycle. All local state — the read-only blob
cache, editable sandbox drafts, transfer-job manifests, and upload staging — is
managed transparently under the paths given by `Config`.

Quick start
-----------
::

    from adsk.flow.data import GQLClient
    from adsk.flow.local.storage_manager import BinaryComponentSpec, Config, StorageManager

    client = GQLClient(...)   # your authenticated GQL client
    sm = StorageManager(client, Config(
        blob_storage_path="/data/blobs",
        sandbox_path="/data/sandbox",
        workspace="my_dcc_app",  # stable per integrator instance, unique across concurrently live ones
    ))

**Download** an asset into the read-only blob cache (no draft created)::

    task = sm.download_asset(asset_id, project_id)
    paths = task.get()        # {0: "/data/blobs/.../file.png", 1: ..., ...}

**Check** whether a version is already cached, without a network call::

    cached_dir = sm.get_cached_path(asset_id, version_number)
    if cached_dir is None:
        sm.download_asset(asset_id, project_id, version_number=version_number).get()

**Download** a single blob by revision and URN::

    task = sm.download_blob(revision_id, blob_urn)
    blob = task.metadata      # BlobRef — available immediately
    path = task.get()         # blocks until the blob is on disk

**Checkout → edit → publish** (draft lifecycle)::

    task = sm.checkout_draft(asset_id, project_id)
    info = task.get()                    # CheckoutDraftInfo; blocks until files are on disk
    # ... edit files under info.draft_path ...
    pub = sm.publish_draft(
        info.draft_id,
        binary_components=[BinaryComponentSpec(name="Main", files=[...])],
    )
    asset = pub.get()                    # published Asset

**Create a brand-new asset** (offline-first; nothing hits the server until publish)::

    draft = sm.create_draft(name="My Asset", parent_id=folder_id)
    # ... copy files into draft.draft_path ...
    asset = sm.publish_draft(
        draft.draft_id,
        binary_components=[BinaryComponentSpec(name="Main", files=[...])],
    ).get()

Error handling
--------------
All errors are subclasses of `StorageManagerError`. Catch specific subclasses
for programmatic recovery::

    from adsk.flow.local.storage_manager import ConflictError, DraftExistsError, NoChangeError

    try:
        info = sm.checkout_draft(asset_id, project_id).get()
    except DraftExistsError:
        # A draft already exists — discard it and retry.
        sm.checkout_draft(asset_id, project_id, discard_existing_draft=True).get()
    except ConflictError as exc:
        print(f"Asset '{exc.asset_id}' was updated since checkout — re-checkout and retry")
    except NoChangeError as exc:
        print(f"Asset '{exc.asset_id}' is unchanged since checkout (revision {exc.revision_number})")
"""

import logging

from adsk.flow.local.storage_manager.component import (
    BinaryComponentSpec,
    ComponentSpec,
    GenericComponentSpec,
    ImageSequenceComponentSpec,
    KnownBinaryTypes,
)
from adsk.flow.local.storage_manager.config import Config
from adsk.flow.local.storage_manager.exceptions import (
    BinaryComponentDropError,
    ComponentSpecError,
    ConflictError,
    CreateAssetError,
    DependencyError,
    DownloadError,
    DraftError,
    DraftExistsError,
    JobOwnershipError,
    NoChangeError,
    StorageError,
    StorageManagerError,
    TransferCancelledError,
    TransferError,
    TransferInProgressError,
    UpdateAssetError,
    UploadError,
)
from adsk.flow.local.storage_manager.manager import StorageManager
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
    TransferProgress,
    UploadJobInfo,
)

# Attach no-op handler to this package's top-level logger so records have somewhere to go
# if the consuming application never configures logging. This sets no level and does not
# affect propagation — applications still control output by configuring the root (or any
# ancestor) logger. See "Configuring Logging for a Library" in the Python logging docs.
logging.getLogger(__name__).addHandler(logging.NullHandler())

__all__ = [
    "AsyncTask",
    "BinaryComponentDropError",
    "BinaryComponentSpec",
    "BlobRef",
    "CheckoutDraftInfo",
    "ClearCacheResult",
    "ComponentSpec",
    "ComponentSpecError",
    "Config",
    "ConflictError",
    "CreateAssetError",
    "DependencyError",
    "DownloadError",
    "DownloadJobInfo",
    "DraftError",
    "DraftExistsError",
    "StorageManager",
    "StorageManagerError",
    "GenericComponentSpec",
    "ImageSequenceComponentSpec",
    "JobKind",
    "JobOwnershipError",
    "JobStatus",
    "KnownBinaryTypes",
    "NewDraftInfo",
    "NoChangeError",
    "ProgressCallback",
    "StorageError",
    "TransferCancelledError",
    "TransferError",
    "TransferInProgressError",
    "TransferProgress",
    "UpdateAssetError",
    "UploadError",
    "UploadJobInfo",
]
