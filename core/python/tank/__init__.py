"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------
"""

# make sure that all sub-modules are imported at the same as the main module
from . import platform
from . import util

# core functionality
from .api import Tank, tank_from_path
from .errors import TankError, TankEngineInitError
from .template import TemplatePath, TemplateString
from .hook import Hook
