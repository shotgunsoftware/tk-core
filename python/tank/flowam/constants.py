# Copyright (c) 2026 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""Constants for Flow Integration."""

import pathlib

# Flow Settings
# -------------
# These are settings names that can be configured within a flow.yml file.
# These attributes are used to prepare a Flow Integration SDK session.

FLOW_AUTH_APP_ID = "auth_application_id"
FLOW_AUTH_BASE_URL = "auth_base_url"
FLOW_AUTH_CALLBACK_URL = "auth_callback_url"
FLOW_ENDPOINT = "endpoint"
FLOW_WEB_URL = "web_url"
FLOW_SANDBOX_ROOT = "sandbox_root"
FLOW_STORAGE_ROOT = "storage_root"

# Location of config for specifying custom schemas used
# in the toolkit Flow integration
FLOW_SCHEMA_CONFIG_PATH = str(pathlib.Path(__file__).resolve().parent) + "/config.json"

# SG Project field that stores the current schema config version,
# used to skip schema provisioning when the version already matches.
FLOW_SCHEMA_VERSION_FIELD = "sg_flow_schema_config_version"
