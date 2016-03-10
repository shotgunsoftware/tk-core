# Copyright (c) 2016 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

# pending QA environment variable
APP_STORE_QA_MODE_ENV_VAR = "TANK_QA_ENABLED"

# app store: the entity that represents the core api
TANK_CORE_VERSION_ENTITY_TYPE = "CustomNonProjectEntity01"

# app store: the entity representing apps
TANK_APP_ENTITY_TYPE = "CustomNonProjectEntity02"

# app store: the entity representing app versions
TANK_APP_VERSION_ENTITY_TYPE = "CustomNonProjectEntity05"

# app store: the entity representing engines
TANK_ENGINE_ENTITY_TYPE = "CustomNonProjectEntity03"

# app store: the entity representing engine versions
TANK_ENGINE_VERSION_ENTITY_TYPE = "CustomNonProjectEntity04"

# app store: the entity representing frameworks
TANK_FRAMEWORK_ENTITY_TYPE = "CustomNonProjectEntity13"

# app store: the entity representing framework versions
TANK_FRAMEWORK_VERSION_ENTITY_TYPE = "CustomNonProjectEntity09"

# app store: the entity representing configs
TANK_CONFIG_ENTITY_TYPE = "CustomNonProjectEntity07"

# app store: the entity representing config versions
TANK_CONFIG_VERSION_ENTITY_TYPE = "CustomNonProjectEntity08"

# app store: the field containing the zip payload
TANK_CODE_PAYLOAD_FIELD = "sg_payload"

# app store: dummy project required when writing event data to the system
TANK_APP_STORE_DUMMY_PROJECT = {"type": "Project", "id": 64}

# Shotgun: The entity that represents Pipeline Configurations in Shotgun
PIPELINE_CONFIGURATION_ENTITY_TYPE = "PipelineConfiguration"

# the location of the toolkit app store
SGTK_APP_STORE = "https://tank.shotgunstudio.com"

# the manifest file inside a bundle
BUNDLE_METADATA_FILE = "info.yml"

# the generation of the logic that handles cloud based deploy.
# if major changes happen to the way cloud based configs are handled
# by the system, for example requiring any existing deployed cloud
# configs to be re-deployed, this version number should be incremented.
BOOTSTRAP_LOGIC_GENERATION = 3

# readme file for toolkit configurations
CONFIG_README_FILE = "README"

# config file with information about which core to use
CONFIG_CORE_DESCRIPTOR_FILE = "core_api.yml"

# the file that defines which storages a configuration requires
STORAGE_ROOTS_FILE = "roots.yml"

# the implied main storage
PRIMARY_STORAGE_NAME = "primary"

# Configuration file containing shotgun site details
CONFIG_SHOTGUN_FILE = "shotgun.yml"

# Configuration file containing setup and path details
PIPELINECONFIG_FILE = "pipeline_configuration.yml"

# field used to upload a config
SHOTGUN_PIPELINECONFIG_ATTACHMENT_FIELD = "sg_config"

# field used to store a config uri
SHOTGUN_PIPELINECONFIG_URI_FIELD = "sg_config_uri"

# The name of the primary pipeline config
PRIMARY_PIPELINE_CONFIG_NAME = "Primary"

# The name of an unmanaged pipeline config
# Unmanaged pipeline configs don't have a corresponding
# record in Shotgun.
UNMANAGED_PIPELINE_CONFIG_NAME = "Unmanaged"

# The project name for a project with no tank name
# not having a Project.tank_name is okay as long as
# the configuration doesn't use templates.
UNNAMED_PROJECT_NAME = "unnamed"

# descriptor keyword denoting the latest version number
LATEST_DESCRIPTOR_KEYWORD = "latest"

# default namespace
DEFAULT_NAMESPACE = "default"

# descriptor uri separator
DESCRIPTOR_URI_PATH_SCHEME = "sgtk"
DESCRIPTOR_URI_PATH_PREFIX = "descriptor"
DESCRIPTOR_URI_SEPARATOR = ":"

# latest core
LATEST_CORE_DESCRIPTOR = {"type": "app_store", "name": "tk-core", "version": "latest"}

# default shotgun desktop python installations
DESKTOP_PYTHON_MAC = "/Applications/Shotgun.app/Contents/Resources/Python/bin/python"
DESKTOP_PYTHON_WIN = "C:\\Program Files\\Shotgun\\Python\\python.exe"
DESKTOP_PYTHON_LINUX = "/opt/Shotgun/Python/bin/python"
