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

from ..util import execute_git_command
from .base import IODescriptorBase

from .. import util

log = util.get_shotgun_deploy_logger()

class IODescriptorGit(IODescriptorBase):
    """
    Base class for git descriptors.

    Abstracts operations around repositories, since all git
    descriptors have a repository associated (via the 'path'
    parameter).
    """

    def __init__(self, descriptor_dict):
        """
        Constructor

        :param descriptor_dict: descriptor dictionary describing the bundle
        :return: Descriptor instance
        """
        super(IODescriptorGit, self).__init__(descriptor_dict)

        self._path = descriptor_dict.get("path")
        # strip trailing slashes - this is so that when we build
        # the name later (using os.basename) we construct it correctly.
        if self._path.endswith("/") or self._path.endswith("\\"):
            self._path = self._path[:-1]

        # Note: the git command always uses forward slashes
        self._sanitized_repo_path = self._path.replace(os.path.sep, "/")

    def _clone_repo(self, target_path):
        """
        Clone the repo into the target path

        :param target_path: The target path to clone the repo to
        :raises:            TankError if the clone command fails
        """
        # Note: git doesn't like paths in single quotes when running on
        # windows - it also prefers to use forward slashes!
        log.debug("Git Cloning %r into %s" % (self, target_path))
        execute_git_command("clone -q \"%s\" \"%s\"" % (self._sanitized_repo_path, target_path))

    def get_system_name(self):
        """
        Returns a short name, suitable for use in configuration files
        and for folders on disk, e.g. 'tk-maya'
        """
        bn = os.path.basename(self._path)
        (name, ext) = os.path.splitext(bn)
        return name

