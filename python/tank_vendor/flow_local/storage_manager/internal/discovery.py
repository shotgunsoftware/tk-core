"""Pure parsing of the binary blobs referenced by an asset revision."""

import hashlib
import json
import re
import urllib.parse
from collections import Counter
from typing import Dict, List, Optional, Tuple

from tank_vendor.flow_data_sdk.base.model_g import AssetRevision
from ..exceptions import StorageManagerError
from .fs import is_zip_path
from ..models import BlobRef

# Basename.ext extracted from colon-delimited blob URNs (no path separators or spaces).
# Matches: H264_5994_Light_Version2.mpd, H264_5994_Light_Version2_fmp4.m3u8,
#          H264-5994-Light-Version2-0c9ea6e2-b155-431d-9f2e-28a9ab4bc788.webm
# Rejects: "file name.mpd" (space), "file\x00.mpd" (control char), bare tokens like "urn"
_FILENAME_RE = re.compile(r"^[^\x00-\x1f\x7f /\\:*?\"<>|=&]+\.[A-Za-z0-9]{1,10}$")


def _filename_from_blob_urn(urn: str) -> str:
    """Derive a cache-relative filename from a blob URN when path is absent.

    Moxion publish transfer often stores streaming/manifest components with a
    uri but no path. Those URNs still embed the storage filename as a
    colon-delimited segment (e.g. H264_5994_Light_Version2.mpd). When no
    such segment is found, fall back to a stable hash so blob_path is never
    empty (an empty path would write directly into the version directory).
    """
    candidates: List[str] = []
    decoded = urn
    for _ in range(3):
        for part in decoded.split(":"):
            candidate = part.strip()
            if not candidate or candidate == "urn" or candidate.startswith("urn%"):
                continue
            if _FILENAME_RE.match(candidate):
                candidates.append(candidate)
        if candidates:
            return candidates[0]
        next_decoded = urllib.parse.unquote(decoded)
        if next_decoded == decoded:
            break
        decoded = next_decoded

    token = hashlib.md5(urn.encode(), usedforsecurity=False).hexdigest()[:16]
    return f"blob-{token}.bin"


def blob_path_from_component_item(item: dict) -> str:
    """Return the encoded relative path for one binary component data entry.

    Raises ValueError if the item has no usable path and uri is not a urn: value.
    """
    raw_path = item.get("path")
    if isinstance(raw_path, str):
        blob_path = raw_path.strip()
        if blob_path:
            return blob_path
    uri = item.get("uri", "")
    if isinstance(uri, str) and uri.startswith("urn:"):
        return _filename_from_blob_urn(uri)
    raise ValueError(f"Cannot derive blob_path: uri={uri!r} has no path and is not a urn:")


def parse_component_data(raw) -> Optional[dict]:
    """Normalize a ComponentData.data value (JSON string or dict) to a dict.

    Returns None if raw is neither a dict nor a JSON-decodable string.
    """
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return None
        return parsed if isinstance(parsed, dict) else None
    if isinstance(raw, dict):
        return raw
    return None


def extract_blobs_from_revision(revision: AssetRevision) -> List[BlobRef]:
    """Pull all binary blob URNs out of a revision's components.

    Non-binary components and components without a parseable blob list are
    skipped. A component whose data is a string we cannot JSON-decode is
    also skipped — that is unexpected for a well-formed revision.

    Raises StorageManagerError if two or more blobs resolve to the same blob_path.
    """
    blobs: List[BlobRef] = []
    if not revision.components:
        return blobs

    for component in revision.components:
        parsed = parse_component_data(component.data)
        if parsed is None:
            continue

        items = parsed.get("data")
        if not isinstance(items, list):
            continue

        for item in items:
            if not isinstance(item, dict):
                continue
            uri = item.get("uri", "")
            if not uri.startswith("urn:"):
                continue
            blob_path = blob_path_from_component_item(item)
            is_zipped = is_zip_path(blob_path)
            blobs.append(
                BlobRef(
                    asset_id=revision.asset_id,
                    revision_number=revision.revision_number,
                    urn=uri,
                    blob_path=blob_path,
                    version_number=revision.version_number if isinstance(revision.version_number, int) else None,
                    is_zipped=is_zipped,
                )
            )

    dupes = sorted(path for path, count in Counter(b.blob_path for b in blobs).items() if count > 1)
    if dupes:
        raise StorageManagerError(
            f"Colliding blob path(s) in revision {revision.revision_number} of asset {revision.asset_id!r}: "
            f"{dupes}. Ambiguous or duplicate filenames derived from blob URNs — cannot safely download "
            f"without overwriting."
        )

    return blobs


def group_blobs_by_version(blobs: List[BlobRef]) -> Dict[Tuple[str, int], List[BlobRef]]:
    """Group blobs by (asset_id, version_number), preserving discovery order.

    Raises StorageManagerError if any blob has no version_number (indicating a
    displaced historical revision).
    """
    groups: Dict[Tuple[str, int], List[BlobRef]] = {}
    for blob in blobs:
        if blob.version_number is None:
            raise StorageManagerError(
                f"Blob {blob.urn!r} on asset {blob.asset_id!r} has no version_number "
                f"(a displaced historical revision) — cannot resolve a version-surface path for it."
            )
        groups.setdefault((blob.asset_id, blob.version_number), []).append(blob)
    return groups
