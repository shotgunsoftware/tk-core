# Copyright (c) 2016 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.
from ...util.shotgun import download

import json
import os
import re
import urllib2

from .downloadable import IODescriptorDownloadable
from ..errors import TankError, TankDescriptorError
from ... import LogManager

log = LogManager.get_logger(__name__)


class IODescriptorGithubRelease(IODescriptorDownloadable):
    """
    Represents a Github Release.
    """

    def __init__(self, descriptor_dict, sg_connection):
        """
        Constructor

        :param descriptor_dict: descriptor dictionary describing the bundle
        :param sg_connection: Shotgun connection to associated site
        :return: Descriptor instance
        """
        super(IODescriptorGithubRelease, self).__init__(descriptor_dict)
        self._validate_descriptor(
            descriptor_dict,
            required=["type", "organization", "repository", "version"],
            optional=[]
        )
        # @todo: validation, check for illegal chars, etc perhaps
        self._sg_connection = sg_connection
        self._organization = descriptor_dict["organization"]
        self._repository = descriptor_dict["repository"]
        self._version = descriptor_dict["version"]

    def _get_bundle_cache_path(self, bundle_cache_root):
        """
        Given a cache root, compute a cache path suitable
        for this descriptor, using the 0.18+ path format.

        :param bundle_cache_root: Bundle cache root path
        :return: Path to bundle cache location
        """
        return os.path.join(
            bundle_cache_root,
            "github",
            self._organization,
            self.get_system_name(),
            self.get_version()
        )

    def get_system_name(self):
        """
        Returns a short name, suitable for use in configuration files
        and for folders on disk, e.g. 'tk-maya'
        """
        return self._repository

    def get_version(self):
        """
        Returns the version number string for this item.
        In this case, this is the linked shotgun attachment id.
        """
        return self._version

    def _download_local(self, destination_path):
        """
        Retrieves this version to local repo.
        Will exit early if app already exists local.

        :param destination_path: The directory path to which the shotgun entity is to be
        downloaded to.
        """
        url = "https://github.com/{organization}/{system_name}/archive/{version}.zip"
        url = url.format(
            organization=self._organization,
            system_name=self.get_system_name(),
            version=self.get_version(),
        )

        try:
            download.download_and_unpack_url(
                self._sg_connection, url, destination_path, auto_detect_bundle=True
            )
        except TankError as e:
            raise TankDescriptorError(
                "Failed to download %s from %s. Error: %s" % (self, url, e)
            )

    def _get_github_releases(self, latest_only=False, url=None):
        """
        Helper method for interacting witht he Github API.  Finds releases using the
        Github API for the organization and repo of this Descriptor instance, and builds
        a list of tag names.  If the results are paginated and there is an additional page after
        the current page, that page's URL will also be returned.

        :param latest_only: If True asks the Github API for the latest release only.
        :param url: If specified, gets releases from this URL instead of building one.  This is
            useful for following pagination links.
        :return: tuple of list, string or None.  The list will contain a list of strings for the
            tag names (versions) that were found.  The second position will contain a URL for the
            next page if the results were paginated, or None if this is the last page of results.
        """
        if not url:
            # If no URL was provided, build one for this descriptor.
            url = "https://api.github.com/repos/{organization}/{system_name}/releases"
            url = url.format(organization=self._organization, system_name=self.get_system_name())
        if self._sg_connection.config.proxy_handler:
            # Grab proxy server settings from the shotgun API.
            opener = urllib2.build_opener(self._sg_connection.config.proxy_handler)
            urllib2.install_opener(opener)
        if latest_only:
            url += "/latest"
        # Find the "next" rel link from the headers, if one is present, and return it, so
        # that it can be followed if need be.
        next_link = None
        try:
            response = urllib2.urlopen(url)
            response_data = json.load(response)
            m = re.search(r"<(.+)>; rel=\"next\"", response.headers.get("link", ""))
            if m:
                next_link = m.group(1)
        except urllib2.HTTPError as e:
            if e.code == 404:
                # Github API gives a 404 when no releases have been published.  Additionally,
                # 404 could mean a non-existant or private repo, but this should have been caught
                # by has_remote_access().
                return ([], None)
            else:
                raise TankDescriptorError("Error communicating with Github API: %s" % e)
        except urllib2.URLError as e:
            raise TankDescriptorError("Unable to contact Github API: %s" % e)
        # zipballs are stored under the tag name, not the release name,
        # so that's the "version" name we want
        if latest_only:
            return ([response_data["tag_name"]], next_link)
        return ([release["tag_name"] for release in response_data], next_link)

    def get_latest_version(self, constraint_pattern=None):
        """
        Returns a descriptor object that represents the latest version.

        :param constraint_pattern: If this is specified, the query will be constrained
               by the given pattern. Version patterns are on the following forms:

                - v0.1.2, v0.12.3.2, v0.1.3beta - a specific version
                - v0.12.x - get the highest v0.12 version
                - v1.x.x - get the highest v1 version

        :returns: IODescriptorGithubRelease object
        """
        if constraint_pattern:
            # get the list of releases from github API.  If we don't find a match on
            # the first request, and there was an additional page linked, follow the link
            # and see if we find a match.  Repeat until a match is found, or there are no
            # more pages.
            can_fetch_more = True
            next_url = None
            version = None
            while not version and can_fetch_more:
                versions, next_url = self._get_github_releases(url=next_url)
                version = self._find_latest_tag_by_pattern(versions, constraint_pattern)
                can_fetch_more = next_url is not None
        else:
            # Otherwise, we can ask for the latest version from the github api
            # directly.
            versions, _ = self._get_github_releases(latest_only=True)
            version = versions[0] if versions else None
        if version is None or version == self.get_version():
            # There is no latest release, or the latest release is this one, so return this descriptor.
            return self
        # If a release was found, generate a descriptor for that version and return it.
        descriptor_dict = {
            "organization": self._organization,
            "repository": self.get_system_name(),
            "version": version,
            "type": "github_release",
        }
        desc = IODescriptorGithubRelease(descriptor_dict, self._sg_connection)
        desc.set_cache_roots(self._bundle_cache_root, self._fallback_roots)
        return desc

    def get_latest_cached_version(self, constraint_pattern=None):
        """
        Returns a descriptor object that represents the latest version
        that is locally available in the bundle cache search path.

        :param constraint_pattern: If this is specified, the query will be constrained
               by the given pattern. Version patterns are on the following forms:

                - v0.1.2, v0.12.3.2, v0.1.3beta - a specific version
                - v0.12.x - get the highest v0.12 version
                - v1.x.x - get the highest v1 version

        :returns: instance deriving from IODescriptorBase or None if not found
        """
        all_versions = self._get_locally_cached_versions()
        version_numbers = all_versions.keys()

        if not version_numbers:
            return None

        version_to_use = self._find_latest_tag_by_pattern(version_numbers, constraint_pattern)
        if version_to_use is None:
            return None

        # make a descriptor dict
        descriptor_dict = {
            "organization": self._organization,
            "repository": self.get_system_name(),
            "version": version_to_use,
            "type": "github_release",
        }

        # and return a descriptor instance
        desc = IODescriptorGithubRelease(descriptor_dict, self._sg_connection)
        desc.set_cache_roots(self._bundle_cache_root, self._fallback_roots)

        log.debug("Latest cached version resolved to %r" % desc)
        return desc

    def has_remote_access(self):
        """
        Probes if the current descriptor is able to handle
        remote requests. If this method returns, true, operations
        such as :meth:`download_local` and :meth:`get_latest_version`
        can be expected to succeed.

        :return: True if a remote is accessible, false if not.
        """
        # check if we can make api request for the specified repo
        can_connect = True
        url = "https://api.github.com/repos/{organization}/{system_name}"
        url = url.format(organization=self._organization, system_name=self.get_system_name())
        if self._sg_connection.config.proxy_handler:
            # Grab proxy server settings from the shotgun API
            opener = urllib2.build_opener(self._sg_connection.config.proxy_handler)
            urllib2.install_opener(opener)
        try:
            log.debug("%r: Probing if a connection to Github can be established..." % self)
            # ensure we get response code 200
            response_code = urllib2.urlopen(url).getcode()
            # Unfortunately, to prevent probing private repos, GH API also gives a 404 response
            # for private repos accessed without a token, so there's no way to helpfully warn the
            # user if they try to download from a private repo.
            can_connect = response_code == 200
            # @todo should we deal with redirects?
            # 301 Permanent redirection. The URI you used to make the request has been superseded by the one specified in the Location header field. This and all future requests to this resource should be directed to the new URI.
            # 302, 307 Temporary redirection. The request should be repeated verbatim to the URI specified in the Location header field but clients should continue to use the original URI for future requests.
            if can_connect:
                log.debug("...connection established!")
            else:
                log.debug("...got unexpected response code %s" % response_code)
        except urllib2.URLError as e:
            log.debug("...could not establish connection: %s" % e)
            can_connect = False
        return can_connect










