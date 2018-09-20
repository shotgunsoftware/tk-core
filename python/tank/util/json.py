# Copyright (c) 2018 Shotgun Software Inc.
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Utility methods for unserializing JSON documents.
"""

# We need to add this to the file or the import json will reimport this
# module instead of importing the global json module.
from __future__ import absolute_import

import json


def _convert_unicode_keys_to_string(input_value):
    """
    Converts any :class:`unicode` instances in the input value into a utf-8
    encoded :class`str` instance.

    :param input_value: Value to convert. Can be a scalar, list or dictionary.

    :returns: A value with utf-8 encoded :class:`str` instances.
    """

    if isinstance(input_value, unicode):
        return input_value.encode("utf8")

    if isinstance(input_value, list):
        return [_convert_unicode_keys_to_string(item) for item in input_value]

    if isinstance(input_value, dict):
        return dict(
            (_convert_unicode_keys_to_string(k), _convert_unicode_keys_to_string(v))
            for k, v in input_value.iteritems()
        )

    return input_value


# This is the Python 2.6 signature. 2.7 has an extra object_hook_pairs argument.
def load(
    fp, encoding=None, cls=None, object_hook=None, parse_float=None,
    parse_int=None, parse_constant=None, **kw
):
    """
    Deserialize ``fp`` (a ``.read()``-supporting file-like object containing
    a JSON document) to a Python object.

    This method is a simple thin wrapper around :func:`json.load` that
    ensures unserialized strings are utf-8 encoded :class:`str` objects.

    See the documentation for :func:`json.load` to learn more about this method.
    """
    loaded_value = json.load(
        fp, encoding, cls, object_hook, parse_float,
        parse_int, parse_constant, **kw
    )

    return _convert_unicode_keys_to_string(loaded_value)


# This is the Python 2.6 signature. 2.7 has an extra object_hook_pairs argument.
def loads(
    s, encoding=None, cls=None, object_hook=None, parse_float=None,
    parse_int=None, parse_constant=None, **kw
):
    """
    Deserialize ``s`` (a ``str`` or ``unicode`` instance containing a JSON
    document) to a Python object.

    This method is a simple thin wrapper around :func:`json.loads` that
    ensures unserialized strings are utf-8 encoded :class:`str` objects.

    See the documentation for :func:`json.loads` to learn more about this method.
    """
    loaded_value = json.loads(
        s, encoding, cls, object_hook, parse_float,
        parse_int, parse_constant, **kw
    )

    return _convert_unicode_keys_to_string(loaded_value)
