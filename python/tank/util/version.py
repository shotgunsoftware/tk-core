# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import re

from distutils.version import LooseVersion
import re

class Version(object):

    def __init__(self, version_string):

        self._app_name = None
        self._version_string = None
        self._version_major = -1
        self._version_minor = -1

        if version_string:
            # Matching only the numbering part not potential appplication name
            match = re.search(r'([\d.]+.*)',version_string)
            if match:

                # group(0) returns only the number part
                tmp_version_string = match.group(0)

                # Shop off the version string and also remove leading and trailing whitespaces
                self._app_name = version_string.replace(tmp_version_string, "").rstrip().lstrip()
                # If empty, replace with None for consistency with other init situation
                if len(self._app_name) == 0:
                    self._app_name = None

                # Shop off trailing "." from number version if not following by a number
                if tmp_version_string[-1]==".":
                    tmp_version_string = tmp_version_string[:-1]

                self._version_string = tmp_version_string

                number_list = self._version_major = tmp_version_string.split(" ")[0].split(".")
                if number_list:
                    if len(number_list)>0:
                        if number_list[0].isdigit():
                            self._version_major = int(number_list[0])
                    if len(number_list)>1:
                        if number_list[1].isdigit():
                            self._version_minor = int(number_list[1])
            else:
                self._app_name = version_string

    def __repr__(self):
        """Official str representation of an application version."""
        return "%s" % (self._version_string)

    def __str__(self):
        """Readable str representation of the version object."""
        return "%s: %s, major:%d, minor:%d, app name:%s" % (self.__class__,
                                               repr(self),
                                               self.major,
                                               self.minor,
                                               self.app_name
                                               )

    @property
    def app_name(self):
        return self._app_name

    @property
    def version_string(self):
        return self._version_string

    @property
    def major(self):
        return int(self._version_major)

    @property
    def minor(self):
        return int(self._version_minor)



def is_version_head(version):
    """
    Returns if the specified version is HEAD or MASTER. The comparison is case insensitive.

    :param version: Version to test.

    :returns: True if version is HEAD or MASTER, false otherwise.
    """
    return version.lower() in ["head", "master"]


def is_version_newer(a, b):
    """
    Is the version number string a newer than b?

    a=v0.12.1 b=0.13.4 -- Returns False
    a=v0.13.1 b=0.13.1 -- Returns True
    a=HEAD b=0.13.4 -- Returns False
    a=master b=0.13.4 -- Returns False

    """
    if b is None:
        # a is always newer than None
        return True

    if is_version_head(a):
        # our version is latest
        return True

    if is_version_head(b):
        # comparing against HEAD - our version is always old
        return False

    if a.startswith("v"):
        a = a[1:]
    if b.startswith("v"):
        b = b[1:]

    return LooseVersion(a) > LooseVersion(b)


def is_version_older(a, b):
    """
    Is the version number string a older than b?

    a=v0.12.1 b=0.13.4 -- Returns False
    a=v0.13.1 b=0.13.1 -- Returns True
    a=HEAD b=0.13.4 -- Returns False
    a=master b=0.13.4 -- Returns False

    """
    if is_version_head(a):
        # other version is latest
        return False

    if is_version_head(b):
        # comparing against HEAD - our version is always old
        return True

    if a.startswith("v"):
        a = a[1:]
    if b.startswith("v"):
        b = b[1:]

    return LooseVersion(a) < LooseVersion(b)

def is_version_number(version):
    """
    Tests whether the given string is a properly formed
    version number (ex: v1.2.3). The test is made using
    the pattern r"v\d+.\d+.\d+$"

    :param str version: The version string to test.

    :rtype: bool
    """
    match = re.match(r"v\d+.\d+.\d+$", version)

    if match:
        return True
    else:
        return False

