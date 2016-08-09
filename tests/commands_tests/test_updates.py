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

from __future__ import with_statement

import os
import re
import logging
import functools
import tempfile

import mock

from tank_test.tank_test_base import TankTestBase, setUpModule

import sgtk
from sgtk.descriptor import Descriptor
from sgtk.descriptor.io_descriptor.base import IODescriptorBase
from sgtk.descriptor.descriptor import create_descriptor

from tank import TankError
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

        _version_regex = re.compile(r"v([0-9]+)\.([0-9]+)\.(.*)")

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

        def _get_required_frameworks(self):
            """
            :returns: List of required frameworks as descriptors dictionaries.
            """
            return self._dependencies

        def _set_required_frameworks(self, dependencies):
            self._dependencies = dependencies

        required_frameworks = property(_get_required_frameworks, _set_required_frameworks)

        def get_major_dependency_descriptor(self):
            return {
                "version": "v%s.x.x" % self._split_version()[0],
                "name": self.name,
                "type": "app_store"
            }

        def _split_version(self):
            """
            Splits the version string into major, minor and remainder.
            """
            return self._version_regex.match(self.version).group(1, 2, 3)

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
        return self._add_typed_bundle(Descriptor.FRAMEWORK, name, version)

    def add_engine(self, name, version):
        """
        Create an engine and register it to the mock store.

        :param name: Name of the engine.
        :param version: Version of the engine.

        :returns: A MockStoreEngine object.
        """
        return self._add_typed_bundle(Descriptor.ENGINE, name, version)

    def add_application(self, name, version):
        """
        Create an appplication and register it to the mock store.

        :param name: Name of the application.
        :param version: Version of the application.

        :returns: A MockStoreApp object.
        """
        return self._add_typed_bundle(Descriptor.APP, name, version)

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
        return self._bundles[bundle_type][name].keys()


# Simpler than having to write three class types that would also have to be documented.
MockStoreApp = functools.partial(MockStore._Entry, bundle_type=Descriptor.APP)
MockStoreFramework = functools.partial(MockStore._Entry, bundle_type=Descriptor.FRAMEWORK)
MockStoreEngine = functools.partial(MockStore._Entry, bundle_type=Descriptor.ENGINE)


class TankMockStoreDescriptor(IODescriptorBase):
    """
    Mocking of the TankAppStoreDescriptor class. Interfaces with the MockStore to return results.
    """

    def __init__(self, location_dict, sg_connection, bundle_type):
        """
        Constructor.

        Patches IODescriptorAppStore so needs to carry the same signature.

        :param location_dict: descriptor dictionary describing the bundle
        :param sg_connection: Shotgun connection to associated site
        :param bundle_type: Either Descriptor.APP, CORE, ENGINE or FRAMEWORK
        """
        IODescriptorBase.__init__(self, location_dict)
        self._type = bundle_type

    def create(self, version):
        """
        Simple method to create an instance of the mocker object. This is required only when testing the framework.

        :returns: A IODescriptorAppStore object.
        """
        descriptor = TankMockStoreDescriptor(
            {"name": self.get_system_name(),
             "type": "app_store",
             "version": version},
            None,
            self._type
        )

        descriptor.set_cache_roots(self._bundle_cache_root, self._fallback_roots)

        return descriptor

    def get_system_name(self):
        """
        See documentation from TankAppStoreDescriptor.
        """
        return self.get_dict()["name"]

    def get_version(self):
        """
        See documentation from TankAppStoreDescriptor.
        """
        return self.get_dict()["version"]

    def exists_local(self):
        """
        See documentation from TankAppStoreDescriptor.
        """
        return True

    def get_latest_version(self, constraint_pattern=None):
        """
        See documentation from TankAppStoreDescriptor.
        """
        if constraint_pattern:
            return self._find_latest_for_pattern(constraint_pattern)
        else:
            return self._find_latest()

    def _find_latest(self):
        """
        Finds the latest version of a bundle.

        :returns: A MockStore._Entry descriptor for the latest version of the bundle.
        """

        versions = MockStore.instance.get_bundle_versions(
            self._type,
            self.get_system_name()
        )
        latest = "v0.0.0"
        for version in versions:
            if LooseVersion(version) > LooseVersion(latest):
                latest = version

        return self.create(latest)

    def _find_latest_for_pattern(self, version_pattern):
        """
        Finds the latest version of a bundle for a given version pattern, e.g. v1.x.x

        :param version_pattern: Version pattern to use when searching for the latest version, e.g. v1.x.x.

        :returns: A MockStore._Entry descriptor for the latest version of the bundle that matches the pattern.
        """

        version_numbers = MockStore.instance.get_bundle_versions(
            self._type,
            self.get_system_name()
        )

        version_to_use = self._find_latest_tag_by_pattern(
            version_numbers,
            version_pattern
        )

        return self.create(version_to_use)

    def get_manifest(self):
        """
        Returns the manifest data
        """
        bundle = MockStore.instance.get_bundle(
            self._type,
            self.get_system_name(),
            self.get_version()
        )

        return {"frameworks": bundle.required_frameworks}

    def has_remote_access(self):
        """
        Do we have a remote connection?
        """
        return True


class _Patcher(object):
    """
    Patches the api for mock store and instantiates and deletes the
    MockStore singleton.
    """

    def __init__(self):
        """
        Constructor.
        """
        self._patch = mock.patch(
            "tank.descriptor.io_descriptor.appstore.IODescriptorAppStore",
            new=TankMockStoreDescriptor
        )

        self._mock_store = MockStore()

    def __enter__(self):
        """
        Patches the api.

        :returns: The mock store object.
        """
        self.start()
        return self._mock_store

    def __exit__(self, *_):
        """
        Unpatches the API.
        """
        self.stop()

    def start(self):
        """
        Patches the api.

        :returns: The mock store object.
        """
        MockStore.instance = self._mock_store
        self._patch.start()
        return MockStore.instance

    def stop(self):
        """
        Unpatches the api.
        """
        del MockStore.instance
        self._patch.stop()

    def __call__(self, func):
        """
        Decorates the provided method so that the api is patched
        during the duration of the call.

        :param func: Function to decorate.

        :returns: A decorated function with an extra
            positional argument referencing the mock store singleton.
        """
        # Need to reapply doc and name to the method or we won't be able
        # to invoke the test individually.
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with self as mock_store:
                # Adds the mockstore at the tail of any expected positional
                # arguments.
                return func(*(args + (mock_store,)), **kwargs)
        return wrapper


def patch_app_store(func=None):
    """
    Patches the TankAppStoreDescriptor class to be able to mock connections
    to the AppStore. If a function is passed in, the method will be decorated
    and the patch will only be applied during the call. Otherwise, the a patcher
    object is created and the caller only needs to call start() on the patcher
    to activate it or use it with the with statement.

    :param func: Function to wrap. Can be None.

    :returns: If the user passed in a function, the decorated function will now have a new
    mock_store parameter passed in. If the user didn't pass a function in,
    the method will return a tuple of (mock.patch, MockStore) objects.
    """
    if func:
        return _Patcher()(func)
    else:
        return _Patcher()


class TestMockStore(TankTestBase):
    """
    Tests the mocker to see if it behaves as expected.
    """

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

        from tank.descriptor.io_descriptor.appstore import IODescriptorAppStore

        # Make sure the created object is actually an instance of the mocked descriptor class.
        self.assertIsInstance(
            IODescriptorAppStore(
                {"name": "tk-test", "type": "app_store", "version": "v1.2.3"},
                None,
                Descriptor.ENGINE
            ), TankMockStoreDescriptor
        )

    def test_non_decorated(self):
        """
        Tests the non decorated usage of the patch_app_store method.
        """
        patcher = patch_app_store()

        from tank.descriptor.io_descriptor.appstore import IODescriptorAppStore

        self.assertNotEqual(TankMockStoreDescriptor, IODescriptorAppStore)

        # Once we use the patch, everything should be mocked.
        with patcher as mock_store:
            self._test_patched(mock_store)

        # Now the patch should be unaplied and nothing should be mocked anymore.
        self.assertNotEqual(TankMockStoreDescriptor, IODescriptorAppStore)

    @patch_app_store
    def test_framework_registration(self, mock_store):
        """
        Makes sure the framework is registered correctly.
        """
        # Version this is a dependency.
        dependency = mock_store.add_framework("tk-framework-dependency", "v1.0.0")
        self.assertEqual(dependency.get_major_dependency_descriptor(), {
            "version": "v1.x.x",
            "name": "tk-framework-dependency",
            "type": "app_store"
        })
        # This is V1 of a framework that has no depdendencies.
        mock_store.add_framework("tk-framework-main", "v1.0.0")
        # This is V2 of a framework that now has a depdendency
        mock_store.add_framework("tk-framework-main", "v2.0.0").required_frameworks = [
            dependency.get_major_dependency_descriptor()
        ]

        # Makes sure we respect the interface of the TankAppStoreDescriptor

        desc = create_descriptor(
            None,
            Descriptor.FRAMEWORK,
            {"name": "tk-framework-main", "version": "v2.0.0", "type": "app_store"}
        )

        self.assertEqual(
            desc.required_frameworks,
            [{"type": "app_store", "name": "tk-framework-dependency", "version": "v1.x.x"}]
        )

        desc = create_descriptor(
            None,
            Descriptor.FRAMEWORK,
            {"name": "tk-framework-main", "version": "v1.0.0", "type": "app_store"}
        )

        self.assertEqual(desc.required_frameworks, [])


class TestSimpleUpdates(TankTestBase):
    """
    Makes sure environment code works with the app store mocker.
    """

    def setUp(self):
        """
        Prepare unit test.
        """
        TankTestBase.setUp(self)

        patcher = patch_app_store()
        self._mock_store = patcher.start()
        self.addCleanup(patcher.stop)

        self.setup_fixtures("app_store_tests")

        self._mock_store.add_engine("tk-test", "v1.0.0")
        self._mock_store.add_application("tk-multi-nodep", "v1.0.0")
        self._mock_store.add_application("tk-multi-nodep", "v2.0.0")
        self._mock_store.add_framework("tk-framework-test", "v1.0.0")
        self._mock_store.add_framework("tk-framework-test", "v1.0.1")
        self._mock_store.add_framework("tk-framework-test", "v1.1.0")

    def test_environment(self):
        """
        Make sure we can instantiate an environment and get information about the installed apps and their descriptors.
        """
        env = Environment(os.path.join(self.project_config, "env", "simple.yml"), self.pipeline_configuration)

        self.assertListEqual(env.get_engines(), ["tk-test"])
        self.assertListEqual(env.get_apps("tk-test"), ["tk-multi-nodep"])
        self.assertListEqual(
            env.get_frameworks(),
            ["tk-framework-test_v1.0.0", "tk-framework-test_v1.0.x", "tk-framework-test_v1.x.x"]
        )

        desc = env.get_framework_descriptor("tk-framework-test_v1.0.0")
        self.assertIsInstance(desc._io_descriptor, TankMockStoreDescriptor)
        self.assertEqual(desc.version, "v1.0.0")

        desc = env.get_engine_descriptor("tk-test")
        self.assertIsInstance(desc._io_descriptor, TankMockStoreDescriptor)
        self.assertEqual(desc.version, "v1.0.0")

        desc = env.get_app_descriptor("tk-test", "tk-multi-nodep")
        self.assertIsInstance(desc._io_descriptor, TankMockStoreDescriptor)
        self.assertEqual(desc.version, "v1.0.0")

    def test_simple_update(self):
        """
        Test Simple update.
        """
        # Run appstore updates.
        command = self.tk.get_command("updates")
        command.set_logger(logging.getLogger("/dev/null"))
        command.execute({"environment_filter": "simple"})

        # Make sure we are v2.
        env = Environment(os.path.join(self.project_config, "env", "simple.yml"), self.pipeline_configuration)

        desc = env.get_app_descriptor("tk-test", "tk-multi-nodep")
        self.assertEqual(desc.version, "v2.0.0")

        desc = env.get_framework_descriptor("tk-framework-test_v1.0.0")
        self.assertEqual(desc.version, "v1.0.0")

        desc = env.get_framework_descriptor("tk-framework-test_v1.0.x")
        self.assertEqual(desc.version, "v1.0.1")

        desc = env.get_framework_descriptor("tk-framework-test_v1.x.x")
        self.assertEqual(desc.version, "v1.1.0")


class TestIncludeUpdates(TankTestBase):
    """
    Tests updates to bundle within includes.
    """

    def setUp(self):
        """
        Prepares unit test with basic bundles.
        """
        TankTestBase.setUp(self)
        self.setup_fixtures("app_store_tests")

        patcher = patch_app_store()
        self._mock_store = patcher.start()
        self.addCleanup(patcher.stop)

        self._engine_bundle = self._mock_store.add_engine("tk-engine", "v1.0.0")
        self._app_bundle = self._mock_store.add_application("tk-multi-app", "v1.0.0")
        self._2nd_level_dep_bundle = self._mock_store.add_framework("tk-framework-2nd-level-dep", "v1.0.0")

        self._update_cmd = self.tk.get_command("updates")
        self._update_cmd.set_logger(logging.getLogger("/dev/null"))

    def _get_env(self, env_name):
        """
        Retrieves the environment file specified.
        """
        return Environment(
            os.path.join(self.project_config, "env", "%s.yml" % env_name), self.pipeline_configuration
        )

    def _update_env(self, env_name):
        """
        Updates given environment.

        :param name: Name of the environment to update.
        """
        self._update_cmd.execute({"environment_filter": env_name})

    def test_update_include(self):
        """
        App should be updated in the common_apps file.
        """
        # Create a new version of the app that is included and update.
        self._mock_store.add_application("tk-multi-app", "v2.0.0")
        self._update_env("updating_included_app")

        # Reload env
        env = self._get_env("updating_included_app")

        # The new version of the app should reside inside common_apps.yml
        _, file_path = env.find_location_for_app("tk-engine", "tk-multi-app")
        self.assertEqual(os.path.basename(file_path), "common_apps.yml")

        self.assertDictEqual(
            env.get_app_descriptor("tk-engine", "tk-multi-app").get_location(),
            {
                "name": "tk-multi-app",
                "version": "v2.0.0",
                "type": "app_store"
            }
        )

    def test_update_include_with_new_framework(self):
        """
        App's new dependency should be installed inside common_apps.yml.

        tk-multi-app v1.0.0 doesn't have any dependency. v2.0.0 however has a dependency
        on a new framework, tk-framework-test. This new framework has a dependency on
        tk-framework-2nd-level-dep. This second framework is however already
        installed in the updating_included_app environment. We need to make sure that
        this framework is added inside the common_apps.yml file, where the app
        is defined, because other environments might not already have the second framework
        in them. In other words, new frameworks that are installed need to be added as close
        as possible as the bundles that depend on them. This is what this test ensures.
        """
        # The 2nd level dependency is initialially available from the main environment file.
        env = self._get_env("updating_included_app")
        _, file_path = env.find_location_for_framework("tk-framework-2nd-level-dep_v1.x.x")
        self.assertEqual(os.path.basename(file_path), "updating_included_app.yml")

        # Create a new framework that we've never seen before.
        fwk = self._mock_store.add_framework("tk-framework-test", "v1.0.0")
        # Add a new version of the app and add give it a dependency on the new framework.
        self._mock_store.add_application("tk-multi-app", "v2.0.0").required_frameworks = [
            fwk.get_major_dependency_descriptor()
        ]
        self._update_env("updating_included_app")

        # Reload env
        env = self._get_env("updating_included_app")

        # The new version of the app should reside inside common_apps.yml
        _, file_path = env.find_location_for_framework("tk-framework-test_v1.x.x")
        self.assertEqual(os.path.basename(file_path), "common_apps.yml")
        desc = env.get_framework_descriptor("tk-framework-test_v1.x.x")
        self.assertEqual(
            desc.get_location()["version"], "v1.0.0"
        )

        # Add another version, which this time will bring in a new framework
        # that is already being used in the environment file.
        fwk = self._mock_store.add_framework("tk-framework-test", "v1.0.1")
        fwk.required_frameworks = [self._2nd_level_dep_bundle.get_major_dependency_descriptor()]

        self._update_env("updating_included_app")

        # Reload env
        env = self._get_env("updating_included_app")

        # The new version of the app should reside inside common_apps.yml
        _, file_path = env.find_location_for_framework("tk-framework-test_v1.x.x")
        self.assertEqual(os.path.basename(file_path), "common_apps.yml")

        # Also, its dependency should now be picked up from the common_apps.yml file.
        _, file_path = env.find_location_for_framework("tk-framework-2nd-level-dep_v1.x.x")
        self.assertEqual(os.path.basename(file_path), "common_apps.yml")
