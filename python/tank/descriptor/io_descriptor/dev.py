# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from __future__ import annotations  # needed for python 3.9 support

import os

from tank_vendor.packaging import version

from ... import LogManager
from ...util import process
from . import git
from .path import IODescriptorPath

log = LogManager.get_logger(__name__)


class IODescriptorDev(IODescriptorPath):
    """
    Represents a local dev item. This item is never downloaded
    into the local storage, you interact with it directly::

        {"type": "dev", "path": "/path/to/app"}

    Optional parameters are possible::

        {"type": "dev", "path": "/path/to/app", "name": "my-app"}

        {"type": "dev",
         "linux_path": "/path/to/app",
         "windows_path": "d:\foo\bar",
         "mac_path": "/path/to/app" }

    Name is optional and if not specified will be determined based on folder path.
    If name is not specified and path is /tmp/foo/bar, the name will set to 'bar'
    """

    def __init__(self, descriptor_dict, sg_connection, bundle_type):
        """
        Constructor

        :param descriptor_dict: descriptor dictionary describing the bundle
        :param sg_connection: Shotgun connection to associated site.
        :param bundle_type: Either AppDescriptor.APP, CORE, ENGINE or FRAMEWORK.
        :return: Descriptor instance
        """
        super().__init__(descriptor_dict, sg_connection, bundle_type)

    def is_dev(self):
        """
        Returns true if this item is intended for development purposes
        """
        return True

    def get_version(self) -> str:
        """
        Returns the version number string for this item.

        Like any path descriptor, this normally returns the version defined
        in the descriptor, or ``Undefined`` if no version is defined.

        As a special case, when no version is defined and the path is the root
        of a git clone, the version is "improved" with information from git, to
        identify exactly which code is in use. See :meth:`_get_git_version`.

        :returns: Version string.
        """
        v = super().get_version()
        if v != self.UNDEFINED_VERSION:
            return v

        return self._get_git_version() or v

    def _get_git_version(self) -> str | None:
        """
        Returns a PEP 440 compliant version derived from git for this item's path.

        The version is derived from ``git describe --tags --long --dirty=.dirty``,
        based on the closest tag:

        - ``--tags`` also matches lightweight tags, which releases use.
        - ``--long`` always yields ``<tag>-<distance>-g<sha>``, even when
          the clone is exactly on the tag.
        - ``--dirty=.dirty`` appends ``.dirty`` when tracked files have
          uncommitted changes, so a modified clone is not reported as the
          committed code.

        That output is converted to a PEP 440 compliant version:

        - ``v1.2.3+g1a2b3c4`` when the clone is exactly on tag ``v1.2.3``.
        - ``v1.2.3.post5+g1a2b3c4`` when the clone is 5 commits past it,
          i.e. a post-release of the tag.
        - ``v1.2.3.post5+g1a2b3c4.dirty`` when it also has uncommitted changes.

        The ``+g<sha>`` local label distinguishes a git clone from a released
        version. If the closest tag does not produce a valid PEP 440 version,
        for example ``release-1.2.3``, no version is derived.

        Only the root of a git clone, i.e. a folder containing ``.git``, is
        described. A folder nested inside a clone, for example a bundle stored
        in a config repository, would otherwise report the version of that
        enclosing repository.

        :returns: Version string, or ``None`` if git cannot describe the path,
            for example because it is not the root of a git clone, has no
            usable tags, or git is not installed.
        """
        # .git is a folder in a regular clone, and a file in worktrees and submodules.
        if not os.path.exists(os.path.join(self._path, ".git")):
            return

        try:
            output = git._check_output(
                [
                    "git",
                    "-C",
                    self._path,
                    "describe",
                    "--tags",
                    "--long",
                    "--dirty=.dirty",
                ]
            )
        except (process.SubprocessCalledProcessError, OSError):
            return

        desc = output.strip()
        if not desc:
            return

        try:
            tag, distance, sha = desc.rsplit("-", 2)
        except ValueError:
            # Not the "<tag>-<distance>-g<sha>" format --long should produce.
            # Be defensive in case a git version or setting changes it.
            return

        if distance == "0":
            git_version = f"{tag}+{sha}"
        else:
            git_version = f"{tag}.post{distance}+{sha}"

        try:
            version.Version(git_version)
        except version.InvalidVersion:
            log.debug(f"Ignoring {git_version!r} from {self._path}: not PEP 440.")
            return

        return git_version
