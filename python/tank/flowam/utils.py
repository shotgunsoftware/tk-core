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
import glob
import os
import re
import webbrowser
from dataclasses import dataclass, asdict
from typing import TYPE_CHECKING

from tank import LogManager
from tank.authentication import flow_auth
from tank.pipelineconfig import PipelineConfiguration
from tank.util import yaml_cache

if TYPE_CHECKING:
    from tank.context import Context
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
from tank_vendor.flow_integration_sdk.objects import FlowProject
from tank_vendor.flow_integration_sdk.schema_builder import create_pipeline_schemas
from tank_vendor.flow_integration_sdk.utils import trace

from .constants import FLOW_SCHEMA_CONFIG_PATH, FLOW_SCHEMA_VERSION_FIELD

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


def init_flow(
    pipeline_config: PipelineConfiguration,
    sg_connection,
    context: Context,
):
    """Do session set up + schema provisioning for the Flow Integration SDK.

    Args:
        pipeline_config: PipelineConfiguration object, used to read flow
            settings from config.
        sg_connection: Shotgun connection, used to write the schema config
            version back to SG.
        context: The current Toolkit context, used to read the flow project id,
            schema version, and SG project id.

    Raises:
        RuntimeError
    """
    logger.info("Doing Flow Integration SDK initialization...")
    flow_project_id = context.flow_project_id
    sg_project_id = context.project["id"]
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

    # Provision pipeline schemas for CPA collections only
    session_collection = globals.get_session_collection()
    if not session_collection.is_cpa_collection():
        logger.info("Skipping pipeline schema provisioning - not a CPA collection.")
    else:
        current_version = schema.get_schema_config_version(FLOW_SCHEMA_CONFIG_PATH)
        if context.flow_schema_version == current_version:
            logger.info(
                f"Schema config version {current_version} matches. "
                "Skipping schema provisioning."
            )
        else:
            try:
                create_pipeline_schemas(
                    project_id=flow_project_id,
                    config_path=FLOW_SCHEMA_CONFIG_PATH,
                )
                sg_connection.update(
                    "Project",
                    sg_project_id,
                    {FLOW_SCHEMA_VERSION_FIELD: current_version},
                )
            except (
                FlowError,
                RuntimeError,
                ValueError,
                KeyError,
                FileNotFoundError,
            ) as exc:
                msg = f"Could not complete Flow schema provisioning: {exc}"
                raise RuntimeError(msg) from exc

    logger.info("Initialization complete!")


@trace
def create_components_for_publish(
    source_paths: list[str] | None = None,
    thumbnail_path: str = "",
    comment: str = "",
    type_ids: list[str] | None = None,
) -> list[ComponentSpec]:
    """Generate the components relevant to publish a new revision.

    Args:
        source_paths: Optional list of local paths to the source files.
        thumbnail_path: Optional path to thumbnail file.
        comment: Generate a comment component with given comment string.
                 Should only be included if the publish method does not
                 explicitly accept a `comment` parameter.
        type_ids: A list of type ids to be converted into type components.
                  This is only relevant if publishing a new asset direct to remote
                  (i.e. not going through sandbox).
    """
    # Source component contains the source file
    components: list[ComponentSpec] = []
    if source_paths:
        source_comp = SourceComponentSpec(*source_paths)
        components.append(source_comp)
    # Thumbnail component contains the thumbnail file
    if thumbnail_path:
        thumbnail_comp = ThumbnailComponentSpec(thumbnail_path)
        components.append(thumbnail_comp)
    # Need to add a special file sequence type component if there are
    # multiple source files
    if source_paths and len(source_paths) > 1:
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


def open_explorer(dir_path: str):
    """Open a file explorer to the directory path provided.

    Args:
        dir_path: Full path to local directory.
    """
    return webbrowser.open(f"file:///{dir_path}")


def search_file_expression(file_path: str):
    """Search file system for files matching expression that
    uses frame padding of the format "%0Nd" where N is an integer
    denoting number of digits in frame padding.

    If path does not contain a frame padding, search for the path as is.
    """
    expr = r"(?P<base_path>.+\.)%0(?P<frame_pad>\d)d(?P<ext>\..+)"
    m = re.match(expr, file_path)
    if m:
        frame_pad = int(m.group("frame_pad"))
        file_expr = m.group("base_path") + frame_pad * "[0-9]" + m.group("ext")
        file_list = glob.glob(file_expr)
        return file_list
    elif os.path.exists(file_path):
        return [file_path]
    return []
