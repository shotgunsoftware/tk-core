# Copyright 2025 Autodesk, Inc.  All rights reserved.
#
# Use of this software is subject to the terms of the Autodesk license agreement
# provided at the time of installation or download, or which otherwise accompanies
# this software in either electronic or hard copy form.
#

import os
import shutil
import sys
import tempfile
import unittest

from sgtk_integration_test import SgtkIntegrationTest


class BootstrapPipTests(SgtkIntegrationTest):
    """
    Tests that it is possible to boostrap an engine when the package installation has been done using pip.

    Note because we can't really use pip here, we're simulating the installation process.
    """

    PYTHON_PACKAGE_LIST = ["sgtk", "tank", "tank_vendor"]

    @classmethod
    def setUpClass(cls):
        super(BootstrapPipTests, cls).setUpClass()

        # Mockup FPTR entities
        cls.project = cls.create_or_update_project(
            "Pip Install SGTK", {"tank_name": "pip_install_sgtk"}
        )
        cls.asset = cls.create_or_update_entity(
            "Asset", "TestAsset", {"project": cls.project}
        )

        # Figure out our location
        current_dir = os.path.abspath(os.path.dirname(__file__))
        python_package_path = os.path.normpath(
            os.path.join(current_dir, "..", "..", "python")
        )

        # Install sgtk in a temporary location pip-liked by manually copying the packages to the temporary location
        cls._sgtk_install_location = tempfile.mkdtemp(prefix="sgtk_install_", dir=None)
        for package in cls.PYTHON_PACKAGE_LIST:
            if os.path.isdir(os.path.join(python_package_path, package)):
                shutil.copytree(
                    os.path.join(python_package_path, package),
                    os.path.join(cls._sgtk_install_location, package),
                    ignore=shutil.ignore_patterns("*.pyc", "__pycache__"),
                )
        sys.path.insert(1, cls._sgtk_install_location)

    @classmethod
    def tearDownClass(cls):
        super(BootstrapPipTests, cls).tearDownClass()

        # Make sure to remove our sgtk install folder
        if os.path.isdir(cls._sgtk_install_location):
            shutil.rmtree(cls._sgtk_install_location)

    def __clean_sgtk_modules(self):
        """Helper method to clean previously installed sgtk modules."""

        modules_to_remove = []

        for module_name in sys.modules:
            if module_name.startswith("sgtk") or module_name.startswith("tank"):
                modules_to_remove.append(module_name)

        for module_name in modules_to_remove:
            del sys.modules[module_name]

    def test_boostrap_engine(self):
        """Bootstrap the engine when the sgtk module has been installed using pip."""

        # Make sure to import the right sgtk module by cleaning all the previously imported modules and reimporting
        # the right one
        self.__clean_sgtk_modules()
        import sgtk

        self.assertEqual(
            os.path.dirname(sgtk.__file__),
            os.path.join(self._sgtk_install_location, "tank"),
        )
        self.assertEqual(
            os.path.dirname(sgtk.bootstrap.__file__),
            os.path.join(self._sgtk_install_location, "tank", "bootstrap"),
        )

        # Bootstrap the engine
        manager = sgtk.bootstrap.ToolkitManager(self.user)
        manager.plugin_id = "basic.test"
        manager.base_configuration = "sgtk:descriptor:path?path={0}".format(
            os.path.normpath(
                os.path.join(os.path.dirname(__file__), "data", "site_config")
            )
        )
        engine = manager.bootstrap_engine("tk-shell", self.asset)
        self.assertEqual(engine.name, "tk-shell")


if __name__ == "__main__":
    unittest.main(failfast=True, verbosity=2)
