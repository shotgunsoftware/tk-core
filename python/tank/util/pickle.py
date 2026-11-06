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
import pickle

from .. import LogManager
from .unicode import ensure_contains_str

log = LogManager.get_logger(__name__)


# kwargs for pickle.load* and pickle.dump* calls.
LOAD_KWARGS = {"encoding": "bytes"}
# Protocol 0 ensures ASCII encoding, which is required when writing
# a pickle to an environment variable.
DUMP_KWARGS = {"protocol": 0}

# Fix unicode issue when ensuring string values
# https://jira.autodesk.com/browse/SG-6588
FALLBACK_ENCODING = "ISO-8859-1"
FALLBACK_ENCODING_KEY = "_payload_encoding"


def dumps(data):
    """
    Return the pickled representation of ``data`` as a ``str``.

    :param data: The object to pickle and store.
    :returns: A pickled binary of the input object.
    :rtype: str
    """
    try:
        return pickle.dumps(data, **DUMP_KWARGS).decode("utf-8")
    except UnicodeError as e:
        # Fix unicode issue when ensuring string values
        # https://jira.autodesk.com/browse/SG-6588
        if e.encoding == "utf-8" and e.reason in (
            "invalid continuation byte",
            "invalid start byte",
        ):
            encoding = FALLBACK_ENCODING
            if isinstance(data, dict):
                data[FALLBACK_ENCODING_KEY] = encoding
                return pickle.dumps(data, **DUMP_KWARGS).decode(encoding)

        raise


def dump(data, fh):
    """
    Write the pickled representation of ``data`` to a file object.

    This methods wraps the functionality from the :func:`pickle.dump` method.

    :param data: The object to pickle and store.
    :param fh: A file object
    """
    pickle.dump(data, fh, **DUMP_KWARGS)


def loads(data):
    """
    Deserialize a pickled representation of an object from a string or bytes.

    :param data: A pickled representation of an object (str or bytes).
    :return: The unpickled object.
    """
    binary = data
    if isinstance(data, str):
        binary = data.encode("utf-8")
    loads_data = ensure_contains_str(pickle.loads(binary))
    if isinstance(loads_data, dict) and FALLBACK_ENCODING_KEY in loads_data:
        encoding = loads_data[FALLBACK_ENCODING_KEY]
        if isinstance(data, str):
            binary = data.encode(encoding)
        loads_data = ensure_contains_str(pickle.loads(binary, **LOAD_KWARGS))

    return loads_data


def load(fh):
    """
    Read the pickled representation of an object from the open file object
    and return the reconstituted object hierarchy specified therein.

    This method wraps the functionality from the :func:`pickle.load` method so
    unicode strings are always returned as utf8-encode.

    :param fh: A file object
    :returns: The unpickled object.
    :rtype: object
    """
    return ensure_contains_str(pickle.load(fh, **LOAD_KWARGS))


def store_env_var_pickled(key, data):
    """
    Stores the provided data under the environment variable specified.

    .. note::
        This method is part of Toolkit's internal API.

    In Python 3 pickle.dumps() returns a binary object that can't be decoded to
    a string for storage in an environment variable.  To work around this, we
    encode the pickled data to base64, compress the result, and store that.

    :param key: The name of the environment variable to store the data in.
    :param data: The object to pickle and store.
    """
    pickled_data = dumps(data)
    if isinstance(pickled_data, bytes):
        pickled_data = pickled_data.decode("utf-8")
    os.environ[key] = pickled_data


def retrieve_env_var_pickled(key):
    """
    Retrieves and unpacks the pickled data stored in the environment variable
    specified.

    .. note::
        This method is part of Toolkit's internal API.

    In Python 3 pickle.dumps() returns a binary object that can't be decoded to
    a string for storage in an environment variable.  To work around this, we
    encode the pickled data to base64, compress the result, and store that.

    :param key: The name of the environment variable to retrieve data from.
    :returns: The original object that was stored.
    """
    if isinstance(key, str):
        envvar_contents = key.encode("utf-8")

    return loads(envvar_contents)
