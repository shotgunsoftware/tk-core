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
    pickled_data = cPickle.dumps(data, protocol=0)
    encoded_data = six.ensure_str(pickled_data)
    os.environ[key] = encoded_data


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
    envvar_contents = six.ensure_binary(os.environ[key])
    return cPickle.loads(envvar_contents)
