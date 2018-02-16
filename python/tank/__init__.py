# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

# Toolkit core API version
__version__ = "HEAD"

########################################################################
# Establish pipeline configuration context if needed
# 
# When the tank command executes, or when the python API is imported
# via the API proxy that is available with every non-localized pipeline config,
# an environment variable TANK_CURRENT_PC, is set, pointing at the configuration
# associated with the currently running config. This is to ensure that the right 
# version of the code is associated with the currently running project 
# configuration. 
#
# However, in the case when a cloned configuration has been localized,
# the API proxy has been replaced by the actual core API code.
# In this case, we will set the TANK_CURRENT_PC explicitly.
#
# The logic below is fundamentally to avoid the issue that when a cloned localized
# configuration has its python sgtk/tank module imported directly, it will associate
# itself with the primary config rather than with the config where the code is located. 

import os
import sys

if "TANK_CURRENT_PC" not in os.environ:
    # find the pipeline configuration root, probe for a key file
    # (templates.yml) and use this test to determine if this code is 
    # a core API located inside a pipeline configuration.
    #
    # NOTE! This is a very particular piece of logic, which is also 
    # duplicated inside the tank command and the python proxy wrappers.
    # it is intentionally left here in the init method to highlight that  
    # is unique and special.
    #
    from . import constants
    current_folder = os.path.abspath(os.path.dirname(__file__))
    pipeline_config = os.path.abspath(os.path.join(current_folder, "..", "..", "..", ".."))
    roots_file = os.path.join(pipeline_config, "config", "core", constants.STORAGE_ROOTS_FILE)
    if os.path.exists(roots_file):
        os.environ["TANK_CURRENT_PC"] = pipeline_config

########################################################################

# first import the log manager since a lot of modules require this.
from .log import LogManager

# make sure that all sub-modules are imported at the same as the main module
from . import authentication
from . import descriptor
from . import bootstrap
from . import commands
from . import deploy
from . import folder
from . import platform
from . import util

# core functionality
from .api import Tank, tank_from_path, tank_from_entity, set_authenticated_user, get_authenticated_user
from .api import Sgtk, sgtk_from_path, sgtk_from_entity
from .pipelineconfig_utils import get_python_interpreter_for_config, get_core_python_path_for_config, get_sgtk_module_path

from .context import Context

from .errors import (
    TankError,
    TankErrorProjectIsSetup,
    TankHookMethodDoesNotExistError,
    TankFileDoesNotExistError,
    TankUnreadableFileError,
    TankInvalidInterpreterLocationError,
    TankInvalidCoreLocationError,
    TankNotPipelineConfigurationError
)

# note: TankEngineInitError used to reside in .errors but was moved into platform.errors
from .platform.errors import TankEngineInitError
from .template import Template, TemplatePath, TemplateString
from .hook import Hook, get_hook_baseclass

from .commands import list_commands, get_command, SgtkSystemCommand

from .templatekey import TemplateKey, SequenceKey, IntegerKey, StringKey, TimestampKey
