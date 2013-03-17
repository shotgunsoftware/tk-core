"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Constants relating to the app/engine part of the Tank Stack.

(for constants relating to the low level part of the tank stack, see ..constants)

"""

import os
import glob
from tank_vendor import yaml
from ..errors import TankError 

###############################################################################################
# bundle (apps and engines) constants

# metadata file for engines and apps
BUNDLE_METADATA_FILE = "info.yml"

# Valid data types for use in app/engine settings schemas
TANK_SCHEMA_VALID_TYPES = [
    "str",
    "int",
    "float",
    "bool",
    "list",
    "dict",
    "tank_type",
    "template",
    "hook",
    "shotgun_entity_type",
    "shotgun_permission_group",
    "shotgun_filter"
]

# Types from the list above that expect "str" values.
TANK_SCHEMA_STRING_TYPES = [
    "tank_type",
    "template",
    "hook",
    "shotgun_entity_type",
    "shotgun_permission_group"
]

# a folder to look for an automatically add to the pythonpath
BUNDLE_PYTHON_FOLDER = "python"

# app store approvals mode
APP_STORE_QA_MODE_ENV_VAR = "TANK_QA_ENABLED"

###############################################################################################
# engine constants

# the file to look for that defines and bootstraps an engine
ENGINE_FILE = "engine.py"
# inside the engine location, the folder in which to look for apps
ENGINE_APPS_LOCATION = "apps"
# inside the engine config location, the folder in which to look for hooks
ENGINE_HOOKS_LOCATIONS = "hooks"
# app settings location
ENGINE_APP_SETTINGS_LOCATION = "app_settings"
# inside the engine config location, the folder in which to look for environments
ENGINE_ENV_LOCATIONS = "env"
# the key in the configuration for an engine which holds the environment
ENGINE_CONFIG_ENVIRONMENT_KEY = "environment"

# special shotgun engine stuff
# possible names for shotgun engine
SHOTGUN_ENGINES = ["tk-shotgun", "sg_shotgun", "shotgun"]
# special shotgun environment
SHOTGUN_ENVIRONMENT = "shotgun"

# hook that is executed when a tank instance initializes.
TANK_INIT_HOOK_NAME = "tank_init"

# hook that is executed before a publish is registered in sg.
TANK_PUBLISH_HOOK_NAME = "before_register_publish"

# hook that is executed whenever an engine has initialized
TANK_ENGINE_INIT_HOOK_NAME = "engine_init"

# hook that is executed whenever a bundle has initialized
TANK_BUNDLE_INIT_HOOK_NAME = "bundle_init"

# default value for hooks
TANK_BUNDLE_DEFAULT_HOOK_SETTING = "default"

# hooks that are used during folder creation.
PROCESS_FOLDER_CREATION_HOOK_NAME = "process_folder_creation"

# the name of the built in create folders hook
CREATE_FOLDERS_CORE_HOOK_NAME = "create_folder"
PICK_ENVIRONMENT_CORE_HOOK_NAME = "pick_environment"
PROCESS_FOLDER_NAME_HOOK_NAME = "process_folder_name"

###############################################################################################
# environment cfg constants

# the configuration key inside an environment which holds all the app configs
ENVIRONMENT_CFG_APPS_SECTION = "apps"

# the key that holds the app location dict
ENVIRONMENT_LOCATION_KEY = "location"

###############################################################################################
# app constants

# the file to look for that defines and bootstraps an app
APP_FILE = "app.py"

###############################################################################################
# framework constants

# the file to look for that defines and bootstraps a framework
FRAMEWORK_FILE = "framework.py"

###############################################################################################
# core stuff

CACHE_DB_FILENAME = "path_cache.db"

###############################################################################################
# folder creation (schema) stuff

# ensure that shotgun fields used for folder creation contains sensible chars
VALID_SG_ENTITY_NAME_REGEX = "^[0-9A-Za-z_\-\.]+$"
VALID_SG_ENTITY_NAME_EXPLANATION = ("letters, numbers and the characters period(.), "
                                    "dash(-) and underscore(_)")

