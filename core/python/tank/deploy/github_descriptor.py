"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

This github descriptor is for a formal github workflow.
It will base version numbering off tags in github.

A studio may use github to formally manage its own apps.

NOTE! Currently only supports public repos!

"""

import os
import copy
import uuid
import shutil
import urllib
import tempfile

# use sg api json to cover py 2.5
# todo - replace with proper external library
from tank_vendor import shotgun_api3 
json = shotgun_api3.shotgun.json

from ..api import Tank
from ..errors import TankError
from ..platform import constants
from .descriptor import AppDescriptor
from .zipfilehelper import unzip_file
from . import util


class TankGitHubDescriptor(AppDescriptor):
    """
    Represents a repository in github. New versions are represented by new tags.
    This class only supports public repositories.
    """

    def __init__(self, project_root, location_dict, type):
        super(TankGitHubDescriptor, self).__init__(project_root, location_dict)

        self._type = type
        self._vendor = location_dict.get("vendor")
        self._name = location_dict.get("repo")
        self._version = location_dict.get("version")
        self._tk = Tank(project_root)

        if self._vendor is None or self._name is None or self._version is None:
            raise TankError("Github descriptor is not valid: %s" % str(location_dict))

    def get_doc_url(self):
        """
        Returns the documentation url for this item. Returns None if the documentation url
        is not defined.
        """
        #https://github.com/shotgunsoftware/tk-core/wiki
        return "https://github.com/%s/%s/wiki" % (self._vendor, self._name)

    def get_system_name(self):
        """
        Returns a short name, suitable for use in configuration files
        and for folders on disk
        """
        return self._name

    def get_version(self):
        """
        Returns the version number string for this item
        """
        return self._version

    def get_path(self):
        """
        returns the path to the folder where this item resides
        """
        name = "%s_%s" % (self._vendor, self._name)
        return self._get_local_location(self._type, "github", name, self._version)

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

        # now attempt to donwload a tag zip file from github
        # urls are on the form
        # https://github.com/shotgunsoftware/python-api/zipball/v3.0.7
        # https://github.com/VENDOR/APP/zipball/TAG
        url = "https://github.com/%s/%s/zipball/%s" % (self._vendor, self._name, self._version)
        (zip_tmp_file, headers) = urllib.urlretrieve(url)

        # now the root folder in this zip file is a unique identifier
        # produced by github - we need to discard that.
        try:
            # unpack zip into temp location
            tmp_folder = os.path.join(tempfile.gettempdir(), "tanktmp_%s" % uuid.uuid4().hex)
            os.mkdir(tmp_folder)
            unzip_file(zip_tmp_file, tmp_folder)
            # get actual file location
            payload = os.path.join(tmp_folder, os.listdir(tmp_folder)[0])
        except Exception, e:
            raise TankError("Could not unpack github tag archive %s: %s" % (url, e))

        # copy all files in the payload folder into the target location
        target = self.get_path()
        
        # make sure parent folder exists
        parent_folder = os.path.dirname(target)
        if not os.path.exists(parent_folder):
            self._tk.execute_hook(constants.CREATE_FOLDERS_CORE_HOOK_NAME, path=parent_folder, sg_entity=None)
        
        # and move it into place
        shutil.move(payload, target)

    def find_latest_version(self):
        """
        Returns a descriptor object that represents the latest version
        """
        # to get all tags for a repository, use github API v3
        # see http://developer.github.com/v3/repos/
        # GET /repos/:user/:repo/tags
        #
        # response
        #
        #[
        #  {
        #    "commit": {
        #      "url": "https://api.github.com/repos/manneohrstrom/tk-shell-helloworld/commits/0b734cfbaa9c7ba270af277ccae9b0f3fa95a605",
        #      "sha": "0b734cfbaa9c7ba270af277ccae9b0f3fa95a605"
        #    },
        #    "tarball_url": "https://github.com/manneohrstrom/tk-shell-helloworld/tarball/v0.1.1",
        #    "name": "v0.1.1",
        #    "zipball_url": "https://github.com/manneohrstrom/tk-shell-helloworld/zipball/v0.1.1"
        #  },
        #  {
        #    "commit": {
        #      "url": "https://api.github.com/repos/manneohrstrom/tk-shell-helloworld/commits/63656d19dac07951fce44c621e2858703d33e361",
        #      "sha": "63656d19dac07951fce44c621e2858703d33e361"
        #    },
        #    "tarball_url": "https://github.com/manneohrstrom/tk-shell-helloworld/tarball/v0.1.0",
        #    "name": "v0.1.0",
        #    "zipball_url": "https://github.com/manneohrstrom/tk-shell-helloworld/zipball/v0.1.0"
        #  }
        #]

        try:
            url = "https://api.github.com/repos/%s/%s/tags" % (self._vendor, self._name)
            fh = urllib.urlopen(url)
            github_response = json.load(fh)
            fh.close()

            tags = [ x.get("name", "") for x in github_response]
        except:
            raise TankError("Could not find list of versions for %s!")

        # now find the highest tag number
        highest = None
        for x in tags:
            if highest is None:
                highest = x
            else:
                if util.is_version_newer(x, highest):
                    highest = x

        new_loc_dict = copy.deepcopy(self._location_dict)
        new_loc_dict["version"] = highest

        return TankGitHubDescriptor(self._project_root, new_loc_dict, self._type)


