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

    The payload cached in the bundle cache is not a git repo
    but only contains the tag given by the version pass with
    the descriptor.

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

    def get_version(self):
        """
        Returns the version number string for this item, .e.g 'v1.2.3'
        """
        return self._version

    def download_local(self):
        """
        Retrieves this version to local repo.
        Will exit early if app already exists local.

        This will connect to remote git repositories.

        The git tag descriptor type will perform the following
        sequence of operations to perform a download local:

        - git clone repo into temp folder
        - extracting the associated tag from temp repo into zip file
          using git archive command
        - unpack zip file into final tk bundle cache location
        - cleans up temp data
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
        zip_tmp = os.path.join(tempfile.gettempdir(), "%s_tk.zip" % uuid.uuid4().hex)
        clone_tmp = os.path.join(tempfile.gettempdir(), "%s_tk_git" % uuid.uuid4().hex)
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

    def get_latest_version(self, constraint_pattern=None):
        """
        Returns a descriptor object that represents the latest version.

        Communicates with the remote repository using git ls-remote.

        :param constraint_pattern: If this is specified, the query will be constrained
               by the given pattern. Version patterns are on the following forms:

                - v0.1.2, v0.12.3.2, v0.1.3beta - a specific version
                - v0.12.x - get the highest v0.12 version
                - v1.x.x - get the highest v1 version

        :returns: IODescriptorGitTag object
        """
        # figure out the latest commit for the given repo and branch
        # 'git ls-remote --tags repo_url' returns
        #
        # 32862181fa982aba99af1e518c51117309009023	refs/tags/v0.18.5rv
        # f08d7e0e5f5bf1402d21a653510c8be77b184f93	refs/tags/v0.18.5rv^{}
        # 5c612bd01cc0db46408e715aca360a133d4eefeb	refs/tags/v0.18.6
        # 4ecc15ac7045eef0d5ab205dede3c5c5f513ec09	refs/tags/v0.18.6^{}
        # 6519356b7f4a829205a1cb71be9ec5b5e4e10409	refs/tags/v0.18.7
        # a8e5ceaa4222b0d8b35cff0a0d2ef1bd680c1a1e	refs/tags/v0.18.7^{}
        # 3c9494743cf7c8e07806b1ae9f1af152994c1fe6	refs/tags/v0.18.8
        # b92f3cc69060b73c26e6236ef2c65859794f1f4e	refs/tags/v0.18.8^{}
        # 5e7014ca28e94f7baf2cea5ca9ba103414095897	refs/tags/v0.18.9
        # 17041e87070354a7c221e33d5a4edd02fd0159a6	refs/tags/v0.18.9^{}
        #
        try:
            command = "ls-remote --tags \"%s\"" % self._sanitized_repo_path
            all_tag_chunks = execute_git_command(command).split("\n")
            log.debug("ls-remote returned: '%s'" % all_tag_chunks)

            # get first chunk of return data
            tags = []
            for tag_chunk_line in all_tag_chunks:
                # 4ecc15ac7045eef0d5ab205dede3c5c5f513ec09	refs/tags/v0.18.6^{}
                tag_match = re.match("^.*refs/tags/([^\^]+)$", tag_chunk_line)
                if tag_match:
                    tags.append(tag_match.group(1))

            if len(tags) == 0:
                raise TankDescriptorError("No tags defined!")

            if constraint_pattern is None:
                # get latest tag
                version_to_use = tags[-1]
            else:
                # get based on constraint patter
                version_to_use = self._find_latest_tag_by_pattern(tags, constraint_pattern)

        except Exception, e:
            raise TankDescriptorError(
                "Could not get tags for %s: %s" % (self._path, e)
            )

        new_loc_dict = copy.deepcopy(self._descriptor_dict)
        new_loc_dict["version"] = version_to_use

        # create new descriptor to represent this tag
        desc = IODescriptorGitTag(new_loc_dict, self._type)
        desc.set_cache_roots(self._bundle_cache_root, self._fallback_roots)
        return desc

