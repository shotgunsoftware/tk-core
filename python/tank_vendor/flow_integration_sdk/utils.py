# -
# *****************************************************************************
# Copyright 2026 Autodesk, Inc. All rights reserved.
#
# These coded instructions, statements, and computer programs contain
# unpublished proprietary information written by Autodesk, Inc. and are
# protected by Federal copyright law. They may not be disclosed to third
# parties or copied or duplicated in any form, in whole or in part, without
# the prior written consent of Autodesk, Inc.
# *****************************************************************************
# +

"""
This module contains general utilities that can be leveraged by Flow integrations.
"""

from __future__ import annotations  # needed for python 3.9 support

import logging
import math
import mimetypes
import os
import re
import sys
import time
import traceback
import urllib
from functools import wraps
from typing import Callable

from .exceptions import DirectoryNotCreatedError, FlowError


# Time in seconds above which profiling info should be printed
# Setting the value to None will turn off profiling globally
# Add/Remove the @trace decorator from a function to turn on/off
# profiling for that function
PROFILING_THRESHOLD = None

# Logging level - used for default logger only
LOGGING_LEVEL = "INFO"
# Callback function used to generate logger object
# (If unset, default python logger will be used)
_logger_callback: Callable[[str], logging.Logger] | None = None
# Logging formatter for default python logger
_formatter = logging.Formatter(
    "%(asctime)s - %(module)s.%(funcName)s [%(lineno)d] %(levelname)s: %(message)s"
)


def trace(func):
    """Decorator to track and record execution time of a function."""

    def profile_output(arg0, t0, t1):
        """Output profiling info to log."""
        # List of internal object types we would want to trace
        supported_objects = [
            "FlowAsset",
            "FlowRevision",
            "FlowBlob",
            "FlowComponent",
            "ComponentSpec",
            "FlowProject",
        ]
        msg = "PROFILING: "
        if arg0.__class__ == type:
            # Class function
            msg += f"{arg0.__name__}.{func.__name__}"
        elif arg0.__class__.__name__ in supported_objects:
            # Member function
            msg += f"{arg0.__class__.__name__}.{func.__name__}"
        else:
            # Global function
            msg += func.__name__
        msg += f": {strtime(t0, t1)}"
        # Only display execution times above threshold
        if t1 - t0 >= PROFILING_THRESHOLD:
            print(msg)

    def strtime(t0, t1):
        """Convert a time range into MM:SS.remainder string format."""
        td = t1 - t0
        minutes = math.floor(td / 60)
        seconds = td - (minutes * 60)
        return f"{minutes:02}:{seconds:02}"

    @wraps(func)
    def wrapper(*args, **kwargs):
        # If profiling is turned off, run function normally
        if PROFILING_THRESHOLD is None:
            return func(*args, **kwargs)

        t0 = time.time()
        try:
            result = func(*args, **kwargs)
        except Exception as e:
            raise e
        finally:
            t1 = time.time()
            arg0 = args[0] if args else None
            profile_output(arg0, t0, t1)
        return result

    return wrapper


def get_logger(name: str):
    """Return a logger with the given name.
    The callback set in _logger_callback will be used to generate the logger.
    """
    if _logger_callback is None:
        # Generate default python logger
        logger = logging.getLogger(name)
        if len(logger.handlers) == 0:
            # Initialize stdout handler
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(_formatter)
            logger.addHandler(handler)
            logger.setLevel(LOGGING_LEVEL)
        return logger
    return _logger_callback(name)


def to_regex_safe_wildcard_string(pattern: str) -> str:
    """Convert a wildcard pattern to a regex-safe pattern string.

    This function escapes all regex special characters in the input pattern
    and converts wildcard asterisks (*) to regex wildcards (.*), allowing
    for safe pattern matching where only * acts as a wildcard.

    Args:
        pattern: Input pattern that may contain wildcards (*) and special
                 regex characters that should be treated as literals.

    Returns:
        A regex pattern string where:
        - All regex special characters are escaped (treated as literals)
        - Asterisks (*) are converted to .* (regex wildcard)

    Examples:
        >>> to_regex_safe_wildcard_string("file.txt")
        'file\\\\.txt'
        >>> to_regex_safe_wildcard_string("*.txt")
        '.*\\\\.txt'
        >>> to_regex_safe_wildcard_string("config[v1.0].data")
        'config\\\\[v1\\\\.0\\\\]\\\\.data'
        >>> to_regex_safe_wildcard_string("*_file_*.txt")
        '.*_file_.*\\\\.txt'
    """
    return re.escape(pattern).replace("\\*", ".*")


def ensure_dir(dir_path: str):
    """Ensure that a directory exists by creating it and all needed parent directories

    Args:
        dir_path: Full path to local directory
    """
    logger = get_logger(__name__)

    if not os.path.exists(dir_path):
        # Try to create the directory
        try:
            logger.info(f"Creating directory {dir_path}")
            os.makedirs(dir_path)
        except OSError as exc:
            # Only complain if the directory wasn't created
            if not os.path.exists(dir_path):
                raise DirectoryNotCreatedError(dir_path=dir_path)
            else:
                logger.warning(str(exc))

    if not os.path.isdir(dir_path):
        # This is very unlikely to happen
        raise DirectoryNotCreatedError(dir_path=dir_path)


def cleanpath(path: str, *extra: str) -> str:
    """Return the same path, normalized and using only front slashes.

    Args:
        path: String absolute or relative path.
        *extra: Zero or more string arguments representing extra bits to
                add to input path in given order.

    Returns:
        str: Path that is the product of all input parameters joined.

    Examples:
        >>> cleanpath('c:\\dev\\my_root', 'my_dir', 'my_file.ma')
        'c:/dev/my_root/my_dir/my_file.ma'
        >>> cleanpath('/Users//smith/folder1/file1.txt')
        '/Users/smith/folder1/file1.txt'
        >>> cleanpath('C:/temp/some_dir/', '/some_folder/')
        'C:/temp/some_dir/some_folder'
        >>> cleanpath('/Applications', '/\\some_app')
        '/Applications/some_app'
        >>> cleanpath('D:', 'MIM_Files')
        'D:/MIM_Files'
        >>> cleanpath('D:\\\\', 'MIM_Files')
        'D:/MIM_Files'
        >>> cleanpath('')
        ''
        >>> cleanpath('', 'blah', 'blah')
        'blah/blah'
        >>> cleanpath('/path/to/dir/')
        '/path/to/dir'
        >>> cleanpath('/path/./to/../file.txt')
        '/path/file.txt'
    """
    # Add slash if first argument is a drive
    # (os.path.join will not add one in this case)
    if path.endswith(":"):
        path += "/"
    # Must strip any leading slashes from extra bits
    extras = []
    for ext in extra:
        extras.append(ext.lstrip("/\\"))
    result = os.path.join(path, *extras)
    if not result:
        return ""
    return os.path.normpath(result).replace("\\", "/")


def abspath(basepath: str, relpath: str) -> str:
    """Return absolute path of a base path plus a path relative to it.

    Args:
        basepath: Absolute file path.
        relpath: Input path that is relative to provided base path.

    Examples:
        >>> abspath('c:/temp', 'dir/myfile.txt')
        'C:/temp/dir/myfile.txt'
        >>> abspath('', 'c:/temp/dir/myfile.txt')
        'C:/temp/dir/myfile.txt'
        >>> abspath('c:/some_folder', '../temp/dir/other_dir')
        'C:/temp/dir/other_dir'
        >>> abspath('c:/temp/dir2/folder', '../../dir/myfile.txt')
        'C:/temp/dir/myfile.txt'
    """
    return cleanpath(os.path.realpath(os.path.join(basepath, relpath)))


def relpath(basepath: str, targetpath: str) -> str:
    r"""Return the target path as a relative path to base path.
    Paths *must* be on same drive.

    Args:
        basepath: Absolute directory path that return path will be relative to.
        targetpath: Absolute path whose relative value will be returned.

    Examples:
        >>> relpath('c:/temp', 'c:/temp/dir/myfile.txt')
        'dir/myfile.txt'
        >>> relpath('c:/some_folder', 'c:/temp/dir/other_dir')
        '../temp/dir/other_dir'
        >>> relpath('c:/temp/dir2/folder', 'C:/temp/dir/myfile.txt')
        '../../dir/myfile.txt'
        >>> relpath(r'c:/temp\dir2/folder', r'C:/temp\dir\myfile.txt')  # noqa: W605
        '../../dir/myfile.txt'
    """
    return cleanpath(os.path.relpath(targetpath, basepath))


def is_sub_directory(root_path: str, full_path: str) -> bool:
    """Return True if the full path provided begins with the root path.

    Args:
        root_path: A root directory.
        full_path: A full path to a directory or file.

    Examples:
        >>> is_sub_directory('c:/temp', 'C:/temp/dir/myfile.txt')
        True
        >>> is_sub_directory('', 'c:/temp/dir/myfile.txt')
        False
        >>> is_sub_directory('c:/some_folder', 'c:/temp/dir/other_dir')
        False
        >>> is_sub_directory('c:/temp/dir2/folder', '')
        False
    """
    if not root_path or not full_path:
        return False
    abs_root = abspath("", root_path)
    abs_full = abspath("", full_path)
    try:
        # Use commonpath to properly check if full_path is under root_path
        # If commonpath of both equals the root, then full is under root
        return os.path.commonpath([abs_root]) == os.path.commonpath(
            [abs_root, abs_full]
        )
    except ValueError:
        # Raised when paths are on different drives (Windows) or one is relative
        return False


def mimetype(ext: str):
    """Return the mimetype of the given file extension.

    Args:
        ext: A file extension which may or may not be preceded by a '.'.
             A file path is also accepted.

    Returns:
        String mimetype, or blank string if extension is not recognized.

    Examples:
        >>> mimetype('jpg')
        'image/jpeg'
        >>> mimetype('.jpeg')
        'image/jpeg'
        >>> mimetype('c:/temp/my_image.jpg')
        'image/jpeg'
        >>> mimetype('.not_a_recognized_file_type')
        ''
    """
    if "." in ext and not ext.startswith("."):
        ext = os.path.splitext(ext)[1]
    else:
        ext = "." + ext.strip(".")
    try:
        return mimetypes.types_map[ext]
    except KeyError:
        return ""


@trace
def download_file(url, local_filename):
    """Download a file from the passed in URL and save it in the specified location.
    Create any folders as necessary.

    Args:
        url: The remote URL to download
        local_filename: The full path to the local destination file

    Raises:
        DirctoryNotCreatedError: If we couldn't create the folder for the download
    """
    # Check if path exists, and create it if it doesn't
    local_dir = os.path.dirname(local_filename)

    # This can raise an exception
    ensure_dir(local_dir)

    try:
        with urllib.request.urlopen(url) as r:  # nosec B210
            try:
                with open(local_filename, "wb") as f:
                    while True:
                        chunk = r.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
            except Exception as exc:  # pylint: disable=broad-except
                msg = f"Failed to write to local file: {local_filename}"
                traceback.print_exc()
                raise FlowError(msg) from exc
    except urllib.error.HTTPError as exc:
        msg = f'HTTP error occurred while accessing url "{url}". {exc}'
        traceback.print_exc()
        raise FlowError(msg) from exc
    except urllib.error.URLError as exc:
        msg = f'Request to get url "{url}" failed. {exc}'
        traceback.print_exc()
        raise FlowError(msg) from exc
