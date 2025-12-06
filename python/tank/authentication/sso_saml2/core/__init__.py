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

def __getattr__(name):
    """
    Retro compatibility - SG-40049 - Temporary workaround for compatibility for
    scripts accessing `sgtk.authentication.sso_saml2.core.sso_saml2_core` when
    only importing `sgtk` and not explicitly importing
    `sgtk.authentication.sso_saml2.core.sso_saml2_core`.

    For instance, in tk-nuke <=v0.16.0
    https://github.com/shotgunsoftware/tk-nuke/blob/v0.16.0/engine.py#L396
    This was removed in https://github.com/shotgunsoftware/tk-nuke/pull/125.

	TODO: Remove this after 2026-07.
    """

    try:
        return object.__getattribute__(__name__, name)
    except AttributeError:
        if name != "sso_saml2_core":
            raise

        try:
            import inspect
            frame = inspect.currentframe().f_back
            caller_mod = frame.f_globals.get("__name__", "")
            is_import = caller_mod.startswith("importlib.") or caller_mod == "builtins"
        except Exception:
            # Any error in frame inspection, assume not import context
            is_import = False

        if is_import:
            raise

        deprecation_message = (
            f"Accessing '{__name__}.{name}' directly without explicit import "
            "is deprecated and compatibility will be discontinued after "
            f"September 2026. Explicitly import '{__name__}.{name}' instead."
        )

        import warnings
        warnings.warn(
            deprecation_message,
            DeprecationWarning,
            stacklevel=2,
        )

        try:
            import tank
            logger = tank.LogManager.get_logger(__name__)
            logger.warning(deprecation_message)
        except:
            pass # nosec

        import importlib
        return importlib.import_module(f"{__name__}.{name}")
