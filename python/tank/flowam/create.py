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

from tank_vendor.flow_integration_sdk.exceptions import CreateAssetError, FlowError
from tank_vendor.flow_integration_sdk.globals import FOLDER_TYPE_ID
from tank_vendor.flow_integration_sdk.objects import FlowAsset, FlowProject
from tank_vendor.flow_integration_sdk.publish import (
    TypeComponentSpec,
    publish_new_asset,
)
from tank_vendor.flow_integration_sdk.schema import get_schema_id
from tank_vendor.flow_integration_sdk.utils import get_logger, trace

# AM folder / type name constants (mirrors POC asset_management/constants.py)
ASSET_FOLDER = "Assets"
ASSET_TYPE = "Asset"
GENERIC_FOLDER = "Generic"
PIPELINE_STEP_TYPE = "type.pipelineStep"
SHOT_FOLDER = "Shots"
SHOT_TYPE = "Shot"


@trace
def create_asset_hierarchy(inputs) -> FlowAsset:
    """Ensure the folder hierarchy above a new generic workfile exists.

    Returns the immediate parent under which the workfile asset should be
    created.

    Args:
        inputs: A ``CreateGenericInputs`` instance (or any inputs object with
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
def get_or_create_root_folder(inputs) -> FlowAsset:
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
                name=ensure_unique_name(SHOT_TYPE, project),
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
                name=ensure_unique_name(ASSET_FOLDER, project),
                parent_id=project.id,
                description="Folder for Asset Build assets.",
                components=[
                    TypeComponentSpec(type_id=FOLDER_TYPE_ID, name=f"Type {ASSET_TYPE}")
                ],
            )
            folder = FlowAsset(raw_asset)
    elif inputs.create_mode.value == "GENERIC":
        folder = project.find_child(GENERIC_FOLDER)
        if not folder:
            logger.info(f'Creating "{GENERIC_FOLDER}" folder...')
            raw_asset = publish_new_asset(
                name=ensure_unique_name(GENERIC_FOLDER, project),
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
def get_or_create_workfile_parent(root_folder: FlowAsset, inputs) -> FlowAsset:
    """Determine (and create if necessary) the task-level folder that will be
    the direct parent of the workfile asset.

    Returns:
        The task-folder :class:`FlowAsset`.
    """
    logger = get_logger(__name__)

    sg_entity_type = inputs.sg_entity_type
    sg_entity_name = inputs.sg_entity_name
    sg_pipeline_step = inputs.sg_pipeline_step
    sg_task_name = inputs.sg_task_name

    container = root_folder.find_child(sg_entity_name)
    if not container:
        logger.info(
            f'Creating container asset for "{sg_entity_name}" under '
            f'folder "{root_folder.name}"...'
        )
        container_type = (
            "type.container.asset"
            if sg_entity_type == ASSET_TYPE
            else "type.container.shot"
        )
        raw_asset = publish_new_asset(
            name=ensure_unique_name(sg_entity_name, root_folder),
            parent_id=root_folder.id,
            components=[
                TypeComponentSpec(
                    type_id=get_schema_id(container_type), name=f"Type {container_type}"
                )
            ],
        )
        container = FlowAsset(raw_asset)

    pipeline_step = container.find_child(sg_pipeline_step)
    if not pipeline_step:
        logger.info(f'Creating pipeline step asset for "{sg_pipeline_step}"...')
        raw_asset = publish_new_asset(
            name=ensure_unique_name(sg_pipeline_step, container),
            parent_id=container.id,
            components=[
                TypeComponentSpec(
                    type_id=get_schema_id(PIPELINE_STEP_TYPE),
                    name=f"Type {PIPELINE_STEP_TYPE}",
                )
            ],
        )
        pipeline_step = FlowAsset(raw_asset)

    task_folder = pipeline_step.find_child(sg_task_name)
    if not task_folder:
        logger.info(f'Creating task folder asset for "{sg_task_name}"...')
        raw_asset = publish_new_asset(
            name=ensure_unique_name(sg_task_name, pipeline_step),
            parent_id=pipeline_step.id,
            description=f'Folder for task "{sg_task_name}".',
            components=[
                TypeComponentSpec(type_id=FOLDER_TYPE_ID, name=f"Type {FOLDER_TYPE_ID}")
            ],
        )
        task_folder = FlowAsset(raw_asset)

    return task_folder


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
