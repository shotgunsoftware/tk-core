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

import os
import pathlib
import subprocess  # nosec
import sys
import tempfile
import zipfile


def zip_recursively(zip_file, root_dir, folder_name):
    """Zip the files at the given folder recursively."""

    path = root_dir / folder_name
    if path.is_dir():
        for root, _, files in os.walk(path):
            for f in files:
                full_file_path = pathlib.Path(os.path.join(root, f))
                zip_file.write(full_file_path, full_file_path.relative_to(root_dir))
    else:
        zip_file.write(path, path.relative_to(root_dir))


def install_common_python_packages(python_dist_dir):
    """
    Install common Python packages.

    :param python_dist_dir: The path containing the package requirements.txt
        file, and where to install the packages.
    :type python_dist_dir: str
    """

    if not os.path.exists(python_dist_dir):
        print(f"Cannot find Python distribution folder {python_dist_dir}")
        return

    with tempfile.TemporaryDirectory() as temp_dir:
        print("Installing common Python packages...")

        temp_dir_path = pathlib.Path(temp_dir)

        requirements_txt = os.path.join(python_dist_dir, "requirements.txt")
        if not os.path.exists(requirements_txt):
            raise Exception(f"Cannot find requirements file {requirements_txt}")

        frozen_requirements_txt = os.path.join(
            python_dist_dir, "frozen_requirements.txt"
        )

        # Pip install everything and capture everything that was installed.
        subprocess.run(
            [
                "python",
                "-m",
                "pip",
                "install",
                "-r",
                requirements_txt,
                "--no-compile",
                # The combination of --target and --upgrade forces pip to install
                # all packages to the temporary directory, even if an already existing
                # version is installed
                "--target",
                temp_dir,
                "--upgrade",
            ]
        )
        subprocess.run(
            ["python", "-m", "pip", "freeze", "--path", temp_dir],
            stdout=open(frozen_requirements_txt, "w"),
        )

        # Quickly compute the number of requirements we have.
        nb_dependencies = len([_ for _ in open(frozen_requirements_txt, "rt")])

        # Figure out if those packages were installed as single file packages or folders.
        package_names = [
            package_name
            for package_name in os.listdir(temp_dir)
            if "info" not in package_name and package_name != "bin"
        ]

        # Make sure we found as many Python packages as there
        # are packages listed inside frozen_requirements.txt
        # assert len(package_names) == nb_dependencies
        assert len(package_names) >= nb_dependencies

        # Write out the zip file for python packages. Compress the zip file with ZIP_DEFLATED. Note
        # that this requires zlib to decompress when importing. Compression also causes import to
        # be slower, but the file size is simply too large to not be compressed
        pkgs_zip_path = os.path.join(python_dist_dir, "pkgs.zip")
        pkgs_zip = zipfile.ZipFile(pkgs_zip_path, "w", zipfile.ZIP_DEFLATED)

        for package_name in package_names:
            print(f"Zipping {package_name}...")
            zip_recursively(pkgs_zip, temp_dir_path, package_name)


def main():
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    install_common_python_packages(f"requirements/{python_version}")


if __name__ == "__main__":
    main()
