# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.
import copy
import os
import re
import subprocess
import sys

from ... import LogManager
from .. import constants as descriptor_constants
from ..errors import TankDescriptorError
from .git import IODescriptorGit

log = LogManager.get_logger(__name__)


class IODescriptorGitTag(IODescriptorGit):
    """
    Represents a tag in a git repository.

    location: {"type": "git", "path": "/path/to/repo.git", "version": "v0.2.1"}

    The payload cached in the bundle cache is not a git repo
    but only contains the tag given by the version pass with
    the descriptor.

    path can be on the form:

        git@github.com:manneohrstrom/tk-hiero-publish.git
        https://github.com/manneohrstrom/tk-hiero-publish.git
        git://github.com/manneohrstrom/tk-hiero-publish.git
        /full/path/to/local/repo.git
    """

    def __init__(self, descriptor_dict, sg_connection, bundle_type):
        """
        Constructor

        :param descriptor_dict: descriptor dictionary describing the bundle
        :param sg_connection: Shotgun connection to associated site.
        :param bundle_type: The type of bundle. ex: Descriptor.APP
        :return: Descriptor instance
        """
        # make sure all required fields are there
        self._validate_descriptor(
            descriptor_dict, required=["type", "path", "version"], optional=[]
        )

        # call base class
        super().__init__(descriptor_dict, sg_connection, bundle_type)

        # path is handled by base class - all git descriptors
        # have a path to a repo
        self._version = descriptor_dict.get("version")
        self._sg_connection = sg_connection
        self._bundle_type = bundle_type

    def __str__(self):
        """
        Human readable representation
        """
        # git@github.com:manneohrstrom/tk-hiero-publish.git, tag v1.2.3
        return "%s, Tag %s" % (self._path, self._version)

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

        return os.path.join(bundle_cache_root, "git", name, self.get_version())

    def _get_cache_paths(self):
        """
        Get a list of resolved paths, starting with the primary and
        continuing with alternative locations where it may reside.

        Note: This method only computes paths and does not perform any I/O ops.

        :return: List of path strings
        """
        # get default cache paths from base class
        paths = super()._get_cache_paths()

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
            "git", self._bundle_cache_root, self._bundle_type, name, self.get_version()
        )
        if legacy_folder:
            paths.append(legacy_folder)

        return paths

    def get_version(self):
        """
        Returns the version number string for this item, .e.g 'v1.2.3'
        """
        return self._version

    def _download_local(self, destination_path):
        """
        Retrieves this version to local repo.
        Will exit early if app already exists local.

        This will connect to remote git repositories.
        Depending on how git is configured, https repositories
        requiring credentials may result in a shell opening up
        requesting username and password.

        The git repo will be cloned into the local cache and
        will then be adjusted to point at the relevant tag.

        :param destination_path: The destination path on disk to which
        the git tag descriptor is to be downloaded to.
        """
        try:
            # clone the repo, checkout the given tag
            self._clone_then_execute_git_commands(
                destination_path, [], depth=1, ref=self._version
            )
        except Exception as e:
            raise TankDescriptorError(
                "Could not download %s, " "tag %s: %s" % (self._path, self._version, e)
            )

    def get_latest_version(self, constraint_pattern=None):
        """
        Returns a descriptor object that represents the latest version.

        This will connect to remote git repositories.
        Depending on how git is configured, https repositories
        requiring credentials may result in a shell opening up
        requesting username and password.

        This will clone the git repository into a temporary location in order to
        introspect its properties.

        :param constraint_pattern: If this is specified, the query will be constrained
               by the given pattern. Version patterns are on the following forms:

                - v0.1.2, v0.12.3.2, v0.1.3beta - a specific version
                - v0.12.x - get the highest v0.12 version
                - v1.x.x - get the highest v1 version

        :returns: IODescriptorGitTag object
        """
        if constraint_pattern:
            tag_name = self._get_latest_by_pattern(constraint_pattern)
        else:
            tag_name = self._get_latest_version()

        new_loc_dict = copy.deepcopy(self._descriptor_dict)
        new_loc_dict["version"] = str(tag_name)

        # create new descriptor to represent this tag
        desc = IODescriptorGitTag(new_loc_dict, self._sg_connection, self._bundle_type)
        desc.set_cache_roots(self._bundle_cache_root, self._fallback_roots)
        return desc

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
        git_tags = self._fetch_tags()
        latest_tag = self._find_latest_tag_by_pattern(git_tags, pattern)
        if latest_tag is None:
            raise TankDescriptorError(
                "'%s' does not have a version matching the pattern '%s'. "
                "Available versions are: %s"
                % (self.get_system_name(), pattern, ", ".join(git_tags))
            )

        return latest_tag

    def _fetch_tags(self):
        try:
            # clone the repo, list all tags
            # for the repository, across all branches
            commands = ["ls-remote -q --tags %s" % self._path]
            output = self._tmp_clone_then_execute_git_commands(commands, depth=1)
            if isinstance(output, bytes):
                output = output.decode("utf-8")
            tags = output.split("\n")
            regex = re.compile(".*refs/tags/([^^]*)$")
            git_tags = []
            for tag in tags:
                m = regex.match(tag)
                if m:
                    git_tags.append(m.group(1))

        except Exception as e:
            raise TankDescriptorError(
                "Could not get list of tags for %s: %s" % (self._path, e)
            )

        if len(git_tags) == 0:
            raise TankDescriptorError(
                "Git repository %s doesn't have any tags!" % self._path
            )

        return git_tags

    def _get_local_repository_tag(self):
        """
        Get the current tag of the local git repository if the path points to one.

        :returns: Tag name (string) or None if not on a tag or not a local repo
        """
        if not os.path.exists(self._path) or not os.path.isdir(self._path):
            return None

        git_dir = os.path.join(self._path, ".git")
        if not os.path.exists(git_dir):
            return None

        try:
            result = subprocess.check_output(
                ["git", "describe", "--tags", "--exact-match", "HEAD"],
                cwd=self._path,
                stderr=subprocess.STDOUT,
            )
            local_tag = result.strip()
            if isinstance(local_tag, bytes):
                local_tag = local_tag.decode("utf-8")

            log.debug(
                "Local repository at %s is currently at tag %s"
                % (self._path, local_tag)
            )
            return local_tag
        except subprocess.CalledProcessError:
            # Not on a tag
            return None
        except Exception as e:
            log.debug(
                "Could not determine local repository tag at %s: %s" % (self._path, e)
            )
            return None

    def _check_local_tag_compatibility(
        self, local_tag, latest_tag, current_py_ver, min_py_ver
    ):
        """
        Check if a local repository tag is compatible with the current Python version.

        :param local_tag: Tag name from local repository
        :param latest_tag: Latest tag that was found incompatible
        :param current_py_ver: Current Python version string
        :param min_py_ver: Minimum Python version required by latest_tag
        :returns: local_tag if compatible, None otherwise
        """
        try:
            # Create a descriptor for this local tag and download it to bundle cache
            local_desc_dict = copy.deepcopy(self._descriptor_dict)
            local_desc_dict["version"] = local_tag
            local_desc = IODescriptorGitTag(
                local_desc_dict, self._sg_connection, self._bundle_type
            )
            local_desc.set_cache_roots(self._bundle_cache_root, self._fallback_roots)

            # Download to bundle cache if not already there
            if not local_desc.exists_local():
                log.debug(
                    "Downloading local tag %s to bundle cache for compatibility check"
                    % local_tag
                )
                local_desc.download_local()

            # Check if this local tag is compatible
            local_manifest = local_desc.get_manifest(
                descriptor_constants.BUNDLE_METADATA_FILE
            )
            if self._check_minimum_python_version(local_manifest):
                log.warning(
                    "Auto-update blocked: Latest tag %s requires Python %s, current is %s. "
                    "Using local repository tag %s which is compatible."
                    % (latest_tag, min_py_ver, current_py_ver, local_tag)
                )
                return local_tag
            else:
                log.debug(
                    "Local tag %s is also not compatible with current Python version"
                    % local_tag
                )
                return None
        except Exception as e:
            log.debug(
                "Could not check compatibility for local tag %s: %s" % (local_tag, e)
            )
            return None

    def _find_compatible_cached_version(self, latest_tag):
        """
        Find the highest compatible version in the bundle cache.

        :param latest_tag: Latest tag to exclude from search
        :returns: Compatible tag name or None if not found
        """
        cached_versions = self._get_locally_cached_versions()
        if not cached_versions:
            return None

        all_cached_tags = list(cached_versions.keys())
        compatible_version = None

        for tag in all_cached_tags:
            # Skip the incompatible latest version
            if tag == latest_tag:
                continue

            try:
                # Check if this cached version is compatible
                temp_dict = copy.deepcopy(self._descriptor_dict)
                temp_dict["version"] = tag
                temp_desc = IODescriptorGitTag(
                    temp_dict, self._sg_connection, self._bundle_type
                )
                temp_desc.set_cache_roots(self._bundle_cache_root, self._fallback_roots)

                cached_manifest = temp_desc.get_manifest(
                    descriptor_constants.BUNDLE_METADATA_FILE
                )
                if self._check_minimum_python_version(cached_manifest):
                    # Found a compatible version, but keep looking for higher ones
                    if compatible_version is None:
                        compatible_version = tag
                    else:
                        # Compare versions to keep the highest
                        latest_of_two = self._find_latest_tag_by_pattern(
                            [compatible_version, tag], None
                        )
                        if latest_of_two == tag:
                            compatible_version = tag
            except Exception as e:
                log.debug(
                    "Could not check compatibility for cached version %s: %s" % (tag, e)
                )
                continue

        return compatible_version

    def _get_latest_version(self):
        """
        Returns the latest tag version, or current version if latest is not
        compatible with current Python version.

        :returns: Tag name (string) of the latest version or current version
        """
        tags = self._fetch_tags()
        latest_tag = self._find_latest_tag_by_pattern(tags, pattern=None)
        if latest_tag is None:
            raise TankDescriptorError(
                "Git repository %s doesn't have any tags!" % self._path
            )

        # Check if latest tag is compatible with current Python
        try:
            # Create a temporary descriptor for the latest tag
            temp_descriptor_dict = copy.deepcopy(self._descriptor_dict)
            temp_descriptor_dict["version"] = latest_tag

            temp_desc = IODescriptorGitTag(
                temp_descriptor_dict, self._sg_connection, self._bundle_type
            )
            temp_desc.set_cache_roots(self._bundle_cache_root, self._fallback_roots)

            # Download if needed to read manifest
            if not temp_desc.exists_local():
                log.debug("Downloading %s to check Python compatibility" % latest_tag)
                temp_desc.download_local()

            # Read manifest and check Python compatibility
            manifest = temp_desc.get_manifest(descriptor_constants.BUNDLE_METADATA_FILE)
            manifest["minimum_python_version"] = "3.10"  # TODO: Remove - hardcoded for testing
            if not self._check_minimum_python_version(manifest):
                # Latest version is NOT compatible - block auto-update
                current_py_ver = ".".join(str(x) for x in sys.version_info[:3])
                min_py_ver = manifest.get("minimum_python_version", "not specified")

                # If current version is "latest", find a compatible alternative
                if self._version == "latest":
                    # First, check if the path points to a local git repository
                    local_tag = self._get_local_repository_tag()
                    if local_tag:
                        compatible_tag = self._check_local_tag_compatibility(
                            local_tag, latest_tag, current_py_ver, min_py_ver
                        )
                        if compatible_tag:
                            return compatible_tag

                    # Second, search for compatible version in bundle cache
                    compatible_version = self._find_compatible_cached_version(
                        latest_tag
                    )
                    if compatible_version:
                        log.warning(
                            "Auto-update blocked: Latest tag %s requires Python %s, current is %s. "
                            "Using highest compatible cached version %s."
                            % (
                                latest_tag,
                                min_py_ver,
                                current_py_ver,
                                compatible_version,
                            )
                        )
                        return compatible_version
                    else:
                        # No compatible version found - use latest anyway with warning
                        log.warning(
                            "Auto-update blocked: Latest tag %s requires Python %s, current is %s. "
                            "No compatible cached version found. Using latest tag anyway."
                            % (latest_tag, min_py_ver, current_py_ver)
                        )
                        return latest_tag
                else:
                    log.warning(
                        "Auto-update blocked: Latest tag %s requires Python %s, current is %s. "
                        "Keeping current version %s."
                        % (latest_tag, min_py_ver, current_py_ver, self._version)
                    )
                    return self._version
            else:
                log.debug(
                    "Latest tag %s is compatible with current Python version"
                    % latest_tag
                )
                return latest_tag

        except Exception as e:
            log.warning(
                "Could not check Python compatibility for tag %s: %s. Proceeding with auto-update."
                % (latest_tag, e)
            )
            return latest_tag

    def get_latest_cached_version(self, constraint_pattern=None):
        """
        Returns a descriptor object that represents the latest version
        that is locally available in the bundle cache search path.

        :param constraint_pattern: If this is specified, the query will be constrained
               by the given pattern. Version patterns are on the following forms:

                - v0.1.2, v0.12.3.2, v0.1.3beta - a specific version
                - v0.12.x - get the highest v0.12 version
                - v1.x.x - get the highest v1 version

        :returns: instance deriving from IODescriptorBase or None if not found
        """
        log.debug("Looking for cached versions of %r..." % self)
        all_versions = list(self._get_locally_cached_versions().keys())
        log.debug("Found %d versions" % len(all_versions))

        if len(all_versions) == 0:
            return None

        # get latest
        version_to_use = self._find_latest_tag_by_pattern(
            all_versions, constraint_pattern
        )
        if version_to_use is None:
            return None

        # create new descriptor to represent this tag
        new_loc_dict = copy.deepcopy(self._descriptor_dict)
        new_loc_dict["version"] = version_to_use
        desc = IODescriptorGitTag(new_loc_dict, self._sg_connection, self._bundle_type)
        desc.set_cache_roots(self._bundle_cache_root, self._fallback_roots)

        log.debug("Latest cached version resolved to %r" % desc)
        return desc
