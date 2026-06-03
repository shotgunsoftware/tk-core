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
import urllib.error
import urllib.request

import sgtk
from sgtk.descriptor import Descriptor
from sgtk.util import sgre as re
from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import ShotgunTestBase, mock

_TESTED_MODULE = "tank.descriptor.io_descriptor.github_release"
_TESTED_CLASS = _TESTED_MODULE + ".IODescriptorGithubRelease"


class MockResponse(object):
    """
    An object that mocks the needed attributes/methods of the object returned by urllib.urlopen().

    It uses json and header files on disk to load the data for the url that should be mocked.
    """

    def __init__(self, page_name):
        """
        Initialize the MockResponse object with the data stored in the .json and .header files.

        :param page_name: The basename of the .json and .header files to load data from.  These
            files are expected to be in the fixtures dir, under descriptor_tests/github/{name}.json
            and descriptor_tests/github/{name}.header, respectively.
        """
        self._page_name = page_name
        fixtures_path = os.path.join(
            os.environ["TK_TEST_FIXTURES"], "descriptor_tests", "github"
        )

        # get the response data from {pagename}.json file in the fixtures dir
        response_path = os.path.join(fixtures_path, page_name + ".json")
        with open(response_path) as response_file:
            self.resp_data = response_file.read()

        # get the headers from {pagename}.header file in the fixtures dir and
        # build a dictionary matching the expected headers from urllib
        header_path = os.path.join(fixtures_path, page_name + ".header")
        with open(header_path) as headers_file:
            # parse the status line
            status_line = headers_file.readline().split(" ")
            status_code = int(status_line[1])
            status_message = " ".join(status_line[2:])
            # parse the rest of the headers
            headers = dict()
            # grab key/value pairs out of headers from curl and build a dict like urllib does
            # explain the regex better
            header_line_regex = r"(?P<key>[a-zA-Z\-]+): (?P<value>.+)"
            for line in headers_file:
                m = re.match(header_line_regex, line)
                if m:
                    # keys will be all-lowercase
                    headers[m.group("key").lower()] = m.group("value")

        self.code = status_code
        self.msg = status_message
        self.headers = headers

    def close(self):
        """
        This method needs to be defined starting with Python 3.9 to prevent a
        warning message:
          [warning]Exception ignored in: <function _TemporaryFileCloser.__del__ at 0x10be9f310>
        """
        pass

    def read(self):
        """
        Return the body of the page, mimicking the response object's behavior.
        """
        return self.resp_data

    def readline(self):
        """
        This method is never called, but must exist for Exception instantiation.
        """
        pass

    def getcode(self):
        """
        Return the page code, mimicking the response object's behavior.
        """
        return self.code

    def get_exception(self):
        """
        If the page has a non-200 code, generate a HTTPError similar to the one that
        urllib.urlopen() would normally throw.
        """
        if self.code != 200:
            return urllib.error.HTTPError(
                self._page_name, self.code, self.msg, self.headers, self
            )
        return None


class GithubIODescriptorTestBase(ShotgunTestBase):
    """
    Base class for testing the Github IODescriptor that provides a convenience method
    for generating a Descriptor, and default values for that descriptor for testing.
    """

    def setUp(self):
        pass
    def _create_desc(
        self, location=None, resolve_latest=False, desc_type=Descriptor.CONFIG
    ):
        """
        Helper method around create_descriptor
        """
        if location is None:
            location = self.default_location_dict
        return sgtk.descriptor.create_descriptor(
            self.mockgun,
            desc_type,
            location,
            bundle_cache_root_override=self.bundle_cache,
            resolve_latest=resolve_latest,
        )


class TestGithubIODescriptorWithRemoteAccess(GithubIODescriptorTestBase):
    """
    Test the GithubIODescriptor with has_remote_access always returning True.
    """

    def setUp(self):
        pass
    def tearDown(self):
        pass
    def test_construction(self):
        pass
    def test_get_latest_release(self):
        pass
    def test_get_latest_release_private_repository_no_env_var(self):
        pass
    def test_get_latest_release_private_repository_with_env_var(self):
        pass
    def test_get_release_failure(self):
        pass
    def test_get_constraint_release(self):
        pass
    def test_bundle_cache_path(self):
        pass
    def test_download_local(self):
        pass
class TestGithubIODescriptorWithoutRemoteAccess(GithubIODescriptorTestBase):
    """
    Test the GithubIODescriptor with has_remote_access always returning False.
    """

    def setUp(self):
        pass
    def tearDown(self):
        pass
    def test_get_latest_cached_release(self):
        pass
    def test_get_constraint_cached_release(self):
        pass
class TestGithubIODescriptorRemoteAccessCheck(GithubIODescriptorTestBase):
    """
    Test the remote aspect check functionality of GithubIODescriptor.
    """

    def test_has_remote_access(self):
        pass
    def test_github_api_proxied(self):
        pass
