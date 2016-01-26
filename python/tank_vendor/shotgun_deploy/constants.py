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
TANK_CORE_VERSION_ENTITY = "CustomNonProjectEntity01"

# app store: the entity representing apps
TANK_APP_ENTITY = "CustomNonProjectEntity02"

# app store: the entity representing app versions
TANK_APP_VERSION_ENTITY = "CustomNonProjectEntity05"

# app store: the entity representing engines
TANK_ENGINE_ENTITY = "CustomNonProjectEntity03"

# app store: the entity representing engine versions
TANK_ENGINE_VERSION_ENTITY = "CustomNonProjectEntity04"

# app store: the entity representing frameworks
TANK_FRAMEWORK_ENTITY = "CustomNonProjectEntity13"

# app store: the entity representing framework versions
TANK_FRAMEWORK_VERSION_ENTITY = "CustomNonProjectEntity09"

# app store: the entity representing configs
TANK_CONFIG_ENTITY = "CustomNonProjectEntity07"

# app store: the entity representing config versions
TANK_CONFIG_VERSION_ENTITY = "CustomNonProjectEntity08"

# app store: the field containing the zip payload
TANK_CODE_PAYLOAD_FIELD = "sg_payload"

# app store: dummy project required when writing event data to the system
TANK_APP_STORE_DUMMY_PROJECT = {"type": "Project", "id": 64}

# Shotgun: The entity that represents Pipeline Configurations in Shotgun
PIPELINE_CONFIGURATION_ENTITY = "PipelineConfiguration"

# the location of the toolkit app store
SGTK_APP_STORE = "https://tank.shotgunstudio.com"

# the manifest file inside a bundle
BUNDLE_METADATA_FILE = "info.yml"