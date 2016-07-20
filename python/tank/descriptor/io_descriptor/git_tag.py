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

from ...util.git import execute_git_command
from ...util.process import subprocess_check_output
from ...util import filesystem
from .git import IODescriptorGit
from ...util.zip import unzip_file
from ..errors import TankDescriptorError
from ... import LogManager

log = LogManager.get_logger(__name__)


class IODescriptorGitTag(IODescriptorGit):
    """
    Represents a tag in a git repository.

    location: {"type": "git", "path": "/path/to/repo.git", "version": "v0.2.1"}

    path can be on the form:

        git@github.com:manneohrstrom/tk-hiero-publish.git
        https://github.com/manneohrstrom/tk-hiero-publish.git
        git://github.com/manneohrstrom/tk-hiero-publish.git
        /full/path/to/local/repo.git
    """

    def __init__(self, descriptor_dict, bundle_type):
        """
        Constructor

        :param descriptor_dict: descriptor dictionary describing the bundle
        :param bundle_type: The type of bundle. ex: Descriptor.APP
        :return: Descriptor instance
        """
        # make sure all required fields are there
        self._validate_descriptor(
            descriptor_dict,
            required=["type", "path", "version"],
            optional=[]
        )

        # call base class
        super(IODescriptorGitTag, self).__init__(descriptor_dict)

        # path is handled by base class - all git descriptors
        # have a path to a repo
        self._version = descriptor_dict.get("version")

        self._type = bundle_type

    def _get_bundle_cache_path(self, bundle_cache_root):
        """
        Given a cache root, compute a cache path suitable
        for this descriptor, using the 0.18+ path format.

        :param bundle_cache_root: Bundle cache root path
        :return: Path to bundle cache location
        """
        # git@github.com:manneohrstrom/tk-hiero-publish.git -> tk-hiero-publish.git
        # /full/path/to/local/repo.git -> repo.git
        name = os.path.basename(self._path)

        return os.path.join(
            bundle_cache_root,
            "git",
            name,
            self.get_version()
        )

    def _get_cache_paths(self):
        """
        Get a list of resolved paths, starting with the primary and
        continuing with alternative locations where it may reside.

        Note: This method only computes paths and does not perform any I/O ops.

        :return: List of path strings
        """
        # get default cache paths from base class
        paths = super(IODescriptorGitTag, self)._get_cache_paths()

        # for compatibility with older versions of core, prior to v0.18.x,
        # add the old-style bundle cache path as a fallback. As of v0.18.x,
        # the bundle cache subdirectory names were shortened and otherwise
        # modified to help prevent MAX_PATH issues on windows. This call adds
        # the old path as a fallback for cases where core has been upgraded
        # for an existing project. NOTE: This only works because the bundle
        # cache root didn't change (when use_bundle_cache is set to False).
        # If the bundle cache root changes across core versions, then this will
        # need to be refactored.

        # git@github.com:manneohrstrom/tk-hiero-publish.git -> tk-hiero-publish.git
        # /full/path/to/local/repo.git -> repo.git
        name = os.path.basename(self._path)

        legacy_folder = self._get_legacy_bundle_install_folder(
            "git",
            self._bundle_cache_root,
            self._type,
            name,
            self.get_version()
        )
        if legacy_folder:
            paths.append(legacy_folder)

        return paths

    def _get_latest_by_pattern(self, pattern):
        """
        Returns a descriptor object that represents the latest
        version, but based on a version pattern.

        :param pattern: Version patterns are on the following forms:

            - v1.2.3 (can return this v1.2.3 but also any forked version under, eg. v1.2.3.2)
            - v1.2.x (examples: v1.2.4, or a forked version v1.2.4.2)
            - v1.x.x (examples: v1.3.2, a forked version v1.3.2.2)
            - v1.2.3.x (will always return a forked version, eg. v1.2.3.2)

        :returns: IODescriptorGitTag object
        """
        # now first clone the repo into a tmp location
        clone_tmp = os.path.join(tempfile.gettempdir(), "%s_tank_clone" % uuid.uuid4().hex)
        filesystem.ensure_folder_exists(clone_tmp)

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
                raise TankDescriptorError("Could not get list of tags for %s: %s" % (self, e))

        finally:
            os.chdir(cwd)

        if len(git_tags) == 0:
            raise TankDescriptorError(
                "Git repository %s doesn't seem to have any tags!" % self._path
            )

        version_to_use = self._find_latest_tag_by_pattern(git_tags, pattern)

        new_loc_dict = copy.deepcopy(self._descriptor_dict)
        new_loc_dict["version"] = version_to_use

        # create new descriptor to represent this tag
        desc = IODescriptorGitTag(new_loc_dict, self._type)
        desc.set_cache_roots(self._bundle_cache_root, self._fallback_roots)
        return desc

    def _get_latest_version(self):
        """
        Returns a descriptor object that represents the latest version.

        :returns: IODescriptorGitTag object
        """
        # now first clone the repo into a tmp location
        clone_tmp = os.path.join(tempfile.gettempdir(), "%s_tank_clone" % uuid.uuid4().hex)
        filesystem.ensure_folder_exists(clone_tmp)

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
                raise TankDescriptorError("Could not get list of tags for %s: %s" % (self, e))

            try:
                latest_version = subprocess_check_output(
                    "git describe --tags %s" % git_hash,
                    shell=True
                ).strip()
            except Exception, e:
                raise TankDescriptorError("Could not get tag for hash %s: %s" % (hash, e))

        finally:
            os.chdir(cwd)

        new_loc_dict = copy.deepcopy(self._descriptor_dict)
        new_loc_dict["version"] = latest_version

        # create new descriptor to represent this tag
        desc = IODescriptorGitTag(new_loc_dict, self._type)
        desc.set_cache_roots(self._bundle_cache_root, self._fallback_roots)
        return desc

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
        filesystem.ensure_folder_exists(target)

        # now first clone the repo into a tmp location
        # then zip up the tag we are looking for
        # finally, move that zip file into the target location
        zip_tmp = os.path.join(tempfile.gettempdir(), "%s_tank.zip" % uuid.uuid4().hex)
        clone_tmp = os.path.join(tempfile.gettempdir(), "%s_tank_clone" % uuid.uuid4().hex)
        filesystem.ensure_folder_exists(clone_tmp)

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
        filesystem.safe_delete_file(zip_tmp)

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
        else:
            super(IODescriptorGitTag, self).copy(target_path, connected)

    def get_latest_version(self, constraint_pattern=None):
        """
        Returns a descriptor object that represents the latest version.

        :param constraint_pattern: If this is specified, the query will be constrained
               by the given pattern. Version patterns are on the following forms:

                - v0.1.2, v0.12.3.2, v0.1.3beta - a specific version
                - v0.12.x - get the highest v0.12 version
                - v1.x.x - get the highest v1 version

        :returns: IODescriptorGitTag object
        """
        if constraint_pattern:
            return self._get_latest_by_pattern(constraint_pattern)
        else:
            return self._get_latest_version()

