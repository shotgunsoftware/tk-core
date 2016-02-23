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
import sys
import copy

from . import paths
from .descriptor_io import create_io_descriptor
from .errors import ShotgunDeployError

def create_descriptor(sg_connection, descriptor_type, location, bundle_cache_root=None):
    """
    Factory method. Use this when creating descriptor objects.

    :param sg_connection: Shotgun connection to associated site
    :param descriptor_type: Either AppDescriptor.APP, CORE, ENGINE or FRAMEWORK
    :param location: A std location dictionary dictionary or string
    :param bundle_cache_root: Root path to where downloaded apps are cached
    :returns: Descriptor object
    """
    from .descriptor_bundle import AppDescriptor, EngineDescriptor, FrameworkDescriptor
    from .descriptor_config import ConfigDescriptor
    from .descriptor_core import CoreDescriptor

    # if bundle root is not set, fall back on default location
    bundle_cache_root = bundle_cache_root or paths.get_bundle_cache_root()

    # first construct a low level IO descriptor
    io_descriptor = create_io_descriptor(
        sg_connection,
        descriptor_type,
        location,
        bundle_cache_root
    )

    # now create a high level descriptor and bind that with the low level descriptor
    if descriptor_type == Descriptor.APP:
        return AppDescriptor(io_descriptor)

    elif descriptor_type == Descriptor.ENGINE:
        return EngineDescriptor(io_descriptor)

    elif descriptor_type == Descriptor.FRAMEWORK:
        return FrameworkDescriptor(io_descriptor)

    elif descriptor_type == Descriptor.CONFIG:
        return ConfigDescriptor(io_descriptor)

    elif descriptor_type == Descriptor.CORE:
        return CoreDescriptor(io_descriptor)

    else:
        raise ShotgunDeployError("Unsupported descriptor type %s" % descriptor_type)


class Descriptor(object):
    """
    A descriptor describes a particular version of an app, engine or core component.
    It also knows how to access metadata such as documentation, descriptions etc.

    Descriptor is subclassed to distinguish different types of payload;
    apps, engines, configs, cores etc. Each payload may have different accessors
    and helper methods.
    """

    (APP, FRAMEWORK, ENGINE, CONFIG, CORE) = range(5)

    def __init__(self, io_descriptor):
        """
        Constructor

        :param io_descriptor: Associated IO descriptor.
        """
        # construct a suitable IO descriptor for this locator
        self._io_descriptor = io_descriptor

    def __eq__(self, other):
        # By default, we can assume equality if the path to the data
        # on disk is equivalent.
        if isinstance(other, self.__class__):
            return self.get_path() == other.get_path()
        else:
            return False

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):
        """
        Used for debug logging
        """
        class_name = self.__class__.__name__
        return "<%s %r>" % (class_name, self._io_descriptor)

    def __str__(self):
        """
        Used for pretty printing
        """
        return "%s %s" % (self.get_system_name(), self.get_version())

    ###############################################################################################
    # data accessors

    def get_location(self):
        """
        Returns the location dict associated with this descriptor

        :returns: Dictionary that can be used to construct the descriptor
        """
        return self._io_descriptor.get_location()

    def copy(self, target_folder):
        """
        Copy the config descriptor into the specified target location

        :param target_folder: Folder to copy the descriptor to
        """
        self._io_descriptor.copy(target_folder)

    def get_bundle_cache_root(self):
        """
        Returns the folder which is used as the base point
        for caching of resources relevant to this descriptor

        :returns: path on disk as string
        """
        return self._io_descriptor.get_bundle_cache_root()

    def get_display_name(self):
        """
        Returns the display name for this item.
        If no display name has been defined, the system name will be returned.

        :returns: Display name as string
        """
        meta = self._io_descriptor.get_manifest()
        display_name = meta.get("display_name")
        if display_name is None:
            display_name = self.get_system_name()
        return display_name

    def is_developer(self):
        """
        Returns true if this item is intended for development purposes

        :returns: True if this is a developer item
        """
        return self._io_descriptor.is_developer()

    def get_description(self):
        """
        Returns a short description for the app.

        :returns: Description as string
        """
        meta = self._io_descriptor.get_manifest()
        desc = meta.get("description")
        if desc is None:
            desc = "No description available." 
        return desc

    def get_icon_256(self):
        """
        Returns the path to a 256px square png icon file for this app

        :returns: Path to a 256px png icon file
        """
        app_icon = os.path.join(self._io_descriptor.get_path(), "icon_256.png")
        if os.path.exists(app_icon):
            return app_icon
        else:
            # return default
            default_icon = os.path.abspath(os.path.join(
                os.path.dirname(__file__),
                "resources",
                "default_bundle_256px.png"
            ))
            return default_icon

    def get_support_url(self):
        """
        Returns a url that points to a support web page where you can get help
        if you are stuck with this item.

        :returns: Url as string or None if not defined
        """
        meta = self._io_descriptor.get_manifest()
        support_url = meta.get("support_url")
        if support_url is None:
            support_url = "https://support.shotgunsoftware.com" 
        return support_url

    def get_doc_url(self):
        """
        Returns the documentation url for this item. Returns None if the documentation url
        is not defined. This is sometimes subclassed, where a descriptor (like the tank app
        store) and support for automatic, built in documentation management. If not, the 
        default implementation will search the manifest for a doc url location.

        :returns: Url as string or None if not defined
        """
        meta = self._io_descriptor.get_manifest()
        doc_url = meta.get("documentation_url")
        # note - doc_url can be none which is fine.
        return doc_url

    def get_deprecation_status(self):
        """
        Returns information about deprecation.

        :returns: Returns a tuple (is_deprecated, message) to indicate
                  if this item is deprecated.
        """
        return self._io_descriptor.get_deprecation_status()

    def get_system_name(self):
        """
        Returns a short name, suitable for use in configuration files
        and for folders on disk
        """
        return self._io_descriptor.get_system_name()
    
    def get_version(self):
        """
        Returns the version number string for this item.
        """
        return self._io_descriptor.get_version()
    
    def get_path(self):
        """
        returns the path to the folder where this item resides
        """
        return self._io_descriptor.get_path()

    def get_changelog(self):
        """
        Returns information about the changelog for this item.

        :returns: A tuple (changelog_summary, changelog_url). Values may be None
                  to indicate that no changelog exists.
        """
        return self._io_descriptor.get_changelog()

    def ensure_local(self):
        """
        Helper method. Ensures that the item is locally available.
        """
        return self._io_descriptor.ensure_local()

    def exists_local(self):
        """
        Returns true if this item exists in a local repo.
        """
        return self._io_descriptor.exists_local()

    def download_local(self):
        """
        Retrieves this version to local repo.
        """
        return self._io_descriptor.download_local()

    def find_latest_version(self, constraint_pattern=None):
        """
        Returns a descriptor object that represents the latest version.

        :param constraint_pattern: If this is specified, the query will be constrained
               by the given pattern. Version patterns are on the following forms:

                - v0.1.2, v0.12.3.2, v0.1.3beta - a specific version
                - v0.12.x - get the highest v0.12 version
                - v1.x.x - get the highest v1 version

        :returns: descriptor object
        """
        # make a copy of the descriptor
        latest = copy.copy(self)
        # find latest I/O descriptor
        latest._io_descriptor = self._io_descriptor.get_latest_version(constraint_pattern)
        return latest


