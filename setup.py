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
import glob
import os
import re
import shutil
import subprocess
import sys

from setuptools import find_packages, setup
from setuptools.command.build_py import build_py as _build_py


class build_py(_build_py):
    def run(self):
        super().run()
        # Copy requirements/any/*.zip into tank_vendor/vendor_any/ inside the
        # build tree so pip-installed packages can find version-independent
        # vendor zips (e.g. flow_data_sdk). Editable installs skip this step
        # intentionally — they use the source-tree requirements/any/ path.
        src_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "requirements", "any"
        )
        dst_dir = os.path.join(self.build_lib, "tank_vendor", "vendor_any")
        if os.path.isdir(src_dir):
            os.makedirs(dst_dir, exist_ok=True)
            for zip_path in glob.glob(os.path.join(src_dir, "*.zip")):
                shutil.copy2(zip_path, dst_dir)


def get_version():
    """
    Helper to extract a version number for this module.

    :returns: A major.minor.patch[.sub] version string or "dev".
    """
    # Try to extract the version number from git
    # this will work when installing from a locally cloned repo, or directly from
    # github, using the syntax:
    #
    # pip install git+https://github.com/shotgunsoftware/tk-core@v0.18.32#egg=sgtk
    #
    # Note: if you install from a cloned git repository
    # (e.g. pip install ./tk-core), the version number
    # will be picked up from the most recently added tag.
    try:
        version_git = subprocess.check_output(
            ["git", "describe", "--tags", "--abbrev=0"], universal_newlines=True
        ).rstrip()
        if re.match(r"v[0-9]*.[0-9]*.[0-9]*", version_git):
            return version_git
        return "dev"
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


def get_install_requires():
    """
    Read dependencies from the version-specific requirements.txt.

    This ensures pip installations use the same dependency versions
    as those vendored in pkgs.zip for Toolkit distributions.

    :returns: A list of requirement strings, e.g. ["PyYAML==6.0.2", ...].
    """
    req_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "requirements",
        f"{sys.version_info.major}.{sys.version_info.minor}",
        "requirements.txt",
    )
    if not os.path.exists(req_file):
        raise Exception(
            f"Python {sys.version_info.major}.{sys.version_info.minor}"
            " is not supported"
        )

    with open(req_file) as f:
        return [
            line.strip()
            for line in f
            if line.strip() and not line.strip().startswith("#")
        ]


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
    cmdclass={"build_py": build_py},
    name="sgtk",
    version=get_version(),
    description="Flow Production Tracking Toolkit Core API",
    long_description=readme,
    author="Autodesk, Inc",
    url="https://github.com/shotgunsoftware/tk-core",
    license=license,
    # Dependencies for pip installations (when pkgs.zip is not available).
    # Versions are read from requirements/<python_version>/requirements.txt
    # to stay in sync with the vendored packages in pkgs.zip.
    install_requires=get_install_requires(),
    # Recursively discover all packages in python folder, excluding any tests
    packages=find_packages(
        "python", exclude=("*.tests", "*.tests.*", "tests.*", "tests")
    ),
    # Additional data which must sit in packages folders
    package_data={
        # If any package contains data files, include them:
        "": ["resources/*", ".txt", "*.*", "hooks/*.py"]
    },
    # Everything can be found under the python folder, but installed without it
    package_dir={"": "python"},
)
