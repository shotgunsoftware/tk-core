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
    ComponentSpec,
    publish_new_asset,
    publish_new_revision,
    TypeComponentSpec,
)
from tank_vendor.flow_integration_sdk.schema import get_schema_id
from tank_vendor.flow_integration_sdk.utils import get_logger


# Asset name templates
ASSET_TYPE = "FPT Asset Type - %s"
ASSET_TYPES = "FPT Asset Types"
NO_ASSET_TYPE = "Assets with no Type"
NO_EPISODE = "Sequences with no Episode"
NO_SEQUENCE = "Shots with no Sequence"
PIPELINE_STEP = "FPT %s Step - %s"
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
PIPELINE_STEPS_TYPE = "component.pipelineSteps"

# Asset map -> maps asset name to asset id
# (cached for quick reference)
ASSET_MAP = {}


class DeliverableComponentSpec(TypeComponentSpec):
    """Specifications for creating a deliverable type component.
    This is a component used to designate an asset as a SG deliverable entity.
    Namely, an Asset, Shot, Sequence or Episode.
    """

    pass


class DeliverableAssetComponentSpec(DeliverableComponentSpec):
    """Specifications for an Asset deliverable."""

    def __init__(
        self,
        asset_type: str = "",
    ):
        """
        Args:
            asset_type: Optional SG asset type designation.
        """
        super().__init__(get_schema_id(DEL_ASSET_TYPE), "Deliverable Asset")

        self.asset_type = asset_type

    def create(self) -> medm_model.ComponentData:
        """Create an MEDM component based on specifications."""
        # NOTE: due to an issue on the medm side, assetType property is just
        #       a string for now...
        return self.create_component(
            name=self.name,
            type_id=self.type_id,
            assetType=self.asset_type,
        )


class DeliverableEpisodeComponentSpec(DeliverableComponentSpec):
    """Specifications for an Episode deliverable."""

    def __init__(self):
        super().__init__(get_schema_id(DEL_EPISODE_TYPE), "Deliverable Episode")


class DeliverableSequenceComponentSpec(DeliverableComponentSpec):
    """Specifications for an Sequence deliverable."""

    def __init__(
        self,
        episode_id: str = "",
    ):
        """
        Args:
            episode_id: Optional MEDM id of episode this sequence belongs to.
        """
        super().__init__(get_schema_id(DEL_SEQUENCE_TYPE), "Deliverable Sequence")

        self.episode_id = episode_id

    def create(self) -> medm_model.ComponentData:
        """Create an MEDM component based on specifications."""
        if self.episode_id:
            episode = self.build_reference_value(self.episode_id)
        else:
            episode = None
        return self.create_component(
            name=self.name,
            type_id=self.type_id,
            episode=episode,
        )


class DeliverableShotComponentSpec(DeliverableComponentSpec):
    """Specifications for an Shot deliverable."""

    def __init__(
        self,
        shot_type: str = "",
        sequence_id: str = "",
    ):
        """
        Args:
            shot_type: Optional SG Shot Type that shot is categorized under.
            sequence_id: Optional MEDM id of sequence this shot belongs to.
        """
        super().__init__(get_schema_id(DEL_SHOT_TYPE), "Deliverable Shot")

        self.shot_type = shot_type
        self.sequence_id = sequence_id

    def create(self) -> medm_model.ComponentData:
        """Create an MEDM component based on specifications."""
        # NOTE: due to an issue on the medm side, shotType property is just
        #       a string for now...
        return self.create_component(
            name=self.name,
            type_id=self.type_id,
            sequence=self.build_reference_value(self.sequence_id),
            shotType=self.shot_type,
        )


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

    def create(self, **kwargs) -> medm_model.ComponentData:
        """Create an MEDM component based on specifications."""
        # NOTE: due to the property naming collision for "name",
        #       we cannot leverage base classes create_component() function here.
        # TODO: support icons
        data = {
            "name": self.value,
            "code": self.code,
            "backgroundColor": self.background_color,
        }
        # Append any additional properties
        for k, v in kwargs.items():
            data[k] = v
        return medm_model.ComponentDataInput(
            name=self.name, data=data, type_id=self.type_id
        )


class ExternalIdComponentSpec(ComponentSpec):
    """Specifications for creating a external id component.
    This is a component used to designate the SG id of the entity an asset
    is mirroring in MEDM.
    """

    def __init__(
        self,
        entity_type: str,
        entity_id: str,
    ):
        """
        Args:
            entity_type: The SG entity type.
            entity_id: The SG entity id.
        """
        self.entity_type = entity_type
        self.entity_id = entity_id

    def create(self, **kwargs) -> medm_model.ComponentData:
        """Create an MEDM component based on specifications."""
        return self.create_component(
            name="sgEntityId",
            type_id=EXTERNAL_ID_TYPE_ID,
            id=f"{self.entity_type}:{self.entity_id}",
        )


class PipelineStepComponentSpec(DynEnumValueComponentSpec):
    """Specifications for creating a pipeline step type component.
    This is a component used to designate an enum. It's list values point
    to assets representing dynamic enum values.
    """

    def __init__(
        self,
        value: str,
        entity_type: str,
        code: str = "",
        background_color: str = "",
        icon: str = "",
    ):
        """
        Args:
            value: The string value of the enum member.
            entity_type: SG entity type that this pipeline step is categorized under.
            code: An optional code name for the value (e.g. a short form).
            background_color: String representing a colour value (e.g. "(0, 0, 0)").
            icon: Path to icon file to be stored with enum member.
                  This will get uploaded as a binary property on the component.
        """
        super().__init__(value, code, background_color, icon)

        self._name = "Pipeline Step"
        self.type_id = get_schema_id(PIPELINE_STEP_TYPE)
        self.entity_type = entity_type

    def create(self) -> medm_model.ComponentData:
        """Create an MEDM component based on specifications."""
        # Use super class create() but send in extra property
        return super().create(entityType=self.entity_type)


class PipelineStepsComponentSpec(ComponentSpec):
    """Specifications for creating a pipeline steps component.
    This is a component used to designate the list of pipeline steps associated
    with an Asset or Shot deliverable.
    """

    def __init__(
        self,
        pipeline_steps: list[str],
    ):
        """
        Args:
            pipeline_steps: List of ids to pipeline step assets in MEDM.
        """
        self.pipeline_steps = pipeline_steps

    def create(self, **kwargs) -> medm_model.ComponentData:
        """Create an MEDM component based on specifications."""

        return self.create_component(
            name="Pipeline Steps",
            type_id=get_schema_id(PIPELINE_STEPS_TYPE),
            targetStep=[self.build_reference_value(p) for p in self.pipeline_steps],
        )


def _medm_search(
    project_id: str, q_filter: str, parent_id: str = ""
) -> list[FlowAsset]:
    """Perform global search in MEDM under given project with provided
    filter criteria.

    Args:
        project_id: Id of project to search under.
        q_filter: Filter criteria following MEDM api specs.
                  See https://git.autodesk.com/learning-content/flow/blob/master/clc/AM-DevGuide/source/dg-using-filters.md
        parent_id: Parent will default to project unless explicitly
                   overridden by this parameter.
                   By default only immediate children will be searched.
                   Set parent_id = "*" for global search.

    Returns:
        List of FlowAsset objects.

    Raises:
        FlowError
    """
    client = get_client()

    # Search under parent, and only include non-deleted assets
    parent_id = parent_id or project_id
    q_filter_pre = "attribute.deletionState=='NOT_DELETED';"
    if parent_id != "*":
        q_filter_pre += f"attribute.parentId=={parent_id};"

    q_input = medm_model.AssetsBySearchInput(
        project_ids=[project_id],
        filter=q_filter_pre + q_filter,
    )
    q_search = client.service_asset.assets_by_search(q_input)

    try:
        q_search.call()
    except GQLAPIError as exc:
        msg = f"Search query failed. {exc}"
        raise FlowError(msg) from exc

    result = [FlowAsset(a) for a in q_search.results]
    return result


def _match_name(
    assets: list[FlowAsset], name: str, sg_id: str = ""
) -> FlowAsset | None:
    """Return asset in list that matches name or None.
    If provided, also match against SG id on the ExternalId component.
    """
    for asset in assets:
        if asset._entity.deletion_state != medm_model.AssetDeletionState.NOT_DELETED:
            continue  # ignore deleted assets
        if asset.name == name:
            if sg_id:
                ext_id_comp = asset.find_component(type_id=EXTERNAL_ID_TYPE_ID)
                if (
                    ext_id_comp
                    and ext_id_comp.properties.get("id").split(":")[-1] == sg_id
                ):
                    return asset
            else:
                return asset
    return None


def _create_types_list(sg_project_id: str, medm_project_id: str, sg, mode: str):
    """Create assets related to Asset Types or Shot Types based on mode provided.
    Valid mode values are "asset" and "shot".

    Raises:
        ValueError
    """
    logger = get_logger(__name__)

    if mode not in ["asset", "shot"]:
        raise ValueError("Invalid mode provided.  Must be 'asset' or 'shot'.")

    LIST_NAME = ASSET_TYPES if mode == "asset" else SHOT_TYPES
    VALUE_NAME = ASSET_TYPE if mode == "asset" else SHOT_TYPE
    ENTITY_NAME = mode.capitalize()

    # Search for existing ASSET_TYPES asset under medm project
    logger.info(f'Checking for existing "{LIST_NAME}" asset in MEDM project...')
    q_filter = f"attribute.name=='{LIST_NAME}';"
    q_filter += f"components.typeId=={get_schema_id(DYN_ENUM_TYPE)}"
    result = _medm_search(medm_project_id, q_filter)
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
    q_filter += f"components.typeId=={get_schema_id(DYN_ENUM_VALUE_TYPE)}"
    dyn_enum_value_assets = _medm_search(medm_project_id, q_filter)

    # Add an explicit "no type" item to host Assets with no type
    # NOTE: not necessary for Shots because shots are organized
    #       under sequences and not types in the hierarchy.
    if mode == "asset":
        sg_types.append(NO_ASSET_TYPE)

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


def _create_pipeline_steps(sg_project_id: str, medm_project_id: str, sg):
    """Create pipeline step assets in MEDM to represent FPT pipeline steps."""
    logger = get_logger(__name__)

    # Query SG Pipeline Steps
    logger.info("Querying SG pipeline steps...")
    steps = sg.find("Step", [], ["code", "short_name", "entity_type", "color"])

    # Query existing Pipeline Step assets within MEDM to avoid re-creating
    wildcard_name = PIPELINE_STEP.replace("%s", "*")
    logger.info(f'Checking for existing "{wildcard_name}" assets in MEDM project...')
    q_filter = f"components.typeId=={get_schema_id(PIPELINE_STEP_TYPE)}"
    step_assets = _medm_search(medm_project_id, q_filter)

    for step in steps:
        step_name = step["code"]
        step_code = step["short_name"]
        step_color = step["color"]
        step_type = step["entity_type"]
        if step_type not in ["Asset", "Shot"]:
            # Ignore other types for now (e.g. "Level")
            continue
        type_comp = PipelineStepComponentSpec(
            value=step_name,
            code=step_code,
            background_color=step_color,
            entity_type=step_type,
        )
        # Check if asset already exists
        name = PIPELINE_STEP % (step_type, step_name)
        existing_asset = _match_name(step_assets, name)
        if existing_asset:
            logger.info(f'Pipeline Step asset "{name}" already exists.')
            ASSET_MAP[name] = existing_asset.id
            step_comp = existing_asset.find_component(
                type_id=get_schema_id(PIPELINE_STEP_TYPE)
            )
            orig_step_code = step_comp.properties.get("code")
            orig_step_color = step_comp.properties.get("backgroundColor")
            if orig_step_code != step_code or orig_step_color != (step_color or "null"):
                logger.info(f'Changes detected. Updating "{name}" asset...')
                publish_new_revision(
                    existing_asset.id,
                    components=[type_comp],
                )
            continue
        logger.info(f'Creating Pipeline Step asset "{name}"...')
        # Publish a new asset representing the asset type
        medm_asset = publish_new_asset(
            name=name,
            parent_id=medm_project_id,
            description=f"{step_name} pipeline step ({step_type})",
            components=[type_comp],
        )
        ASSET_MAP[name] = medm_asset.id


def _get_entity_pipeline_steps(
    entity_type: str, entity_id: str, sg
) -> PipelineStepsComponentSpec:
    """Query the pipeline steps that are attached to the tasks associated
    with the given SG entity.

    Args:
        entity_type: Valid values are "Asset" and "Shot".
        entity_id: Id of SG entity.
        sg: SG API handle.

    Raises:
        ValueError
        RuntimeError
    """
    if entity_type not in ["Asset", "Shot"]:
        raise ValueError("Invalid entity_type provided.  Must be 'Asset' or 'Shot'.")

    # Query tasks associated with entity
    tasks = sg.find(
        "Task",
        [
            ["entity", "is", {"type": entity_type, "id": entity_id}],
        ],
        ["step", "step.Step.entity_type"],
    )
    # Map pipeline step asspcoated with each task to MEDM ids of pipeline step proxy assets
    pipeline_step_ids = []
    for task in tasks:
        step_name = task["step"]["name"]
        step_type = task["step.Step.entity_type"]
        step_asset_name = PIPELINE_STEP % (step_type, step_name)
        if step_asset_name not in ASSET_MAP:
            raise RuntimeError(f'Could not find MEDM proxy asset "{step_asset_name}".')
        step_asset_id = ASSET_MAP[step_asset_name]
        # Pipeline steps might be duplicated across tasks, keep list unique
        if step_asset_id not in pipeline_step_ids:
            pipeline_step_ids.append(step_asset_id)

    # Generate a component spec listing the associated pipeline specs that
    # can be added to a Shot or Asset deliverable
    return PipelineStepsComponentSpec(pipeline_steps=pipeline_step_ids)


def _compare_pipeline_steps(pipesteps_comp_spec, pipesteps_comp) -> bool:
    """Compare the pipeline steps in component specs vs. in component list.
    Return True if they are equivalent, otherwise False.
    """
    new_pipestep_ids = pipesteps_comp_spec.pipeline_steps
    # this will be an array of data blocks
    target_step_data = pipesteps_comp.properties["targetStep"]
    old_pipestep_ids = [data["objectId"]["id"] for data in target_step_data]
    return set(new_pipestep_ids) == set(old_pipestep_ids)


def _create_asset_deliverables(sg_project_id: str, medm_project_id: str, sg):
    """Create assets in MEDM to represent proxies of SG Assets."""
    logger = get_logger(__name__)

    # Query Asset entities in SG
    sg_assets = sg.find(
        "Asset",
        [["project", "is", {"type": "Project", "id": sg_project_id}]],
        ["id", "code", "sg_asset_type"],
    )

    # Search for existing entities of same type in MEDM project
    logger.info("Checking for existing Asset deliverable assets in MEDM project...")
    q_filter = f"components.typeId=={get_schema_id(DEL_ASSET_TYPE)}"
    memd_assets = _medm_search(medm_project_id, q_filter)

    for sg_asset in sg_assets:
        sg_name = sg_asset["code"]
        sg_id = sg_asset["id"]
        sg_asset_type = sg_asset["sg_asset_type"]
        # Generate components (do it early because we may need it for updating
        # as well as creation)
        type_comp = DeliverableAssetComponentSpec(asset_type=sg_asset_type)
        ext_id_comp = ExternalIdComponentSpec(entity_type="Asset", entity_id=sg_id)
        pipeline_steps_comp = _get_entity_pipeline_steps("Asset", sg_id, sg)
        # Check if asset already exists
        name = sg_name
        map_name = (
            f"{name}:{sg_id}"  # for deliverables add sg id to guarantee uniqueness
        )
        existing_asset = _match_name(memd_assets, name, str(sg_id))
        if existing_asset:
            logger.info(f'Asset deliverable "{name}" already exists.')
            ASSET_MAP[map_name] = existing_asset.id
            # Check for changes that could require an update
            orig_type_comp = existing_asset.find_component(
                type_id=get_schema_id(DEL_ASSET_TYPE)
            )
            orig_asset_type = orig_type_comp.properties.get("assetType")
            orig_pipeline_steps_comp = existing_asset.find_component(
                type_id=get_schema_id(PIPELINE_STEPS_TYPE)
            )
            if orig_asset_type != (
                sg_asset_type or "null"
            ) or not _compare_pipeline_steps(
                pipeline_steps_comp, orig_pipeline_steps_comp
            ):
                logger.info(f'Changes detected. Updating "{name}" asset...')
                publish_new_revision(
                    existing_asset.id,
                    components=[type_comp, ext_id_comp, pipeline_steps_comp],
                )
            continue
        logger.info(f'Creating Asset deliverable asset "{name}"...')
        # Publish a new asset representing the asset type
        medm_asset = publish_new_asset(
            name=name,
            parent_id=medm_project_id,
            description=f'Proxy for Asset deliverable "{sg_name}".',
            components=[type_comp, ext_id_comp, pipeline_steps_comp],
        )
        ASSET_MAP[map_name] = medm_asset.id


def _create_episode_deliverables(sg_project_id: str, medm_project_id: str, sg):
    """Create assets in MEDM to represent proxies of SG Episodes."""
    logger = get_logger(__name__)

    # Query Episode entities in SG
    sg_episodes = sg.find(
        "Episode",
        [["project", "is", {"type": "Project", "id": sg_project_id}]],
        ["id", "code"],
    )

    # Search for existing entities of same type in MEDM project
    logger.info("Checking for existing Episode deliverable assets in MEDM project...")
    q_filter = f"components.typeId=={get_schema_id(DEL_EPISODE_TYPE)}"
    memd_assets = _medm_search(medm_project_id, q_filter)

    # Add a "no episode" placeholder asset to host sequences with no episode
    sg_episodes.append({"code": NO_EPISODE, "id": None})

    for sg_episode in sg_episodes:
        sg_name = sg_episode["code"]
        sg_id = sg_episode["id"]
        # Check if asset already exists
        name = sg_name
        map_name = (
            f"{name}:{sg_id}"  # for deliverables add sg id to guarantee uniqueness
        )
        existing_asset = _match_name(memd_assets, name, str(sg_id) if sg_id else "")
        if existing_asset:
            logger.info(f'Episode deliverable "{name}" already exists.')
            ASSET_MAP[map_name] = existing_asset.id
            continue
        logger.info(f'Creating Episode deliverable asset "{name}"...')
        # Publish a new asset representing the asset type
        components = [DeliverableEpisodeComponentSpec()]
        if sg_id:
            components.append(
                ExternalIdComponentSpec(entity_type="Episode", entity_id=sg_id)
            )
        medm_asset = publish_new_asset(
            name=name,
            parent_id=medm_project_id,
            description=f'Proxy for Episode deliverable "{sg_name}".',
            components=components,
        )
        ASSET_MAP[map_name] = medm_asset.id


def _create_sequence_deliverables(sg_project_id: str, medm_project_id: str, sg):
    """Create assets in MEDM to represent proxies of SG Sequences."""
    logger = get_logger(__name__)

    # Query Sequence entities in SG
    # NOTE: depending on project configuration, episode info
    #       could be under "episode" or "sg_episode" field, so must fetch both
    sg_sequences = sg.find(
        "Sequence",
        [["project", "is", {"type": "Project", "id": sg_project_id}]],
        [
            "id",
            "code",
            "sg_episode",
            "episode",
        ],
    )

    # Search for existing entities of same type in MEDM project
    logger.info("Checking for existing Sequence deliverable assets in MEDM project...")
    q_filter = f"components.typeId=={get_schema_id(DEL_SEQUENCE_TYPE)}"
    memd_assets = _medm_search(medm_project_id, q_filter)

    # Add a "no episode" placeholder asset to host sequences with no episode
    sg_sequences.append({"code": NO_SEQUENCE, "id": None})

    for sg_sequence in sg_sequences:
        sg_name = sg_sequence["code"]
        sg_id = sg_sequence["id"]
        # Check if asset already exists
        name = sg_name
        map_name = (
            f"{name}:{sg_id}"  # for deliverables add sg id to guarantee uniqueness
        )
        existing_asset = _match_name(memd_assets, name, str(sg_id) if sg_id else "")
        if existing_asset:
            logger.info(f'Sequence deliverable "{name}" already exists.')
            ASSET_MAP[map_name] = existing_asset.id
            continue
        logger.info(f'Creating Sequence deliverable asset "{name}"...')
        # Find episode proxy to be associated
        ep_field = "episode" if "episode" in sg_sequence else "sg_episode"
        if sg_name == NO_SEQUENCE:
            ep_id = ""
        else:
            if sg_sequence[ep_field]:
                ep_name = (
                    f'{sg_sequence[ep_field]["code"]}:{sg_sequence[ep_field]["id"]}'
                )
            else:
                ep_name = NO_EPISODE
            if ep_name not in ASSET_MAP:
                raise RuntimeError(f'Could not find MEDM proxy episode "{ep_name}".')
            ep_id = ASSET_MAP[ep_name]
        # Publish a new asset representing the asset type
        components = [DeliverableSequenceComponentSpec(episode_id=ep_id)]
        if sg_id:
            components.append(
                ExternalIdComponentSpec(entity_type="Sequence", entity_id=sg_id)
            )
        medm_asset = publish_new_asset(
            name=name,
            parent_id=medm_project_id,
            description=f'Proxy for Sequence deliverable "{sg_name}".',
            components=components,
        )
        ASSET_MAP[map_name] = medm_asset.id


def _create_shot_deliverables(sg_project_id: str, medm_project_id: str, sg):
    """Create assets in MEDM to represent proxies of SG Sequences."""
    logger = get_logger(__name__)

    # Query Shot entities in SG
    # NOTE: depending on project configuration, sequence info
    #       could be under "sequence" or "sg_sequence" field, so must fetch both
    sg_shots = sg.find(
        "Shot",
        [["project", "is", {"type": "Project", "id": sg_project_id}]],
        [
            "id",
            "code",
            "sg_shot_type",
            "sequence.Sequence.code",
            "sequence.Sequence.id",
            "sg_sequence.Sequence.code",
            "sg_sequence.Sequence.id",
        ],
    )

    # Search for existing entities of same type in MEDM project
    logger.info("Checking for existing Shot deliverable assets in MEDM project...")
    q_filter = f"components.typeId=={get_schema_id(DEL_SHOT_TYPE)}"
    memd_assets = _medm_search(medm_project_id, q_filter)

    for sg_shot in sg_shots:
        sg_name = sg_shot["code"]
        sg_id = sg_shot["id"]
        sg_shot_type = sg_shot["sg_shot_type"]
        # Check if asset already exists
        name = sg_name
        map_name = (
            f"{name}:{sg_id}"  # for deliverables add sg id to guarantee uniqueness
        )
        existing_asset = _match_name(memd_assets, name, str(sg_id))
        if existing_asset:
            logger.info(f'Shot deliverable "{name}" already exists.')
            ASSET_MAP[map_name] = existing_asset.id
            continue
        logger.info(f'Creating Shot deliverable asset "{name}"...')
        # Find episode proxy to be associated
        sq_field = "sequence" if "sequence" in sg_shot else "sg_sequence"
        if sg_shot[f"{sq_field}.Sequence.code"]:
            sq_sg_name = sg_shot[f"{sq_field}.Sequence.code"]
            sq_sg_id = sg_shot[f"{sq_field}.Sequence.id"]
            sq_name = f"{sq_sg_name}:{sq_sg_id}"
        else:
            sq_name = NO_SEQUENCE
        if sq_name not in ASSET_MAP:
            raise RuntimeError(f'Could not find MEDM proxy sequence "{sq_name}".')
        sq_id = ASSET_MAP[sq_name]
        # Publish a new asset representing the asset type
        type_comp = DeliverableShotComponentSpec(
            shot_type=sg_shot_type, sequence_id=sq_id
        )
        ext_id_comp = ExternalIdComponentSpec(entity_type="Shot", entity_id=sg_id)
        pipeline_steps_comp = _get_entity_pipeline_steps("Shot", sg_id, sg)
        medm_asset = publish_new_asset(
            name=name,
            parent_id=medm_project_id,
            description=f'Proxy for Shot deliverable "{sg_name}".',
            components=[type_comp, ext_id_comp, pipeline_steps_comp],
        )
        ASSET_MAP[map_name] = medm_asset.id


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

    # Create Asset deliverables for each SG Asset entity
    _create_asset_deliverables(sg_project_id, medm_project_id, sg)

    # Create Episode deliverables for each SG Episode entity
    _create_episode_deliverables(sg_project_id, medm_project_id, sg)

    # Create Sequence deliverables for each SG Sequence entity
    _create_sequence_deliverables(sg_project_id, medm_project_id, sg)

    # Create Shot deliverables for each SG Shot entity
    _create_shot_deliverables(sg_project_id, medm_project_id, sg)

    logger.info("-------- PROJECT SET UP COMPLETE! ---------")
