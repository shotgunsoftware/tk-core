"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

A github descriptor which watches app repositories and grabs changes as they happen.
This makes it easier to "get latest" even if there is a larger group collaborating
on a larger number of repos.
"""

import os
import re
import subprocess

from ..errors import TankError
from .descriptor import AppDescriptor


class TankGitHubDevDescriptor(AppDescriptor):
    """
    Represents a repository in github.
    """

    def __init__(self, project_root, location_dict, type, version=None):
        """
        Note! The version is special. Some notes:

        Because the location does not have a version (it always tracks HEAD),
        we typically don't instantiate this object with a notion of a version.

        However, in order to probe that a more recent version is available
        in github, we need to be able to distinguish between versions.

        The find_latest_version() method will return a descriptor object
        which represents the latest github commit.

        - If you ask get_version() on the find_latest_version() object, the
          most recent github SHA is returned.
        - If you ask get_version() on an object created from a location string,
          the local head revision SHA is returned. However, if the git repo does
          not yet exist locally, "unknown" is returned.
        """
        super(TankGitHubDevDescriptor, self).__init__(project_root, location_dict)

        self._type = type
        self._vendor = location_dict.get("vendor")
        self._name = location_dict.get("name")
        self._display_name = location_dict.get("display_name", self._name)
        
        if self._vendor is None or self._name is None:
            raise TankError("Github dev descriptor is not valid: %s" % str(location_dict))
        self._version = version
        self._repo_str = "git@github.com:%s/%s.git" % (self._vendor, self._name)
        

    def __repr__(self):
        if self._version is None:
            return "Github dev item %s %s LOCAL HEAD" % (self._vendor, self._name)
        else:
            return "Github dev item %s %s %s" % (self._vendor, self._name, self._version)

    ###############################################################################################
    # data accessors

    def _get_default_display_name(self):
        """
        Returns the display name for this item
        """
        return self._display_name

    def get_short_name(self):
        """
        Returns a short name, suitable for use in configuration files
        and for folders on disk
        """
        return self._name

    def __get_local_version(self):
        """
        returns the local version of a repo
        """
        if not os.path.exists(self.get_path()):
            return "unknown"

        cwd = os.getcwd()
        try:
            os.chdir(self.get_path())
            revision = subprocess.check_output("git rev-parse HEAD", shell=True).strip()
        except:
            revision = "unknown"
        finally:
            os.chdir(cwd)

        return revision

    def get_version(self):
        """
        Returns the version number string for this item
        """
        # if the descriptor was initialized without a version number it means
        # that we should prove the current code for its version no.
        if self._version is None:
            # get the SHA for the latest version
            self._version = self.__get_local_version()

        return self._version

    def get_location(self):
        """
        Returns the location for this descriptor
        """
        return self._location_dict

    def get_path(self):
        """
        returns the path to the folder where this item resides
        """
        name = "%s_%s" % (self._vendor, self._name)
        return self._get_local_location(self._type, "github_dev", name, "repository")

    ###############################################################################################
    # methods

    def exists_local(self):
        """
        Returns true if this item exists in a local repo
        """

        # this is tricky - we are not checking for the existance of a particular repository,
        # we are checking for the existance of a particular VERSION!

        if not os.path.exists(self.get_path()):
            # no repo at all - definitely doesn't exist local :)
            return False

        # get this descriptors version
        our_version = self.get_version()
        # get local repo's version
        local_version = self.__get_local_version()

        return our_version == local_version

    def download_local(self):
        """
        Retrieves this version to local repo.
        Will exit early if app already exists local.
        """
        target = self.get_path()

        if not os.path.exists(target):

            # perhaps we should use the folder hook here?
            os.makedirs(target, 0775)

            cmd = "git clone %s %s" % (self._repo_str, target)
            if os.system(cmd) != 0:
                raise Exception("Could not execute command '%s'!" % cmd)

        # get latest via git pull
        cwd = os.getcwd()
        try:
            os.chdir(target)
            cmd = "git pull"
            if os.system(cmd) != 0:
                raise Exception("Could not execute command '%s'!" % cmd)
        finally:
            os.chdir(cwd)

    def find_latest_version(self):
        """
        Returns a descriptor object that represents the latest version
        """
        # ask the remote github branch about the latest SHA
        ver = None
        try:
            revision = subprocess.check_output("git ls-remote %s master" % self._repo_str, shell=True).strip()
            # output:
            # 0992a93b450179d0ff7904ae9cbbf9867502dc3b    refs/heads/master
            # grab sha
            ver = re.search("^([0-9a-f]+)", revision).groups()[0]
        except:
            pass

        return TankGitHubDevDescriptor(self._project_root, self._location_dict, self._type, ver)
