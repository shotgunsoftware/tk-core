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
    TODO retro compat with tk-nuke .... TODO
    SG-40049

    To remove when we drop support for tk-nuke vX.Y.Z TODO FIXME
    """

    try:
        return object.__getattribute__(__name__, name)
    except AttributeError:
        if name != "sso_saml2_core":
            raise

        import importlib
        import inspect
        import warnings

        frame = inspect.currentframe().f_back
        caller_mod = frame.f_globals.get("__name__", "")
        is_import = caller_mod.startswith("importlib.") or caller_mod == "builtins"

        if not is_import:
            warnings.warn(
                f"Accessing '{__name__}.{name}' directly is deprecated. Please import '{__name__}.{name}' explicitly.",
                DeprecationWarning,
                stacklevel=2,
            )

        return importlib.import_module(f"{__name__}.{name}")
