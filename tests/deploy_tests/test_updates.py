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
import functools

import mock

from tank_test.tank_test_base import TankTestBase, setUpModule
from sgtk.deploy.descriptor import AppDescriptor
from sgtk.deploy import app_store_descriptor
from tank.platform.environment import Environment
from distutils.version import LooseVersion


class MockStore(object):
    """
    MockStore fakes the AppStore backend. It is possible to populate it with
    bundle versions and requirements.
    """

    class _Entry(object):
        """
        Mocks a bundle type.
        """

        def __init__(self, name, version, dependencies=[], bundle_type=None):
            """
            Constructor.

            :param name: Name of the new bundle.
            :param version: Version of the new bundle.
            :param depedencies: Dependencies of the new bundle.
            :param bundle_type: Type of the new bundle.
            """
            # Bundle_type can't actually be done. That argument is at the end only
            # because functools.partial cannot be used to set positional
            # arguments in the middle of a method's signature.
            self._name = name
            self._version = version
            self._dependencies = dependencies
            self._bundle_type = bundle_type

        @property
        def bundle_type(self):
            """
            :returns: Type of the bundle.
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
            return self._dependencies

        @required_frameworks.setter
        def required_frameworks(self, dependencies):
            self._dependencies = dependencies

    APP, ENGINE, FRAMEWORK = AppDescriptor.APP, AppDescriptor.ENGINE, AppDescriptor.FRAMEWORK

    def __init__(self):
        """
        Constructor.
        """
        self._bundles = {}

    def _add_typed_bundle(self, bundle_type, name, version):
        """
        Instantiate a bundle using the factory and registers it in the mock store.

        :param factory: Callable that will instantiate the bundle.
        :param name: Name for the bundle.
        :param version: Version of the bundle.

        :returns: The object returned by the factory.
        """
        bundle = self._Entry(name, version, [], bundle_type)
        self.add_bundle(bundle)
        return bundle

    def add_framework(self, name, version):
        """
        Create a framework and registers it to the mock store.

        :param name: Name of the framework.
        :param version: Version of the framework.

        :returns: A MockStoreFramework object.
        """
        return self._add_typed_bundle(self.FRAMEWORK, name, version)

    def add_engine(self, name, version):
        """
        Create an engine and register it to the mock store.

        :param name: Name of the engine.
        :param version: Version of the engine.

        :returns: A MockStoreEngine object.
        """
        return self._add_typed_bundle(self.ENGINE, name, version)

    def add_application(self, name, version):
        """
        Create an appplication and register it to the mock store.

        :param name: Name of the application.
        :param version: Version of the application.

        :returns: A MockStoreApp object.
        """
        return self._add_typed_bundle(self.APP, name, version)

    def add_bundle(self, bundle):
        """
        Registers a mock bundle.

        :param bundle: Bundle to register
        """
        self._bundles.setdefault(bundle.bundle_type, {}).setdefault(bundle.name, {})[bundle.version] = bundle

    def get_bundle(self, bundle_type, name, version):
        """
        Retrieves a specific bundle.

        :param bundle_type: Type of the bundle to retrieve.
        :param name: Name of the bundle to retrieve.
        :param version: Version of the bundle to retrieve.

        :returns: The requested bundle.
        """
        return self._bundles[bundle_type][name][version]

    def get_bundle_versions(self, bundle_type, name):
        """
        Retrieves all versions strings of a specific bundle.

        :param bundle_type. Type of the bundles to retrieve.
        :param name: Name of the bundles to retrieve.

        :returns: List of version strings for a particular bundle.
        """
        return self._bundles[bundle_type][name].iterkeys()


# Cleaner than having to write three class types that would also have to be documented.
MockStoreApp = functools.partial(MockStore._Entry, bundle_type=MockStore.APP)
MockStoreFramework = functools.partial(MockStore._Entry, bundle_type=MockStore.FRAMEWORK)
MockStoreEngine = functools.partial(MockStore._Entry, bundle_type=MockStore.ENGINE)


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
        return app_store_descriptor.TankAppStoreDescriptor(
            None, None, {"name": name, "type": "app_store", "version": version}, bundle_type
        )

    def __init__(self, pc_path, bundle_install_path, location_dict, bundle_type, mock_store):
        """
        Constructor.
        """
        AppDescriptor.__init__(self, pc_path, bundle_install_path, location_dict)
        self._type = bundle_type
        self._mock_store = mock_store

    def get_system_name(self):
        """
        See documentation from TankAppStoreDescriptor.
        """
        return self.get_location()["name"]

    def get_version(self):
        """
        See documentation from TankAppStoreDescriptor.
        """
        return self.get_location()["version"]

    def _get_metadata(self):
        """
        See documentation from TankAppStoreDescriptor.
        """
        dependencies = self._mock_store.get_bundle(
            self._type, self.get_system_name(), self.get_version()
        ).required_frameworks
        return {
            "frameworks": [
                {
                    "name": d.name,
                    "version": d.version,
                    "type": "app_store"
                } for d in dependencies
            ]
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
        versions = self._mock_store.get_bundle_versions(
            self._type, self.get_system_name()
        )
        latest = "v0.0.0"
        for version in versions:
            if LooseVersion(version) > LooseVersion(latest):
                latest = version
        return self.create(self.get_system_name(), latest, self._type)


def patch_app_store(func=None):
    """
    Patches the TankAppStoreDescriptor class to be able to mock connections
    to the AppStore. If a function is passed in, the method will be decorated
    and the patch will only be applied during the call. Otherwise, the patch
    is created automatically and the caller only needs to call start() on the patch
    to activate it.

    :param func: Function to wrap. Can be None.

    :returns: If the user passed in a function, the decorated function will now have a new
    mock_store parameter passed in. If the user didn't pass a function in,
    the method will return a tuple of (mock.patch, MockStore) objects.
    """
    mock_store = MockStore()
    app_store_patch = mock.patch(
        "tank.deploy.app_store_descriptor.TankAppStoreDescriptor",
        new=functools.partial(TankMockStoreDescriptor, mock_store=mock_store)
    )
    app_store_patch.mock_store = mock_store

    if func is None:
        return app_store_patch, mock_store
    else:
        def wrapper(*args, **kwargs):
            with app_store_patch:
                return functools.partial(func, mock_store=mock_store)(*args, **kwargs)
        return wrapper


class TestMockStore(TankTestBase):
    """
    Tests the mocker to see if it behaves as expected.
    """

    def setUp(self):
        """
        Prepare unit test.
        """
        TankTestBase.setUp(self)

    @patch_app_store
    def test_decorated(self, mock_store):
        """
        Makes sure everything is patched in correctly.
        """
        self._test_patched(mock_store)

    def _test_patched(self, mock_store):
        """
        Tests that the mock_store parameter is the MockStore and that
        the TankAppStoreDescriptor class has been properly patched.
        """
        # Make sure this is the mock store.
        self.assertIsInstance(mock_store, MockStore)
        # Register an engine with it.
        mock_store.add_engine("tk-test", "v1.2.3")

        # Make sure the created object is actually an instance of the mocked descriptor class.
        self.assertIsInstance(
            app_store_descriptor.TankAppStoreDescriptor(
                None, None, {"name": "tk-test", "version": "v1.2.3"}, AppDescriptor.ENGINE
            ), TankMockStoreDescriptor
        )

    def test_non_decorated(self):
        """
        Tests the non decorated usage of the patch_app_store method.
        """
        patch, mock_store = patch_app_store()

        self.assertNotEqual(TankMockStoreDescriptor, app_store_descriptor.TankAppStoreDescriptor)

        # Once we use the patch, everything should be mocked.
        with patch:
            self._test_patched(mock_store)

        # Now the patch should be unaplied and nothing should be mocked anymore.
        self.assertNotEqual(TankMockStoreDescriptor, app_store_descriptor.TankAppStoreDescriptor)

    @patch_app_store
    def test_framework_registration(self, mock_store):
        """
        Makes sure the framework is registered correctly.
        """
        # Version this is a dependency.
        dependency = mock_store.add_framework("tk-framework-dependency", "v1.0.0")
        # This is V1 of a framework that has no depdendencies.
        mock_store.add_framework("tk-framework-main", "v1.0.0")
        # This is V2 of a framework that now has a depdendency
        mock_store.add_framework("tk-framework-main", "v2.0.0").required_frameworks = [dependency]

        # Makes sure we respect the interface of the TankAppStoreDescriptor
        desc = app_store_descriptor.TankAppStoreDescriptor(
            None, None, {"name": "tk-framework-main", "version": "v2.0.0"}, AppDescriptor.FRAMEWORK
        )
        self.assertEqual(
            desc.get_required_frameworks(),
            [{"type": "app_store", "name": "tk-framework-dependency", "version": "v1.0.0"}]
        )
        desc = app_store_descriptor.TankAppStoreDescriptor(
            None, None, {"name": "tk-framework-main", "version": "v1.0.0"}, AppDescriptor.FRAMEWORK
        )
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

        self._patcher, self._mock_store = patch_app_store()
        self._patcher.start()
        self.addCleanup(self._patcher.stop)

        self.setup_fixtures("app_store_tests")

        self._mock_store.add_engine("tk-test", "v1.0.0")
        self._mock_store.add_application("tk-multi-test", "v1.0.0")
        self._mock_store.add_application("tk-multi-test", "v2.0.0")
        self._mock_store.add_framework("tk-framework-test", "v1.0.0")

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
