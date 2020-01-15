# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import mock
from mock import patch
import os
from sgtk.util import sgre as re
from tank_vendor.six.moves import urllib

import sgtk
from sgtk.descriptor import Descriptor
from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import ShotgunTestBase

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
        """
        Sets up the next test's environment.
        """
        ShotgunTestBase.setUp(self)

        self.bundle_cache = os.path.join(self.project_root, "bundle_cache")
        self.default_location_dict = {
            "type": "github_release",
            "organization": "shotgunsoftware",
            "repository": "tk-core",
            "version": "v1.2.1",
        }
        super(GithubIODescriptorTestBase, self).setUp()

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
        # patch has_remote_access to always return True
        self._has_remote_access_mock = patch(_TESTED_CLASS + ".has_remote_access")
        self._has_remote_access_mock.start()
        self._has_remote_access_mock.return_value = True
        super(TestGithubIODescriptorWithRemoteAccess, self).setUp()

    def tearDown(self):
        self._has_remote_access_mock.stop()
        super(TestGithubIODescriptorWithRemoteAccess, self).tearDown()

    def test_construction(self):
        """
        Test that the Descriptor construction is successful, and correctly sets
        the version and system name.
        """
        desc = self._create_desc()
        self.assertEqual(
            desc.get_system_name(), self.default_location_dict["repository"]
        )
        self.assertEqual(desc.get_version(), self.default_location_dict["version"])

    def test_get_latest_release(self):
        """
        Test that the get_latest_version() method correctly finds the latest release,
        and loads the correct url from the Github API.
        """
        with patch(_TESTED_MODULE + ".urllib.request.urlopen") as urlopen_mock:
            # Make sure that the correct URL is requested, and the response is correctly
            # parsed for the latest tag name.
            urlopen_mock.return_value = MockResponse("releases_latest")
            desc = self._create_desc(self.default_location_dict, True)
            desc2 = desc.find_latest_version()
            # Make sure the right URL was hit.
            target_url = "https://api.github.com/repos/{o}/{r}/releases/latest"
            target_url = target_url.format(
                o=self.default_location_dict["organization"],
                r=self.default_location_dict["repository"],
            )
            urlopen_mock.assert_called_with(target_url)
            self.assertEqual(desc2.version, "v1.2.3")

    def test_get_release_failure(self):
        """
        Test that the get_latest_version() method correctly responds as expected
        to a broken network connection and a 404 or 500 error from the Github API.
        """
        with patch(_TESTED_MODULE + ".urllib.request.urlopen") as urlopen_mock:
            desc = self._create_desc()

            # URLError from urllib should raise TankDescriptorError.
            urlopen_mock.side_effect = urllib.error.URLError("Some Exception")
            with self.assertRaises(sgtk.descriptor.TankDescriptorError):
                desc.find_latest_version()

            # A non 200, non 404 response from Github should also raise a TankDescriptorError.
            urlopen_mock.side_effect = MockResponse("repo_root_500").get_exception()
            with self.assertRaises(sgtk.descriptor.TankDescriptorError):
                desc.find_latest_version()

            # A 404 response from Github should give us back the current Descriptor.
            urlopen_mock.side_effect = MockResponse("repo_root_404").get_exception()
            self.assertEqual(desc.find_latest_version(), desc)

    def test_get_constraint_release(self):
        """
        Test that the get_latest_version() method correctly finds the latest acceptable
        release when a contstraint pattern is provided, and that it loads the correct
        url(s) from the Github API.
        """
        desc = self._create_desc()
        # Build the urls that should be hit for page 1 and 2
        target_url_page_1 = "https://api.github.com/repos/{o}/{r}/releases"
        target_url_page_1 = target_url_page_1.format(
            o=self.default_location_dict["organization"],
            r=self.default_location_dict["repository"],
        )
        # The second page is retrieved from the URL specified in the headers from the first response
        # this value should match the rel="next" link from releases.header
        target_url_page_2 = (
            "https://api.github.com/repositories/174021161/releases?page=2"
        )

        # Test with two pages of results, but the desired item on first page.
        # We should not request the second page.
        with patch(_TESTED_MODULE + ".urllib.request.urlopen") as urlopen_mock:
            urlopen_mock.side_effect = [
                MockResponse("releases"),
                MockResponse("releases_page_2"),
            ]
            desc2 = desc.find_latest_version(constraint_pattern="v1.2.x")
            urlopen_mock.assert_called_with(target_url_page_1)
            self.assertEqual(urlopen_mock.call_count, 1)
            self.assertEqual(desc2.get_version(), "v1.2.30")

        # Now test again, but the desired item will be on the second page, make sure
        # we request it.
        with patch(_TESTED_MODULE + ".urllib.request.urlopen") as urlopen_mock:
            urlopen_mock.side_effect = [
                MockResponse("releases"),
                MockResponse("releases_page_2"),
            ]
            desc2 = desc.find_latest_version(constraint_pattern="v1.1.x")
            calls = [mock.call(target_url_page_1), mock.call(target_url_page_2)]
            urlopen_mock.assert_has_calls(calls)
            self.assertEqual(urlopen_mock.call_count, 2)
            self.assertEqual(desc2.get_version(), "v1.1.1")

    def test_bundle_cache_path(self):
        """
        Test that the bund_cache_path is built as expected.
        """
        desc = self._create_desc()
        expected_bundle_cache_path = os.path.join(
            self.bundle_cache,
            "github",
            self.default_location_dict["organization"],
            self.default_location_dict["repository"],
            self.default_location_dict["version"],
        )
        found_bundle_cache_path = desc._io_descriptor._get_bundle_cache_path(
            self.bundle_cache
        )
        self.assertEqual(found_bundle_cache_path, expected_bundle_cache_path)

    def test_download_local(self):
        """
        Test that download_local downloads from the correct URL, and handles an Exception as expected.
        """
        desc = self._create_desc()
        expected_url = "https://github.com/{o}/{r}/archive/{v}.zip"
        expected_url = expected_url.format(
            o=self.default_location_dict["organization"],
            r=self.default_location_dict["repository"],
            v=self.default_location_dict["version"],
        )

        with patch(
            "tank.util.shotgun.download.download_and_unpack_url"
        ) as download_and_unpack_url_mock:
            # Raise an exception first and ensure it's caught and a TankDescriptorError is raised.
            download_and_unpack_url_mock.side_effect = sgtk.TankError()
            with self.assertRaises(sgtk.descriptor.TankDescriptorError):
                desc.download_local()

        with patch(
            "tank.util.shotgun.download.download_and_unpack_url"
        ) as download_and_unpack_url_mock:
            # Now reset and let the download "succeed" and ensure the correct calls were made, and
            # the expected arguments were passed.
            desc.download_local()
            calls = download_and_unpack_url_mock.call_args_list
            self.assertEqual(len(calls), 1)
            # calls will be a tuple of call objects, which can be indexed into to
            # get tuples of (args, kwargs).
            # first positional arg of first call
            self.assertEqual(calls[0][0][0], self.mockgun)
            # second positional arg of first call
            self.assertEqual(calls[0][0][1], expected_url)


class TestGithubIODescriptorWithoutRemoteAccess(GithubIODescriptorTestBase):
    """
    Test the GithubIODescriptor with has_remote_access always returning False.
    """

    def setUp(self):
        # patch has_remote_access to always return True
        self._has_remote_access_mock = patch(_TESTED_CLASS + ".has_remote_access")
        self._has_remote_access_mock.start()
        self._has_remote_access_mock.return_value = False
        super(TestGithubIODescriptorWithoutRemoteAccess, self).setUp()

    def tearDown(self):
        self._has_remote_access_mock.stop()
        super(TestGithubIODescriptorWithoutRemoteAccess, self).tearDown()

    def test_get_latest_cached_release(self):
        """
        Test that the get_latest_cached_version() method correctly finds the latest release
        on disk.
        """
        with patch(
            _TESTED_CLASS + "._get_locally_cached_versions"
        ) as cached_versions_mock:
            desc = self._create_desc()

            # Ensure that the latest cached version is returned if present.
            cached_versions_dict = {"v3.2.1": "/fake/path", "v4.2.1": "/faker/path"}
            cached_versions_mock.return_value = cached_versions_dict
            desc2 = desc.find_latest_cached_version()
            self.assertEqual(desc2.get_version(), "v4.2.1")

            # If no cached versions are present, None should be returned.
            cached_versions_mock.return_value = dict()
            self.assertEqual(desc.find_latest_cached_version(), None)

    def test_get_constraint_cached_release(self):
        """
        Test that the get_latest_cached_version() method correctly finds the latest
        acceptable release on disk when a constraint pattern is provided.
        """
        with patch(
            _TESTED_CLASS + "._get_locally_cached_versions"
        ) as cached_versions_mock:
            desc = self._create_desc()

            # Ensure that the latest cached version that matches the provided constraint pattern
            # is returned (and not a newer one that doesn't match the constraint pattern.)
            cached_versions_dict = {"v3.2.1": "/fake/path", "v4.2.1": "/faker/path"}
            cached_versions_mock.return_value = cached_versions_dict
            desc2 = desc.find_latest_cached_version(constraint_pattern="v3.x.x")
            self.assertEqual(desc2.get_version(), "v3.2.1")

            # If no cached versions match the provided constraint pattern, None should be returned.
            desc2 = desc.find_latest_cached_version(constraint_pattern="v5.x.x")
            self.assertEqual(desc2, None)


class TestGithubIODescriptorRemoteAccessCheck(GithubIODescriptorTestBase):
    """
    Test the remote aspect check functionality of GithubIODescriptor.
    """

    def test_has_remote_access(self):
        """
        Test that the has_remote_access() method returns as expected when able and unable to
        connect to the Github API, and requests the correct URL.
        """
        desc = self._create_desc()
        target_url = "https://api.github.com/repos/{o}/{r}"
        target_url = target_url.format(
            o=self.default_location_dict["organization"],
            r=self.default_location_dict["repository"],
        )
        with patch(_TESTED_MODULE + ".urllib.request.urlopen") as urlopen_mock:
            # normal good response
            urlopen_mock.return_value = MockResponse("repo_root")
            self.assertEqual(desc.has_remote_access(), True)
            urlopen_mock.assert_called_with(target_url)

            # 404 response
            urlopen_mock.side_effect = MockResponse("repo_root_404").get_exception()
            self.assertEqual(desc.has_remote_access(), False)

            # No internet connection, no response from GH API, etc
            urlopen_mock.side_effect = urllib.error.URLError("Test exception.")
            self.assertEqual(desc.has_remote_access(), False)

    def test_github_api_proxied(self):
        """
        Ensure that urllib calls install a proxy when the shotgun config has a proxy_handler.
        """
        try:
            proxy_handler = urllib.request.ProxyHandler({"http": "127.0.0.1"})
            self.mockgun.config.proxy_handler = proxy_handler
            with patch(_TESTED_MODULE + ".urllib.request.urlopen") as urlopen_mock:
                with patch(
                    _TESTED_MODULE + ".urllib.request.install_opener"
                ) as install_opener_mock:
                    # Test that the proxy is installed for has_remote_access.
                    urlopen_mock.return_value = MockResponse("repo_root")
                    desc = self._create_desc()
                    desc.has_remote_access()
                    # get most recent install_opener call
                    last_call = install_opener_mock.call_args_list[-1]
                    # get the first arg passed
                    opener = last_call[0][0]
                    # Ensure the first handler on the opener is our proxy handler.
                    self.assertEqual(opener.handlers[0], proxy_handler)

                    # Test that the proxy is installed for accessing github API.
                    urlopen_mock.return_value = MockResponse("releases_latest")
                    desc.find_latest_version()
                    # get most recent install_opener call
                    last_call = install_opener_mock.call_args_list[-1]
                    # get the first arg passed
                    opener = last_call[0][0]
                    # Ensure the first handler on the opener is our proxy handler.
                    self.assertEqual(opener.handlers[0], proxy_handler)
        finally:
            # Remove the proxy handler from mockgun config
            self.mockgun.config.proxy_handler = None
