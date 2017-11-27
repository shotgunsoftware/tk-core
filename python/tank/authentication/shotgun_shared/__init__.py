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
This module contains files which are shared between RV and Toolkit.
"""

# Classes
from .saml2_sso import (  # noqa
    Saml2Sso,
    Saml2SsoError,
    Saml2SsoMissingQtModuleError,
    Saml2SsoMultiSessionNotSupportedError,
)

# Functions
from .saml2_sso import (  # noqa
    get_csrf_key,
    get_csrf_token,
    get_logger,
    get_saml_claims_expiration,
    get_saml_user_name,
    get_session_id,
    has_sso_info_in_cookies,
    is_sso_enabled_on_site,
    set_logger_parent,
)
