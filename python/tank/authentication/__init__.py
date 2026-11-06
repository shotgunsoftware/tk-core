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

from .core_defaults_manager import CoreDefaultsManager
from .defaults_manager import DefaultsManager
from .errors import ConsoleLoginWithSSONotSupportedError  # For backward compatibility.
from .errors import (  # noqa
    AuthenticationCancelled,
    AuthenticationError,
    ConsoleLoginNotSupportedError,
    IncompleteCredentials,
    ShotgunAuthenticationError,
    UnresolvableHumanUser,
    UnresolvableScriptUser,
)
from .flow_auth import FlowAuthenticationHandler, get_flow_access_token, get_flow_client
from .shotgun_authenticator import ShotgunAuthenticator
from .user import (  # noqa
    ShotgunSamlUser,
    ShotgunUser,
    ShotgunWebUser,
    deserialize_user,
    serialize_user,
)
from .web_login_support import (
    get_shotgun_authenticator_support_web_login,
    set_shotgun_authenticator_support_web_login,
)
