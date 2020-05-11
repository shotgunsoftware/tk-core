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
import logging
import functools
import tempfile

import mock

from .tank_test_base import TankTestBase, setUpModule

import sgtk
from sgtk.descriptor import Descriptor
from sgtk.descriptor.io_descriptor.base import IODescriptorBase
from sgtk.descriptor import create_descriptor
from sgtk.util import sgre as re

from tank import TankError
from tank.platform.environment import InstalledEnvironment
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

        required_frameworks = property(
            _get_required_frameworks, _set_required_frameworks
        )

        def get_major_dependency_descriptor(self):
            return {
                "version": "v%s.x.x" % self._split_version()[0],
                "name": self.name,
                "type": "app_store",
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

    def add_core(self, version):
        """
        Create a core and register it to the mock store.

        :param version: Version of tk-core.

        :returns: A MockStoreCore object.
        """
        return self._add_typed_bundle(Descriptor.CORE, "tk-core", version)

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
        self._bundles.setdefault(bundle.bundle_type, {}).setdefault(bundle.name, {})[
            bundle.version
        ] = bundle

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
        return list(self._bundles[bundle_type][name].keys())


# Simpler than having to write three class types that would also have to be documented.
MockStoreCore = functools.partial(MockStore._Entry, bundle_type=Descriptor.CORE)
MockStoreApp = functools.partial(MockStore._Entry, bundle_type=Descriptor.APP)
MockStoreFramework = functools.partial(
    MockStore._Entry, bundle_type=Descriptor.FRAMEWORK
)
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
        IODescriptorBase.__init__(self, location_dict, sg_connection, bundle_type)
        self._type = bundle_type

    def create(self, version):
        """
        Simple method to create an instance of the mocker object. This is required only when testing the framework.

        :returns: A IODescriptorAppStore object.
        """
        descriptor = TankMockStoreDescriptor(
            {"name": self.get_system_name(), "type": "app_store", "version": version},
            None,
            self._type,
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
            self._type, self.get_system_name()
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
            self._type, self.get_system_name()
        )

        version_to_use = self._find_latest_tag_by_pattern(
            version_numbers, version_pattern
        )

        return self.create(version_to_use)

    def get_manifest(self, _):
        """
        Returns the manifest data
        """
        bundle = MockStore.instance.get_bundle(
            self._type, self.get_system_name(), self.get_version()
        )

        return {"frameworks": bundle.required_frameworks}

    def has_remote_access(self):
        """
        Do we have a remote connection?
        """
        return True

    def clone_cache(self, cache_root):
        """
        The descriptor system maintains an internal cache where it downloads
        the payload that is associated with the descriptor. Toolkit supports
        complex cache setups, where you can specify a series of path where toolkit
        should go and look for cached items.

        :param cache_root: Root point of the cache location to copy to.
        :returns: True if the cache was copied, false if not
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
            new=TankMockStoreDescriptor,
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
        IODescriptorBase._factory["app_store"] = TankMockStoreDescriptor
        return MockStore.instance

    def stop(self):
        """
        Unpatches the api.
        """
        del MockStore.instance
        self._patch.stop()
        from tank.descriptor.io_descriptor.appstore import IODescriptorAppStore

        IODescriptorBase._factory["app_store"] = IODescriptorAppStore

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
