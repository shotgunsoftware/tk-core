# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from .factory import (
    create_io_descriptor,
    descriptor_dict_to_uri,
    descriptor_uri_to_dict,
    is_descriptor_version_missing,
)


def _initialize_descriptor_factory():
    """
    Register the IODescriptor subclasses with the IODescriptorBase factory.
    This complex process for handling the IODescriptor abstract factory
    management is in order to avoid local imports in classes.
    """
    from .appstore import IODescriptorAppStore
    from .base import IODescriptorBase
    from .dev import IODescriptorDev
    from .git_branch import IODescriptorGitBranch
    from .git_tag import IODescriptorGitTag
    from .github_release import IODescriptorGithubRelease
    from .manual import IODescriptorManual
    from .path import IODescriptorPath
    from .shotgun_entity import IODescriptorShotgunEntity

    IODescriptorBase.register_descriptor_factory("app_store", IODescriptorAppStore)
    IODescriptorBase.register_descriptor_factory("dev", IODescriptorDev)
    IODescriptorBase.register_descriptor_factory("path", IODescriptorPath)
    IODescriptorBase.register_descriptor_factory("shotgun", IODescriptorShotgunEntity)
    IODescriptorBase.register_descriptor_factory("git", IODescriptorGitTag)
    IODescriptorBase.register_descriptor_factory("git_branch", IODescriptorGitBranch)
    IODescriptorBase.register_descriptor_factory(
        "github_release", IODescriptorGithubRelease
    )
    IODescriptorBase.register_descriptor_factory("manual", IODescriptorManual)


def _register_custom_descriptors() -> None:
    """
    Import the modules listed in ``SGTK_IO_DESCRIPTOR_MODULES`` and call their
    ``register_io_descriptors(io_descriptor_base)`` function, which registers
    custom types with ``register_descriptor_factory``.

    :raises: RegisterDescriptorError if a module cannot be loaded or registered.
    """
    import importlib
    import os
    import sys

    from .base import IODescriptorBase
    from ..errors import RegisterDescriptorError

    # Desktop overrides PYTHONPATH on startup, so modules need their own search path.
    paths = os.environ.get("SGTK_IO_DESCRIPTOR_PATHS", "")
    search_paths = [p.strip() for p in paths.split(os.pathsep) if p.strip()]
    for path in search_paths:
        if path not in sys.path:
            sys.path.insert(0, path)

    names = [
        n.strip()
        for n in os.environ.get("SGTK_IO_DESCRIPTOR_MODULES", "").split(os.pathsep)
        if n.strip()
    ]

    # Cached modules would keep classes bound to the core before a core swap, so
    # drop the listed packages and anything loaded from the configured paths.
    top_levels = {name.split(".")[0] for name in names}
    roots = tuple(os.path.join(os.path.realpath(p), "") for p in search_paths)
    for module_name, module in list(sys.modules.items()):
        if module_name.split(".")[0] in {"tank", "sgtk", "tank_vendor"}:
            continue
        module_file = getattr(module, "__file__", None)
        if module_name.split(".")[0] in top_levels or (
            roots
            and module_file
            and os.path.realpath(module_file).startswith(roots)
        ):
            sys.modules.pop(module_name, None)

    for name in names:
        try:
            importlib.import_module(name).register_io_descriptors(IODescriptorBase)
        except Exception as e:
            raise RegisterDescriptorError(
                "Failed to register custom IO descriptors from '%s': %s" % (name, e)
            )


_initialize_descriptor_factory()
_register_custom_descriptors()
del _initialize_descriptor_factory
