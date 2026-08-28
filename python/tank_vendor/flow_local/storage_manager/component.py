import math
import os.path
import uuid
import zipfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from tank_vendor.flow_data_sdk.base.model_g import ComponentDataInput
from .exceptions import ComponentSpecError
from .internal.fs import cleanpath, get_mimetype_from_ext

_MAX_BLOBS_PER_COMPONENT = 10


@dataclass
class UploadBlob:
    """Data class containing relevant information for blob transfer."""

    # Client-generated `upload://` handle for the blob. Recorded on the server
    # under the component data's `uri` key and reused as the upload slot id.
    upload_uri: str
    # Full path to blob file in sandbox.
    full_path: str
    # Path of blob file relative to draft directory.
    blob_path: str


class KnownBinaryTypes(str, Enum):
    """Well-known Autodesk binary schema type IDs — a convenience reference only.

    The SDK never requires these values. Pass any valid type_id (including
    user-defined studio schemas such as `mygame.studio:component.binary.maya-1.0.0`)
    to BinaryComponent.
    """

    BINARY_BASE = "autodesk.me:component.binary-1.0.0"
    BINARY_VIDEO = "autodesk.me:component.binary.video-1.0.0"
    BINARY_IMAGE = "autodesk.me:component.binary.image-1.0.0"
    BINARY_IMAGE_SEQUENCE = "autodesk.me:component.binary.imageSequence-1.0.0"


class ComponentSpec(ABC):
    """Abstract base class for component specification objects."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return name of component, uniquely identifying within a revision."""
        ...

    @abstractmethod
    def create(self) -> ComponentDataInput:
        """Create MEDM component based on specifications."""
        ...


class GenericComponentSpec(ComponentSpec):
    """Non-binary component specification for metadata or custom schema components.

    Use this to attach typed metadata (schema-validated JSON payloads) to an asset
    without uploading any files. It is also the mechanism for attaching schema type
    ids to an asset — pass an empty *data* dict and the appropriate *type_id*.

    Args:
        name: Component name, unique within the asset's revision.
        type_id: Schema type id for the component
            (e.g. `"autodesk.me:component.metadata.custom-1.0.0"`).
        data: Arbitrary JSON-serialisable dict stored as the component payload.
            Defaults to an empty dict.
    """

    def __init__(self, name: str, type_id: str, data: Optional[dict] = None):
        self._name = name
        self._type_id = type_id
        self._data = data or {}

    @property
    def name(self) -> str:
        return self._name

    def create(self) -> ComponentDataInput:
        return ComponentDataInput(name=self._name, type_id=self._type_id, data=self._data)


def _zip_files(files: List[str], suffix: str = "") -> str:
    """Zip *files* into a single archive adjacent to the first file and return its path.

    All files are stored with only their basename (no subdirectory paths inside the zip)
    so that extraction lands them flat in the destination directory.
    MEDM supports max 10 blobs per binary component — this is the transport workaround.
    suffix is appended to the archive stem (e.g. `"_batch0"`) to name batches uniquely.
    """
    base_dir = os.path.dirname(files[0])
    base_name = os.path.splitext(os.path.basename(files[0]))[0]
    zip_path = cleanpath(base_dir, f"{base_name}{suffix}.zip")
    with zipfile.ZipFile(zip_path, "w") as zf:
        for f in files:
            zf.write(f, arcname=os.path.basename(f), compress_type=zipfile.ZIP_DEFLATED)
    return zip_path


class BinaryComponentSpec(ComponentSpec):
    """Specification for a binary component and the files it carries.

    Each file becomes a blob whose encoded path (the component data `path`)
    determines where it is reproduced on download. By default that path is the
    file's basename. Pass base_dir to encode the path *relative to that
    directory* instead, preserving subfolders end-to-end — e.g. with
    `base_dir=<draft folder>` a file at `<draft>/textures/wood.png` is encoded
    as `textures/wood.png` and recreated under that subfolder on checkout.

    Blob paths must be unique across all components in a single publish;
    `publish_draft` rejects collisions so downloads never need to rename files.

    Args:
        name: Component name, unique within the asset's revision.
        files: Local file paths to upload. Multiple files are bundled into one
            zipped blob (MEDM caps a binary component at 10 blobs).
        type_id: Schema type id for the component. See `KnownBinaryTypes`.
        purpose: Optional free-form tag stored with the component (e.g. "source").
        base_dir: When set, blob paths are encoded relative to this directory
            (preserving subfolders); otherwise only the basename is used.
        **properties: Extra key/values merged into the component data payload.
    """

    def __init__(
        self,
        name: str,
        files: List[str],
        type_id: str = KnownBinaryTypes.BINARY_BASE,
        purpose: str = "",
        base_dir: Optional[str] = None,
        **properties,
    ):
        self._name = name
        self._files = files
        self._type_id = type_id
        self._purpose = purpose
        self._base_dir = base_dir
        self._properties = properties
        self._upload_blobs: Optional[List[UploadBlob]] = None
        self._component_data: Optional[ComponentDataInput] = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def upload_blobs(self) -> List[UploadBlob]:
        if self._upload_blobs is None:
            raise ComponentSpecError(f"create() must be called before accessing upload_blobs on '{self._name}'")
        return list(self._upload_blobs)

    def create(self) -> ComponentDataInput:
        """Create a MEDM binary component that is ready for upload.
        Idempotent — repeated calls return the same result.
        """
        if self._component_data is not None:
            return self._component_data

        for file in self._files:
            if not os.path.exists(file):
                raise ComponentSpecError(f"File not found for component '{self._name}': {file}")

        # todo: we need to consider adding type_id validation through schema check via MEDM call

        files = self._zip_if_needed(self._files)

        self._upload_blobs = []
        blobs = []
        for file in files:
            uri = f"upload://{uuid.uuid4()}"
            if self._base_dir is not None:
                # Encode the path relative to base_dir so subfolders are preserved.
                blob_path = cleanpath(os.path.relpath(file, self._base_dir))
            else:
                blob_path = os.path.basename(file)
            blobs.append(
                {
                    "uri": uri,
                    "path": blob_path,
                    "mimeType": get_mimetype_from_ext(file),
                    "size": os.path.getsize(file),
                }
            )
            self._upload_blobs.append(UploadBlob(upload_uri=uri, full_path=file, blob_path=blob_path))

        self._component_data = ComponentDataInput(
            name=self._name,
            type_id=self._type_id,
            data={**self._properties, "data": blobs, "purpose": self._purpose},
        )
        return self._component_data

    # MEDM supports max 10 blobs per binary component — multiple files are zipped into one.
    # fixme: temporary solution
    @staticmethod
    def _zip_if_needed(files: List[str]) -> List[str]:
        if len(files) <= 1:
            return files
        return [_zip_files(files)]


class ImageSequenceComponentSpec(BinaryComponentSpec):
    """Component spec for an image sequence (EXR frames, etc.).

    A specialization of `BinaryComponentSpec` for image sequences. Zips
    frame files into a single blob for upload and stores the frame range using
    MEDM's native `fStart`/`fEnd`/`fInc` fields on the
    `autodesk.me:component.binary.imageSequence-1.0.0` schema. On download,
    the SDK extracts the zip and surfaces each frame individually.

    Always uses `KnownBinaryTypes.BINARY_IMAGE_SEQUENCE` as the schema —
    this is the only schema that (a) defines the `fStart`/`fEnd`/`fInc`
    fields that survive MEDM's schema validation, and (b) is recognised by the
    download path for automatic zip expansion. A different `type_id` would
    silently drop the frame metadata and disable expansion; use
    `BinaryComponentSpec` directly for any other binary type.

    Requires at least two files — a single-frame asset should use
    `BinaryComponentSpec` instead.

    Args:
        name:        Component name, unique within the asset revision.
        files:       Frame files to upload, in frame order. Must have len >= 2.
        frame_start: First frame number (stored as `fStart`).
        frame_end:   Last frame number (stored as `fEnd`).
        frame_step:  Frame step/increment (stored as `fInc`). Defaults to 1.
        purpose:     Optional free-form tag stored with the component.
        base_dir:    When set, the zip blob path is encoded relative to this
                     directory; otherwise only the basename is used.
    """

    def __init__(
        self,
        name: str,
        files: List[str],
        frame_start: int,
        frame_end: int,
        frame_step: int = 1,
        purpose: str = "",
        base_dir: Optional[str] = None,
    ):
        # No **properties — frame metadata uses typed params (frame_start/end/step) instead.
        # type_id is fixed: only BINARY_IMAGE_SEQUENCE defines fStart/fEnd/fInc and triggers
        # zip expansion on download. Callers cannot override it.
        super().__init__(
            name=name, files=files, type_id=KnownBinaryTypes.BINARY_IMAGE_SEQUENCE, purpose=purpose, base_dir=base_dir
        )
        self._frame_start = frame_start
        self._frame_end = frame_end
        self._frame_step = frame_step

    def create(self) -> ComponentDataInput:
        """Create a MEDM image-sequence component ready for upload.

        Frames are sorted and split into at most `_MAX_BLOBS_PER_COMPONENT`
        batches, each zipped into its own blob. Each blob gets its own
        `UploadJobInfo`, enabling per-batch resume on upload failure.
        `fStart` / `fEnd` / `fInc` are stored globally on the component.
        Idempotent — repeated calls return the same result.
        """
        if self._component_data is not None:
            return self._component_data

        if len(self._files) < 2:
            raise ComponentSpecError(
                f"ImageSequenceComponentSpec '{self._name}' requires at least 2 files; "
                f"got {len(self._files)}. Use BinaryComponentSpec for single-frame assets."
            )

        for file in self._files:
            if not os.path.exists(file):
                raise ComponentSpecError(f"File not found for component '{self._name}': {file}")

        sorted_files = sorted(self._files)
        n = len(sorted_files)
        # For N <= MAX_BLOBS: keep all frames in one zip
        # For N > MAX_BLOBS: split into exactly MAX_BLOBS batches to stay within
        # the MEDM per-component blob limit while enabling per-batch resume.
        if n <= _MAX_BLOBS_PER_COMPONENT:
            batches = [sorted_files]
        else:
            batch_size = math.ceil(n / _MAX_BLOBS_PER_COMPONENT)
            batches = [sorted_files[i : i + batch_size] for i in range(0, n, batch_size)]

        self._upload_blobs = []
        blob_data = []
        for i, batch in enumerate(batches):
            zip_path = _zip_files(batch, suffix=f"_batch{i}")
            uri = f"upload://{uuid.uuid4()}"
            blob_path = os.path.basename(zip_path)
            blob_data.append(
                {
                    "uri": uri,
                    "path": blob_path,
                    "mimeType": get_mimetype_from_ext(zip_path),
                    "size": os.path.getsize(zip_path),
                }
            )
            self._upload_blobs.append(UploadBlob(upload_uri=uri, full_path=zip_path, blob_path=blob_path))

        self._component_data = ComponentDataInput(
            name=self._name,
            type_id=self._type_id,
            data={
                "data": blob_data,
                "purpose": self._purpose,
                "fStart": self._frame_start,
                "fEnd": self._frame_end,
                "fInc": self._frame_step,
            },
        )
        return self._component_data
