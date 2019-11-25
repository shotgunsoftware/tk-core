# Copyright (c) 2019 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os

from .. import LogManager

from tank_vendor.shotgun_api3.lib.six.moves import cPickle
from tank_vendor.shotgun_api3.lib import six

log = LogManager.get_logger(__name__)


def dumps_str(data):
    """
    Generates a pickle string for the provided data.  This wraps cPickle.dumps()
    and produces a str on both Python 2 and 3, while cPickle.dumps() produces
    binary on Python 3 and a str on Python 2.

    :param data: The object to pickle and store.
    :returns: A pickled str of the input object.
    :rtype: str
    """
    # Force pickle protocol 0, since this is a non-binary pickle protocol.
    # See https://docs.python.org/2/library/pickle.html#pickle.HIGHEST_PROTOCOL
    # Decode the result to a str before returning.
    return six.ensure_str(cPickle.dumps(data, protocol=0))


def store_env_var_pickled(key, data):
    """
    Stores the provided data under the environment variable specified.

    In Python 3 pickle.dumps() returns a binary object that can't be decoded to
    a string for storage in an environment variable.  To work around this, we
    encode the pickled data to base64, compress the result, and store that.

    :param key: The name of the environment variable to store the data in.
    :param data: The object to pickle and store.
    """
    # Force pickle protocol 0, since this is a non-binary pickle protocol.
    # See https://docs.python.org/2/library/pickle.html#pickle.HIGHEST_PROTOCOL
    if six.PY2:
        os.environ[key] = cPickle.dumps(data)
    else:
        os.environb[six.ensure_binary(key)] = cPickle.dumps(data, protocol=0)


def _to_simple_data_types(data):
    if isinstance(data, six.binary_type):
        return six.ensure_str(data)
    elif isinstance(data, six.text_type):
        return six.ensure_str(data)
    elif isinstance(data, list):
        return [_to_simple_data_types(item) for item in data]
    elif isinstance(data, dict):
        return dict([
            (_to_simple_data_types(key), _to_simple_data_types(value))
            for key, value in data.items()
        ])
    else:
        return data


def retrieve_env_var_pickled(key):
    """
    Retrieves and unpacks the pickled data stored in the environment variable
    specified.

    In Python 3 pickle.dumps() returns a binary object that can't be decoded to
    a string for storage in an environment variable.  To work around this, we
    encode the pickled data to base64, compress the result, and store that.

    :param key: The name of the environment variable to retrieve data from.
    :returns: The original object that was stored.
    """
    if six.PY2:
        return _to_simple_data_types(cPickle.loads(six.ensure_binary(os.environ[key])))
    else:
        key = six.ensure_binary(key)
        return _to_simple_data_types(
            cPickle.loads(os.environb[key], encoding="bytes")
        )
    