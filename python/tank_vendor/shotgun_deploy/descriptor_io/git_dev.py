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
import re
import copy
import uuid
import tempfile

from ..util import subprocess_check_output, execute_git_command
from .base import IODescriptorBase
from ..zipfilehelper import unzip_file
from ..errors import ShotgunDeployError
from ...shotgun_base import ensure_folder_exists

from .. import util
log = util.get_shotgun_deploy_logger()

class IODescriptorGitDev(IODescriptorBase):
    """
    Represents a cloned git repository.

    # location: {"type": "git_dev", "path": "/path/to/repo.git"}

    path can be on the form:

        git@github.com:manneohrstrom/tk-hiero-publish.git
        https://github.com/manneohrstrom/tk-hiero-publish.git
        git://github.com/manneohrstrom/tk-hiero-publish.git
        /full/path/to/local/repo.git
    """

    def __init__(self, bundle_cache_root, location_dict):
        super(IODescriptorGitDev, self).__init__(bundle_cache_root, location_dict)

        self._path = location_dict.get("path")
        # strip trailing slashes - this is so that when we build
        # the name later (using os.basename) we construct it correctly.
        if self._path.endswith("/") or self._path.endswith("\\"):
            self._path = self._path[:-1]

        if self._path is None:
            raise ShotgunDeployError("Descriptor is not valid: %s" % str(location_dict))


    def get_system_name(self):
        """
        Returns a short name, suitable for use in configuration files
        and for folders on disk
        """
        bn = os.path.basename(self._path)
        (name, ext) = os.path.splitext(bn)
        return name

    def get_version(self):
        """
        Returns the version number string for this item
        """
        return "v0.0.0"

    def get_path(self):
        """
        returns the path to the folder where this item resides
        """
        # git@github.com:manneohrstrom/tk-hiero-publish.git -> tk-hiero-publish.git
        # /full/path/to/local/repo.git -> repo.git
        name = os.path.basename(self._path)
        return self._get_local_location("git_dev", name, self.get_version())

    def download_local(self):
        """
        Retrieves this version to local repo.
        Will exit early if app already exists local.
        """
        if self.exists_local():
            # nothing to do!
            return
        target = self.get_path()
        #self.clone(target)

    def get_latest_version(self, constraint_pattern=None):
        """
        Returns a descriptor object that represents the latest version.
        
        :param constraint_pattern: If this is specified, the query will be constrained
        by the given pattern. Version patterns are on the following forms:
        
            - v1.2.3 (means the descriptor returned will inevitably be same as self)
            - v1.2.x 
            - v1.x.x

        :returns: descriptor object
        """
        return self

    def clone(self, target_path):
        """
        Clone the repo into the target path
        
        :param target_path: The target path to clone the repo to
        :raises:            TankError if the clone command fails
        """
        # Note: git doesn't like paths in single quotes when running on 
        # windows - it also prefers to use forward slashes!
        log.debug("Git Cloning %r into %s" % (self, target_path))
        sanitized_repo_path = self._path.replace(os.path.sep, "/")
        execute_git_command("clone -q \"%s\" \"%s\"" % (sanitized_repo_path, target_path))

