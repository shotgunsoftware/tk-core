# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
This git descriptor is for a formal git workflow.
It will base version numbering off tags in git.
"""

import os
import re
import copy
import uuid
import tempfile

from .util import subprocess_check_output, execute_git_command
from ..api import Tank
from ..errors import TankError
from ..platform import constants
from .descriptor import AppDescriptor, VersionedSingletonDescriptor
from .zipfilehelper import unzip_file

class TankGitDescriptor(VersionedSingletonDescriptor):
    """
    Represents a repository in git. New versions are represented by new tags.
    
    path can be on the form:
    git@github.com:manneohrstrom/tk-hiero-publish.git
    https://github.com/manneohrstrom/tk-hiero-publish.git
    git://github.com/manneohrstrom/tk-hiero-publish.git
    /full/path/to/local/repo.git
    """

    def __init__(self, pc_path, bundle_install_path, location_dict, type):
        super(TankGitDescriptor, self).__init__(pc_path, bundle_install_path, location_dict)

        self._type = type
        self._path = location_dict.get("path")
        # strip trailing slashes - this is so that when we build
        # the name later (using os.basename) we construct it correctly.
        if self._path.endswith("/") or self._path.endswith("\\"):
            self._path = self._path[:-1] 
        self._version = location_dict.get("version")

        if self._path is None or self._version is None:
            raise TankError("Git descriptor is not valid: %s" % str(location_dict))


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
        return self._version

    def get_path(self):
        """
        returns the path to the folder where this item resides
        """
        # git@github.com:manneohrstrom/tk-hiero-publish.git -> tk-hiero-publish.git
        # /full/path/to/local/repo.git -> repo.git        
        name = os.path.basename(self._path)
        return self._get_local_location(self._type, "git", name, self._version)

    def exists_local(self):
        """
        Returns true if this item exists in a local repo
        """
        return os.path.exists(self.get_path())

    def download_local(self):
        """
        Retrieves this version to local repo.
        Will exit early if app already exists local.
        """
        if self.exists_local():
            # nothing to do!
            return

        target = self.get_path()
        if not os.path.exists(target):
            old_umask = os.umask(0)
            os.makedirs(target, 0777)
            os.umask(old_umask)                

        # now first clone the repo into a tmp location
        # then zip up the tag we are looking for
        # finally, move that zip file into the target location
        zip_tmp = os.path.join(tempfile.gettempdir(), "%s_tank.zip" % uuid.uuid4().hex)
        clone_tmp = os.path.join(tempfile.gettempdir(), "%s_tank_clone" % uuid.uuid4().hex)
        old_umask = os.umask(0)
        os.makedirs(clone_tmp, 0777)
        os.umask(old_umask)                

        # now clone and archive
        cwd = os.getcwd()
        try:
            # clone the repo
            self.__clone_repo(clone_tmp)
            os.chdir(clone_tmp)            
            execute_git_command("archive --format zip --output %s %s" % (zip_tmp, self._version))
        finally:
            os.chdir(cwd)
        
        # unzip core zip file to app target location
        unzip_file(zip_tmp, target)

    def find_latest_version(self, constraint_pattern=None):
        """
        Returns a descriptor object that represents the latest version.
        
        :param constraint_pattern: If this is specified, the query will be constrained
        by the given pattern. Version patterns are on the following forms:
        
            - v1.2.3 (means the descriptor returned will inevitably be same as self)
            - v1.2.x 
            - v1.x.x

        :returns: descriptor object
        """
        if constraint_pattern:
            return self._find_latest_by_pattern(constraint_pattern)
        else:
            return self._find_latest_version()


    def _find_latest_by_pattern(self, pattern):
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
        old_umask = os.umask(0)
        os.makedirs(clone_tmp, 0777)
        os.umask(old_umask)                

        # get the most recent tag hash
        cwd = os.getcwd()
        try:
            # clone the repo
            self.__clone_repo(clone_tmp)
            os.chdir(clone_tmp)
            
            try:
                # get list of tags from git
                git_tags = subprocess_check_output("git tag", shell=True).split("\n")
            except Exception, e:
                raise TankError("Could not get list of tags for %s: %s" % (self._path, e))

        finally:
            os.chdir(cwd)
        
        if len(git_tags) == 0:
            raise TankError("Git repository %s doesn't seem to have any tags!" % self._path)

        version_to_use = self._find_latest_tag_by_pattern(git_tags, pattern)

        new_loc_dict = copy.deepcopy(self._location_dict)
        new_loc_dict["version"] = version_to_use

        return TankGitDescriptor(
            self._pipeline_config_path,
            self._bundle_install_path,
            new_loc_dict,
            self._type
        )

    def _find_latest_tag_by_pattern(self, version_numbers, pattern):
        """
        Given a list of version strings (e.g. 'v1.2.3'), find the one that best matches the given pattern.

        Version numbers passed in that don't match the pattern v1.2.3... will be ignored.

        :param version_numbers: List of version number strings, e.g. ``['v1.2.3', 'v1.2.5']``
        :param pattern: Version pattern string, e.g. 'v1.x.x'. Patterns are on the following forms:

            - v1.2.3 (can return this v1.2.3 but also any forked version under, eg. v1.2.3.2)
            - v1.2.x (examples: v1.2.4, or a forked version v1.2.4.2)
            - v1.x.x (examples: v1.3.2, a forked version v1.3.2.2)
            - v1.2.3.x (will always return a forked version, eg. v1.2.3.2)

        :returns: The most appropriate tag in the given list of tags
        :raises: TankError if parsing fails
        """
        # now put all version number strings which match the form
        # vX.Y.Z(.*) into a nested dictionary where it is keyed recursively
        # by each digit (ie. major, minor, increment, then any additional
        # digit optionally used by forked versions)
        #
        versions = {}
        for version_num in version_numbers:
            try:
                version_split = map(int, version_num[1:].split("."))
            except Exception, e:
                # this git tag is not on the expected form vX.Y.Z where X Y and Z are ints. skip.
                continue

            if len(version_split) < 3:
                # git tag has no minor or increment number. skip.
                continue

            # fill our versions dictionary
            #
            # For example, the following versions:
            # v1.2.1, v1.2.2, v1.2.3.1, v1.4.3, v1.4.2.1, v1.4.2.2, v1.4.1,
            #
            # Would generate the following:
            # {1:
            #   {2: {1: {},
            #        2: {},
            #        3: {1: {}
            #       }
            #   },
            #   4: {1: {},
            #       2: {1: {}, 2: {}},
            #       3: {}
            #       }
            #   }
            # }
            #
            current = versions
            for number in version_split:
                if number not in current:
                    current[number] = {}
                current = current[number]

        # now search for the latest version matching our pattern
        version_to_use = None
        if not re.match("^v([0-9]+|x)(.([0-9]+|x)){2,}$", pattern):
            raise TankError("Cannot parse version expression '%s'!" % pattern)

        # split our pattern, beware each part is a string (even integers)
        version_split = re.findall("([0-9]+|x)", pattern)
        if 'x' in version_split:
            # check that we don't have an incorrect pattern using x
            # then a digit, eg. v4.x.2
            if re.match("^v[0-9\.]+[x\.]+[0-9\.]+$", pattern):
                raise TankError("Incorrect version pattern '%s'. There should be no digit after a 'x'." % pattern)

        current = versions
        version_to_use = None
        # process each digit in the pattern
        for version_digit in version_split:
            if version_digit == 'x':
                # replace the 'x' by the latest at this level
                version_digit = max(current.keys(), key=int)
            version_digit = int(version_digit)
            if version_digit not in current:
                raise TankError("%s does not have a version matching the pattern '%s'. "
                                "Available versions are: %s" % (self._path, pattern, ", ".join(version_numbers)))
            current = current[version_digit]
            if version_to_use is None:
                version_to_use = "v%d" % version_digit
            else:
                version_to_use = version_to_use + ".%d" % version_digit

        # at this point we have a matching version (eg. v4.x.x => v4.0.2) but
        # there may be forked versions under this 4.0.2, so continue to recurse into
        # the versions dictionary to find the latest forked version
        while len(current):
            version_digit = max(current.keys())
            current = current[version_digit]
            version_to_use = version_to_use + ".%d" % version_digit

        return version_to_use

    def _find_latest_version(self):
        """
        Returns a descriptor object that represents the latest version.
        
        :returns: descriptor object
        """
        
        # now first clone the repo into a tmp location
        clone_tmp = os.path.join(tempfile.gettempdir(), "%s_tank_clone" % uuid.uuid4().hex)
        old_umask = os.umask(0)
        os.makedirs(clone_tmp, 0777)
        os.umask(old_umask)                

        # get the most recent tag hash
        cwd = os.getcwd()
        try:
            # clone the repo
            self.__clone_repo(clone_tmp)
            os.chdir(clone_tmp)
            
            try:
                git_hash = subprocess_check_output("git rev-list --tags --max-count=1", shell=True).strip()
            except Exception, e:
                raise TankError("Could not get list of tags for %s: %s" % (self._path, e))

            try:
                latest_version = subprocess_check_output("git describe --tags %s" % git_hash, shell=True).strip()
            except Exception, e:
                raise TankError("Could not get tag for hash %s: %s" % (hash, e))
        
        finally:
            os.chdir(cwd)

        new_loc_dict = copy.deepcopy(self._location_dict)
        new_loc_dict["version"] = latest_version

        return TankGitDescriptor(self._pipeline_config_path, self._bundle_install_path, new_loc_dict, self._type)

    def __clone_repo(self, target_path):
        """
        Clone the repo into the target path
        
        :param target_path: The target path to clone the repo to
        :raises:            TankError if the clone command fails
        """
        # Note: git doesn't like paths in single quotes when running on 
        # windows - it also prefers to use forward slashes!
        sanitized_repo_path = self._path.replace(os.path.sep, "/")        
        execute_git_command("clone -q \"%s\" \"%s\"" % (sanitized_repo_path, target_path))

