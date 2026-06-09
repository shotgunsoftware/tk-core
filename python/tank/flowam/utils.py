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
from tank.pipelineconfig import PipelineConfiguration
from tank.util import yaml_cache


logger = LogManager.get_logger(__name__)


def get_config_flow_settings(pipeline_config: PipelineConfiguration) -> dict:
    """Retrieve Flow settings from config.
    
    Args:
        pipeline_config: PipelineConfiguration object.
                            This is used to determine the location from which to
                            search for the "flow.yml" config file that contains Flow settings.
    
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