#!/usr/bin/env python3
# Copyright (c) 2024 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import subprocess
import os
import sys

from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile


PYTHON_VERSION = f"{sys.version_info.major}.{sys.version_info.minor}"


def zip_recursively(zip_file, root_dir, folder_name):
    for root, _, files in os.walk(root_dir / folder_name):
        for file in files:
            full_file_path = Path(os.path.join(root, file))
            zip_file.write(full_file_path, full_file_path.relative_to(root_dir))


def ensure_init_file(package_dir):
    """
    Ensures that every package contains an __init__.py file.
    This is required for Python to recognize the directory as a package.
    """
    for root, _, files in os.walk(package_dir):
        if "__init__.py" not in files:
            init_file_path = Path(root) / "__init__.py"
            with open(init_file_path, "w") as f:
                f.write("")


with TemporaryDirectory() as temp_dir:
    temp_dir = Path(temp_dir)

    # Make sure the requirements folder exists
    if not os.path.exists(f"requirements/{PYTHON_VERSION}/requirements.txt"):
        raise RuntimeError(f"Python {PYTHON_VERSION} requirements not found.")

    # Pip install everything and capture everything that was installed.
    print(f"Installing Python {PYTHON_VERSION} requirements...")
    subprocess.run(
        [
            "python",
            "-m",
            "pip",
            "install",
            "-r",
            f"requirements/{PYTHON_VERSION}/requirements.txt",
            "--no-compile",
            # The combination of --target and --upgrade forces pip to install
            # all packages to the temporary directory, even if an already existing
            # version is installed
            "--target",
            str(temp_dir),
            "--upgrade",
        ]
    )
    print("Writing out frozen requirements...")
    subprocess.run(
        ["python", "-m", "pip", "freeze", "--path", str(temp_dir)],
        stdout=open(f"requirements/{PYTHON_VERSION}/frozen_requirements.txt", "w"),
    )
    print("temp_dir: ", temp_dir)

    # Figure out if those packages were installed as single file packages or folders.
    package_names = [
        package_name
        for package_name in os.listdir(temp_dir)
        if "info" not in package_name
        and package_name != "bin"
        and ".pyd" not in package_name
    ]

    # Write out the zip file
    pkgsZip = ZipFile(
        Path(__file__).parent / "requirements" / PYTHON_VERSION / "pkgs.zip", "w"
    )
    # For every single package
    for package_name in package_names:
        print(f"Zipping {package_name}...")
        # If we have a .py file to zip, simple write it
        full_package_path = temp_dir / package_name
        if full_package_path.suffix == ".py":
            pkgsZip.write(full_package_path, full_package_path.relative_to(temp_dir))
        else:
            # Otherwise zip package folders recursively.
            ensure_init_file(full_package_path)
            zip_recursively(pkgsZip, temp_dir, package_name)
