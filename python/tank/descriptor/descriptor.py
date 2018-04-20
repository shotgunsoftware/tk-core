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
import copy

from . import constants

from ..log import LogManager

logger = LogManager.get_logger(__name__)


class Descriptor(object):
    """
    A descriptor describes a particular version of an app, engine or core component.
    It also knows how to access metadata such as documentation, descriptions etc.

    Descriptor is subclassed to distinguish different types of payload;
    apps, engines, configs, cores etc. Each payload may have different accessors
    and helper methods.
    """

    (APP, FRAMEWORK, ENGINE, CONFIG, CORE, INSTALLED_CONFIG) = range(6)

    def __init__(self, io_descriptor):
        """
        Use the factory method :meth:`create_descriptor` when
        creating new descriptor objects.

        :param io_descriptor: Associated IO descriptor.
        """
        # construct a suitable IO descriptor for this descriptor
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
        return "%s %s" % (self.system_name, self.version)

    def _get_manifest(self):
        """
        Returns the info.yml metadata associated with this descriptor.

        :returns: dictionary with the contents of info.yml
        """
        return self._io_descriptor.get_manifest(constants.BUNDLE_METADATA_FILE)

    ###############################################################################################
    # data accessors

    def get_dict(self):
        """
        Returns the dictionary associated with this descriptor

        :returns: Dictionary that can be used to construct the descriptor
        """
        return self._io_descriptor.get_dict()

    # legacy support for previous method name
    get_location = get_dict

    def get_uri(self):
        """
        Returns the uri associated with this descriptor
        The uri is a string based representation that is equivalent to the
        descriptor dictionary returned by the get_dict() method.

        :returns: Uri string that can be used to construct the descriptor
        """
        return self._io_descriptor.get_uri()

    def copy(self, target_folder):
        """
        Copy the config descriptor into the specified target location.

        :param target_folder: Folder to copy the descriptor to
        """
        self._io_descriptor.copy(target_folder)

    def clone_cache(self, cache_root):
        """
        The descriptor system maintains an internal cache where it downloads
        the payload that is associated with the descriptor. Toolkit supports
        complex cache setups, where you can specify a series of path where toolkit
        should go and look for cached items.

        This is an advanced method that helps in cases where a user wishes to
        administer such a setup, allowing a cached payload to be copied from
        its current location into a new cache structure.

        If the descriptor's payload doesn't exist on disk, it will be downloaded.

        :param cache_root: Root point of the cache location to copy to.
        """
        return self._io_descriptor.clone_cache(cache_root)

    @property
    def display_name(self):
        """
        The display name for this item.
        If no display name has been defined, the system name will be returned.
        """
        meta = self._get_manifest()
        display_name = meta.get("display_name")
        if display_name is None:
            display_name = self.system_name
        return display_name

    def is_dev(self):
        """
        Returns true if this item is intended for development purposes

        :returns: True if this is a developer item
        """
        return self._io_descriptor.is_dev()

    def is_immutable(self):
        """
        Returns true if this descriptor never changes its content.
        This is true for most descriptors as they represent a particular
        version, tag or commit of an item. Examples of non-immutable
        descriptors include path and dev descriptors, where the
        descriptor points at a "live" location on disk where a user
        can make changes at any time.

        :returns: True if this is a developer item
        """
        return self._io_descriptor.is_immutable()

    @property
    def description(self):
        """
        A short description of the item.
        """
        meta = self._get_manifest()
        desc = meta.get("description")
        if desc is None:
            desc = "No description available."
        return desc

    @property
    def icon_256(self):
        """
        The path to a 256px square png icon file representing this item
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

    @property
    def support_url(self):
        """
        A url that points at a support web page associated with this item.
        If not url has been defined, ``None`` is returned.
        """
        meta = self._get_manifest()
        support_url = meta.get("support_url")
        if support_url is None:
            support_url = "https://support.shotgunsoftware.com"
        return support_url

    @property
    def documentation_url(self):
        """
        The documentation url for this item. If no documentation url has been defined,
        a url to the toolkit user guide is returned.
        """
        meta = self._get_manifest()
        doc_url = meta.get("documentation_url")
        if doc_url is None:
            doc_url = "https://support.shotgunsoftware.com/hc/en-us/articles/115000068574-User-Guide"
        return doc_url

    @property
    def deprecation_status(self):
        """
        Information about deprecation status.

        :returns: Returns a tuple (is_deprecated, message) to indicate
                  if this item is deprecated.
        """
        return self._io_descriptor.get_deprecation_status()

    @property
    def system_name(self):
        """
        A short name, suitable for use in configuration files and for folders on disk.
        """
        return self._io_descriptor.get_system_name()

    @property
    def version(self):
        """
        The version number string for this item.
        """
        return self._io_descriptor.get_version()

    def get_path(self):
        """
        Returns the path to a location where this item is cached.

        When locating the item, any bundle cache fallback paths
        will first be searched in the order they have been defined,
        and lastly the main bundle cached will be checked.

        If the item is not locally cached, ``None`` is returned.

        :returns: Path string or ``None`` if not cached.
        """
        return self._io_descriptor.get_path()

    @property
    def changelog(self):
        """
        Information about the changelog for this item.

        :returns: A tuple (changelog_summary, changelog_url). Values may be ``None``
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

        .. note:: Different descriptor types implements this logic differently,
                  but general good practice is to follow the semantic version numbering
                  standard for any versions used in conjunction with toolkit. This ensures
                  that toolkit can track and correctly determine not just the latest version
                  but also apply constraint pattern matching such as looking for the latest
                  version matching the pattern ``v1.x.x``. You can read more about semantic
                  versioning here: http://semver.org/

        :param constraint_pattern: If this is specified, the query will be constrained
               by the given pattern. Version patterns are on the following forms:

                - v0.1.2, v0.12.3.2, v0.1.3beta - a specific version
                - v0.12.x - get the highest v0.12 version
                - v1.x.x - get the highest v1 version

        :returns: instance derived from :class:`Descriptor`
        """
        # make a copy of the descriptor
        latest = copy.copy(self)
        # find latest I/O descriptor
        latest._io_descriptor = self._io_descriptor.get_latest_version(constraint_pattern)
        return latest

    def find_latest_cached_version(self, constraint_pattern=None):
        """
        Returns a descriptor object that represents the latest version
        that can be found in the local bundle caches.

        .. note:: Different descriptor types implements this logic differently,
                  but general good practice is to follow the semantic version numbering
                  standard for any versions used in conjunction with toolkit. This ensures
                  that toolkit can track and correctly determine not just the latest version
                  but also apply constraint pattern matching such as looking for the latest
                  version matching the pattern ``v1.x.x``. You can read more about semantic
                  versioning here: http://semver.org/

        :param constraint_pattern: If this is specified, the query will be constrained
               by the given pattern. Version patterns are on the following forms:

                - v0.1.2, v0.12.3.2, v0.1.3beta - a specific version
                - v0.12.x - get the highest v0.12 version
                - v1.x.x - get the highest v1 version

        :returns: Instance derived from :class:`Descriptor` or ``None`` if no cached version
                  is available.
        """
        io_desc = self._io_descriptor.get_latest_cached_version(constraint_pattern)
        if io_desc is None:
            return None

        # make a copy of the descriptor
        latest = copy.copy(self)
        # find latest I/O descriptor
        latest._io_descriptor = io_desc
        return latest

    def has_remote_access(self):
        """
        Probes if the current descriptor is able to handle
        remote requests. If this method returns, true, operations
        such as :meth:`download_local` and :meth:`find_latest_version`
        can be expected to succeed.

        :return: True if a remote is accessible, false if not.
        """
        return self._io_descriptor.has_remote_access()

    # compatibility accessors to ensure that all systems
    # calling this (previously internal!) parts of toolkit
    # will still work.
    def get_display_name(self):
        return self.display_name

    def get_description(self):
        return self.description

    def get_icon_256(self):
        return self.icon_256

    def get_support_url(self):
        return self.support_url

    def get_doc_url(self):
        return self.documentation_url

    def get_deprecation_status(self):
        return self.deprecation_status

    def get_system_name(self):
        return self.system_name

    def get_version(self):
        return self.version

    def get_changelog(self):
        return self.changelog
