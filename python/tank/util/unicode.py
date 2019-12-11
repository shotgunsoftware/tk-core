# Copyright (c) 2019 Shotgun Software Inc.
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Utility methods for filtering dictionaries
"""

import six

def ensure_contains_str(input_value):
    """
    Converts any :class:`unicode` instances in the input value into a utf-8
    encoded :class`str` instance.

    :param input_value: Value to convert. Can be a scalar, list or dictionary.

    :returns: A value with utf-8 encoded :class:`str` instances.
    """
    if isinstance(input_value, (six.text_type, six.binary_type)):
        return six.ensure_str(input_value)

    if isinstance(input_value, list):
        return [ensure_contains_str(item) for item in input_value]

    if isinstance(input_value, dict):
        return dict(
            (ensure_contains_str(k), ensure_contains_str(v))
            for k, v in input_value.items()
        )

    return input_value