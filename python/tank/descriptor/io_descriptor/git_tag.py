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

from tank_vendor import yaml

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
                f"Local repository at {self._path} is currently at tag {local_tag}"
            )
            return local_tag
        except subprocess.CalledProcessError:
            # Not on a tag
            return None
        except Exception as e:
            log.debug(f"Could not determine local repository tag at {self._path}: {e}")
            return None

    def _check_local_tag_compatibility(
        self, local_tag, latest_tag, current_py_ver, min_py_ver
    ):
        """
        Check if a local repository tag is compatible with the current Python version.

        :param str local_tag: Tag name from local repository
        :param str latest_tag: Latest tag that was found incompatible
        :param str current_py_ver: Current Python version string (e.g., "3.7.0")
        :param str min_py_ver: Minimum Python version required by latest_tag
        :returns: local_tag if compatible, None otherwise
        :rtype: str or None
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
                    f"Downloading local tag {local_tag} to bundle cache for compatibility check"
                )
                local_desc.download_local()

            # Check if this local tag is compatible
            local_manifest = local_desc.get_manifest(
                descriptor_constants.BUNDLE_METADATA_FILE
            )
            if self._check_minimum_python_version(local_manifest):
                log.warning(
                    f"Auto-update blocked: Latest tag {latest_tag} requires Python {min_py_ver}, current is {current_py_ver}. "
                    f"Using local repository tag {local_tag} which is compatible."
                )
                return local_tag
            else:
                log.debug(
                    f"Local tag {local_tag} is also not compatible with current Python version"
                )
                return None
        except Exception as e:
            log.debug(f"Could not check compatibility for local tag {local_tag}: {e}")
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
                    f"Could not check compatibility for cached version {tag}: {e}"
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
                f"Git repository {self._path} doesn't have any tags!"
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

            manifest = None
            if temp_desc.exists_local():
                # Latest tag is cached - check it directly
                manifest = temp_desc.get_manifest(
                    descriptor_constants.BUNDLE_METADATA_FILE
                )
            elif self._version == "latest":
                # For "latest" descriptors, try to find compatible version without downloading
                # This searches local repo and bundle cache
                local_tag = self._get_local_repository_tag()
                log.debug("local_tag: %s" % local_tag)
                if local_tag and local_tag == latest_tag:
                    # Local repo is already at latest tag, we can check it
                    try:
                        # Try to get manifest from local git checkout (not bundle cache)
                        local_repo_path = os.path.dirname(self._path)
                        manifest_path = os.path.join(
                            local_repo_path, descriptor_constants.BUNDLE_METADATA_FILE
                        )
                        if os.path.exists(manifest_path):
                            with open(manifest_path) as f:
                                manifest = yaml.load(f, Loader=yaml.FullLoader)
                    except Exception as e:
                        log.debug(f"Could not read manifest from local git repo: {e}")
                    manifest["minimum_python_version"] = "3.10"
            if manifest and not self._check_minimum_python_version(manifest):
                # Latest version is NOT compatible - block auto-update
                current_py_ver = (
                    f"{sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]}"
                )
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
                            f"Auto-update blocked: Latest tag {latest_tag} requires Python {min_py_ver}, current is {current_py_ver}. "
                            f"Using highest compatible cached version {compatible_version}."
                        )
                        return compatible_version
                    else:
                        # No compatible version found - use latest anyway with warning
                        log.warning(
                            f"Auto-update blocked: Latest tag {latest_tag} requires Python {min_py_ver}, current is {current_py_ver}. "
                            "No compatible cached version found. Using latest tag anyway."
                        )
                        return latest_tag
                else:
                    log.warning(
                        f"Auto-update blocked: Latest tag {latest_tag} requires Python {min_py_ver}, current is {current_py_ver}. "
                        f"Keeping current version {self._version}."
                    )
                    return self._version
            else:
                log.debug(
                    f"Latest tag {latest_tag} is compatible with current Python version"
                )
                return latest_tag

        except Exception as e:
            log.warning(
                f"Could not check Python compatibility for tag {latest_tag}: {e}. Proceeding with auto-update."
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
        log.debug(f"Looking for cached versions of {self}...")
        all_versions = list(self._get_locally_cached_versions().keys())
        log.debug(f"Found {len(all_versions)} versions")

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

        log.debug(f"Latest cached version resolved to {desc}")
        return desc
