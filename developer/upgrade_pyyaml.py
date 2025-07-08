# Copyright (c) 2021 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import argparse
import os
import shutil
import subprocess
import tempfile


class PackageUpgrade(object):
    def __init__(self):
        self.url = "https://github.com/yaml/pyyaml.git"
        self.base_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        self.pyyaml_dir = os.path.join(self.base_dir, "python", "tank_vendor", "yaml")

        parser = argparse.ArgumentParser()
        parser.add_argument(
            "-t", "--tag", help="Tag to checkout. If not specify, detect the latest one"
        )
        self.args = parser.parse_args()

    def upgrade(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            self._upgrade(temp_dir)

    def _upgrade(self, temp_dir):
        print("Updating pyyaml package")

        # clone the repo and change current directory
        clone_dir = self.clone_repo(temp_dir)
        os.chdir(clone_dir)

        tag = self.args.tag or self.get_latest_tag()

        # checkout tag
        self.checkout_tag(tag)

        # print last commit
        self.print_last_commit()

        # delete the pyyaml folder
        self.remove_pyyaml_folder()

        # copy new files
        self.copy_new_pyyaml_files()

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

    def remove_pyyaml_folder(self):
        print("Remove yaml folder")
        shutil.rmtree(self.pyyaml_dir)

    def copy_new_pyyaml_files(self):
        print("Copy new pyyaml package files")
        source = os.path.join("lib3", "yaml")
        target = os.path.join(self.pyyaml_dir)
        shutil.copytree(source, target)

        for source in ["README", "LICENSE", "CHANGES"]:
            target = os.path.join(self.pyyaml_dir, source)
            shutil.copy(source, target)


if __name__ == "__main__":
    package = PackageUpgrade()
    package.upgrade()
