# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

# Basic setup.py so tk-core could be installed as
# a standard Python package
from setuptools import setup, find_packages
import os
import subprocess

def get_version():
    """
    Helper to extract a version number for this module.

    :returns: A major.minor.patch[.sub] version string or "dev".
    """
    # Try to extract the version number from git
    # this will work when installing from a locally cloned repo, or directly from
    # github, using something like:
    # pip install git+https://github.com/shotgunsoftware/tk-core@v0.0.1.piptest#egg=sgtk
    # Please note that the version number will be something like: v0.18.32-12-g24316e3
    # 'git describe' can certainly be tuned to only return a plain tag if needed,
    # any tag instead of just annotated ones, e.g. with something like:
    # git describe --abbrev=0 --tags
    try:
        version_git = subprocess.check_output(["git", "describe"]).rstrip()
        return version_git
    except:
        # Blindly ignore problems, git might be not available, or the user could
        # be installing from zip archive, etc...
        pass

    # If everything fails, return a sensible string highlighting that the version
    # couldn't be extracted. If a version is not specified in `setup`, 0.0.0
    # will be used by default, it seems better to have an explicit keyword for
    # this case, following TK "dev" locator pattern and the convention described here:
    # http://peak.telecommunity.com/DevCenter/setuptools#specifying-your-project-s-version
    return "dev"

# Retrieve long description and licence from external files
try:
    f = open("README.md")
    readme = f.read().strip()
finally:
    if f:
        f.close()
try:
    f = open("LICENSE")
    license = f.read().strip()
finally:
    if f:
        f.close()

setup(
    name="sgtk",
    version=get_version(),
    description="Shotgun Pipeline Toolkit Core API",
    long_description=readme,
    author="Shotgun Software",
    author_email="support@shotgunsoftware.com",
    url="https://github.com/shotgunsoftware/tk-core",
    license=license,
    # Recursively discover all packages in python folder, excluding any tests
    packages=find_packages("python", exclude=("*.tests", "*.tests.*", "tests.*", "tests")),

    # Additional data which must sit in packages folders
    package_data={
        # If any package contains data files, include them:
        "": ["resources/*", ".txt", "*.*"],
    },
    # Everything can be found under the python folder, but installed without it
    package_dir = {"": "python"}
)
