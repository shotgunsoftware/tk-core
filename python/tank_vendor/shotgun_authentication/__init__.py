# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
The Shotgun Authentication module.

This module provides the user with a dialog or console prompts
to retrieve the login and password from a user in order to authenticate. A session is then
created and stored on disk. Whenever a connection to the Shotgun site is required, those
credentials are reused. If a Toolkit-enabled process is launched a second time, the stored
credentials are reused if available.
"""

from .errors import *
from .shotgun_authenticator import ShotgunAuthenticator
from .defaults_manager import DefaultsManager
from .user import deserialize_user, serialize_user
from .sg_auth_logging import get_logger
