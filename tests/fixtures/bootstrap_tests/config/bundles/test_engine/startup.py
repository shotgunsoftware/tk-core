# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os

import sgtk
from sgtk.platform import SoftwareLauncher, SoftwareVersion, LaunchInformation


class TestLauncher(SoftwareLauncher):
    """
    SoftwareLauncher stub for unit testing.
    """
    def scan_software(self):
        """
        Performs a scan for software installations.

        :param list versions: List of strings representing versions
                              to search for. If set to None, search
                              for all versions. A version string is
                              DCC-specific but could be something
                              like "2017", "6.3v7" or "1.2.3.52".
        :returns: List of :class:`SoftwareVersion` instances
        """
        sw_versions = []
        for version in range(0, 10):
            sw_path = "/path/to/unit/test/app/%s/executable"
            sw_icon = "%s/icons/exec.png" % os.path.dirname(sw_path)
            sw_versions.append(
                SoftwareVersion(
                    version,
                    "Unit Test App",  # product
                    sw_path,
                    sw_icon,
                )
            )
        return sw_versions

    def prepare_launch(self, exec_path, args, file_to_open=None):
        """
        Prepares the given software for launch.

        :param str exec_path: Path to DCC executable to launch.
        :param str args: Command line arguments as strings.
        :param str file_to_open: (optional) Full path name of a file to open on launch.
        :returns: :class:`LaunchInformation` instance
        """
        required_env = {}
        startup_path = os.path.join(self.disk_location, "startup")
        sgtk.util.append_path_to_env_var("PYTHONPATH", startup_path)
        required_env["PYTHONPATH"] = os.environ["PYTHONPATH"]
        if file_to_open:
            required_env["FILE_TO_OPEN"] = file_to_open

        return LaunchInformation(exec_path, args, required_env)

    # pass through methods to the private implementation of the base class so it can be
    # unit tested easily.
    def _is_version_supported(self, version):
        return self._SoftwareLauncher__is_version_supported(version)

    def _is_product_supported(self, version):
        return self._SoftwareLauncher__is_product_supported(version)

