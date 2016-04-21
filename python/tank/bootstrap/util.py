# Copyright (c) 2016 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import re
import subprocess

from .errors import ShotgunDeployError
from . import constants
from ..shotgun_base import get_sgtk_logger

def get_shotgun_deploy_logger():
    """
    Returns a logger object suitable for the shotgun deploy module.

    This logger should be used for all logged messages inside
    the shotgun_deploy module. Typically, this this imported
    at the top of a python file::

        from . import util
        log = util.get_shotgun_deploy_logger()

    Then, in the running code, calls are made to the log object.

    :returns: python logger
    """
    return get_sgtk_logger("deploy")

log = get_shotgun_deploy_logger()

def is_toolkit_activated_in_shotgun(sg):
    """
    Checks that toolkit has been activated in sg.

    :return: True if true, false otherwise
    """
    log.debug("Checking if Toolkit is enabled in Shotgun...")
    entity_types = sg.schema_entity_read()
    # returns a dict keyed by entity type
    enabled = constants.PIPELINE_CONFIGURATION_ENTITY_TYPE in entity_types
    log.debug("...enabled: %s" % enabled)
    return enabled


