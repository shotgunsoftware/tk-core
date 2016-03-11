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
import logging

import mock

from tank_test.tank_test_base import TankTestBase, setUpModule
from sgtk.deploy import app_store_descriptor
from sgtk.deploy.descriptor import AppDescriptor
from tank.platform.environment import Environment
from distutils.version import LooseVersion



class MockStore(object):
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
        MockStore.instance = MockStore()

    def add_bundle(self, bundle):
        """
        Registers a mock framework.
        """
        self._bundles.setdefault(bundle.bundle_type, {}).setdefault(bundle.name, {})[bundle.version] = bundle

    def get_bundle(self, bundle_type, name, version):
        """
        Registers a mock framework.
        """
        return self._bundles[bundle_type][name][version]

    def get_bundle_versions(self, bundle_type, name):
        """
        :returns: Versions of a given framework.
        """
        return self._bundles[bundle_type][name].iterkeys()


class MockStoreBundleEntry(object):
    """
    Mocks a bundle.
    """

    def __init__(self, name, version, dependencies, bundle_type):
        """
        Constructor.
        """
        self._name = name
        self._version = version
        self._dependencies = dependencies if isinstance(dependencies, list) else [dependencies]
        self._bundle_type = bundle_type

    @property
    def bundle_type(self):
        """
        :returns: Name of the bundle.
        """
        return self._bundle_type

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


class MockStoreApp(MockStoreBundleEntry):
    """
    Mocks an app.
    """

    def __init__(self, name, version, dependencies=[]):
        """
        Constructor.
        """
        MockStoreBundleEntry.__init__(self, name, version, dependencies, MockStore.APP)
        MockStore.instance.add_bundle(self)


class MockStoreFramework(MockStoreBundleEntry):
    """
    Mocks an app.
    """

    def __init__(self, name, version, dependencies=[]):
        """
        Constructor.
        """
        MockStoreBundleEntry.__init__(self, name, version, dependencies, MockStore.FRAMEWORK)
        MockStore.instance.add_bundle(self)


class MockStoreEngine(MockStoreBundleEntry):
    """
    Mocks an app.
    """

    def __init__(self, name, version, dependencies=[]):
        """
        Constructor.
        """
        MockStoreBundleEntry.__init__(self, name, version, dependencies, MockStore.ENGINE)
        MockStore.instance.add_bundle(self)


class TankMockStoreDescriptor(AppDescriptor):
    """
    Mocking of the TankAppStoreDescriptor class. Interfaces with the MockStore to return results.
    """

    @staticmethod
    def create(name, version, bundle_type):
        """
        Simple method to create an instance of the mocker object. This is required only when testing the framework.

        :returns: A TankMockStoreDescriptor object.
        """
        return TankMockStoreDescriptor(None, None, {"name": name, "type": "app_store", "version": version}, bundle_type)

    def __init__(self, pc_path, bundle_install_path, location_dict, bundle_type):
        """
        Constructor.
        """
        AppDescriptor.__init__(self, pc_path, bundle_install_path, location_dict)

        self._entry = MockStore.instance.get_bundle(bundle_type, location_dict["name"], location_dict["version"])

    def get_system_name(self):
        """
        See documentation from TankAppStoreDescriptor.
        """
        return self._entry.name

    def get_version(self):
        """
        See documentation from TankAppStoreDescriptor.
        """
        return self._entry.version

    def _get_metadata(self):
        """
        See documentation from TankAppStoreDescriptor.
        """
        return {
            "frameworks": self._entry.required_frameworks
        }

    def run_post_install(self):
        """
        See documentation from TankAppStoreDescriptor.
        """
        pass

    def exists_local(self):
        """
        See documentation from TankAppStoreDescriptor.
        """
        return True

    def find_latest_version(self, constraint=None):
        """
        See documentation from TankAppStoreDescriptor.
        """
        versions = MockStore.instance.get_bundle_versions(self._entry.bundle_type, self._entry.name)
        latest = "v0.0.0"
        for version in versions:
            if LooseVersion(version) > LooseVersion(latest):
                latest = version
        return TankMockStoreDescriptor.create(self._entry.name, latest, self._entry.bundle_type)


def mock_app_store():
    """
    Mocks the appstore class for unit testing.

    :returns: A tuple of (patch, AppStoreMock object)
    """
    MockStore.reset()

    patcher = mock.patch(
        "tank.deploy.app_store_descriptor.TankAppStoreDescriptor",
        new=TankMockStoreDescriptor
    )
    return patcher


class TestMockStore(TankTestBase):
    """
    Tests the mocker to see if it behaves as expected.
    """

    def setUp(self):
        """
        Prepare unit test.
        """
        TankTestBase.setUp(self)

        self._patcher = mock_app_store()
        self._patcher.start()
        self.addCleanup(self._patcher.stop)

    def test_mocked_app_store(self):
        """
        Makes sure we mocked the right thing.
        """
        MockStoreFramework("tk-framework-main", "v2.0.0")

        self.assertIsInstance(
            TankMockStoreDescriptor.create("tk-framework-main", "v2.0.0", AppDescriptor.FRAMEWORK),
            TankMockStoreDescriptor
        )

    def test_framework_registration(self):
        """
        Makes sure the framework is registered correctly.
        """
        # Version this is a dependency.
        dependency = MockStoreFramework("tk-framework-dependency", "v1.0.0")
        # This is V1 of a framework that has no depdendencies.
        MockStoreFramework("tk-framework-main", "v1.0.0")
        # This is V2 of a framework that now has a depdendency
        MockStoreFramework("tk-framework-main", "v2.0.0", dependency)

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

        self._patcher = mock_app_store()
        self._patcher.start()
        self.addCleanup(self._patcher.stop)

        self.setup_fixtures("app_store_tests")

        MockStoreEngine("tk-test", "v1.0.0")
        MockStoreApp("tk-multi-test", "v1.0.0")
        MockStoreApp("tk-multi-test", "v2.0.0")
        MockStoreFramework("tk-framework-test", "v1.0.0")

    def test_environment(self):
        """
        Make sure we can instantiate an environment and get information about the installed apps and their descriptors.
        """
        env = Environment(os.path.join(self.project_config, "env", "main.yml"), self.pipeline_configuration)

        self.assertEqual(env.get_engines(), ["tk-test-instance"])
        self.assertEqual(env.get_apps("tk-test-instance"), ["tk-multi-test-instance"])
        self.assertEqual(env.get_frameworks(), ["tk-framework-test_v1.0.0"])

        desc = env.get_framework_descriptor("tk-framework-test_v1.0.0")
        self.assertIsInstance(desc, TankMockStoreDescriptor)
        self.assertEqual(desc.get_version(), "v1.0.0")

        desc = env.get_engine_descriptor("tk-test-instance")
        self.assertIsInstance(desc, TankMockStoreDescriptor)
        self.assertEqual(desc.get_version(), "v1.0.0")

        desc = env.get_app_descriptor("tk-test-instance", "tk-multi-test-instance")
        self.assertIsInstance(desc, TankMockStoreDescriptor)
        self.assertEqual(desc.get_version(), "v1.0.0")

    def test_simple_update(self):
        """
        Test Simple update.
        """
        # Run appstore updates.
        command = self.tk.get_command("updates")
        command.set_logger(logging.getLogger("/dev/null"))
        command.execute(["tk-test-instance", "tk-multi-test-instance"])

        # Make sure we are v2.
        env = Environment(os.path.join(self.project_config, "env", "main.yml"), self.pipeline_configuration)
        desc = env.get_app_descriptor("tk-test-instance", "tk-multi-test-instance")
        self.assertEqual(desc.get_version(), "v2.0.0")
