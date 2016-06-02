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
from distutils.core import setup
setup(
    name="sgtk",
    version="0.18",
    # These are the pure Python packages we ship
    packages=[
        "sgtk",
        "tank",
        "tank.authentication",
        "tank.bootstrap",
        "tank.commands",
        "tank.deploy",
        "tank.descriptor",
        "tank.descriptor.io_descriptor",
        "tank.folder",
        "tank.platform",
        "tank.platform.qt",
        "tank.util",
        "tank_vendor",
        "tank_vendor.ruamel_yaml",
        "tank_vendor.shotgun_api3",
        "tank_vendor.shotgun_api3.lib",
        "tank_vendor.shotgun_api3.lib.httplib2",
        "tank_vendor.shotgun_authentication",
        "tank_vendor.yaml",
    ],
    # Additional data which must sit in packages folders
    package_data={
        "tank.descriptor": ["resources/*"],
        "tank.util": ["resources/*"],
        "tank.platform.qt": [
            "*.png", "*.sh", "*.ui", "*.qrc", "*.css", "*.qpalette",
        ],
        "tank_vendor.shotgun_api3.lib.httplib2": ["cacerts.txt"],
    },
    # Everything can be found under the python folder
    package_dir = {"": "python"}
)