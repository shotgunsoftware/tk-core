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
from tank_vendor.flow_integration_sdk.globals import FOLDER_TYPE_ID
from tank_vendor.flow_integration_sdk.objects import FlowAsset, FlowProject
from tank_vendor.flow_integration_sdk.publish import (
    LayerComponentSpec,
    TypeComponentSpec,
    publish_new_asset,
    publish_new_revision,
)
from tank_vendor.flow_integration_sdk.schema import get_schema_id
from tank_vendor.flow_integration_sdk.utils import get_logger, trace

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
PIPELINE_STEP_TYPE = "type.pipelineStep"
SHOT_CONTAINER_TYPE = "type.container.shot"
TEMPLATE_TYPE = "type.template"
WORKFILE_TYPE = "type.workfile"


class CreateMode(Enum):
    """Enum of modes for creating a new asset."""

    NEW = "new"  #: Create a DCC asset from a new scene as the source.
    CURRENT = "current"  #: Create a DCC asset from the current scene as the source.
    TEMPLATE = "template"  #: Create a DCC asset from template scene as the source.
    GENERIC = "generic"  #: Create a generic asset from a specified source file.


@trace
def create_asset_hierarchy(inputs: BaseInputs) -> FlowAsset:
    """Ensure the folder hierarchy above a new generic workfile exists.

    Returns the immediate parent under which the workfile asset should be
    created.

    Args:
        inputs: A ``BaseInputs`` instance (or any inputs object with
                ``am_project_id``, ``sg_entity_name``, and a ``create_mode``
                compatible with ``CreateMode.GENERIC``).

    Returns:
        The parent :class:`FlowAsset` for the new workfile.
    """
    root_folder = get_or_create_root_folder(inputs)

    if inputs.sg_entity_name:
        parent = get_or_create_workfile_parent(root_folder, inputs)
    else:
        parent = root_folder

    return parent


@trace
def get_or_create_root_folder(inputs: BaseInputs) -> FlowAsset:
    """Retrieve (or create) the top-level folder for the new asset.

    Returns:
        Folder :class:`FlowAsset`.

    Raises:
        CreateAssetError
    """
    logger = get_logger(__name__)

    am_project_id = inputs.am_project_id
    sg_entity_type = inputs.sg_entity_type

    try:
        project = FlowProject(am_project_id)
    except FlowError as exc:
        msg = f"Invalid Flow project id provided: {am_project_id}"
        raise CreateAssetError(data=inputs.asdict(), details=msg) from exc

    if sg_entity_type == SHOT_TYPE:
        folder = project.find_child(SHOT_TYPE)
        if not folder:
            logger.info(f'Creating "{SHOT_TYPE}" folder...')
            raw_asset = publish_new_asset(
                name=SHOT_TYPE,
                parent_id=project.id,
                description="Folder for Shot assets.",
                components=[
                    TypeComponentSpec(type_id=FOLDER_TYPE_ID, name=f"Type {SHOT_TYPE}")
                ],
            )
            folder = FlowAsset(raw_asset)
    elif sg_entity_type == ASSET_TYPE:
        folder = project.find_child(ASSET_FOLDER)
        if not folder:
            logger.info(f'Creating "{ASSET_FOLDER}" folder...')
            raw_asset = publish_new_asset(
                name=ASSET_FOLDER,
                parent_id=project.id,
                description="Folder for Asset Build assets.",
                components=[
                    TypeComponentSpec(type_id=FOLDER_TYPE_ID, name=f"Type {ASSET_TYPE}")
                ],
            )
            folder = FlowAsset(raw_asset)
    elif inputs.create_mode == CreateMode.GENERIC:
        folder = project.find_child(GENERIC_FOLDER)
        if not folder:
            logger.info(f'Creating "{GENERIC_FOLDER}" folder...')
            raw_asset = publish_new_asset(
                name=GENERIC_FOLDER,
                parent_id=project.id,
                description="Folder for Generic assets.",
                components=[
                    TypeComponentSpec(
                        type_id=FOLDER_TYPE_ID, name=f"Type {GENERIC_FOLDER}"
                    )
                ],
            )
            folder = FlowAsset(raw_asset)
    else:
        msg = f"Invalid entity type provided: {sg_entity_type}."
        raise CreateAssetError(data=inputs.asdict(), details=msg)

    return folder


@trace
def get_or_create_workfile_parent(
    root_folder: FlowAsset, inputs: BaseInputs
) -> FlowAsset:
    """Determine (and create if necessary) the folder that will be the direct
    parent of the workfile asset.

    Returns:
        The pipeline step :class:`FlowAsset` for generic assets, or the root
        asset container under the pipeline step for DCC assets.
    """
    logger = get_logger(__name__)

    sg_entity_type = inputs.sg_entity_type
    sg_entity_name = inputs.sg_entity_name
    sg_pipeline_step = inputs.sg_pipeline_step

    container = root_folder.find_child(sg_entity_name)
    container_type = (
        ASSET_CONTAINER_TYPE if sg_entity_type == ASSET_TYPE else SHOT_CONTAINER_TYPE
    )
    if not container:
        logger.info(
            f'Creating container asset for "{sg_entity_name}" under '
            f'folder "{root_folder.name}"...'
        )
        medm_asset = publish_new_asset(
            name=sg_entity_name,
            parent_id=root_folder.id,
            components=[
                TypeComponentSpec(type_id=get_schema_id(container_type), name=f"Type")
            ],
        )
        container = FlowAsset(medm_asset)

    pipeline_step = container.find_child(sg_pipeline_step)
    if not pipeline_step:
        logger.info(f'Creating pipeline step folder for "{sg_pipeline_step}"...')
        medm_asset = publish_new_asset(
            name=sg_pipeline_step,
            parent_id=container.id,
            components=[TypeComponentSpec(type_id=FOLDER_TYPE_ID, name="Type")],
        )
        pipeline_step = FlowAsset(medm_asset)

        logger.info(
            f'Adding layer component for "{sg_pipeline_step}" on '
            f'container "{container.name}"...'
        )
        publish_new_revision(
            asset_id=container.id,
            components=[
                LayerComponentSpec(
                    layer_name=sg_pipeline_step, asset_id=pipeline_step.id
                )
            ],
            components_action=medm_model.ListAction.ADD,
        )
    if inputs.create_mode == CreateMode.GENERIC:
        # Parent generic assets directly under pipeline step
        parent = pipeline_step
    else:
        # For dcc assets, parent them under a root asset
        # that will house the dcc asset as one of its "representations"
        # NOTE: the root asset will be container type for now
        asset_root = pipeline_step.find_child(sg_entity_name)
        if not asset_root:
            logger.info(f'Creating root asset for "{sg_entity_name}"...')
            medm_asset = publish_new_asset(
                name=sg_entity_name,
                parent_id=pipeline_step.id,
                description=f'Root asset for "{sg_entity_name}".',
                components=[
                    TypeComponentSpec(
                        type_id=get_schema_id(container_type), name=f"Type"
                    )
                ],
            )
            asset_root = FlowAsset(medm_asset)
        parent = asset_root

    return parent


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
