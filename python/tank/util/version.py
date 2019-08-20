# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from __future__ import absolute_import
import re

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
    return _compare_versions(a, b)


def is_version_older(a, b):
    """
    Is the version number string a older than b?

    a=v0.12.1 b=0.13.4 -- Returns True
    a=v0.13.1 b=0.13.1 -- Returns True
    a=HEAD b=0.13.4 -- Returns False
    a=master b=0.13.4 -- Returns False

    """
    return _compare_versions(b, a)


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


def _compare_versions(a, b):
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

    # In Python 3, LooseVersion comparisons between versions where a non-numeric
    # version component is compared to a numeric one fail.  We'll work around this
    # as follows:
    version_expr = re.compile(r"\d+\.\d+\.\d+$")
    if version_expr.match(a) and version_expr.match(b):
        # in the case of two correctly formed numeric versions, use LooseVersion
        # for comparison.
        return LooseVersion(a) > LooseVersion(b)
    elif version_expr.match(a) or version_expr.match(b):
        # To mimick the behavior in Python 2.7 as closely as possible, we will
        # consider whichever version is non-numeric as newer.
        return is_version_number(a)
    # In the case that both versions are non-numeric, do a string comparison.
    return a > b
