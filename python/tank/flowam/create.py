# Copyright (c) 2026 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from __future__ import annotations  # needed for python 3.9 support

import re
from enum import Enum

from tank_vendor.flow_data_sdk.base import model as medm_model

from tank_vendor.flow_integration_sdk.exceptions import CreateAssetError, FlowError
from tank_vendor.flow_integration_sdk.globals import (
    CG_ASSET_TYPE_ID,
    CG_SHOT_TYPE_ID,
    DELIVERABLE_ASSET_TYPE,
    DELIVERABLE_SHOT_TYPE,
    EXTERNAL_ID_TYPE_ID,
    FOLDER_TYPE_ID,
    FOR_DELIVERABLE_TYPE,
    FOR_PIPELINE_STEP_TYPE,
    PIPELINE_STEP_TYPE,
)
from tank_vendor.flow_integration_sdk.objects import FlowAsset, FlowProject
from tank_vendor.flow_integration_sdk.publish import (
    ForDeliverableComponentSpec,
    ForPipelineStepComponentSpec,
    LayerComponentSpec,
    TypeComponentSpec,
    publish_new_asset,
    publish_new_revision,
)
from tank_vendor.flow_integration_sdk.schema import get_schema_id
from tank_vendor.flow_integration_sdk.utils import get_logger, trace
from tank_vendor.flow_integration_sdk.query import (
    generate_search_filter,
    medm_search,
)

from .utils import BaseInputs

# Folder names
ASSET_FOLDER = "Assets"
SHOT_FOLDER = "Shots"
GENERIC_FOLDER = "Generic"
TEMPLATE_FOLDER = "Templates"

# SG entity types
SHOT_TYPE = "Shot"
ASSET_TYPE = "Asset"

# Custom schema types
ASSET_CONTAINER_TYPE = "type.container.asset"
CONTAINER_TYPE = "type.container"
DERIVATIVE_TYPE = "type.derivative"
GENERIC_WORKFILE_TYPE = "type.workfile.generic"
SHOT_CONTAINER_TYPE = "type.container.shot"
TEMPLATE_TYPE = "type.template"
WORKFILE_TYPE = "type.workfile"


class CreateMode(Enum):
    """Enum of modes for creating a new asset."""

    NEW = "new"  #: Create a DCC asset from a new scene as the source.
    CURRENT = "current"  #: Create a DCC asset from the current scene as the source.
    TEMPLATE = "template"  #: Create a DCC asset from template scene as the source.
    GENERIC = "generic"  #: Create a generic asset from a specified source file.


def _find_deliverable(project_id: str, sg_entity: dict) -> FlowAsset | None:
    """Query for a deliverable asset matching sg entity.
    This is a "virtual" asset that should be returned by
    the federated api as long as the sg entity exists.

    Returns:
        FlowAsset object for deliverable if found, otherwise None.

    Raises:
        ValueError
    """
    sg_entity_type = sg_entity.get("type")
    sg_entity_id = sg_entity.get("id")
    if sg_entity_type == ASSET_TYPE:
        deliverable_type = DELIVERABLE_ASSET_TYPE
    elif sg_entity_type == SHOT_TYPE:
        deliverable_type = DELIVERABLE_SHOT_TYPE
    else:
        raise ValueError("sg_entity has invalid or missing type.")
    if not sg_entity_id:
        raise ValueError("sg_entity is missing 'id' field.")

    q_filter = generate_search_filter(
        type_id=get_schema_id(deliverable_type),
        components={
            get_schema_id(deliverable_type): {},
            EXTERNAL_ID_TYPE_ID: {
                "id": f"{sg_entity_type}:{sg_entity_id}",
            },
        },
    )
    result = medm_search(project_id, q_filter=q_filter)
    if result:
        return result[0]
    return None


def _find_pipeline_step(project_id: str, sg_pipeline_step: dict) -> FlowAsset | None:
    """Query for a pipeline step asset matching sg pipeline step.
    This is a "virtual" asset that should be returned by
    the federated api as long as the sg pipeline step exists.

    Returns:
        FlowAsset object for pipeline step if found, otherwise None.

    Raises:
        ValueError
    """
    sg_step_name = sg_pipeline_step.get("name")
    sg_step_type = sg_pipeline_step.get("entity_type")
    if not sg_step_name:
        raise ValueError("sg_pipeline_step is missing 'name' field.")
    if not sg_step_type:
        raise ValueError("sg_pipeline_step is missing 'entity_type' field.")

    # Query for the pipeline step asset matching the sg pipeline step
    q_filter = generate_search_filter(
        type_id=get_schema_id(PIPELINE_STEP_TYPE),
        components={
            get_schema_id(PIPELINE_STEP_TYPE): {
                "name": sg_step_name,
                "entityType": sg_step_type,
            },
        },
    )
    result = medm_search(project_id, q_filter=q_filter)
    if result:
        return result[0]
    return None


@trace
def create_federated_hierarchy(inputs: BaseInputs):
    """When creating an asset in association with an SG entity
    or SG pipeline step, we must establish certain MEDM
    proxy assets with correct relationships connecting them
    to the "virtual"/federated SG representations within MEDM.

    We must create:
        -> a container asset with a FOR_DELIVERABLE_TYPE component
           which points to the SG deliverable asset (parented to project)
        -> a root asset with a PIPELINE_STEP_TYPE component
           pointing to the SG pipeline step and SG deliverable asset
           (parented to the project)

    Returns:
        The parent :class:`FlowAsset` for the new workfile.

    Raises:
        CreateAssetError
    """
    logger = get_logger(__name__)

    am_project_id = inputs.am_project_id
    sg_entity = inputs.sg_entity
    sg_entity_type = inputs.sg_entity["type"]
    sg_entity_name = inputs.sg_entity["name"]
    sg_entity_id = inputs.sg_entity["id"]
    sg_pipeline_step = inputs.sg_pipeline_step

    try:
        project = FlowProject(am_project_id)
    except FlowError as exc:
        msg = f"Invalid Flow project id provided: {am_project_id}"
        raise CreateAssetError(data=inputs.asdict(), details=msg) from exc

    if inputs.create_mode == CreateMode.GENERIC:
        # Parent generic assets directly under project
        return project

    container_type = SHOT_CONTAINER_TYPE
    root_type_id = CG_SHOT_TYPE_ID
    if sg_entity_type == ASSET_TYPE:
        container_type = ASSET_CONTAINER_TYPE
        root_type_id = CG_ASSET_TYPE_ID

    # Find deliverable asset matching sg entity
    deliverable = _find_deliverable(am_project_id, sg_entity)
    if not deliverable:
        msg = f"Deliverable asset for {sg_entity_type} {sg_entity_id} does not exist."
        raise CreateAssetError(data=inputs.asdict(), details=msg)

    # Query for existing container asset
    q_filter = generate_search_filter(
        type_id=get_schema_id(container_type),
        components={
            get_schema_id(FOR_DELIVERABLE_TYPE): {
                "targetDeliverable.objectId.id": deliverable.id,
            },
        },
    )
    result = project.search_children(q_filter=q_filter)
    container = result[0] if result else None

    if not container:
        # Create a container asset that will have a "For Deliverable"
        # component pointing to the SG deliverable asset
        # This asset will later be populated with Layer components
        # that point to "root" assets associated with specific pipeline steps
        logger.info(
            f'Creating container asset for "{sg_entity_name}" under '
            f'project "{project.name}"...'
        )
        type_comp = TypeComponentSpec(
            type_id=get_schema_id(container_type), name="Type"
        )
        del_comp = ForDeliverableComponentSpec(deliverable_id=deliverable.id)
        medm_asset = publish_new_asset(
            name=sg_entity_name,
            parent_id=project.id,
            components=[type_comp, del_comp],
        )
        container = FlowAsset(medm_asset)

    # Find pipeline step asset matching sg pipeline step
    pipeline_step = _find_pipeline_step(am_project_id, sg_pipeline_step)
    if not pipeline_step:
        msg = f"Pipelines Step asset for {sg_pipeline_step['name']} does not exist."
        raise CreateAssetError(data=inputs.asdict(), details=msg)

    # For dcc assets, parent them under a root asset
    # that will house the dcc asset as one of its "representations"

    # Query for existing root asset
    q_filter = generate_search_filter(
        type_id=root_type_id,
        components={
            get_schema_id(FOR_PIPELINE_STEP_TYPE): {
                "targetStep.objectId.id": pipeline_step.id,
                "targetDeliverable.objectId.id": deliverable.id,
            },
        },
    )
    result = project.search_children(q_filter=q_filter)
    asset_root = result[0] if result else None

    if not asset_root:
        logger.info(f'Creating root asset for "{sg_entity_name}"...')
        type_comp = TypeComponentSpec(type_id=root_type_id, name="Type")
        step_comp = ForPipelineStepComponentSpec(
            pipeline_step_id=pipeline_step.id,
            deliverable_id=deliverable.id,
        )
        medm_asset = publish_new_asset(
            name=sg_entity_name,
            parent_id=project.id,
            description=f'Root asset for "{sg_entity_name}".',
            components=[type_comp, step_comp],
        )
        asset_root = FlowAsset(medm_asset)

        # We need to add a layer component to the container asset
        # pointing to this root asset
        step_name = sg_pipeline_step["name"]
        logger.info(
            f'Adding layer component for "{step_name}" on '
            f'container "{container.name}"...'
        )
        publish_new_revision(
            asset_id=container.id,
            components=[
                LayerComponentSpec(
                    layer_name=step_name,
                    asset_id=asset_root.id,
                    display_name=step_name,
                )
            ],
            components_action=medm_model.ListAction.ADD,
        )

    return asset_root


@trace
def create_generic_hierarchy(inputs: BaseInputs) -> FlowAsset:
    """Retrieve (or create) the top-level folder for the new asset.

    Returns:
        Folder :class:`FlowAsset`.

    Raises:
        CreateAssetError
    """
    logger = get_logger(__name__)

    am_project_id = inputs.am_project_id

    try:
        project = FlowProject(am_project_id)
    except FlowError as exc:
        msg = f"Invalid Flow project id provided: {am_project_id}"
        raise CreateAssetError(data=inputs.asdict(), details=msg) from exc

    folder = project.find_child(GENERIC_FOLDER)
    if not folder:
        logger.info(f'Creating "{GENERIC_FOLDER}" folder...')
        raw_asset = publish_new_asset(
            name=GENERIC_FOLDER,
            parent_id=project.id,
            description="Folder for Generic assets.",
            components=[
                TypeComponentSpec(type_id=FOLDER_TYPE_ID, name=f"Type {GENERIC_FOLDER}")
            ],
        )
        folder = FlowAsset(raw_asset)
    return folder


def ensure_unique_name(name: str, parent: FlowAsset | FlowProject) -> str:
    """Return a unique sibling name under *parent*, adding a numeric suffix
    if a child with the same name already exists.

    Example: siblings ``["asset 1", "asset 2 (1)"]``, input ``"asset 2"``
    → returns ``"asset 2 (2)"``.
    """
    logger = get_logger(__name__)

    if parent.find_child(name):
        copies = parent.find_children(f"{name} (*)")
        highest_index = 0
        for c in copies:
            m = re.match(rf"{re.escape(name)} \((?P<index>\d+)\)", c.name)
            if m:
                try:
                    index = int(m.group("index"))
                except ValueError:
                    continue
                if index > highest_index:
                    highest_index = index
        new_name = f"{name} ({highest_index + 1})"
        logger.warning(
            f'A child named "{name}" already exists under "{parent.name}". '
            f'Renaming to "{new_name}".'
        )
        name = new_name

    return name
