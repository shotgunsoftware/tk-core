"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

This git descriptor is for a formal git workflow.
It will base version numbering off tags in git.
"""

import os
import copy
import uuid
import zipfile
import tempfile
import subprocess

from ..api import Tank
from ..errors import TankError
from ..platform import constants
from .descriptor import AppDescriptor

class TankGitDescriptor(AppDescriptor):
    """
    Represents a repository in git. New versions are represented by new tags.
    """

    def __init__(self, project_root, location_dict, type):
        super(TankGitDescriptor, self).__init__(project_root, location_dict)

        self._type = type
        self._tk = Tank(project_root)
        self._path = location_dict.get("path")
        self._version = location_dict.get("version")

        if self._path is None or self._version is None:
            raise TankError("Git descriptor is not valid: %s" % str(location_dict))

    def __repr__(self):
        if self._type == AppDescriptor.APP:
            return "Git App %s, %s" % (self._path, self._version)
        elif self._type == AppDescriptor.ENGINE:
            return "Git Engine %s, %s" % (self._path, self._version)
        else:
            return "Git <Unknown> %s, %s" % (self._path, self._version)

    ###############################################################################################
    # data accessors

    def _get_default_display_name(self):
        """
        Returns the display name for this item
        """
        return os.path.basename(self._path)

    def get_short_name(self):
        """
        Returns a short name, suitable for use in configuration files
        and for folders on disk
        """
        return os.path.basename(self._path)

    def get_version(self):
        """
        Returns the version number string for this item
        """
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
        name = os.path.basename(self._path)
        return self._get_local_location(self._type, "git", name, self._version)

    ###############################################################################################
    # methods

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
            self._tk.execute_hook(constants.CREATE_FOLDERS_CORE_HOOK_NAME, path=target)

        # do a git archive from the remote repository
        # download to temp
        zip_tmp = os.path.join(tempfile.gettempdir(), "%s_tank.zip" % uuid.uuid4().hex)
        cmd = "git archive --format zip --output %s --remote %s %s" % (zip_tmp, self._path, self._version)
        if os.system(cmd) != 0:
            raise TankError("Failed to download %s - error executing command %s" % (self, cmd))

        # unzip core zip file to app target location
        z = zipfile.ZipFile(zip_tmp, "r")
        z.extractall(target)

    def find_latest_version(self):
        """
        Returns a descriptor object that represents the latest version
        """
        # get the most recent tag hash
        cwd = os.getcwd()
        try:
            os.chdir(self._path)
            git_hash = subprocess.check_output("git rev-list --tags --max-count=1", shell=True).strip()
        except Exception, e:
            raise TankError("Could not get list of tags for %s: %s" % (self._path, e))
        finally:
            os.chdir(cwd)

        # and now get the name of the tag fort his hash
        cwd = os.getcwd()
        try:
            os.chdir(self._path)
            latest_version = subprocess.check_output("git describe --tags %s" % git_hash, shell=True).strip()
        except Exception, e:
            raise TankError("Could not get tag for hash %s: %s" % (hash, e))
        finally:
            os.chdir(cwd)

        new_loc_dict = copy.deepcopy(self._location_dict)
        new_loc_dict["version"] = latest_version

        return TankGitDescriptor(self._project_root, new_loc_dict, self._type)


