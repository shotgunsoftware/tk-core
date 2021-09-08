# Copyright (c) 2021 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import shutil
import subprocess
import tempfile


class PackageUpgrade(object):
    def __init__(self):
        self.url = "https://github.com/yaml/pyyaml.git"
        self.base_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        self.pyyaml_dir = os.path.join(self.base_dir, "python", "tank_vendor", "yaml")
        self.pyyaml_old_dir = os.path.join(
            self.base_dir, "python", "tank_vendor", "yaml.old"
        )

    def upgrade(self):
        print("Updating pyyaml package")

        temp_dir = tempfile.mkdtemp()

        # clone the repo and change current directory
        clone_dir = self.clone_repo(temp_dir)
        os.chdir(clone_dir)

        # get latest tag
        tag = self.get_latest_tag()

        # checkout tag
        self.checkout_tag(tag)

        # print last commit
        self.print_last_commit()

        # rename the pyyaml folder
        self.rename_pyyaml_folder()

        # copy new files
        self.copy_new_pyyaml_files()

        # copy old required files
        self.copy_old_required_files()

        # delete old folder
        self.remove_old_folder()

        shutil.rmtree(temp_dir, ignore_errors=True)

    def clone_repo(self, temp_dir):
        clone_dir = os.path.join(temp_dir, "pyyaml")
        cmd = 'git clone -q "{0}" "{1}"'.format(self.url, clone_dir)
        print(cmd)
        os.system(cmd)

        return clone_dir

    def get_latest_tag(self):
        cmd = ["git", "tag", "--sort=committerdate"]
        print(" ".join(cmd))
        tag = subprocess.check_output(cmd).splitlines()[-1]
        tag = tag.decode("utf-8")  # py3 compatibility
        print(tag)

        return tag

    def checkout_tag(self, tag):
        cmd = "git checkout -q %s" % tag
        print(cmd)
        os.system(cmd)

    def print_last_commit(self):
        cmd = "git log --oneline -n 1"
        print(cmd)
        os.system(cmd)

    def rename_pyyaml_folder(self):
        print("Renaming current yaml folder")
        if os.path.isdir(self.pyyaml_old_dir):
            print("Deleting a previous backup of yaml folder")
            shutil.rmtree(self.pyyaml_old_dir)
        shutil.move(self.pyyaml_dir, self.pyyaml_old_dir)

    def copy_new_pyyaml_files(self):
        print("Copy new pyyaml package files")
        os.makedirs(self.pyyaml_dir)
        source = os.path.join("lib", "yaml")
        target = os.path.join(self.pyyaml_dir, "python2")
        shutil.copytree(source, target)

        source = os.path.join("lib3", "yaml")
        target = os.path.join(self.pyyaml_dir, "python3")
        shutil.copytree(source, target)

        for source in ["README", "LICENSE", "CHANGES"]:
            target = os.path.join(self.pyyaml_dir, source)
            shutil.copy(source, target)

    def copy_old_required_files(self):
        print("Copy old pyyaml package files")
        source = os.path.join(self.pyyaml_old_dir, "__init__.py")
        target = os.path.join(self.pyyaml_dir, "__init__.py")
        shutil.copy(source, target)

    def remove_old_folder(self):
        print("Remove old pyyaml package folder")
        shutil.rmtree(self.pyyaml_old_dir)


def main():
    package = PackageUpgrade()
    package.upgrade()


if __name__ == "__main__":
    main()
