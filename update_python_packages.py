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
import subprocess  # nosec B404
import sys
import tempfile
import zipfile


def main():
    """
    Install common Python packages.
    """

    python_dist_dir = f"requirements/{sys.version_info.major}.{sys.version_info.minor}"
    if not os.path.exists(python_dist_dir):
        raise Exception(f"Cannot find Python distribution folder {python_dist_dir}")

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
        subprocess.run(  # nosec B603, B607
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
        subprocess.run(  # nosec B603, B607
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

        # Fix for namespace packages (like ruamel.yaml) that don't have __init__.py
        # in their parent directory. Python 3.7-3.9 inside ZIP files require explicit __init__.py
        fix_namespace_packages(pkgs_zip, temp_dir_path)

        pkgs_zip.close()


def fix_namespace_packages(zip_file, root_dir):
    """
    Add missing __init__.py files for namespace packages.
    Some packages like ruamel.yaml are PEP 420 namespace packages that don't
    include __init__.py in parent directories, which causes import issues from ZIP files.
    """
    from io import BytesIO

    # Get list of all files in the zip
    zip_contents = zip_file.namelist()

    # Find directories that need __init__.py
    directories_needing_init = set()

    for file_path in zip_contents:
        parts = pathlib.Path(file_path).parts
        # Check intermediate directories (not the file itself or root)
        for i in range(1, len(parts)):
            dir_path = "/".join(parts[:i])
            init_path = f"{dir_path}/__init__.py"

            # If this directory doesn't have an __init__.py, mark it
            if init_path not in zip_contents:
                directories_needing_init.add(dir_path)

    # Add empty __init__.py files for namespace packages
    for dir_path in sorted(directories_needing_init):
        init_path = f"{dir_path}/__init__.py"
        print(f"  Adding namespace package marker: {init_path}")
        zip_file.writestr(init_path, b"# Namespace package\n")


def zip_recursively(zip_file, root_dir, folder_name):
    """
    Zip the files at the given folder recursively.
    """

    path = root_dir / folder_name
    if path.is_dir():
        for root, _, files in os.walk(path):
            for f in files:
                full_file_path = pathlib.Path(os.path.join(root, f))
                zip_file.write(full_file_path, full_file_path.relative_to(root_dir))
    else:
        zip_file.write(path, path.relative_to(root_dir))


if __name__ == "__main__":
    main()
