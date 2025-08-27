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
This module offers different SSO integration warppers for Shotgun.
"""

from typing import TYPE_CHECKING

# Exceptions
from .core.errors import (  # noqa
    SsoSaml2Error,
    SsoSaml2IncompletePySide2,
    SsoSaml2MissingQtCore,
    SsoSaml2MissingQtGui,
    SsoSaml2MissingQtModuleError,
    SsoSaml2MissingQtNetwork,
    SsoSaml2MultiSessionNotSupportedError,
)

# Functions
from .utils import (  # noqa
    get_saml_claims_expiration,
    has_sso_info_in_cookies,
    has_unified_login_flow_info_in_cookies,
)

from .core.utils import (  # noqa
    get_logger,
    set_logger_parent,
)

# NOTE ABOUT LAZY EXPORTS
# -----------------------
# We intentionally avoid importing Qt-dependent modules at package import time
# to prevent loading PySide2/PySide6 when importing the Toolkit core. To keep
# backward compatibility for consumers that import
#   from tank.authentication.sso_saml2 import SsoSaml2, SsoSaml2Toolkit
# we expose these names lazily via module-level __getattr__. This ensures the
# same public API without triggering Qt imports until actually used.

__all__ = [
    # Public classes (resolved lazily)
    "SsoSaml2",
    "SsoSaml2Toolkit",
    # Public exceptions
    "SsoSaml2Error",
    "SsoSaml2IncompletePySide2",
    "SsoSaml2MissingQtCore",
    "SsoSaml2MissingQtGui",
    "SsoSaml2MissingQtModuleError",
    "SsoSaml2MissingQtNetwork",
    "SsoSaml2MultiSessionNotSupportedError",
    # Public functions
    "get_saml_claims_expiration",
    "has_sso_info_in_cookies",
    "has_unified_login_flow_info_in_cookies",
    "get_logger",
    "set_logger_parent",
]

if TYPE_CHECKING:  # pragma: no cover - used for type checkers only
    from .sso_saml2 import SsoSaml2 as SsoSaml2  # noqa: F401
    from .sso_saml2_toolkit import (
        SsoSaml2Toolkit as SsoSaml2Toolkit,  # noqa: F401
    )


def __getattr__(name):  # pragma: no cover - trivial delegation
    if name == "SsoSaml2":
        from .sso_saml2 import SsoSaml2 as _SsoSaml2

        return _SsoSaml2
    if name == "SsoSaml2Toolkit":
        from .sso_saml2_toolkit import (
            SsoSaml2Toolkit as _SsoSaml2Toolkit,
        )

        return _SsoSaml2Toolkit
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():  # pragma: no cover
    return sorted(globals().keys() | set(__all__))
