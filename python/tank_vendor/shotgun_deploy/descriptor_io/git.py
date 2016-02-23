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
import uuid
import tempfile

from ..util import subprocess_check_output, execute_git_command
from .base import IODescriptorBase
from ..zipfilehelper import unzip_file
from ..errors import ShotgunDeployError
from ...shotgun_base import ensure_folder_exists, safe_delete_file

from .. import util
log = util.get_shotgun_deploy_logger()

class IODescriptorGit(IODescriptorBase):
    """
    Represents a tag in a git repository.

    location: {"type": "git", "path": "/path/to/repo.git", "version": "v0.2.1"}

    path can be on the form:

        git@github.com:manneohrstrom/tk-hiero-publish.git
        https://github.com/manneohrstrom/tk-hiero-publish.git
        git://github.com/manneohrstrom/tk-hiero-publish.git
        /full/path/to/local/repo.git

    Uris are on the form:

        sgtk:git:path/to/git/repo:v12.3.4

    """

    def __init__(self, location_dict):
        """
        Constructor

        :param location_dict: Location dictionary describing the bundle
        :return: Descriptor instance
        """
        super(IODescriptorGit, self).__init__(location_dict)

        self._validate_locator(
            location_dict,
            required=["type", "path", "version"],
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

    def _get_cache_paths(self):
        """
        Get a list of resolved paths, starting with the primary and
        continuing with alternative locations where it may reside.

        :return: List of path strings
        """
        paths = []

        # git@github.com:manneohrstrom/tk-hiero-publish.git -> tk-hiero-publish.git
        # /full/path/to/local/repo.git -> repo.git
        name = os.path.basename(self._path)

        for root in [self._bundle_cache_root] + self._fallback_roots:
            paths.append(
                os.path.join(
                    root,
                    "git",
                    name,
                    self.get_version()
                )
            )
        return paths

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

    def _get_latest_by_pattern(self, pattern):
        """
        Returns a descriptor object that represents the latest
        version, but based on a version pattern.

        :param pattern: Version patterns are on the following forms:

            - v1.2.3 (can return this v1.2.3 but also any forked version under, eg. v1.2.3.2)
            - v1.2.x (examples: v1.2.4, or a forked version v1.2.4.2)
            - v1.x.x (examples: v1.3.2, a forked version v1.3.2.2)
            - v1.2.3.x (will always return a forked version, eg. v1.2.3.2)

        :returns: descriptor object
        """
        # now first clone the repo into a tmp location
        clone_tmp = os.path.join(tempfile.gettempdir(), "%s_tank_clone" % uuid.uuid4().hex)
        ensure_folder_exists(clone_tmp)

        # get the most recent tag hash
        cwd = os.getcwd()
        try:
            # clone the repo
            self._clone_repo(clone_tmp)
            os.chdir(clone_tmp)

            try:
                # get list of tags from git
                git_tags = subprocess_check_output(
                    "git tag",
                    shell=True
                ).split("\n")
            except Exception, e:
                raise ShotgunDeployError("Could not get list of tags for %s: %s" % (self, e))

        finally:
            os.chdir(cwd)

        if len(git_tags) == 0:
            raise ShotgunDeployError(
                "Git repository %s doesn't seem to have any tags!" % self._path
            )

        version_to_use = self._find_latest_tag_by_pattern(git_tags, pattern)

        new_loc_dict = copy.deepcopy(self._location_dict)
        new_loc_dict["version"] = version_to_use

        # create new descriptor to represent this tag
        desc = IODescriptorGit(new_loc_dict)
        desc.set_cache_roots(self._bundle_cache_root, self._fallback_roots)
        return desc

    def _get_latest_version(self):
        """
        Returns a descriptor object that represents the latest version.

        :returns: descriptor object
        """
        # now first clone the repo into a tmp location
        clone_tmp = os.path.join(tempfile.gettempdir(), "%s_tank_clone" % uuid.uuid4().hex)
        ensure_folder_exists(clone_tmp)

        # get the most recent tag hash
        cwd = os.getcwd()
        try:
            # clone the repo
            self._clone_repo(clone_tmp)
            os.chdir(clone_tmp)

            try:
                git_hash = subprocess_check_output(
                    "git rev-list --tags --max-count=1",
                    shell=True
                ).strip()
            except Exception, e:
                raise ShotgunDeployError("Could not get list of tags for %s: %s" % (self, e))

            try:
                latest_version = subprocess_check_output(
                    "git describe --tags %s" % git_hash,
                    shell=True
                ).strip()
            except Exception, e:
                raise ShotgunDeployError("Could not get tag for hash %s: %s" % (hash, e))

        finally:
            os.chdir(cwd)

        new_loc_dict = copy.deepcopy(self._location_dict)
        new_loc_dict["version"] = latest_version

        # create new descriptor to represent this tag
        desc = IODescriptorGit(new_loc_dict)
        desc.set_cache_roots(self._bundle_cache_root, self._fallback_roots)
        return desc

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

        # clone into temp location and extract tag
        ensure_folder_exists(target)

        # now first clone the repo into a tmp location
        # then zip up the tag we are looking for
        # finally, move that zip file into the target location
        zip_tmp = os.path.join(tempfile.gettempdir(), "%s_tank.zip" % uuid.uuid4().hex)
        clone_tmp = os.path.join(tempfile.gettempdir(), "%s_tank_clone" % uuid.uuid4().hex)
        ensure_folder_exists(clone_tmp)

        # now clone and archive
        cwd = os.getcwd()
        try:
            # clone the repo
            self._clone_repo(clone_tmp)
            os.chdir(clone_tmp)
            log.debug("Extracting tag %s..." % self._version)
            execute_git_command(
                "archive --format zip --output %s %s" % (zip_tmp, self._version)
            )
        finally:
            os.chdir(cwd)

        # unzip core zip file to app target location
        log.debug("Unpacking %s bytes to %s..." % (os.path.getsize(zip_tmp), target))
        unzip_file(zip_tmp, target)

        # clear temp file
        safe_delete_file(zip_tmp)

    def copy(self, target_path):
        """
        Copy the contents of the descriptor to an external location

        :param target_path: target path
        """
        # git repos are cloned into place to retain their
        # repository status
        log.debug("Copying %r -> %s" % (self, target_path))
        # now clone and archive
        cwd = os.getcwd()
        try:
            # clone the repo
            self._clone_repo(target_path)
            os.chdir(target_path)
            execute_git_command("checkout %s -q" % self._version)
        finally:
            os.chdir(cwd)

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
            return self._get_latest_by_pattern(constraint_pattern)
        else:
            return self._get_latest_version()

