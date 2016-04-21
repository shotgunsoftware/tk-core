# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from distutils.version import LooseVersion

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
