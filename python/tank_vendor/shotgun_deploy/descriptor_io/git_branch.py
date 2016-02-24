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
from .base import IODescriptorBase
from ..errors import ShotgunDeployError
from ...shotgun_base import ensure_folder_exists

from .. import util
log = util.get_shotgun_deploy_logger()

class IODescriptorGitBranch(IODescriptorBase):
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

    Uris are on the form:

        sgtk:git_branch:path/to/git/repo:master:17fedd8a4e3c7c004316af5001331ad2c9e14bd5
        sgtk:git_branch:path/to/git/repo:master:latest

    The hash can be short, as long as it is unique, e.g. it follows the same logic
    that git is using for shortening its hashes. A recommendation is to use the first
    seven digits to describe a hash that is unique within a repository.
    """

    def __init__(self, location_dict):
        """
        Constructor

        :param location_dict: Location dictionary describing the bundle
        :return: Descriptor instance
        """
        super(IODescriptorGitBranch, self).__init__(location_dict)

        self._validate_locator(
            location_dict,
            required=["type", "path", "version", "branch"],
            optional=[]
        )

        self._path = location_dict.get("path")
        # strip trailing slashes - this is so that when we build
        # the name later (using os.basename) we construct it correctly.
        if self._path.endswith("/") or self._path.endswith("\\"):
            self._path = self._path[:-1]

        # Note: the git command always uses forward slashes
        self._sanitized_repo_path = self._path.replace(os.path.sep, "/")

        self._version = location_dict.get("version")
        self._branch = location_dict.get("branch")

    def _get_cache_paths(self):
        """
        Get a list of resolved paths, starting with the primary and
        continuing with alternative locations where it may reside.

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

    @classmethod
    def dict_from_uri(cls, uri):
        """
        Given a location uri, return a location dict

        :param uri: Location uri string
        :return: Location dictionary
        """
        # sgtk:git_branch:git/path:branchname:commithash

        # explode into dictionary
        location_dict = cls._explode_uri(uri, "git_branch", ["path", "branch", "version"])

        # validate it
        cls._validate_locator(
            location_dict,
            required=["type", "path", "branch", "version"],
            optional=[]
        )
        return location_dict

    @classmethod
    def uri_from_dict(cls, location_dict):
        """
        Given a location dictionary, return a location uri

        :param location_dict: Location dictionary
        :return: Location uri string
        """
        # sgtk:git_branch:git/path:branchname:commithash

        cls._validate_locator(
            location_dict,
            required=["type", "path", "branch", "version"],
            optional=[]
        )

        return "sgtk:git_branch:%s:%s:%s" % (
            location_dict["path"],
            location_dict["branch"],
            location_dict["version"]
        )

    def get_system_name(self):
        """
        Returns a short name, suitable for use in configuration files
        and for folders on disk, e.g. 'tk-maya'
        """
        bn = os.path.basename(self._path)
        (name, ext) = os.path.splitext(bn)
        return name

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

    def copy(self, target_path):
        """
        Copy the contents of the descriptor to an external location

        :param target_path: target path
        """
        self._clone_into(target_path)

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
        new_loc_dict = copy.deepcopy(self._location_dict)
        new_loc_dict["version"] = git_hash
        desc = IODescriptorGitBranch(new_loc_dict)
        desc.set_cache_roots(self._bundle_cache_root, self._fallback_roots)
        return desc


