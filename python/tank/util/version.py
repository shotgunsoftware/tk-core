# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.
import contextlib
import warnings

from tank_vendor.packaging.version import parse as version_parse

from .. import LogManager
from ..errors import TankError
from . import sgre as re

logger = LogManager.get_logger(__name__)
GITHUB_HASH_RE = re.compile("^[0-9a-fA-F]{7,40}$")

# Normalize non-standard version formats
# into PEP 440–compliant forms ("1.2.3") to ensure compatibility with
# Python’s version parsing utilities (e.g., packaging.version.parse).
# Reference: https://peps.python.org/pep-0440/
_VERSION_PATTERNS = [
    (  # Extract version from software names: "Software Name 21.0" -> "21.0"
        re.compile(r"^[a-zA-Z\s]+(\d+(?:\.\d+)*)(?:\s|$)"),
        r"\1",
    ),
    (  # Dot-v format: "6.3v6" -> "6.3.6"
        re.compile(r"^(\d+)\.(\d+)v(\d+)$"),
        r"\1.\2.\3",
    ),
    (  # Simple v format: "2019v0.1" -> "2019.0.1"
        re.compile(r"^(\d+)v(\d+(?:\.\d+)*)$"),
        r"\1.\2",
    ),
    (  # Service pack with/without dot: "2017.2sp1" or "2017.2.sp1" -> "2017.2.post1"
        re.compile(r"^(\d+(?:\.\d+)*)\.?(sp|hotfix|hf)(\d+)$"),
        r"\1.post\3",
    ),
]


def is_version_head(version):
    """
    Returns if the specified version is HEAD or MASTER. The comparison is case insensitive.

    :param version: Version to test.

    :returns: True if version is HEAD or MASTER, false otherwise.
    """
    return version.lower() in ["head", "master"]


def _is_git_commit(version):
    """
    Returns if the version looks like a git commit id.

    :param version: Version to test.

    :returns: True if the version is a commit id, false otherwise.
    """
    return GITHUB_HASH_RE.match(version) is not None


def is_version_newer(a, b):
    """
    Is the version string ``a`` newer than ``b``?

    If one of the version is `master`, `head`, or formatted like a git commit sha,
    it is considered more recent than the other version.

    :raises TankError: Raised if the two versions are different git commit shas, as
        they can't be compared.

    :returns: ``True`` if ``a`` is newer than ``b`` but not equal, ``False`` otherwise.
    """
    return _compare_versions(a, b)


def is_version_older(a, b):
    """
    Is the version string ``a`` older than ``b``?

    If one of the version is `master`, `head`, or formatted like a git commit sha,
    it is considered more recent than the other version.

    :raises TankError: Raised if the two versions are different git commit shas, as
        they can't be compared.

    :returns: ``True`` if ``a`` is older than ``b`` but not equal, ``False`` otherwise.
    """
    return _compare_versions(b, a)


def is_version_newer_or_equal(a, b):
    """
    Is the version string ``a`` newer than or equal to ``b``?

    If one of the version is `master`, `head`, or formatted like a git commit sha,
    it is considered more recent than the other version.

    :raises TankError: Raised if the two versions are different git commit shas, as
        they can't be compared.

    :returns: ``True`` if ``a`` is newer than or equal to ``b``, ``False`` otherwise.
    """
    return is_version_older(a, b) is False


def is_version_older_or_equal(a, b):
    """
    Is the version string ``a`` older than or equal to ``b``?

    If one of the version is `master`, `head`, or formatted like a git commit sha,
    it is considered more recent than the other version.

    :raises TankError: Raised if the two versions are different git commit shas, as
        they can't be compared.

    :returns: ``True`` if ``a`` is older than or equal to ``b``, ``False`` otherwise.
    """
    return is_version_newer(a, b) is False


def is_version_number(version):
    r"""
    Tests whether the given string is a properly formed
    version number (ex: v1.2.3). The test is made using
    the pattern r"v\d+.\d+.\d+$"

    :param str version: The version string to test.

    :rtype: bool
    """
    match = re.match(r"v\d+.\d+.\d+$", version)

    if match:
        return True
    else:
        return False


@contextlib.contextmanager
def suppress_known_deprecation():
    """
    Imported function from setuptools.distutils module
    """
    with warnings.catch_warnings(record=True) as ctx:
        warnings.filterwarnings(
            action="default",
            category=DeprecationWarning,
            message="distutils Version classes are deprecated.",
        )
        yield ctx


def normalize_version_format(version: str) -> str:
    """
    Normalize version strings by applying common format transformations.

    This function exists because packaging.version.parse() follows PEP 440
    and cannot handle non-standard version formats like "v1.2.3" or "6.3v6",
    which are commonly found in various software tools and DCCs but don't
    conform to the PEP 440 specification.

    Transformations applied:
    - Extract version numbers from software names: "Software Name 21.0" -> "21.0"
    - Convert dot-v format: "6.3v6" -> "6.3.6"
    - Convert simple v format: "2019v0.1" -> "2019.0.1"
    - Convert service pack formats: "2017.2sp1" -> "2017.2.post1", "2017.2.sp1" -> "2017.2.post1"

    :param str version: Version string to normalize
    :return str: Normalized version string compatible with PEP 440
    """

    for compiled_pattern, replacement in _VERSION_PATTERNS:
        version = compiled_pattern.sub(replacement, version)

    return version


def _compare_versions(a, b):
    """
    Tests if version a is newer than version b.

    :param str a: The first version string to compare.
    :param str b: The second version string to compare.

    :rtype: bool
    """
    if b in [None, "Undefined"]:
        # a is always newer than None or `Undefined`
        return True

    if _is_git_commit(a) and not _is_git_commit(b):
        return True
    elif _is_git_commit(b) and not _is_git_commit(a):
        return False
    elif _is_git_commit(a) and _is_git_commit(b):
        if a.lower() == b.lower():
            return False
        else:
            raise TankError("Can't compare two git commits lexicographically.")

    if is_version_head(a):
        # our version is latest
        return True

    if is_version_head(b):
        # comparing against HEAD - our version is always old
        return False

    a = normalize_version_format(a)
    b = normalize_version_format(b)

    # Use packaging.version (either system or vendored)
    # This is now guaranteed to be available
    version_a = version_parse(a)
    version_b = version_parse(b)

    return version_a > version_b
