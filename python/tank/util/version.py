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
import sys
import warnings

version_parse = None
try:
    import packaging.version

    version_parse = packaging.version.parse
except ModuleNotFoundError:
    try:
        # Try importing from setuptools.
        # If it fails, then we can't do much at the moment
        # The DCC should have either setuptools or packaging installed.
        from setuptools._distutils.version import LooseVersion

        version_parse = LooseVersion
    except ModuleNotFoundError:
        try:
            from distutils.version import LooseVersion

            version_parse = LooseVersion
        except ModuleNotFoundError:
            version_parse = str

from .. import LogManager
from ..errors import TankError
from . import sgre as re

logger = LogManager.get_logger(__name__)
GITHUB_HASH_RE = re.compile("^[0-9a-fA-F]{7,40}$")

# Normalize non-standard version formats (e.g., "v1.2.3", "6.3v6", "1.2-3")
# into PEP 440–compliant forms ("1.2.3") to ensure compatibility with
# Python’s version parsing utilities (e.g., packaging.version.parse).
# Reference: https://peps.python.org/pep-0440/
_VERSION_PATTERNS = [
    (re.compile(r"^v(\d+)\.(\d+)\.(\d+)$"), r"\1.\2.\3"),  # v prefix: v1.2.3 -> 1.2.3
    (
        re.compile(r"^(\d+)\.(\d+)v(\d+)$"),
        r"\1.\2.\3",
    ),  # v middle format: 6.3v6 -> 6.3.6
    (re.compile(r"^(\d+)\.(\d+)-(\d+)$"), r"\1.\2.\3"),  # Dash format: 1.2-3 -> 1.2.3
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


def _normalize_version_format(version_string):
    """
    Normalize version strings by applying common format transformations.

    This function exists because packaging.version.parse() follows PEP 440
    and cannot handle non-standard version formats like "v1.2.3" or "6.3v6",
    which are commonly found in various software tools and DCCs but don't
    conform to the PEP 440 specification.

    Transformations applied:
    - Strip whitespace and convert to lowercase
    - Remove leading 'v' prefix
    - Convert "v1.2.3" format to "1.2.3"
    - Convert "6.3v6" format to "6.3.6" (middleware version format)
    - Convert "1.2-3" format to "1.2.3" (dash-separated format)

    :param str version_string: Version string to normalize
    :return str: Normalized version string
    """
    # Clean input: strip whitespace, lowercase, remove leading 'v'
    v = version_string.strip().lower().lstrip("v")

    for compiled_pattern, replacement in _VERSION_PATTERNS:
        result = compiled_pattern.sub(replacement, v)
        if result != v:
            return result

    return v


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

    a = _normalize_version_format(a)
    b = _normalize_version_format(b)

    if "packaging" in sys.modules:
        version_a = version_parse(a)
        version_b = version_parse(b)

        return version_a > version_b
    elif version_parse is LooseVersion:
        # Es LooseVersion
        # In Python 3, LooseVersion comparisons between versions where a non-numeric
        # version component is compared to a numeric one fail.  We'll work around this
        # as follows:
        # First, try to use LooseVersion for comparison.  This should work in
        # most cases.
        try:
            with suppress_known_deprecation():
                # Supress `distutils Version classes are deprecated.` for Python 3.10
                version_a = LooseVersion(a).version
                version_b = LooseVersion(b).version

                version_num_a = []
                version_num_b = []
                # taking only the integers of the version to make comparison
                for version in version_a:
                    if isinstance(version, (int)):
                        version_num_a.append(version)
                    elif version == "-":
                        break
                for version in version_b:
                    if isinstance(version, (int)):
                        version_num_b.append(version)
                    elif version == "-":
                        break

                # Comparing equal number versions with with one of them with '-' appended, if a version
                # has '-' appended it's older than the same version with '-' at the end
                if version_num_a == version_num_b:
                    if "-" in a and "-" not in b:
                        return False  # False, version a is older than b
                    elif "-" in b and "-" not in a:
                        return True  # True, version a is older than b
                    else:
                        return LooseVersion(a) > LooseVersion(
                            b
                        )  # If both has '-' compare '-rcx' versions
                else:
                    return LooseVersion(a) > LooseVersion(
                        b
                    )  # If they are different numeric versions
        except TypeError:
            version_expr = re.compile(r"^((?:\d+)(?:\.\d+)*)(.+)$")
            match_a = version_expr.match(a)
            match_b = version_expr.match(b)
            if match_a and match_b:
                # If we could get two numeric versions, generate LooseVersions for
                # them.
                ver_a = LooseVersion(match_a.group(1))
                ver_b = LooseVersion(match_b.group(1))
                if ver_a != ver_b:
                    # If they're not identical, return based on this comparison
                    return ver_a > ver_b
                else:
                    # If the numeric versions do match, do a string comparsion for
                    # the rest.
                    return match_a.group(2) > match_b.group(2)
            elif match_a or match_b:
                # If only one had a numeric version, treat that as the newer version.
                return bool(match_a)
    else:
        # Fallback a comparación de strings
        return a > b
