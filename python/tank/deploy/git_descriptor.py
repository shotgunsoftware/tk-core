"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

This git descriptor is for a formal git workflow.
It will base version numbering off tags in git.
"""

import os
import copy
import uuid
import tempfile

from .util import subprocess_check_output
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

    def __init__(self, pipeline_config, location_dict, type):
        super(TankGitDescriptor, self).__init__(pipeline_config, location_dict)

        self._pipeline_config = pipeline_config
        self._type = type
        self._path = location_dict.get("path")
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
        # git@github.com:manneohrstrom/tk-hiero-publish.git -> tk-hiero-publish
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
            # Note: git doesn't like paths in single quotes when running on windows!
            if os.system("git clone -q \"%s\" %s" % (self._path, clone_tmp)) != 0:
                raise TankError("Could not clone git repository '%s'!" % self._path)
            
            os.chdir(clone_tmp)
            
            if os.system("git archive --format zip --output %s %s" % (zip_tmp, self._version)) != 0:
                raise TankError("Could not find tag %s in git repository %s!" % (self._version, self._path))
        finally:
            os.chdir(cwd)
        
        # unzip core zip file to app target location
        unzip_file(zip_tmp, target)

    def find_latest_version(self):
        """
        Returns a descriptor object that represents the latest version
        """
        # now first clone the repo into a tmp location
        clone_tmp = os.path.join(tempfile.gettempdir(), "%s_tank_clone" % uuid.uuid4().hex)
        old_umask = os.umask(0)
        os.makedirs(clone_tmp, 0777)
        os.umask(old_umask)                

        # get the most recent tag hash
        cwd = os.getcwd()
        try:
            # Note: git doesn't like paths in single quotes when running on windows!
            if os.system("git clone -q \"%s\" %s" % (self._path, clone_tmp)) != 0:
                raise TankError("Could not clone git repository '%s'!" % self._path)
            
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

        return TankGitDescriptor(self._pipeline_config, new_loc_dict, self._type)


