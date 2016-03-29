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
import copy

from ..util import subprocess_check_output, execute_git_command
from .git import IODescriptorGit
from ..errors import ShotgunDeployError
from ...shotgun_base import ensure_folder_exists

from .. import util
log = util.get_shotgun_deploy_logger()

class IODescriptorGitBranch(IODescriptorGit):
    """
    Represents a commit in git, belonging to a particular branch.

    Branch format:
    location: {"type": "git_branch",
               "path": "/path/to/repo.git",
               "branch": "master",
               "version": "17fedd8a4e3c7c004316af5001331ad2c9e14bd5"}

    Short hashes can be used:
    location: {"type": "git_branch",
               "path": "/path/to/repo.git",
               "branch": "master",
               "version": "17fedd8"}

    path can be on the form:

        git@github.com:manneohrstrom/tk-hiero-publish.git
        https://github.com/manneohrstrom/tk-hiero-publish.git
        git://github.com/manneohrstrom/tk-hiero-publish.git
        /full/path/to/local/repo.git

    The hash can be short, as long as it is unique, e.g. it follows the same logic
    that git is using for shortening its hashes. A recommendation is to use the first
    seven digits to describe a hash that is unique within a repository.
    """

    def __init__(self, descriptor_dict):
        """
        Constructor

        :param descriptor_dict: descriptor dictionary describing the bundle
        :return: Descriptor instance
        """
        # make sure all required fields are there
        self._validate_descriptor(
            descriptor_dict,
            required=["type", "path", "version", "branch"],
            optional=[]
        )

        # call base class
        super(IODescriptorGitBranch, self).__init__(descriptor_dict)

        # path is handled by base class - all git descriptors
        # have a path to a repo
        self._version = descriptor_dict.get("version")
        self._branch = descriptor_dict.get("branch")

    def _get_cache_paths(self):
        """
        Get a list of resolved paths, starting with the primary and
        continuing with alternative locations where it may reside.

        Note: This method only computes paths and does not perform any I/O ops.

        :return: List of path strings
        """
        paths = []

        # to be MAXPATH-friendly, we only use the first seven chars
        short_hash = self._version[:7]

        # git@github.com:manneohrstrom/tk-hiero-publish.git -> tk-hiero-publish.git
        # /full/path/to/local/repo.git -> repo.git
        name = os.path.basename(self._path)

        for root in [self._bundle_cache_root] + self._fallback_roots:
            paths.append(
                os.path.join(
                    root,
                    "git",
                    name,
                    short_hash
                )
            )
        return paths

    def _clone_into(self, target_path):
        """
        Clone a repo into the given path, switch branch and position it at a commit.

        :param target_path: Path to clone into. This cannot exist on disk.
        """

        # ensure *parent* folder exists
        parent_folder = os.path.dirname(target_path)
        ensure_folder_exists(parent_folder)

        # now clone, set to branch and set to specific commit
        cwd = os.getcwd()
        try:
            # clone the repo
            self._clone_repo(target_path)
            os.chdir(target_path)
            log.debug("Switching to branch %s..." % self._branch)
            execute_git_command("checkout -q %s" % self._branch)
            log.debug("Setting commit to %s..." % self._version)
            execute_git_command("reset --hard -q %s" % self._version)
        finally:
            os.chdir(cwd)

    def get_version(self):
        """
        Returns the version number string for this item, .e.g 'v1.2.3'
        or the branch name 'master'
        """
        return self._version

    def download_local(self):
        """
        Retrieves this version to local repo.
        Will exit early if app already exists local.
        """
        if self.exists_local():
            # nothing to do!
            return

        # cache into the primary location
        target = self._get_cache_paths()[0]
        self._clone_into(target)

    def copy(self, target_path, connected=False):
        """
        Copy the contents of the descriptor to an external location

        :param target_path: target path to copy the descriptor to.
        :param connected: For descriptor types that supports it, attempt
                          to create a 'connected' copy that has a relationship
                          with the descriptor. This is typically useful for SCMs
                          such as git, where rather than copying the content in
                          its raw form, you clone the repository, thereby creating
                          a setup where changes can be made and pushed back to the
                          connected server side repository.
        """
        if connected:
            self._clone_into(target_path)
        else:
            super(IODescriptorGitBranch, self).copy(target_path, connected)

    def get_latest_version(self, constraint_pattern=None):
        """
        Returns a descriptor object that represents the latest version.

        :param constraint_pattern: If this is specified, the query will be constrained
               by the given pattern. Version patterns are on the following forms:

                - v0.1.2, v0.12.3.2, v0.1.3beta - a specific version
                - v0.12.x - get the highest v0.12 version
                - v1.x.x - get the highest v1 version

        :returns: descriptor object
        """
        if constraint_pattern:
            log.warning(
                "%s does not handle constraint patters. "
                "Latest version will be used." % self
            )

        # figure out the latest commit for the given repo and branch
        # git ls-remote repo_url branch_name
        # returns: 'hash	remote_branch'
        try:
            log.debug(
                "Calling ls-remote to find latest remote "
                "commit for %s branch %s" % (self._path, self._branch)
            )
            cmd = "git ls-remote \"%s\" \"%s\"" % (self._sanitized_repo_path, self._branch)
            branch_info = subprocess_check_output(cmd, shell=True).strip()
            log.debug("ls-remote returned: '%s'" % branch_info)
        except Exception, e:
            raise ShotgunDeployError(
                "Could not get latest commit for %s, "
                "branch %s: %s" % (self._path, self._branch, e)
            )

        # get first chunk of return data
        git_hash = branch_info.split()[0]

        # make a new descriptor
        new_loc_dict = copy.deepcopy(self._descriptor_dict)
        new_loc_dict["version"] = git_hash
        desc = IODescriptorGitBranch(new_loc_dict)
        desc.set_cache_roots(self._bundle_cache_root, self._fallback_roots)
        return desc


