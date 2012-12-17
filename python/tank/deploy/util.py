"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------
"""

from distutils.version import LooseVersion


def is_version_newer(a, b):
    """
    Is the version number string a newer than b?
    
    a=v0.12.1 b=0.13.4 -- Returns False
    a=v0.13.1 b=0.13.1 -- Returns True
    a=HEAD b=0.13.4 -- Returns False
    a=master b=0.13.4 -- Returns False

    """
    if a.lower() in ["head", "master"]:
        # our version is latest
        return True
    
    if b.lower() in ["head", "master"]:
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
    if a.lower() in ["head", "master"]:
        # other version is latest
        return False
    
    if b.lower() in ["head", "master"]:
        # comparing against HEAD - our version is always old
        return True

    if a.startswith("v"):
        a = a[1:]
    if b.startswith("v"):
        b = b[1:]

    return LooseVersion(a) < LooseVersion(b)
