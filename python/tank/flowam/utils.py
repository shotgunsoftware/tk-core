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

import os

from tank import LogManager
from tank.authentication import flow_auth
from tank.pipelineconfig import PipelineConfiguration
from tank.util import yaml_cache
from tank_vendor.flow_integration_sdk import globals, schema, storage
from tank_vendor.flow_integration_sdk.exceptions import FlowError
from tank_vendor.flow_integration_sdk.objects import FlowProject

from .constants import FLOW_SCHEMA_CONFIG_PATH


logger = LogManager.get_logger(__name__)


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

    logger.info("Initialzation complete!")
