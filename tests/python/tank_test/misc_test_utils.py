# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Miscellaneous utility methods
"""

import os
import platform


def format_value(num, suffix='B'):
    """
    Formats a possibly large value into a more readable
    value. e.g.: 4.6GB instead of 4592672954

    Reference: https://stackoverflow.com/a/1094933/710183

    :param num: An integer representing a byte count
    :param suffix: A string of a suffix to be appended to the returned value (e.g.: KB, KiB)
    :return: A human readable string of a possible large value
    """
    for unit in ['','K','M','G','T','P','E','Z']:
        if abs(num) < 1024.0:
            return "%6.1f %s%s" % (num, unit, suffix)
        num /= 1024.0

    return "%6.1f %s%s" % (num, 'Yi', suffix)


def get_size(start_path='.'):
    """
    Returns the size of the specified element, recursively calculating
    its size if the specified element is a folder.

    Reference: https://stackoverflow.com/a/16465439/710183

    :param start_path:
    :return: An integer size in bytes
    """
    if os.path.isdir(start_path):
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(start_path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                # Skip if entry is a link
                if not os.path.islink(fp):
                    total_size += os.path.getsize(fp)
    else:
        total_size = os.path.getsize(start_path)

    return total_size


def creation_date(path_to_file):
    """
    Try to get the date that a file was created, falling back to when it was
    last modified if that isn't possible.

    Reference: https://stackoverflow.com/a/39501288/710183

    :param path_to_file: A string of a path to a file or folder
    :return: An integer size in bytes
    """
    if platform.system() == 'Windows':
        return os.path.getctime(path_to_file)
    else:
        stat = os.stat(path_to_file)
        try:
            return stat.st_birthtime
        except AttributeError:
            # We're probably on Linux. No easy way to get creation dates here,
            # so we'll settle for when its content was last modified.
            return stat.st_mtime