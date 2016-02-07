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


class Descriptor(object):
    """
    An app descriptor describes a particular version of an app, engine or core component.
    It also knows how to access metadata such as documentation, descriptions etc.

    Several AppDescriptor classes exists, all deriving from this base class, and the
    factory method descriptor_factory() manufactures the correct descriptor object
    based on a location dict, that is found inside of the environment config.

    Different App Descriptor implementations typically handle different source control
    systems: There may be an app descriptor which knows how to communicate with the
    Tank App store and one which knows how to handle the local file system.
    """

    (APP, FRAMEWORK, ENGINE, CONFIG, CORE) = range(5)

    ###############################################################################################
    # constants and helpers

    def __init__(self, io_descriptor):
        """
        Constructor
        """
        # construct a suitable IO descriptor for this locator
        self._io_descriptor = io_descriptor

    def __repr__(self):
        class_name = self.__class__.__name__
        return "<%s %s %s>" % (class_name, self.get_system_name(), self.get_version())

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
        """
        return self._io_descriptor.get_location()

    def get_display_name(self):
        """
        Returns the display name for this item.
        If no display name has been defined, the system name will be returned.
        """
        meta = self._io_descriptor.get_manifest()
        display_name = meta.get("display_name")
        if display_name is None:
            display_name = self.get_system_name()
        return display_name

    def is_developer(self):
        """
        Returns true if this item is intended for development purposes
        """
        return self._io_descriptor.is_developer()

    def get_description(self):
        """
        Returns a short description for the app.
        """
        meta = self._io_descriptor.get_manifest()
        desc = meta.get("description")
        if desc is None:
            desc = "No description available." 
        return desc

    def get_icon_256(self):
        """
        Returns the path to a 256px square png icon file for this app
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
        """
        meta = self._io_descriptor.get_manifest()
        doc_url = meta.get("documentation_url")
        # note - doc_url can be none which is fine.
        return doc_url

    def get_deprecation_status(self):
        """
        Returns (is_deprecated (bool), message (str)) to indicate if this item is deprecated.
        """
        # only some descriptors handle this. Default is to not support deprecation, e.g.
        # always return that things are active.
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
        Returns a tuple: (changelog_summary, changelog_url). Values may be None
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
        Returns true if this item exists in a local repo
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
        
            - v1.2.3 (means the descriptor returned will inevitably be same as self)
            - v1.2.x 
            - v1.x.x

        :returns: descriptor object
        """
        self._io_descriptor = self._io_descriptor.get_latest_version(constraint_pattern)

        # @todo - this interface makes less sense now with the new object structure.
        return self

