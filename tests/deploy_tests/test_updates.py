# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Unit tests tank updates.
"""

import os

import mock

from tank_test.tank_test_base import TankTestBase, setUpModule
from sgtk.deploy import app_store_descriptor
from sgtk.deploy.descriptor import AppDescriptor
from tank.platform.environment import Environment


class AppStoreMocker(object):
    """
    Allows to create a mock app store.
    """

    APP, ENGINE, FRAMEWORK = AppDescriptor.APP, AppDescriptor.ENGINE, AppDescriptor.FRAMEWORK

    def __init__(self):
        """
        Constructor.
        """
        self._bundles = {}

    @staticmethod
    def reset():
        """
        Instantiates the app store mocker.
        """
        AppStoreMocker.instance = AppStoreMocker()

    def add_bundle(self, bundle_type, bundle):
        """
        Registers a mock framework.
        """
        self._bundles.setdefault(bundle_type, {}).setdefault(bundle.name, {})[bundle.version] = bundle

    def get_bundle(self, bundle_type, name, version):
        """
        Registers a mock framework.
        """
        return self._bundles[bundle_type][name][version]

    def get_bundle_verions(self, bundle_type, name):
        """
        :returns: Versions of a given framework.
        """
        return self._bundles[bundle_type][name].keys()


class BundleMocker(object):
    """
    Mocks a bundle.
    """

    def __init__(self, name, version, dependencies):
        """
        Constructor.
        """
        self._name = name
        self._version = version
        self._dependencies = dependencies if isinstance(dependencies, list) else [dependencies]

    @property
    def name(self):
        """
        :returns: Name of the bundle.
        """
        return self._name

    @property
    def version(self):
        """
        :returns: Version of the bundle.
        """
        return self._version

    @property
    def required_frameworks(self):
        """
        :returns: List of required frameworks as descriptors dictionaries.
        """
        return [
            {
                "name": d.name,
                "version": d.version,
                "type": "app_store"
            } for d in self._dependencies
        ]


class AppMocker(BundleMocker):
    """
    Mocks an app.
    """

    def __init__(self, name, version, dependencies=[]):
        """
        Constructor.
        """
        BundleMocker.__init__(self, name, version, dependencies)
        AppStoreMocker.instance.add_bundle(AppStoreMocker.APP, self)


class FrameworkMocker(BundleMocker):
    """
    Mocks an app.
    """

    def __init__(self, name, version, dependencies=[]):
        """
        Constructor.
        """
        BundleMocker.__init__(self, name, version, dependencies)
        AppStoreMocker.instance.add_bundle(AppStoreMocker.FRAMEWORK, self)


class EngineMocker(BundleMocker):
    """
    Mocks an app.
    """

    def __init__(self, name, version, dependencies=[]):
        """
        Constructor.
        """
        BundleMocker.__init__(self, name, version, dependencies)
        AppStoreMocker.instance.add_bundle(AppStoreMocker.ENGINE, self)


class TankAppStoreDescriptorMock(object):
    """
    Mocking of the TankAppStoreDescriptor class. Interfaces with the AppStoreMocker to return results.
    """

    @staticmethod
    def create(name, version, bundle_type):
        """
        Simple method to create an instance of the mocker object. This is required only when testing the framework.

        :returns: A TankAppStoreDescriptorMock object.
        """
        return TankAppStoreDescriptorMock(None, None, {"name": name, "version": version}, bundle_type)

    def __init__(self, pc_path, bundle_install_path, location_dict, bundle_type):
        """
        Constructor.
        """
        self._mock_entry = AppStoreMocker.instance.get_bundle(bundle_type, location_dict["name"], location_dict["version"])

    def get_system_name(self):
        """
        See documentation from TankAppStoreDescriptor.
        """
        return self._mock_entry.name

    def get_version(self):
        """
        See documentation from TankAppStoreDescriptor.
        """
        return self._mock_entry.version

    def get_required_frameworks(self):
        """
        See documentation from TankAppStoreDescriptor.
        """
        return self._mock_entry.required_frameworks


def mock_app_store():
    """
    Mocks the appstore class for unit testing.

    :returns: A tuple of (patch, AppStoreMock object)
    """
    AppStoreMocker.reset()

    patcher = mock.patch(
        "tank.deploy.app_store_descriptor.TankAppStoreDescriptor",
        new=TankAppStoreDescriptorMock
    )
    return patcher, AppStoreMocker.instance


class TestAppStoreMocker(TankTestBase):
    """
    Tests the mocker to see if it behaves as expected.
    """

    def setUp(self):
        """
        Prepare unit test.
        """
        TankTestBase.setUp(self)

        self._patcher, self._app_store_mocker = mock_app_store()
        self._patcher.start()
        self.addCleanup(self._patcher.stop)

    def test_mocked_app_store(self):
        """
        Makes sure we mocked the right thing.
        """
        FrameworkMocker("tk-framework-main", "v2.0.0")

        self.assertIsInstance(
            TankAppStoreDescriptorMock.create("tk-framework-main", "v2.0.0", AppDescriptor.FRAMEWORK),
            TankAppStoreDescriptorMock
        )

    def test_framework_registration(self):
        """
        Makes sure the framework is registered correctly.
        """
        # Version this is a dependency.
        dependency = FrameworkMocker("tk-framework-dependency", "v1.0.0")
        # This is V1 of a framework that has no depdendencies.
        FrameworkMocker("tk-framework-main", "v1.0.0")
        # This is V2 of a framework that now has a depdendency
        FrameworkMocker("tk-framework-main", "v2.0.0", dependency)

        # Makes sure we respect the interface of the TankAppStoreDescriptor
        desc = app_store_descriptor.TankAppStoreDescriptor(None, None, {"name": "tk-framework-main", "version": "v2.0.0"}, AppDescriptor.FRAMEWORK)
        self.assertEqual(
            desc.get_required_frameworks(),
            [{"type": "app_store", "name": "tk-framework-dependency", "version": "v1.0.0"}]
        )
        desc = app_store_descriptor.TankAppStoreDescriptor(None, None, {"name": "tk-framework-main", "version": "v1.0.0"}, AppDescriptor.FRAMEWORK)
        self.assertEqual(desc.get_required_frameworks(), [])


class TestAppStoreUpdate(TankTestBase):
    """
    Makes sure environment code works with the app store mocker.
    """

    def setUp(self):
        """
        Prepare unit test.
        """
        TankTestBase.setUp(self)

        self._patcher, self._app_store_mocker = mock_app_store()
        self._patcher.start()
        self.addCleanup(self._patcher.stop)

        self.setup_fixtures("app_store_tests")

        EngineMocker("tk-test", "v1.0.0")
        AppMocker("tk-multi-test", "v1.0.0")
        AppMocker("tk-multi-test", "v2.0.0")
        FrameworkMocker("tk-framework-test", "v1.0.0")

    def test_environment(self):
        """
        Make sure we can instantiate an environment and get information about the installed apps and their descriptors.
        """
        env = Environment(os.path.join(self.project_config, "env", "main.yml"), self.pipeline_configuration)

        self.assertEqual(env.get_engines(), ["tk-test-instance"])
        self.assertEqual(env.get_apps("tk-test-instance"), ["tk-multi-test-instance"])
        self.assertEqual(env.get_frameworks(), ["tk-framework-test_v1.0.0"])

        desc = env.get_framework_descriptor("tk-framework-test_v1.0.0")
        self.assertIsInstance(desc, TankAppStoreDescriptorMock)

        desc = env.get_engine_descriptor("tk-test-instance")
        self.assertIsInstance(desc, TankAppStoreDescriptorMock)

        desc = env.get_app_descriptor("tk-test-instance", "tk-multi-test-instance")
        self.assertIsInstance(desc, TankAppStoreDescriptorMock)

