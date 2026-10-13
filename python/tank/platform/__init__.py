# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.


from . import events

# base classes to derive from
from .application import Application

# Engine management
from .engine import (
    Engine,
    current_engine,
    find_app_settings,
    get_engine_path,
    start_engine,
)
from .errors import (
    TankContextChangeNotSupportedError,
    TankEngineInitError,
    TankMissingEngineError,
    TankMissingEnvironmentFile,
    TankUnresolvedEnvironmentError,
)
from .framework import Framework
from .software_launcher import (
    LaunchInformation,
    SoftwareLauncher,
    SoftwareVersion,
    create_engine_launcher,
)
from .util import (
    change_context,
    current_bundle,
    get_framework,
    get_logger,
    import_framework,
    restart,
)
