# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Encapsulates basic yaml commands to tailor specific Toolkit needs.
One such need is to override the default constructor for the
yaml.resolver.BaseResolver.DEFAULT_SCALAR_TAG tag to encode strings
as 'utf8' instead of the default 'ascii' to allow for non-ascii
characters in environment configuration and bundle manifest yaml files.
"""
import sys

from tank_vendor import yaml
from tank_vendor import ruamel_yaml


def construct_yaml_str_as_utf8(loader, node):
    """
    Defines how to convert strings from yaml to Python.
    Overrides default behavior of encoding with ascii
    to encode with utf-8 instead.

    :param loader: yaml Loader instance being used to
                   read the input stream
    :param node: yaml Node containing data to be converted
    :returns: utf-8 encoded str or unicode
    """
    value = loader.construct_scalar(node)
    if sys.version_info[0] == 3:
        return value
    try:
        return value.encode("utf-8")
    except UnicodeEncodeError:
        return value

# Set the utf-8 constructor as the default scalar
# constructor in the yaml module
yaml.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_SCALAR_TAG,
    construct_yaml_str_as_utf8
)

# Set the utf-8 constructor as the default scalar
# constructor in the ruamel_yaml module
ruamel_yaml.add_constructor(
    ruamel_yaml.resolver.BaseResolver.DEFAULT_SCALAR_TAG,
    construct_yaml_str_as_utf8
)


def yaml_load(stream):
    """
    Yaml load command that parses the given stream and returns
    a Python object constructed from for the first document in
    the stream. If there are no documents in the stream, it
    returns None.

    :param stream: Input stream to parse yaml data from
    :returns: Data parsed from stream as a dict
    """
    return yaml.load(stream)


def yaml_load_preserve(stream):
    """
    In addition to the functionality provided by yaml_load,
    the Python object returned from this command also holds
    the additional contextual metadata required by the YAML
    parser to maintain the lexical integrity of the content
    Utilizes the ruamel_yaml library.

    :param stream: Input stream to parse yaml data from
    :returns: Data based from input stream as a dict
    """
    return ruamel_yaml.load(stream, ruamel_yaml.RoundTripLoader)


def yaml_dump(data, stream=None):
    """
    Yaml command to serialize the given Python object into
    the stream. If stream is None, it returns the produced
    stream.

    :param data: Python dict to serialize
    :param stream: (optional) Stream handle to write the
                   serialized python object to.
    :returns: serialized Python object or None
    """
    return yaml.dump(data, stream)


def yaml_safe_dump(data, stream=None):
    """
    Yaml command to serialize the given Python object into
    the stream. If stream is None, it returns the produced
    stream. The safe dump produces only standard yaml tags
    and cannont represent an arbitrary Python object.

    :param data: Python dict to serialize
    :param stream: (optional) Stream handle to write the
                   serialized python object to.
    :returns: serialized Python object or None
    """
    return yaml.safe_dump(data, stream)


def yaml_dump_preserve(data, stream=None):
    """
    In addition to the functionality provided by yaml_dump,
    this command also preserves the formatting found in the
    original stream, including comments. Note that safe_dump
    is not needed when using the roundtrip dumper, it will
    adopt a 'safe' behaviour by default. Utilizes the
    ruamel_yaml library.

    :param data: Python dict to serialize as YAML
    :param stream: (optional) Stream handle to write
                   the serialized Python object to.
    :returns: Serialized Python object or None
    """
    return ruamel_yaml.dump(
        data, stream,
        default_flow_style=False,
        Dumper=ruamel_yaml.RoundTripDumper,
    )
