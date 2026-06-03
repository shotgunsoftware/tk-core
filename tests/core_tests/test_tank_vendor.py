# Copyright (c) 2025 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import importlib
import sys
import unittest
from unittest import mock

from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import ShotgunTestBase

# Configuration: Add or remove packages here to test different third-party libraries
# Packages from pkgs.zip are always tested. Packages from requirements/any/
# are version-gated below.
PACKAGES_TO_TEST = [
    {
        "name": "yaml",
        "attributes": ["safe_load", "safe_dump"],  # Expected attributes
        "description": "YAML parser (ruamel.yaml)",
    },
    {
        "name": "shotgun_api3",
        "attributes": ["Shotgun", "__version__"],
        "description": "Shotgun API",
    },
    {
        "name": "packaging",
        "attributes": ["version", "__version__"],
        "description": "Package version handling",
    },
    {
        "name": "distro",
        "attributes": ["id", "name"],
        "description": "Linux distribution detection",
    },
]

# Flow Data SDK uses types.UnionType and typing.TypeAlias, both 3.10+ only.
# On 3.7/3.9 the shared loader will warn-and-continue; do not assert it here.
if sys.version_info >= (3, 10):
    PACKAGES_TO_TEST.append(
        {
            "name": "flow_data_sdk",
            "attributes": [
                "GQLClient",
                "WorkflowContext",
                "SDK_VERSION",
                "DEFAULT_ENDPOINT",
                "DEFAULT_AUTH_BASE_URL",
                "GQLAPIError",
            ],
            "description": "Autodesk Flow Data SDK (beta)",
        }
    )


class TestTankVendorImports(ShotgunTestBase):
    """Test importing third-party packages via tank_vendor namespace."""

    def test_direct_imports(self):
        pass
    def test_namespace_aliases(self):
        pass
    def test_submodule_import(self):
        pass
    def test_sys_modules_registration(self):
        pass
    def test_mock_patch_compatibility(self):
        pass
class TestTankVendorMetaFinder(ShotgunTestBase):
    """Test the _TankVendorMetaFinder import hook functionality."""

    def test_meta_finder_installed(self):
        pass
    def test_meta_finder_redirects_imports(self):
        pass
    def test_meta_finder_handles_nonexistent_module(self):
        pass
class TestTankVendorPackageLoading(ShotgunTestBase):
    """Test package loading and validation from pkgs.zip."""

    def test_packages_available(self):
        pass
    def test_package_attributes_accessible(self):
        pass
class TestShotgunAPI3CertPatch(ShotgunTestBase):
    """Test the shotgun_api3 certificate patching functionality."""

    def test_cert_patch_applied(self):
        pass
    def test_cert_file_returns_path(self):
        pass
@unittest.skipIf(
    sys.version_info < (3, 10),
    "Flow Data SDK requires Python 3.10+ (uses types.UnionType / typing.TypeAlias)",
)
class TestFlowDataSDK(ShotgunTestBase):
    """Test the Flow Data SDK loaded from requirements/any/."""

    def test_submodule_import(self):
        pass
    def test_sdk_version_resolved_from_dist_info(self):
        pass
    def test_dist_info_via_importlib_metadata(self):
        pass
@unittest.skipIf(
    sys.version_info >= (3, 10),
    "Test verifies behaviour when the SDK is unimportable due to <3.10 syntax/types",
)
class TestFlowDataSDKAbsentOnOldPython(ShotgunTestBase):
    """
    On Python 3.7 and 3.9, flow_data_sdk fails to import because its source
    references types.UnionType and typing.TypeAlias (both 3.10+). The shared
    loader is supposed to warn and continue, leaving tank_vendor itself
    fully usable. These tests pin that contract.
    """

    def test_tank_vendor_imports_cleanly(self):
        pass
    def test_flow_data_sdk_unavailable(self):
        pass
if __name__ == "__main__":
    unittest.main()
