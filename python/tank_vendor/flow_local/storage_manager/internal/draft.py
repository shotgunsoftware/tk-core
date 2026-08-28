import dataclasses
import json
import os
import shutil

from ..config import Config
from ..exceptions import DraftError, StorageError
from .context import get_active_config
from .fs import atomic_write_json, cleanpath, ensure_dir
from .storage import CACHE_FORMAT_VERSION, storage_key
from ..models import BlobRef, CheckoutDraftInfo, DraftInfo, NewDraftInfo

_DRAFT_FILE = ".draft"


def _draft_parent_dir(cfg: Config, draft_id: str) -> str:
    """Return the per-draft directory (parent of the draft/ payload dir) for draft_id.

    Isolated by cache format version (physical isolation across incompatible SDK builds) and
    then by workspace (isolation between concurrent tool/DCC instances sharing one sandbox_path).
    """
    return cleanpath(cfg.sandbox_path, f"cache_fmt_v{CACHE_FORMAT_VERSION}", cfg.workspace, draft_id)


def draft_dir(draft_id: str) -> str:
    """Return the sandbox draft directory for a draft id (uuid or storage key)."""
    cfg = get_active_config()
    return cleanpath(_draft_parent_dir(cfg, draft_id), "draft")


def sandbox_draft_dir(asset_id: str) -> str:
    """Return the sandbox draft directory for a published asset."""
    return draft_dir(storage_key(asset_id))


def _sidecar_path(draft_path: str) -> str:
    """Return the ``.draft`` sidecar path inside *draft_path*."""
    return cleanpath(draft_path, _DRAFT_FILE)


def write_draft_info(info: DraftInfo) -> None:
    """Write draft metadata to the ``.draft`` sidecar inside ``info.draft_path``."""
    if not info.draft_path:
        raise DraftError("Cannot write draft info: draft_path is not set on the info object.")
    ensure_dir(info.draft_path)
    path = _sidecar_path(info.draft_path)
    try:
        data = dataclasses.asdict(info)
        if isinstance(info, NewDraftInfo):
            data["draft_type"] = "new"
        elif isinstance(info, CheckoutDraftInfo):
            data["draft_type"] = "checkout"
        atomic_write_json(path, data, indent=2)
    except OSError as exc:
        raise DraftError(f"Could not write draft info to {path}: {exc}") from exc


def read_draft_info(draft_path: str) -> DraftInfo:
    """Read and return the draft's NewDraftInfo or CheckoutDraftInfo.

    Raises DraftError if the sidecar is missing, unreadable, or malformed.
    """
    path = _sidecar_path(draft_path)
    try:
        with open(path, encoding="utf-8") as json_file:
            data = json.load(json_file)
    except (OSError, json.JSONDecodeError) as exc:
        raise DraftError(f"Could not read draft info at {path}: {exc}") from exc

    draft_type = data.get("draft_type")
    try:
        if draft_type == "new":
            fields = {field.name for field in dataclasses.fields(NewDraftInfo)}
            return NewDraftInfo(**{k: v for k, v in data.items() if k in fields})
        if draft_type == "checkout":
            fields = {field.name for field in dataclasses.fields(CheckoutDraftInfo)}
            kwargs = {k: v for k, v in data.items() if k in fields}
            # BlobRef objects are serialised as plain dicts by dataclasses.asdict —
            # reconstruct them so callers always receive typed objects.
            raw_deps = kwargs.pop("dependencies", [])
            kwargs["dependencies"] = [BlobRef(**d) for d in raw_deps if isinstance(d, dict)]
            return CheckoutDraftInfo(**kwargs)
    except TypeError as exc:
        raise DraftError(f"Draft info at {path} is malformed: {exc}") from exc

    raise DraftError(f"Draft info at {path} has unknown draft_type: {draft_type!r}")


def rename_draft_folder(old_draft_id: str, new_draft_id: str) -> None:
    """Rename the draft folder from *old_draft_id* to *new_draft_id*.

    Falls back to copytree + rmtree when os.rename fails (e.g. cross-device).
    """
    cfg = get_active_config()
    old_parent = _draft_parent_dir(cfg, old_draft_id)
    new_parent = _draft_parent_dir(cfg, new_draft_id)
    try:
        os.rename(old_parent, new_parent)
    except OSError:
        try:
            shutil.copytree(old_parent, new_parent)
            shutil.rmtree(old_parent)
        except (OSError, shutil.Error) as exc:
            raise StorageError(f"Could not rename draft folder from {old_parent!r} to {new_parent!r}: {exc}") from exc


def discard_asset_draft(asset_id: str) -> bool:
    """Delete the sandbox draft folder for *asset_id*, if it exists.

    Returns True if a draft existed and was removed, False if there was none.
    """
    folder = sandbox_draft_dir(asset_id)
    if os.path.isdir(folder):
        shutil.rmtree(folder, ignore_errors=True)
        return True
    return False
