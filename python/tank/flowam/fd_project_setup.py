# Copyright (c) 2026 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
This is a temporary module necessary to provide classes and utilities
to aid in the creation of 'fake' FPT entities within MEDM in order to
simulate data federation.  It includes code for

    * ComponentSpec subclasses required for new asset types
    * Code to build project scaffolding, populating MEDM with FPT proxies for
      various relevant entities
"""

from tank_vendor.flow_data_sdk.base import model as medm_model
from tank_vendor.flow_data_sdk.base.exceptions import GQLAPIError

from tank_vendor.flow_integration_sdk.exceptions import FlowError
from tank_vendor.flow_integration_sdk.globals import get_client
from tank_vendor.flow_integration_sdk.objects import FlowAsset
from tank_vendor.flow_integration_sdk.publish import (
    publish_new_asset,
    TypeComponentSpec,
)
from tank_vendor.flow_integration_sdk.schema import get_schema_id
from tank_vendor.flow_integration_sdk.utils import get_logger


# Asset name templates
ASSET = "FPT Asset - %s"
ASSET_TYPE = "FPT Asset Type - %s"
ASSET_TYPES = "FPT Asset Types"
EPISODE = "FPT Episode - %s"
PIPELINE_STEP = "FPT %s Step - %s"
SEQUENCE = "FPT Sequence - %s"
SHOT = "FPT Shot - %s"
SHOT_TYPE = "FPT Shot Type - %s"
SHOT_TYPES = "FPT Shot Types"

# Schema types
DEL_ASSET_TYPE = "type.deliverable.asset"
DEL_EPISODE_TYPE = "type.deliverable.episode"
DEL_SEQUENCE_TYPE = "type.deliverable.sequence"
DEL_SHOT_TYPE = "type.deliverable.shot"
DYN_ENUM_TYPE = "type.dynamicEnum"
DYN_ENUM_VALUE_TYPE = "type.dynamicEnumValue"
EXTERNAL_ID_TYPE_ID = "autodesk.me:component.externalId-1.0.0"
PIPELINE_STEP_TYPE = "type.pipelineStep"

# Asset map -> maps asset name to asset id
# (cached for quick reference)
ASSET_MAP = {}


class DynEnumComponentSpec(TypeComponentSpec):
    """Specifications for creating a dynamic enum type component.
    This is a component used to designate an enum. It's list values point
    to assets representing dynamic enum values.
    """

    def __init__(
        self,
        values: list[str],
        type_scope: str = "",
        property_scope: str = "",
    ):
        """
        Args:
            values: List of asset ids representing "dynamic enum values".
                    (i.e. assets with a DYN_ENUM_VALUE_TYPE component on it)
            type_sope: The asset or component type this enum is used for (optional).
            property_scope: The property name this enum is used for (optional).
            icon: Path to icon file to be stored with enum member.
                  This will get uploaded as a binary property on the component.
        """
        super().__init__(get_schema_id(DYN_ENUM_TYPE), "Dynamic Enum")

        self.values = values
        self.type_scope = type_scope
        self.property_scope = property_scope

    def create(self) -> medm_model.ComponentData:
        """Create an MEDM component based on specifications."""
        return self.create_component(
            name=self.name,
            type_id=self.type_id,
            values=[self.build_reference_value(v) for v in self.values],
            typeScope=self.type_scope,
            propertyScope=self.property_scope,
        )


class DynEnumValueComponentSpec(TypeComponentSpec):
    """Specifications for creating a dynamic enum value type component.
    This is a component used to designate an asset as representing one valid value within
    a dynamic enum. It can optionally contain rich information about the value for display
    purposes.
    """

    def __init__(
        self,
        value: str,
        code: str = "",
        background_color: str = "",
        icon: str = "",
    ):
        """
        Args:
            value: The string value of the enum member.
            code: An optional code name for the value (e.g. a short form).
            background_color: String representing a colour value (e.g. "(0, 0, 0)").
            icon: Path to icon file to be stored with enum member.
                  This will get uploaded as a binary property on the component.
        """
        super().__init__(get_schema_id(DYN_ENUM_VALUE_TYPE), "Dynamic Enum Value")

        self.value = value
        self.code = code
        self.background_color = background_color
        self.icon = icon  # not used currently

    def create(self) -> medm_model.ComponentData:
        """Create an MEDM component based on specifications."""
        # NOTE: due to the property naming collision for "name",
        #       we cannot leverage base classes create_component() function here.
        # TODO: support icons
        data = {
            "name": self.value,
            "code": self.code,
            "backgroundColor": self.background_color,
        }
        return medm_model.ComponentDataInput(
            name=self.name, data=data, type_id=self.type_id
        )


class PipelineStepComponentSpec(DynEnumValueComponentSpec):
    """Specifications for creating a pipeline step type component.
    This is a component used to designate an enum. It's list values point
    to assets representing dynamic enum values.
    """

    def __init__(
        self,
        value: str,
        code: str = "",
        background_color: str = "",
        icon: str = "",
        type_id: str = "",
    ):
        """
        Args:
            value: The string value of the enum member.
            code: An optional code name for the value (e.g. a short form).
            background_color: String representing a colour value (e.g. "(0, 0, 0)").
            icon: Path to icon file to be stored with enum member.
                  This will get uploaded as a binary property on the component.
        """
        super().__init__(value, code, background_color, icon)

        self._name = "Pipeline Step"
        self.type_id = type_id or get_schema_id(PIPELINE_STEP_TYPE)


def _medm_find_children(parent_id: str, q_filter: str = "") -> list[FlowAsset]:
    """Query MEDM for children under the given parent using an optional filter.

    Args:
        parent_id: Id of parent asset/project.
        q_filter: Filter criteria following MEDM api specs.
                  See https://git.autodesk.com/learning-content/flow/blob/master/clc/AM-DevGuide/source/dg-using-filters.md
                  (NOTE: not all filters supported)

    Returns:
        List of FlowAsset objects.

    Raises:
        FlowError
    """
    client = get_client()

    q_input = medm_model.AssetsByTraversalInput(
        start_at_id=parent_id,  # search under parent
        depth=1,  # search immediate children only
        direction=medm_model.TraverseDirectionEnum.OUTGOING.value,
        filters=q_filter,
    )
    q_children = client.service_asset.assets_by_traversal(q_input)

    try:
        q_children.call()
    except GQLAPIError as exc:
        msg = f"Find children query failed. {exc}"
        raise FlowError(msg) from exc

    # NOTE: the starting asset (i.e. parent) will always be returned in
    #       the asset list, so we must skip that one
    result = [FlowAsset(a) for a in q_children.assets if a.id != parent_id]
    return result


def _medm_search(project_id: str, q_filter: str) -> list[FlowAsset]:
    """Perform global search in MEDM under given project with provided
    filter criteria.

    Args:
        project_id: Id of project to search under.
        q_filter: Filter criteria following MEDM api specs.
                  See https://git.autodesk.com/learning-content/flow/blob/master/clc/AM-DevGuide/source/dg-using-filters.md

    Returns:
        List of FlowAsset objects.

    Raises:
        FlowError
    """
    client = get_client()

    q_input = medm_model.AssetsBySearchInput(
        project_ids=[project_id],
        filter=q_filter,
    )
    q_search = client.service_asset.assets_by_search(q_input)

    try:
        q_search.call()
    except GQLAPIError as exc:
        msg = f"Search query failed. {exc}"
        raise FlowError(msg) from exc

    result = [FlowAsset(a) for a in q_search.results]
    return result


def _match_name(assets: list[FlowAsset], name: str) -> FlowAsset | None:
    """Return asset in list that matches name or None."""
    for asset in assets:
        if asset.name == name:
            return asset
    return None


def _create_types_list(sg_project_id: str, medm_project_id: str, sg, mode: str):
    """Create assets related to Asset Types or Shot Types based on mode provided.
    Valid mode values are "asset" and "shot".
    """
    logger = get_logger(__name__)

    if mode not in ["asset", "shot"]:
        raise ValueError("Invalid mode provided.  Must be 'asset' or 'shot'.")

    LIST_NAME = ASSET_TYPES if mode == "asset" else SHOT_TYPES
    VALUE_NAME = ASSET_TYPE if mode == "asset" else SHOT_TYPE
    ENTITY_NAME = mode.capitalize()

    # Search for existing ASSET_TYPES asset under medm project
    logger.info(f'Checking for existing "{LIST_NAME}" asset in MEDM project...')
    q_filter = f"has.component.type=={get_schema_id(DYN_ENUM_TYPE)};"
    q_filter += f"components[typeId:{get_schema_id(DYN_ENUM_TYPE)}].data.propertyScope=='{ENTITY_NAME} Type'"
    result = _medm_find_children(medm_project_id, q_filter)
    types_asset = result[0] if result else None

    if types_asset:
        logger.info(f'"{LIST_NAME}" asset already exists.')
        # NOTE: we are assuming that Asset Types don't change in SG, and once
        #       they have been mirrored once in MEDM, there is no need to check for updates
        ASSET_MAP[LIST_NAME] = types_asset.id
        return types_asset
    else:
        logger.info(f'"{LIST_NAME}" asset not found. Creating it...')

    # Query SG Asset Types
    logger.info(f"Querying SG {mode} types...")
    sg_project = {"type": "Project", "id": sg_project_id}
    sg_type_field = f"sg_{mode}_type"
    schema = sg.schema_field_read(
        ENTITY_NAME, field_name=sg_type_field, project_entity=sg_project
    )
    sg_types = schema[sg_type_field]["properties"]["valid_values"]["value"]

    # Query existing Asset Type assets within MEDM to avoid re-creating
    # NOTE: only search query supports name matching
    prefix_name = VALUE_NAME.replace("%s", "")
    logger.info(f'Checking for existing "{prefix_name}*" assets in MEDM project...')
    q_filter = f"attribute.name=startswith='{prefix_name}';"
    q_filter += f"attribute.parentId=={medm_project_id};"
    q_filter += f"components.typeId=={get_schema_id(DYN_ENUM_VALUE_TYPE)}"
    dyn_enum_value_assets = _medm_search(medm_project_id, q_filter)

    d_types = {}  # map asset types to ids of asset representing it
    for sg_type in sg_types:
        # Check if asset already exists
        name = VALUE_NAME % sg_type
        existing_asset = _match_name(dyn_enum_value_assets, name)
        if existing_asset:
            logger.info(f'Dynamic Enum Value asset "{name}" already exists.')
            d_types[sg_type] = existing_asset.id
            ASSET_MAP[name] = existing_asset.id
            continue
        logger.info(f'Creating Dynamic Enum Value asset "{name}"...')
        # Publish a new asset representing the asset type
        type_comp = DynEnumValueComponentSpec(value=sg_type)
        medm_asset = publish_new_asset(
            name=name,
            parent_id=medm_project_id,
            description=f"{sg_type} {ENTITY_NAME} Type",
            components=[type_comp],
        )
        d_types[sg_type] = medm_asset.id
        ASSET_MAP[name] = medm_asset.id

    # Publish a new asset repesenting the list of asset types
    logger.info(f'Creating Dynamic Enum asset "{LIST_NAME}"...')
    type_comp = DynEnumComponentSpec(
        values=d_types.values(),
        property_scope=f"{ENTITY_NAME} Type",
    )
    medm_asset = publish_new_asset(
        name=LIST_NAME,
        parent_id=medm_project_id,
        description=f"{ENTITY_NAME} Types list",
        components=[type_comp],
    )
    logger.info(f"SG {ENTITY_NAME} Types successfully mirrored in MEDM.")
    ASSET_MAP[LIST_NAME] = medm_asset.id
    return FlowAsset(medm_asset)


def _create_pipeline_steps(
    sg_project_id: str, medm_project_id: str, sg
) -> list[FlowAsset]:
    """Create pipeline step assets in MEDM to represent FPT pipeline steps."""
    logger = get_logger(__name__)

    # Query SG Pipeline Steps
    logger.info("Querying SG pipeline steps...")
    steps = sg.find("Step", [], ["code", "short_name", "entity_type", "color"])

    # Query existing Pipeline Step assets within MEDM to avoid re-creating
    wildcard_name = PIPELINE_STEP.replace("%s", "*")
    logger.info(f'Checking for existing "{wildcard_name}" assets in MEDM project...')
    q_filter = f"has.component.type=={get_schema_id(PIPELINE_STEP_TYPE)}"
    step_assets = _medm_find_children(medm_project_id, q_filter)

    for step in steps:
        # NOTE: entity_type not used for now...
        step_name = step["code"]
        step_code = step["short_name"]
        step_color = step["color"]
        step_type = step["entity_type"]
        if step_type not in ["Asset", "Shot"]:
            # Ignore other types for now (e.g. "Level")
            continue
        # Check if asset already exists
        name = PIPELINE_STEP % (step_type, step_name)
        existing_asset = _match_name(step_assets, name)
        if existing_asset:
            logger.info(f'Pipeline Step asset "{name}" already exists.')
            ASSET_MAP[name] = existing_asset.id
            continue
        logger.info(f'Creating Pipeline Step asset "{name}"...')
        # Publish a new asset representing the asset type
        type_comp = PipelineStepComponentSpec(
            value=step_name,
            code=step_code,
            background_color=step_color,
            type_id=get_schema_id(f"{PIPELINE_STEP_TYPE}.{step_type.lower()}"),
        )
        medm_asset = publish_new_asset(
            name=name,
            parent_id=medm_project_id,
            description=f"{step_name} pipeline step ({step_type})",
            components=[type_comp],
        )
        ASSET_MAP[name] = medm_asset.id


def run_project_setup(sg_project_id: str, medm_project_id: str, sg):
    """Populate MEDM project with a mirror of existing entities and other relevant
    data in FPT.

    The following assets need to be created under the parent project:
        - ASSET_TYPES -> one asset that contains list of all Asset Types in FPT project
        - ASSET_TYPE* -> an asset for each Asset Type in FPT project
        - PIPELINE_STEP* -> an asset for each Pipeline Step in FPT project
        - ASSET* -> an asset for each Asset entity in FPT project
            - tracks its FPT id
            - tracks its ASSET_TYPE
        - EPISODE* -> an asset for each Episode entity in FPT project
            - tracks its FPT id
        - SEQUENCE* -> an asset for each Sequence entity in FPT project
            - tracks its FPT id
            - tracks its episode (optional)
        - SHOT* -> an asset for each Shot entity in FPT project
            - tracks its FPT id
            - tracks its sequence

    Args:
        sg_project_id: Flow Production Tracking project id.
        medm_project_id: Flow Asset Management project id.
        sg: Handle to shotgun api.
    """
    logger = get_logger(__name__)
    logger.info("-------- BEGIN PROJECT SET UP... ---------")

    # Create ASSET_TYPES and ASSET_TYPE* assets if necessary
    _create_types_list(sg_project_id, medm_project_id, sg, "asset")

    # Create SHOT_TYPES and SHOT_TYPE* assets if necessary
    _create_types_list(sg_project_id, medm_project_id, sg, "shot")

    # Create PIPELINE_STEP* assets if necessary
    _create_pipeline_steps(sg_project_id, medm_project_id, sg)

    logger.info("-------- PROJECT SET UP COMPLETE! ---------")
