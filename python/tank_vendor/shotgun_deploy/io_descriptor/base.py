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
import re
import cgi
import urlparse

from .. import util
from .. import constants
from ..errors import ShotgunDeployError

from ...shotgun_base import copy_folder
from ... import yaml


log = util.get_shotgun_deploy_logger()

class IODescriptorBase(object):
    """
    An I/O descriptor describes a particular version of an app, engine or core component.
    It also knows how to access metadata such as documentation, descriptions etc.

    Several Descriptor classes exists, all deriving from this base class, and the
    factory method create_descriptor() manufactures the correct descriptor object
    based on a location dict, that is found inside of the environment config.

    Different App Descriptor implementations typically handle different source control
    systems: There may be an app descriptor which knows how to communicate with the
    Tank App store and one which knows how to handle the local file system.

    A descriptor is immutable in the sense that it always points at the same code -
    this may be a particular frozen version out of that toolkit app store that
    will not change or it may be a dev area where the code can change. Given this,
    descriptors are cached and only constructed once for a given descriptor URL.
    """

    # @todo - need a way to clear this cache (for example when switching tk APIs)
    #         we should look at a general cache system (maybe part of shotgun_base)
    #         where we can keep better track of globals in general.
    _instances = dict()

    def __new__(cls, location_dict, *args, **kwargs):
        """
        Handles caching of descriptors.

        Executed prior to __init__ being executed.

        Since all our normal descriptors are immutable - they represent a specific,
        read only and cached version of an app, engine or framework on disk, we can
        also cache their wrapper objects.

        :param bundle_cache_root: Root location for bundle cache
        :param location_dict: Location dictionary describing the bundle
        :returns: Descriptor instance
        """
        instance_cache = cls._instances

        # The cache is keyed based on the location dict
        cache_key = str(location_dict)

        # Instantiate and cache if we need to, otherwise just return what we
        # already have stored away.
        if cache_key not in instance_cache:
            # If the bundle install path isn't in the cache, then we are
            # starting fresh. Otherwise, check to see if the app (by name)
            # is cached, and if not initialize its specific cache. After
            # that we instantiate and store by version.
            instance_cache[cache_key] = super(IODescriptorBase, cls).__new__(
                cls,
                location_dict,
                *args,
                **kwargs
            )

        return instance_cache[cache_key]

    def __init__(self, location_dict):
        """
        Constructor

        :param bundle_cache_root: Root location for bundle cache storage
        :param location_dict: dictionary describing the location
        """
        self._bundle_cache_root = None
        self._fallback_roots = []
        self._location_dict = location_dict
        self.__manifest_data = None

    def set_cache_roots(self, primary_root, fallback_roots):
        """
        Specify where to go look for cached versions of the app.
        The primary root is where new data is always written to
        if something is downloaded and cached. The fallback_roots
        parameter is a list of paths where the descriptor system
        will look in case a cached entry is not found in the
        primary root. If you specify several fallback roots, they
        will be traversed in order.

        This is an internal method that is part of the construction
        of the descriptor instances. Do not call directly.

        :param primary_root: Path for reading and writing cached apps
        :param fallback_roots: Paths to attempt to read cached apps from
                               in case it's not found in the primary root.
                               Paths will be traversed in the order they are
                               specified.

        """
        self._bundle_cache_root = primary_root
        self._fallback_roots = fallback_roots

    def __repr__(self):
        """
        Low level representation
        """
        class_name = self.__class__.__name__
        return "<%s %s>" % (class_name, self.get_uri())

    @classmethod
    def _validate_locator(cls, location, required, optional):
        """
        Validate that the locator dictionary has got the necessary keys.

        Raises ShotgunDeployError if required parameters are missing.
        Logs warnings if parameters outside the required/optional range are specified.

        :param location: Location dict
        :param required: List of required parameters
        :param optional: List of optionally supported parameters
        :raises: ShotgunDeployError if the location dict does not include all parameters.
        """
        location_keys_set = set(location.keys())
        required_set = set(required)
        optional_set = set(optional)

        if not required_set.issubset(location_keys_set):
            missing_keys = required_set.difference(location_keys_set)
            raise ShotgunDeployError("%s are missing required keys %s" % (location, missing_keys))

        all_keys = required_set.union(optional_set)

        if location_keys_set.difference(all_keys):
            log.warning(
                "Found unsupported parameters %s in %s. "
                "These will be ignored." % (location_keys_set.difference(all_keys), location)
            )

    def _find_latest_tag_by_pattern(self, version_numbers, pattern):
        """
        Given a list of version strings (e.g. 'v1.2.3'), find the one
        that best matches the given pattern.

        Version numbers passed in that don't match the pattern v1.2.3... will be ignored.

        :param version_numbers: List of version number strings, e.g. ``['v1.2.3', 'v1.2.5']``
        :param pattern: Version pattern string, e.g. 'v1.x.x'. Patterns are on the following forms:

            - v1.2.3 (can return this v1.2.3 but also any forked version under, eg. v1.2.3.2)
            - v1.2.x (examples: v1.2.4, or a forked version v1.2.4.2)
            - v1.x.x (examples: v1.3.2, a forked version v1.3.2.2)
            - v1.2.3.x (will always return a forked version, eg. v1.2.3.2)

        :returns: The most appropriate tag in the given list of tags
        :raises: ShotgunDeployError if parsing fails
        """
        # now put all version number strings which match the form
        # vX.Y.Z(.*) into a nested dictionary where it is keyed recursively
        # by each digit (ie. major, minor, increment, then any additional
        # digit optionally used by forked versions)
        #
        versions = {}
        for version_num in version_numbers:
            try:
                version_split = map(int, version_num[1:].split("."))
            except Exception, e:
                # this git tag is not on the expected form vX.Y.Z where X Y and Z are ints. skip.
                continue

            if len(version_split) < 3:
                # git tag has no minor or increment number. skip.
                continue

            # fill our versions dictionary
            #
            # For example, the following versions:
            # v1.2.1, v1.2.2, v1.2.3.1, v1.4.3, v1.4.2.1, v1.4.2.2, v1.4.1,
            #
            # Would generate the following:
            # {1:
            #   {2: {1: {},
            #        2: {},
            #        3: {1: {}
            #       }
            #   },
            #   4: {1: {},
            #       2: {1: {}, 2: {}},
            #       3: {}
            #       }
            #   }
            # }
            #
            current = versions
            for number in version_split:
                if number not in current:
                    current[number] = {}
                current = current[number]

        # now search for the latest version matching our pattern
        version_to_use = None
        if not re.match("^v([0-9]+|x)(.([0-9]+|x)){2,}$", pattern):
            raise ShotgunDeployError("Cannot parse version expression '%s'!" % pattern)

        # split our pattern, beware each part is a string (even integers)
        version_split = re.findall("([0-9]+|x)", pattern)
        if 'x' in version_split:
            # check that we don't have an incorrect pattern using x
            # then a digit, eg. v4.x.2
            if re.match("^v[0-9\.]+[x\.]+[0-9\.]+$", pattern):
                raise ShotgunDeployError(
                    "Incorrect version pattern '%s'. "
                    "There should be no digit after a 'x'." % pattern
                )

        current = versions
        version_to_use = None
        # process each digit in the pattern
        for version_digit in version_split:
            if version_digit == 'x':
                # replace the 'x' by the latest at this level
                version_digit = max(current.keys(), key=int)
            version_digit = int(version_digit)
            if version_digit not in current:
                raise ShotgunDeployError(
                    "%s does not have a version matching the pattern '%s'. "
                    "Available versions are: %s" % (self._path, pattern, ", ".join(version_numbers))
                )
            current = current[version_digit]
            if version_to_use is None:
                version_to_use = "v%d" % version_digit
            else:
                version_to_use = version_to_use + ".%d" % version_digit

        # at this point we have a matching version (eg. v4.x.x => v4.0.2) but
        # there may be forked versions under this 4.0.2, so continue to recurse into
        # the versions dictionary to find the latest forked version
        while len(current):
            version_digit = max(current.keys())
            current = current[version_digit]
            version_to_use = version_to_use + ".%d" % version_digit

        return version_to_use


    def copy(self, target_path):
        """
        Copy the contents of the descriptor to an external location

        :param target_path: target path to copy the descriptor to.
        """
        log.debug("Copying %r -> %s" % (self, target_path))
        # base class implementation does a straight copy
        # make sure config exists
        self.ensure_local()
        # copy descriptor in
        copy_folder(self.get_path(), target_path)

    def get_manifest(self):
        """
        Returns the info.yml metadata associated with this descriptor.
        Note that this call involves deep introspection; in order to
        access the metadata we normally need to have the code content
        local, so this method may trigger a remote code fetch if necessary.

        :returns: dictionary with the contents of info.yml
        """
        if self.__manifest_data is None:
            # make sure payload exists locally
            if not self.exists_local():
                # @todo - at this point add to a metadata cache for performance
                # we can either just store it in a pickle, in order to avoid yaml parsing, which
                # is expensive, or if we want to be more fancy, we can maintain a single
                # "registry" file which holds the metadata for all known bundles in a single place.
                # given that all descriptors are immutable (except the ones where the immutable)
                # property returns false, we can keep adding to this global cache file over time.
                self.download_local()

            # get the metadata
            bundle_root = self.get_path()
            file_path = os.path.join(bundle_root, constants.BUNDLE_METADATA_FILE)

            if not os.path.exists(file_path):
                # at this point we have downloaded the bundle, but it may have
                # an invalid internal structure.
                raise ShotgunDeployError("Toolkit metadata file '%s' missing." % file_path)

            try:
                file_data = open(file_path)
                try:
                    metadata = yaml.load(file_data)
                finally:
                    file_data.close()
            except Exception, exp:
                raise ShotgunDeployError("Cannot load metadata file '%s'. Error: %s" % (file_path, exp))

            # cache it
            self.__manifest_data = metadata

        return self.__manifest_data

    @classmethod
    def dict_from_uri(cls, uri):
        """
        Convert a uri string into a location dictionary.

        Example:

        - uri:           sgtk:location:app_store?name=hello&version=v123
        - expected_type: app_store
        - returns:   {'type': 'app_store',
                      'name': 'hello',
                      'version': 'v123'}

        :param uri: uri string
        :return: dictionary with keys type and all keys specified
                 in the item_keys parameter matched up by items in the
                 uri string.
        """
        parsed_uri = urlparse.urlparse(uri)
        # example:
        # >>> urlparse.urlparse("sgtk:location:app_store?foo=bar&baz=buz")
        # ParseResult(scheme='sgtk', netloc='', path='location:app_store',
        #             params='', query='foo=bar&baz=buz', fragment='')


        if parsed_uri.scheme != constants.LOCATOR_URI_PATH_SCHEME:
            raise ShotgunDeployError("Invalid uri '%s' - must begin with 'sgtk'" % uri)

        split_path = parsed_uri.path.split(constants.LOCATOR_URI_SEPARATOR)
        # e.g. 'location:app_store' -> ('location', 'app_store')
        if len(split_path) != 2 or split_path[0] != constants.LOCATOR_URI_PATH_PREFIX:
            raise ShotgunDeployError("Invalid uri '%s' - must begin with sgtk:location" % uri)

        location_dict = {}

        location_dict["type"] = split_path[1]

        # now pop remaining keys into a dict and key by item_keys
        # note: using deprecated cfg method for 2.5 compatibility
        # example:
        # >>> cgi.parse_qs("path=foo&version=v1.2.3")
        # {'path': ['foo'], 'version': ['v1.2.3']}
        for (param, value) in cgi.parse_qs(parsed_uri.query).iteritems():
            if len(value) > 1:
                raise ShotgunDeployError("Invalid uri '%s' - duplicate parameters" % uri)
            location_dict[param] = value[0]

        return location_dict

    def get_location(self):
        """
        Returns the location dict associated with this descriptor
        """
        return self._location_dict

    @classmethod
    def uri_from_dict(cls, location_dict):
        """
        Create a locator uri given some data

        {'type': 'app_store', 'bar':'baz'} --> 'sgtk:location:app_store?bar=baz'

        :param location_dict: Location dictionary
        :return: location uri
        """
        if "type" not in location_dict:
            raise ShotgunDeployError(
                "Cannot create uri from %s - missing type field" % location_dict
            )

        uri_chunks = [
            constants.LOCATOR_URI_PATH_SCHEME,
            constants.LOCATOR_URI_PATH_PREFIX,
            location_dict["type"]
        ]
        uri = constants.LOCATOR_URI_SEPARATOR.join(uri_chunks)

        qs_chunks = []
        for (param, value) in location_dict.iteritems():
            if param == "type":
                continue
            qs_chunks.append("%s=%s" % (param, value))
        qs = "&".join(qs_chunks)

        return "%s?%s" % (uri, qs)

    def get_uri(self):
        """
        Return the string based uri representation of this object

        :return: Uri string
        """
        return self.uri_from_dict(self._location_dict)

    def get_deprecation_status(self):
        """
        Returns information about deprecation.

        :returns: Returns a tuple (is_deprecated, message) to indicate
                  if this item is deprecated.
        """
        # only some descriptors handle this. Default is to not support deprecation, e.g.
        # always return that things are active.
        return False, ""

    def get_changelog(self):
        """
        Returns information about the changelog for this item.

        :returns: A tuple (changelog_summary, changelog_url). Values may be None
                  to indicate that no changelog exists.
        """
        return (None, None)

    def is_dev(self):
        """
        Returns true if this item is intended for development purposes
        """
        return False

    def is_immutable(self):
        """
        Returns true if this item's content never changes
        """
        return True

    def ensure_local(self):
        """
        Convenience method. Ensures that the descriptor exists locally.
        """
        if not self.exists_local():
            log.debug("Downloading %s to the local Toolkit install location..." % self)
            self.download_local()

    def exists_local(self):
        """
        Returns true if this item exists in a locally accessible form
        """
        return self.get_path() is not None

    def get_path(self):
        """
        Returns the path to the folder where this item resides. If no
        cache exists for this path, None is returned.
        """
        for path in self._get_cache_paths():
            # we determine local existence based on the info.yml
            info_yml_path = os.path.join(path, constants.BUNDLE_METADATA_FILE)
            if os.path.exists(info_yml_path):
                return path

        return None


    ###############################################################################################
    # stuff typically implemented by deriving classes

    def _get_cache_paths(self):
        """
        Get a list of resolved paths, starting with the primary and
        continuing with alternative locations where it may reside

        Note: This method only computes paths and does not perform any I/O ops.

        :return: List of path strings
        """
        raise NotImplementedError

    def get_system_name(self):
        """
        Returns a short name, suitable for use in configuration files
        and for folders on disk, e.g. 'tk-maya'
        """
        raise NotImplementedError
    
    def get_version(self):
        """
        Returns the version number string for this item, .e.g 'v1.2.3'
        """
        raise NotImplementedError

    def download_local(self):
        """
        Retrieves this version to local repo.
        """
        raise NotImplementedError

    def get_latest_version(self, constraint_pattern=None):
        """
        Returns a descriptor object that represents the latest version.

        :param constraint_pattern: If this is specified, the query will be constrained
               by the given pattern. Version patterns are on the following forms:

                - v0.1.2, v0.12.3.2, v0.1.3beta - a specific version
                - v0.12.x - get the highest v0.12 version
                - v1.x.x - get the highest v1 version

        :returns: descriptor object
        """
        raise NotImplementedError



