# -
# *****************************************************************************
# Copyright 2026 Autodesk, Inc. All rights reserved.
#
# These coded instructions, statements, and computer programs contain
# unpublished proprietary information written by Autodesk, Inc. and are
# protected by Federal copyright law. They may not be disclosed to third
# parties or copied or duplicated in any form, in whole or in part, without
# the prior written consent of Autodesk, Inc.
# *****************************************************************************
# +

"""
This module provides asset publishing utilities.
"""

from __future__ import annotations  # needed for python 3.9 support

import os
import uuid
import shutil
import tempfile
import zipfile
from abc import ABC, abstractmethod
from dataclasses import dataclass

from tank_vendor.flow_data_sdk.base import model as medm_model
from tank_vendor.flow_data_sdk.base.exceptions import GQLAPIError

from . import transferapi
from .exceptions import (
    CreateAssetError,
    ComponentSpecError,
    FlowError,
    PublishAssetError,
)
from .globals import (
    BASE_TYPE_ID,
    BINARY_TYPE_ID,
    COMMENT_COMP,
    COMMENT_TYPE_ID,
    DER_SOURCE_COMP,
    DER_SOURCE_TYPE,
    FILE_SEQ_TYPE,
    get_client,
    IMAGE_TYPE_ID,
    LAYER_COMP,
    LAYER_TYPE,
    SOURCE_COMP,
    SOURCE_PURPOSE,
    THUMBNAIL_COMP,
    THUMBNAIL_PURPOSE,
    TYPE_COMP,
    VARIANT_SET_TYPE,
)
from .schema import get_schema_id, is_sub_type
from .storage import (
    _cache_asset_info,
    _find_component,
    get_storage_revision_dir,
)
from .utils import cleanpath, get_logger, mimetype, trace


@dataclass
class UploadBlob:
    """Data class containing relevant information for blob transfer."""

    #: Local uri assigned to blob.
    uri: str
    #: Full path to blob file in sandbox.
    full_path: str
    #: Path of blob file relative to draft directory.
    blob_path: str


class ComponentSpec(ABC):
    """Abstract base class for component specification objects.
    This should be subclassed.
    """

    @property
    def name(self) -> str:
        """Return name of component.
        (Should be uniquely identifying within a revision.)
        """
        raise NotImplementedError()

    @abstractmethod
    def create(self) -> medm_model.Component:
        """Create an MEDM component based on specifications."""
        raise NotImplementedError()

    @staticmethod
    @trace
    def create_component(
        name: str, type_id: str, **data
    ) -> medm_model.ComponentDataInput:
        """Generate a medm_model.Component object.

        Args:
            name: Name of component. This must be unique within a revision.
            **data: The remaining keyword args will be treated as additional properties
                    to be set on the component, for example, purpose.

        Returns:
            Component object that can be added to an AssetRevision.
        """
        return medm_model.ComponentDataInput(name=name, data=data, type_id=type_id)

    @staticmethod
    def build_reference_value(object_id: str) -> dict:
        """Build a component property value for a reference-2.0.0 typed property.

        Build the nested object required for component properties typed as
        autodesk.me:reference-2.0.0, which inherits from autodesk.data:reference-2.0.0
        and stores the referenced entity ID under objectId.id.

        Args:
            object_id: The URN or ID of the entity being referenced.

        Returns:
            Dict matching the autodesk.data:reference-2.0.0 schema structure.

        Examples:
            >>> ComponentSpec.build_reference_value("urn:medm:asset:c:p:abc")
            {'objectId': {'id': 'urn:medm:asset:c:p:abc'}}
        """
        return {"objectId": {"id": object_id}}


class BinaryComponentSpec(ComponentSpec):
    """Base class for all binary component specs."""

    def __init__(self):
        # List of blob upload information stored as UploadBlob objects
        # At creation time, the medm component will be given a uuid per blob.
        # The ids along with the associated file paths on disk are tracked in
        # UploadBlob data structures to be used later on for blob uploading.
        self._upload_blobs = []

    def create(
        self,
        name: str,
        files: list[str],
        type_id: str = "",
        purpose: str = "",
        **properties,
    ) -> medm_model.Component:
        """Create a medm binary component that is ready for upload.

        Args:
            name: Name of component. If the component name already exists, an exception
                  will be thrown unless "overwrite" is True in which case, the existing
                  component will be replaced.
            files: Full paths to existing files to be added to component.
                   (Order will be preserved.)
            type_id: Type of binary component to be created. If not specified, the base
                     binary type will be used.
            purpose: A string constant, describing the general purpose of the component.
            **properties: The remaining keyword args will be treated as additional properties
                          to be set on the binary component, for example, resolution
                          information for a thumbnail.

        Returns:
            Binary component created.

        Raises:
            ComponentSpecError
        """
        # Check that the files are valid
        for file in files:
            if not os.path.exists(file):
                msg = f"Invalid source path provided for binary component: {file}"
                raise ComponentSpecError(details=msg)

        # Check that the type is valid
        if type_id and not is_sub_type(BINARY_TYPE_ID, type_id):
            msg = f"Type id {type_id} is not a binary component type."
            raise ComponentSpecError(details=msg)
        type_id = type_id or BINARY_TYPE_ID

        # NOTE: TEMPORARY SOLUTION!
        #       Due to a limitation in MEDM where only a max of 10 blobs
        #       can be stored per binary component, we must zip multiple files
        #       and upload as a single blob.
        if len(files) > 1:
            # Generate the zip in the same directory as the first file
            base_dir = os.path.dirname(files[0])
            # At this point we can assume the file sequence has been vetted
            # for the correct naming convention - parse the base name out of
            # the first file to use as the zip file name.
            base_name = os.path.basename(files[0]).split(".")[0]
            zip_path = cleanpath(base_dir, f"{base_name}.zip")
            with zipfile.ZipFile(zip_path, "w") as zip_file:
                # Add each file to zip with only its base name
                # and with lossless compression
                for f in files:
                    zip_file.write(
                        f,
                        arcname=os.path.basename(f),
                        compress_type=zipfile.ZIP_DEFLATED,
                    )
            files = [zip_path]

        blobs = []  # blob list
        self._upload_blobs = []
        for i, file in enumerate(files):
            # Associate each blob with a unique id which will be
            # used for uploading later
            uri = f"upload://{uuid.uuid4()}"
            blob_path = os.path.basename(file)
            # Add blob info for medm component
            blobs.append(
                {
                    "uri": uri,
                    "path": blob_path,
                    "mimeType": mimetype(file),
                    "size": os.path.getsize(file),
                }
            )
            # Store upload information for each blob for later use when publishing
            self._upload_blobs.append(
                UploadBlob(
                    uri=uri,
                    full_path=file,
                    blob_path=blob_path,
                )
            )

        data = {}  # data block
        for prop, val in properties.items():
            data[prop] = val
        data["data"] = blobs
        data["purpose"] = purpose

        # Create new component
        return self.create_component(name=name, type_id=type_id, **data)


class CommentComponentSpec(ComponentSpec):
    """Specifications for creating a comment component.
    This is a component used to store the publish comment of a revision.
    There is only expected to be one of these per revision.
    """

    def __init__(self, comment: str):
        """
        Args:
            comment: Description of revision provided at publish time.
        """
        self.comment = comment

    @property
    def name(self) -> str:
        return COMMENT_COMP

    def create(self) -> medm_model.Component:
        """Create an MEDM component based on specifications."""

        # NOTE: comment components have an optional "body" property that we are not
        #       leveraging for now...
        return self.create_component(
            name=self.name,
            type_id=COMMENT_TYPE_ID,
            subjectLine=self.comment,
        )


class DerivativeSourceComponentSpec(ComponentSpec):
    """Specifications for creating a derivative source component.
    This is a component used in a derivative asset to point back to its source asset.
    There is only expected to be one of these per revision.
    """

    def __init__(self, version_id: str):
        """
        Args:
            version_id: Id of source version.
        """
        self.version_id = version_id

    @property
    def name(self) -> str:
        return DER_SOURCE_COMP

    def create(self) -> medm_model.Component:
        """Create an MEDM component based on specifications."""
        return self.create_component(
            name=self.name,
            type_id=get_schema_id(DER_SOURCE_TYPE),
            targetVersion=self.build_reference_value(self.version_id),
        )


class SourceComponentSpec(BinaryComponentSpec):
    """Specifications for creating a source component.
    This is a component used to store the main source file(s) of the revision.
    There is only expected to be one of these per revision.
    """

    def __init__(self, *files):
        """
        Args:
            files: List of files to be stored in the component.
        """
        self.files = files

    @property
    def name(self) -> str:
        return SOURCE_COMP

    @trace
    def create(self) -> medm_model.Component:
        """Create an MEDM component based on specifications."""
        return super().create(name=self.name, files=self.files, purpose=SOURCE_PURPOSE)


class ThumbnailComponentSpec(BinaryComponentSpec):
    """Specifications for creating a thumbnail component.
    This is a component used to store the thumbnail for the revision.
    There is only expected to be one of these per revision.
    """

    def __init__(self, thumbnail_file: str):
        """
        Args:
            thumbnail_file: Path to thumbnail file.
        """
        self.file = thumbnail_file

    @property
    def name(self) -> str:
        return THUMBNAIL_COMP

    @trace
    def create(self) -> medm_model.Component:
        """Create an MEDM component based on specifications."""
        return super().create(
            name=self.name,
            files=[self.file],
            purpose=THUMBNAIL_PURPOSE,
            type_id=IMAGE_TYPE_ID,
        )


class TypeComponentSpec(ComponentSpec):
    """Specifications for creating a type component.
    This is a component used to provide a type designation for the revision.
    More than one type component may be added to a revision.

    .. note::  Designating a "type" for an asset in MEDM involves adding a "type" component
               to a revision. There is no restriction on the number of type components
               on a revision, and no requirement that types must remain the same from one revision
               to the next. Therefore, maintaining a consistent type is largely up to the pipeline.
    """

    def __init__(self, type_id: str = "", name: str = ""):
        """
        Args:
            type_id: The MEDM type identifier for the type component.
                     If not provided, the base type id will be used.
            name: A unique name for the type component
                  (since there may be more than one).
                  If not provided, a default name will be used.

        Raises:
            ComponentSpecError
        """
        # If provided, type id must be subtype of base type
        if type_id and not is_sub_type(BASE_TYPE_ID, type_id):
            msg = f"Type id {type_id} is not a subclass of base type."
            raise ComponentSpecError(details=msg)

        self.type_id = type_id or BASE_TYPE_ID
        self._name = name or TYPE_COMP

    @property
    def name(self) -> str:
        return self._name

    def create(self) -> medm_model.Component:
        """Create an MEDM component based on specifications."""
        return self.create_component(
            name=self.name,
            type_id=self.type_id,
        )


class VariantSetComponentSpec(ComponentSpec):
    """Specifications for creating a variant set component.
    This is a component used in a conceptually atomic asset
    to list available variant sets and variants for the asset.
    There can be multiple such components on an asset with
    that may span multiple variant sets.

    Example: If an asset were to have two orthogonal variant
             sets for model representation, and surfacing look
             as outlined below.

        -> Set 1 = Representation
                - Variant (Maya)
                - Variant (Alembic)
        -> Set 2 = Look
                - Variant (Default)
                - Variant (Dirty)

            This would require four VariantSet components to
            be added to the asset.

        -> VariantSet 1 = Representation-Maya
        -> VariantSet 2 = Representation-Alembic
        -> VariantSet 3 = Look-Default
        -> VariantSet 4 = Look-Dirty
    """

    def __init__(
        self, set_name: str, variant_name: str, asset_id: str, display_name: str = ""
    ):
        """
        Args:
            set_name: Name of variant set under which this variant belongs.
            variant_name: Name of this specific variant under the set name.
            asset_id: The asset which represents this variant.
            display_name: An optional display name for this set+variant combo.
        """
        self.set_name = set_name
        self.variant_name = variant_name
        self.asset_id = asset_id
        self.display_name = display_name

    @property
    def name(self) -> str:
        return f"{self.set_name}-{self.variant_name}"

    def create(self) -> medm_model.Component:
        """Create an MEDM component based on specifications."""
        return self.create_component(
            name=self.name,
            type_id=get_schema_id(VARIANT_SET_TYPE),
            setName=self.set_name,
            variantName=self.variant_name,
            targetAsset=self.build_reference_value(self.asset_id),
            displayName=self.display_name,
        )


class FileSeqComponentSpec(TypeComponentSpec):
    """Specifications for creating a file sequence type component.
    This is a component used to designate an asset as containing a file sequence.
    This may be combined with other type designations to describe the nature of the asset.
    """

    def __init__(
        self,
        frame_start: int,
        frame_end: int,
        frame_set: str,
        file_format: str,
        name: str = "",
    ):
        """
        Args:
            frame_start: First frame of file sequence.
            frame_end: End frame of file sequence.
            frame_set: A string expression denoting the set of frames
                       within the sequence. (e.g. "1-5,10,13-20")
            file_format: A string expression denoting the file naming and
                         frame padding convention of the sequence.
                         (e.g. "render.%04d.exr")
            name: A unique name for the type component
                  (since there may be more than one type component).
                  If not provided, a default name will be used.

        Raises:
            ComponentSpecError
        """
        # NOTE: for now, this type id will be passed in because it will
        #       be a custom schema. Later when the file sequence type id
        #       is formalized under autodesk namespace, we will create a
        #       global constant and use that instead.

        # If provided, type id must be subtype of base type
        type_id = get_schema_id(FILE_SEQ_TYPE)
        if not is_sub_type(BASE_TYPE_ID, type_id):
            msg = f"Type id {type_id} is not a subclass of base type."
            raise ComponentSpecError(details=msg)

        self.frame_start = frame_start
        self.frame_end = frame_end
        self.frame_set = frame_set
        self.file_format = file_format
        self._name = name or TYPE_COMP

    @property
    def name(self) -> str:
        return self._name

    @trace
    def create(self) -> medm_model.Component:
        """Create an MEDM component based on specifications."""
        return self.create_component(
            name=self.name,
            type_id=get_schema_id(FILE_SEQ_TYPE),
            frameStart=self.frame_start,
            frameEnd=self.frame_end,
            frameSet=self.frame_set,
            fileFormat=self.file_format,
        )


class LayerComponentSpec(ComponentSpec):
    """Specifications for creating a layer component.

    A layer component represents a named compositional relationship where the
    target asset contributes compositionally to this asset. It carries a
    ``targetAsset`` reference to the contributing child asset.
    """

    def __init__(self, layer_name: str, asset_id: str):
        """
        Args:
            layer_name: Name identifying this layer relationship
                        (e.g. the pipeline-step name).
            asset_id: MEDM id of the target asset the layer points to.
        """
        self.layer_name = layer_name
        self.asset_id = asset_id

    @property
    def name(self) -> str:
        return f"{LAYER_COMP}-{self.layer_name}"
    
    def create(self) -> medm_model.Component:
        """Create an MEDM component based on specifications."""
        return self.create_component(
            name=self.name,
            type_id=get_schema_id(LAYER_TYPE),
            layerName=self.layer_name,
            targetAsset=self.build_reference_value(self.asset_id),
        )


@trace
def publish_new_asset(
    name: str,
    parent_id: str,
    description: str = "",
    components: list[ComponentSpec] | None = None,
    used_versions: list[str] | None = None,
) -> medm_model.Asset:
    """Create a new asset in AM.

    Args:
        name: Name of asset.
        parent: Entity under which to create the asset.
                This should be an Asset or a Project object.
                This can also be the id of an asset or project.
        description: Optional description of asset.
        components: List of component specifications that will be converted into components
                    to be attached to asset revision.
                    (Components are used to store binaries and metadata on revisions.)
        used_versions: List of version ids of other assets used by this asset.
                       (Stored as "uses" relationships with other asset versions.)

    Raises:
        CreateAssetError
    """
    # Prepare medm component objects for publish
    medm_components = _generate_medm_components(components)

    # Prepare medm uses inputs for publish
    medm_uses = _generate_medm_uses(used_versions)

    # Call create asset mutation
    client = get_client()
    m_input = medm_model.CreateAssetInput(
        name=name,
        parent_id=parent_id,
        components=medm_components,
        description=description,
        uses=medm_uses,
    )
    m_create = client.service_asset.create_asset(m_input)
    try:
        m_create.call()
    except GQLAPIError as exc:
        msg = f'Error creating asset "{name}" on remote. {exc}.  Request id: {exc.request_id}'
        raise CreateAssetError(details=msg) from exc

    # Get new published asset
    asset = m_create.asset

    # Upload associated binaries
    if components is not None:
        bin_specs = [
            spec for spec in components if isinstance(spec, BinaryComponentSpec)
        ]
        if not bin_specs:
            return asset  # nothing to transfer
        _upload_binaries(asset, bin_specs)

    return asset


@trace
def publish_new_revision(
    asset_id: str,
    components: list[ComponentSpec] | None = None,
    components_action: medm_model.ListAction = medm_model.ListAction.REPLACE,
    used_versions: list[str] | None = None,
) -> medm_model.Asset:
    """Publish a new version of an existing asset.

    Args:
        asset_id: Medm id of asset to be published.
        components: List of component specifications that will be converted into components
                    to be attached to asset revision.
                    (Components are used to store binaries and metadata on revisions.)
        components_action: Whether the component list should replace existing components
                           or append to them. Valid values are ListAction.REPLACE (default)
                           and ListAction.ADD.
        used_versions: List of version ids of other assets used by this asset.
                       (Stored as "uses" relationships with other asset versions.)
        components_action: Should component list replace existing components or append to them?
                          Valid values are:
                            * ListAction.REPLACE (default)
                            * ListAction.ADD

    Returns:
        Updated asset object.
        NOTE: input asset object should be deprecated after publish.

    Raises:
        PublishAssetError
    """
    # Prepare medm component objects for publish
    medm_components = _generate_medm_components(components)

    # Prepare medm uses inputs for publish
    medm_uses = _generate_medm_uses(used_versions)

    client = get_client()
    m_input = medm_model.UpdateAssetInput(
        id=asset_id,
        components=medm_components,
        components_action=components_action.value,
        named_version_change=medm_model.NamedVersionChangeEnum.CREATE_NEW.value,
        uses=medm_uses,
    )

    m_update = client.service_asset.update_asset(m_input)
    try:
        m_update.call()
    except GQLAPIError as exc:
        msg = f"Failed to update asset. {exc}"
        raise PublishAssetError(details=msg) from exc

    # Get updated asset
    asset = m_update.asset

    # Upload associated binaries
    if components is not None:
        bin_specs = [
            spec for spec in components if isinstance(spec, BinaryComponentSpec)
        ]
        if not bin_specs:
            return asset  # nothing to transfer
        _upload_binaries(asset, bin_specs)

    return asset


def _generate_medm_components(
    comp_specs: list[ComponentSpec],
) -> medm_model.ComponentDataInput:
    """Given component specs create medm component objects to be used in a publish."""
    comp_specs = [] if comp_specs is None else comp_specs
    medm_components = [comp.create() for comp in comp_specs]
    return medm_components


def _generate_medm_uses(used_versions: list[str]) -> medm_model.UsesTargetInput:
    """Convert a list of version ids into a list of UsesTargetInput objects."""
    used_versions = [] if used_versions is None else used_versions
    uses_inputs = []
    for version_id in used_versions:
        uses_inputs.append(medm_model.UsesTargetInput(to_version_id=version_id))
    return uses_inputs


@trace
def _upload_binaries(asset: medm_model.Asset, bin_specs: list[BinaryComponentSpec]):
    """Upload binaries of an asset post publish.

    Args:
        bin_specs: List of BinaryComponentSpecs which indicate where
                   to find files to be uploaded. These should correspond
                   to existing binary components on asset.
    """
    logger = get_logger(__name__)

    # Now upload the blobs to remote storage
    # Before doing so, copy all binary data into a temporary location
    # to insulate the transfer from external changes.

    logger.info("Copying binary data to temporary location for transfer...")
    with tempfile.TemporaryDirectory() as tmpdir:
        for bin_spec in bin_specs:
            for upload_blob in bin_spec._upload_blobs:
                temp_path = cleanpath(tmpdir, upload_blob.blob_path)
                try:
                    shutil.copyfile(upload_blob.full_path, temp_path)
                except Exception as exc:  # pylint: disable=broad-except
                    msg = f'Failed to copy "{upload_blob.full_path}" to temp location "{temp_path}". {exc}'
                    raise PublishAssetError(details=msg) from exc
                upload_blob.full_path = temp_path

        # Do file transfer to both remote and primary storage
        _transfer_files(asset, bin_specs)


@trace
def _transfer_files(asset: medm_model.Asset, bin_specs: list[BinaryComponentSpec]):
    """Transfer files associated with binary components to both remote
    storage and primary storage. The medm asset provided is expected to
    have been published to MEDM already. The binary components provided are expected
    to have been relocated to a temporary location for transfer.

    Raises:
        PublishAssetError
    """
    logger = get_logger(__name__)
    logger.info("Transfering binary data to cloud...")

    # The API will have mutated the component objects on the medm asset now,
    # and their uri attributes will have been replaced with a URN which can be used
    # to upload the blobs to.

    # NOTE: this whole process sucks! It's possible that the asset will be published,
    # but the binary data transfer will fail, in which case you have a half published
    # asset.  This is really a flaw in the way the API works - you should upload the
    # data first and then publish if the data transfer succeeds!

    # The transfer API uses the raw graphql connection
    gql_client = get_client()

    for bin_spec in bin_specs:
        # Find matching component represented by the component spec object
        comp = _find_component(asset, name=bin_spec.name)
        if not comp:
            msg = f'Component "{bin_spec.name}" missing on medm asset object.'
            raise PublishAssetError(details=msg)

        for i, upload_blob in enumerate(bin_spec._upload_blobs):
            comp_blobs = comp.data.get("data", [])
            if i >= len(comp_blobs):
                msg = f'Component "{comp.name}" missing blob {i}.'
                raise PublishAssetError(details=msg)
            blob_urn = comp_blobs[i]["uri"]

            logger.info(f"Uploading {upload_blob.full_path}...")

            transferapi.upload_blob(
                client=gql_client,
                file_path=upload_blob.full_path,
                urn_id=blob_urn,
                upload_uri=upload_blob.uri,
            )

            logger.info(f"File {upload_blob.full_path} uploaded successfully!")

    # Copy files to blob storage as well (create folder if necessary)
    logger.info("Transfering binary data to local storage...")
    # Storage directory for latest version of asset
    storage_dir = get_storage_revision_dir(asset.id, asset.revision_number)
    if not os.path.exists(storage_dir):
        os.makedirs(storage_dir)
    has_failures = False
    for bin_spec in bin_specs:
        for upload_blob in bin_spec._upload_blobs:
            source_path = cleanpath(upload_blob.full_path)
            storage_path = cleanpath(storage_dir, upload_blob.blob_path)
            logger.info(f"Copying {source_path} -> {storage_path}")
            try:
                shutil.copyfile(source_path, storage_path)
            except Exception as exc:  # pylint: disable=broad-except
                # Since this copy is not publish critical, we will not stop execution
                # if it fails
                logger.warning(f"Copy to primary storage failed: {exc}")
                has_failures = True

    # Add sidecar file to cache important asset data if necessary
    try:
        _cache_asset_info(asset.id)
    except FlowError as exc:
        logger.warning(f"Caching asset info in storage dir failed: {exc}")
        has_failures = True

    if has_failures:
        logger.info("All critical transfers complete!")
        logger.warning("Some non-critical transfers/processes failed.")
    else:
        logger.info("All transfers complete!")
