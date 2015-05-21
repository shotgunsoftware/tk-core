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
from .descriptor import AppDescriptor
from .zipfilehelper import unzip_file

class TankGitDescriptor(AppDescriptor):
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
        
            - v1.2.3 (means the descriptor returned will inevitably be same as self)
            - v1.2.x 
            - v1.x.x

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

        # now put all version number strings which match the form
        # vX.Y.Z into a nested dictionary where it is keyed by major,
        # then minor then increment.
        #
        # For example, the following versions:
        # v1.2.1, v1.2.2, v1.2.3, v1.4.3, v1.4.2, v1.4.1
        # 
        # Would generate the following:
        # { "1": { "2": [1,2,3], "4": [3,2,1] } }
        #  
        
        versions = {}
        
        for version_num in git_tags:

            try:
                (major_str, minor_str, increment_str) = version_num[1:].split(".")
                (major, minor, increment) = (int(major_str), int(minor_str), int(increment_str))
            except:
                # this version number was not on the form vX.Y.Z where X Y and Z are ints. skip.
                continue
            
            if major not in versions:
                versions[major] = {}
            if minor not in versions[major]:
                versions[major][minor] = []
            if increment not in versions[major][minor]:
                versions[major][minor].append(increment)


        # now handle the different version strings
        version_to_use = None
        if "x" not in pattern:
            # we are looking for a specific version
            if pattern not in git_tags:
                raise TankError("Could not find requested version '%s' in '%s'." % (pattern, self._path))
            else:
                # the requested version exists in the app store!
                version_to_use = pattern 
        
        elif re.match("v[0-9]+\.x\.x", pattern):
            # we have a v123.x.x pattern
            (major_str, _, _) = pattern[1:].split(".")
            major = int(major_str)
            
            if major not in versions:
                raise TankError("%s does not have a version matching the pattern '%s'. "
                                "Available versions are: %s" % (self._path, pattern, ", ".join(git_tags)))

            # now find the max version
            max_minor = max(versions[major].keys())            
            max_increment = max(versions[major][max_minor])
            version_to_use = "v%s.%s.%s" % (major, max_minor, max_increment)
            
            
        elif re.match("v[0-9]+\.[0-9]+\.x", pattern):
            # we have a v123.345.x pattern
            (major_str, minor_str, _) = pattern[1:].split(".")
            major = int(major_str)
            minor = int(minor_str)

            # make sure the constraints are fulfilled
            if (major not in versions) or (minor not in versions[major]):
                raise TankError("%s does not have a version matching the pattern '%s'. "
                                "Available versions are: %s" % (self._path, pattern, ", ".join(git_tags)))
            
            # now find the max increment
            max_increment = max(versions[major][minor])
            version_to_use = "v%s.%s.%s" % (major, minor, max_increment)
        
        else:
            raise TankError("Cannot parse version expression '%s'!" % pattern)


        new_loc_dict = copy.deepcopy(self._location_dict)
        new_loc_dict["version"] = version_to_use

        return TankGitDescriptor(
            self._pipeline_config_path,
            self._bundle_install_path,
            new_loc_dict,
            self._type
        )
        


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


