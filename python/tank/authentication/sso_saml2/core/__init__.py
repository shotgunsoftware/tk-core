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

from typing import TYPE_CHECKING

__all__ = [
	"SsoSaml2Core",
]

if TYPE_CHECKING:  # pragma: no cover
	from .sso_saml2_core import SsoSaml2Core as SsoSaml2Core  # noqa: F401


def __getattr__(name):  # pragma: no cover
	if name == "SsoSaml2Core":
		from .sso_saml2_core import SsoSaml2Core as _SsoSaml2Core

		return _SsoSaml2Core
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():  # pragma: no cover
	return sorted(globals().keys() | set(__all__))
