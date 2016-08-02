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
    version="0.18",
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
        "": ["resources/*", ".txt", "*.png", "*.sh", "*.ui", "*.qrc", "*.css", "*.qpalette"],
    },
    # Everything can be found under the python folder, but installed without it
    package_dir = {"": "python"}
)
