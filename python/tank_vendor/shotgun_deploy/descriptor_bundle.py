# Copyright (c) 2016 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

from .descriptor import Descriptor

class BundleDescriptor(Descriptor):

    def __init__(self, io_descriptor):
        super(BundleDescriptor, self).__init__(io_descriptor)

    def get_version_constraints(self):
        """
        Returns a dictionary with version constraints. The absence of a key
        indicates that there is no defined constraint. The following keys can be
        returned: min_sg, min_core, min_engine and min_desktop
        """
        constraints = {}

        manifest = self._io_descriptor.get_manifest()

        if manifest.get("requires_shotgun_version") is not None:
            constraints["min_sg"] = manifest.get("requires_shotgun_version")

        if manifest.get("requires_core_version") is not None:
            constraints["min_core"] = manifest.get("requires_core_version")

        if manifest.get("requires_engine_version") is not None:
            constraints["min_engine"] = manifest.get("requires_engine_version")

        if manifest.get("requires_desktop_version") is not None:
            constraints["min_desktop"] = manifest.get("requires_desktop_version")

        return constraints

    def get_required_context(self):
        """
        Returns the required context, if there is one defined for a bundle.
        This is a list of strings, something along the lines of
        ["user", "task", "step"] for an app that requires a context with
        user task and step defined.

        Always returns a list, with an empty list meaning no items required.
        """
        manifest = self._io_descriptor.get_manifest()
        rc = manifest.get("required_context")
        if rc is None:
            rc = []
        return rc


    def get_supported_platforms(self):
        """
        Returns the platforms supported. Possible values
        are windows, linux and mac.

        Always returns a list, returns an empty list if there is
        no constraint in place.

        example: ["windows", "linux"]
        example: []
        """
        manifest = self._io_descriptor.get_manifest()
        sp = manifest.get("supported_platforms")
        if sp is None:
            sp = []
        return sp

    def get_configuration_schema(self):
        """
        Returns the manifest configuration schema for this bundle.
        Always returns a dictionary.
        """
        manifest = self._io_descriptor.get_manifest()
        cfg = manifest.get("configuration")
        # always return a dict
        if cfg is None:
            cfg = {}
        return cfg


    def get_required_frameworks(self):
        """
        returns the list of required frameworks for this item.
        Always returns a list for example

        [{'version': 'v0.1.0', 'name': 'tk-framework-widget'}]

        Each item contains a name and a version key.
        """
        manifest = self._io_descriptor.get_manifest()
        frameworks = manifest.get("frameworks")
        # always return a list
        if frameworks is None:
            frameworks = []
        return frameworks

class EngineDescriptor(BundleDescriptor):

    def __init__(self, io_descriptor):
        super(EngineDescriptor, self).__init__(io_descriptor)



class AppDescriptor(BundleDescriptor):

    def __init__(self, io_descriptor):
        super(AppDescriptor, self).__init__(io_descriptor)

    def get_supported_engines(self):
        """
        Returns the engines supported for this app. May return None,
        meaning that anything goes.

        return: None                   (all engines are fine!)
        return: ["tk-maya", "tk-nuke"] (works with maya and nuke)
        """
        manifest = self._io_descriptor.get_manifest()
        return manifest.get("supported_engines")

class FrameworkDescriptor(BundleDescriptor):

    def __init__(self, io_descriptor):
        super(FrameworkDescriptor, self).__init__(io_descriptor)

    def is_shared_framework(self):
        """
        Returns a boolean indicating whether the bundle is a shared framework.

        Shared frameworks only have a single instance per instance name in the
        current environment.
        """
        manifest = self._io_descriptor.get_manifest()
        shared = manifest.get("shared")
        # always return a bool
        if shared is None:
            # frameworks are now shared by default unless you opt out.
            shared = True
        return shared
