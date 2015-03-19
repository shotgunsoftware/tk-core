# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.


# make sure that all sub-modules are imported at the same as the main module
from . import platform
from . import util

# core functionality
from .api import Tank, tank_from_path, tank_from_entity
from .api import Sgtk, sgtk_from_path, sgtk_from_entity
from .errors import TankError, TankEngineInitError, TankAuthenticationError, TankErrorProjectIsSetup
from .template import TemplatePath, TemplateString
from .hook import Hook, get_hook_baseclass

from .deploy.tank_command import list_commands, get_command

# Make sure that the Core Authentication Manager is instantiated is no other is set.
from .util.core_authentication_manager import CoreAuthenticationManager
if not CoreAuthenticationManager.is_activated():
    CoreAuthenticationManager.activate()
