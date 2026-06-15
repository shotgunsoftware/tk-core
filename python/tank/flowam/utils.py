# Copyright (c) 2026 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""Shared utilities for Flow Integration."""

from __future__ import annotations  # needed for python 3.9 support

import fileseq
import os
import re
from dataclasses import dataclass, asdict

from tank import LogManager
from tank.authentication import flow_auth
from tank.pipelineconfig import PipelineConfiguration
from tank.util import yaml_cache
from tank_vendor.flow_integration_sdk import globals, schema, storage
from tank_vendor.flow_integration_sdk.exceptions import FlowError
from tank_vendor.flow_integration_sdk.publish import (
    ComponentSpec,
    CommentComponentSpec,
    SourceComponentSpec,
    ThumbnailComponentSpec,
    TypeComponentSpec,
    FileSeqComponentSpec,
)
from tank_vendor.flow_integration_sdk.objects import FlowProject, FlowRevision
from tank_vendor.flow_integration_sdk.utils import (
    cleanpath,
    trace,
)

from .constants import FLOW_SCHEMA_CONFIG_PATH


logger = LogManager.get_logger(__name__)


@dataclass
class BaseInputs:
    def format_str(self, tab: int = 0):
        s = ""
        for prop, value in self.__dict__.items():
            s += "\t" * tab + f"{prop} = {value}\n"
        return s.rstrip()

    def validate(self):
        """Do validation of input values."""
        pass

    def asdict(self):
        return asdict(self)

    def log_intro(self, intro_message: str):
        """Log an intro message along with the values of
        input object.
        """

        msg = f"""
    ---------------------------------------
    {intro_message} with inputs:
{self.format_str(tab=3)}
    --------------------------------------"""
        logger.info(msg)


def get_config_flow_settings(pipeline_config: PipelineConfiguration) -> dict:
    """Retrieve Flow settings from config.

    Args:
        pipeline_config: PipelineConfiguration object.
                         This is used to determine the location from which to
                         search for the "flow.yml" config file that contains Flow settings.
                         Config file will be searched in two locations:
                            * {CONFIG ROOT}/config/core/flow.yml
                            * {CONFIG ROOT}/core/flow.yml

    Returns:
        Dictionary result of reading the "flow.yml" config file if found.
        Otherwise, return empty dictionary.
    """
    config_root = pipeline_config.get_config_location()
    if not config_root:
        logger.error("Pipeline config has no config location.")
        return {}

    # Config path if reading from cached config
    override_path_cache = os.path.join(
        config_root,
        "config",
        "core",
        "flow.yml",
    )
    # Config path if reading form dev descriptor
    override_path_dev = os.path.join(
        config_root,
        "core",
        "flow.yml",
    )

    logger.info(f"Checking for Flow config: {override_path_dev}")
    if os.path.exists(override_path_dev):
        return yaml_cache.g_yaml_cache.get(override_path_dev) or {}
    else:
        logger.info(f"Checking for Flow config: {override_path_cache}")
        if os.path.exists(override_path_cache):
            return yaml_cache.g_yaml_cache.get(override_path_cache) or {}
        else:
            logger.error("Flow config could not be found!")
    return {}


def init_flow(pipeline_config: PipelineConfiguration, flow_project_id: str):
    """Do some session set up in order to use the Flow Integration SDK.

    Args:
        pipeline_config: PipelineConfiguration object.
        flow_project_id: The flow project associated with current sg project context.

    Raises:
        RuntimeError
    """
    logger.info("Doing Flow Integration SDK initialization...")
    logger.info(f"Flow AM Project ID: {flow_project_id}")

    # Read flow settings from config
    settings = get_config_flow_settings(pipeline_config)
    flow_endpoint = settings.get("endpoint")
    flow_web_url = settings.get("web_url")
    flow_sandbox_root = settings.get("sandbox_root")
    flow_storage_root = settings.get("storage_root")

    # Configure logger
    globals.set_logger_callback(LogManager().get_logger)
    # Initialize MEDM GQL client
    globals.init_client(flow_endpoint, flow_auth.FlowAuthenticationHandler())
    # Store web url
    globals.set_webapp_url(flow_web_url)
    # Set session collection
    try:
        project = FlowProject(flow_project_id)
    except FlowError as exc:
        msg = f"Could not complete Flow initialization: {exc}"
        raise RuntimeError(msg) from exc
    globals.init_session_collection(
        project.collection_id, project.organization_id, project.group_id
    )
    # Cache custom schema config
    try:
        schema.cache_schema_config(FLOW_SCHEMA_CONFIG_PATH)
    except (RuntimeError, ValueError) as exc:
        msg = "Could not complete Flow initialization: {exc}"
        raise RuntimeError(msg) from exc
    # Configure storage roots
    storage.set_sandbox_root(flow_sandbox_root, create_dir=True)
    storage.set_storage_root(flow_storage_root, create_dir=True)

    logger.info("Initialization complete!")


@trace
def identify_component(file_path: str) -> dict | None:
    """Given a file path, determine if it belongs to an asset, and
    return information identifying the exact component blob that the path
    is associated with.

    NOTE: Only paths within primary storage (NFS cache) can be identified.
    All other paths, including sandbox paths, will return None.

    Args:
        file_path: Absolute path to a file.
        ignore_root: If True, root directory does not need to map to
                     current configured roots. It is recommended to keep
                     this to True if not trying validate full path for optimal
                     performance.

    Returns:
        Dictionary with keys:
            * asset_id -> Id of asset
            * revision_id -> Id of revision
            * version_id -> Id of version
            * component_name -> Name of component
            * blob_index -> Index into binary array of component

        or None if the file path cannot be identified.
    """
    file_path = cleanpath(file_path)

    # Absolute path pattern (expecting a root)
    expr = r".*(?P<comp_path>/[^/]+/((r\d+)|(draft))/.+)"
    m = re.match(expr, file_path)
    if not m:
        # Relative path pattern (expecting to begin with storage id)
        expr = r"(?P<comp_path>[^/]+/((r\d+)|(draft))/.+)"
        m = re.match(expr, file_path)
        if not m:
            # Not an asset path - failed test for overall asset path pattern
            return None
    comp_path = m.group("comp_path")

    # add prepended / to match expected asset path pattern if not present
    if not comp_path.startswith("/"):
        comp_path = "/" + comp_path

    # Parse expected pieces of asset path
    try:
        _, storage_id, rev_num, comp_path = comp_path.split("/", maxsplit=3)
    except ValueError:
        # Not an asset path - unable to parse into key path components
        return None

    # Look up asset based on storage key
    try:
        asset_id = storage.storage_key_to_asset_id(storage_id)
    except FlowError:
        # Not an asset path - storage key component does not map to an asset
        return None

    # Convert revision number to integer
    if rev_num == "draft":
        # Not an asset path - draft paths don't count
        return None
    else:
        try:
            rev_num = int(rev_num.strip("r"))
        except ValueError:
            # Not an asset path - non-int value for revision number component
            return None

    revision_id = FlowRevision.get_revision_id(asset_id, rev_num)
    try:
        # NOTE: Using accessor method rather than constructing new instance
        #       because this will return a cached object if it exists
        #       This is ok since revisions are immutable.
        revision = FlowRevision.get_revision(revision_id)
    except FlowError:
        # Not an asset - revision number is out of range
        return None

    # Determine component and blob index based on component path
    # Try and match against existing binary components on revision
    component = blob_index = None
    bin_comps = revision.get_binary_components()
    if "%" in comp_path:
        # File sequence paths will be stored as a zip file
        comp_path, _, _ = comp_path.rsplit(".", maxsplit=2)
        comp_path += ".zip"
    for comp in bin_comps:
        for i, blob in enumerate(comp.blobs):
            if blob.path == comp_path:
                component = comp
                blob_index = i
                break
    if component is None:
        # Not an asset path - no component blob matches file
        return None

    return {
        "asset_id": asset_id,
        "revision_id": revision_id,
        "version_id": revision.version_id,
        "component_name": component.name,
        "blob_index": blob_index,
    }


@trace
def create_components_for_publish(
    source_paths: list[str],
    thumbnail_path: str = "",
    comment: str = "",
    type_ids: list[str] | None = None,
) -> list[ComponentSpec]:
    """Generate the components relevant to publish a new revision.

    Args:
        source_paths: List of local paths to the source files.
        thumbnail_path: Optional path to thumbnail file.
        comment: Generate a comment component with given comment string.
                 Should only be included if the publish method does not
                 explicitly accept a `comment` parameter.
        type_ids: A list of type ids to be converted into type components.
                  This is only relevant if publishing a new asset direct to remote
                  (i.e. not going through sandbox).
    """
    # Source component contains the source file
    source_comp = SourceComponentSpec(*source_paths)
    components: list[ComponentSpec] = [source_comp]
    # Thumbnail component contains the thumbnail file
    if thumbnail_path:
        thumbnail_comp = ThumbnailComponentSpec(thumbnail_path)
        components.append(thumbnail_comp)
    # Need to add a special file sequence type component if there are
    # multiple source files
    if len(source_paths) > 1:
        sequences = fileseq.findSequencesInList(source_paths)
        if len(sequences) > 1:
            msg = "Ambiguous file sequence provided for publish."
            msg += " Multiple file sequences have been detected in the"
            msg += " source path list. Please input files with common"
            msg += " base name with frame padding (e.g. <name>.####.<ext>)."
            raise FlowError(msg)
        # Determine file format
        pad_len = sequences[0].getPaddingNum(sequences[0].padding())
        frame_expr = f"%0{pad_len}d"
        file_format = os.path.basename(sequences[0].frame(frame_expr))
        components.append(
            FileSeqComponentSpec(
                type_id=schema.get_schema_id(globals.FILE_SEQ_TYPE),
                frame_start=sequences[0].start(),
                frame_end=sequences[0].end(),
                frame_set=str(sequences[0].frameSet()),
                file_format=file_format,
                name=globals.FILE_SEQ_COMP,
            )
        )
    # Add comment if provided
    if comment:
        comment_comp = CommentComponentSpec(comment=comment)
        components.append(comment_comp)
    # Add type components if specified
    type_ids = [] if type_ids is None else type_ids
    for i, type_id in enumerate(type_ids):
        # NOTE: component names must be unique!
        type_comp = TypeComponentSpec(type_id=type_id, name=f"Type {i}")
        components.append(type_comp)
    return components
