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
Encapsulates basic yaml commands to tailor specific Toolkit needs. One such
need is to override the u'tag:yaml.org,2002:str' yaml Constructor method for
Loaders used by Toolkit to encode strings as 'utf8' instead of the default
'ascii' to allow for non-ascii characters in environment configuration and
bundle manifest yaml files.
"""

# Imports needed for yaml commands
from tank_vendor import yaml
from tank_vendor import ruamel_yaml

# Imports needed to construct a utf-8 safe yaml Loader
from tank_vendor.yaml.reader import Reader
from tank_vendor.yaml.scanner import Scanner
from tank_vendor.yaml.parser import Parser
from tank_vendor.yaml.composer import Composer
from tank_vendor.yaml.constructor import Constructor
from tank_vendor.yaml.resolver import Resolver

# Imports needed to construct a utf-8 safe ruamel_yaml RoundTripLoader
from tank_vendor.ruamel_yaml.reader import Reader as RYReader
from tank_vendor.ruamel_yaml.scanner import RoundTripScanner
from tank_vendor.ruamel_yaml.parser_ import Parser as RYParser
from tank_vendor.ruamel_yaml.composer import Composer as RYComposer
from tank_vendor.ruamel_yaml.constructor import RoundTripConstructor
from tank_vendor.ruamel_yaml.resolver import Resolver as RYResolver

class Utf8Constructor(Constructor):
    """
    Yaml Constructor class that encodes data
    tagged with u'tag:yaml.org,2002:str' as
    utf-8 instead of ascii
    """
    def construct_yaml_str_utf8(self, node):
        value = self.construct_scalar(node)
        try:
            return value.encode("utf-8")
        except UnicodeEncodeError:
            return value

# Override the the default SafeConstructor.construct_yaml_str
# method for this tag.
Utf8Constructor.add_constructor(
    u'tag:yaml.org,2002:str',
    Utf8Constructor.construct_yaml_str_utf8
)

class Utf8Loader(Reader, Scanner, Parser, Composer, Utf8Constructor, Resolver):
    """
    Yaml Loader class to that utilizes utf-8 encoded strings throughout.
    """
    def __init__(self, stream):
        Reader.__init__(self, stream)
        Scanner.__init__(self)
        Parser.__init__(self)
        Composer.__init__(self)
        Utf8Constructor.__init__(self)
        Resolver.__init__(self)

class Utf8RoundTripConstructor(RoundTripConstructor):
    """
    Yaml RoundTripConstructor class that encodes data
    tagged with u'tag:yaml.org,2002:str' as utf-8
    instead of ascii
    """
    def construct_yaml_str_utf8(self, node):
        value = self.construct_scalar(node)
        if PY3:
            return value
        try:
            return value.encode("utf-8")
        except UnicodeEncodeError:
            return value

# Override the the default SafeConstructor.construct_yaml_str
# method for this tag.
Utf8RoundTripConstructor.add_constructor(
    u'tag:yaml.org,2002:str',
    Utf8RoundTripConstructor.construct_yaml_str_utf8
)

class Utf8RoundTripLoader(
    RYReader, RoundTripScanner, RYParser, RYComposer,
    Utf8RoundTripConstructor, RYResolver
):
    """
    Yaml RoundTripLoader class that encodes data
    tagged with u'tag:yaml.org,2002:str' as utf-8
    instead of ascii. The RoundTripLoader is
    implemented in the ruamel_yaml library, not
    the standard yaml library.
    """
    def __init__(self, stream):
        RYReader.__init__(self, stream)
        RoundTripScanner.__init__(self)
        RYParser.__init__(self)
        RYComposer.__init__(self)
        Utf8RoundTripConstructor.__init__(self)
        RYResolver.__init__(self)

def yaml_load(stream):
    """
    Yaml load command that parses the given stream and returns
    a Python object constructed from for the first document in
    the stream. If there are no documents in the stream, it
    returns None.

    :param stream: Input stream to parse yaml data from
    :returns: Data parsed from stream as a dict
    """
    return yaml.load(stream, Utf8Loader)

def yaml_load_preserve(stream):
    """
    In addition to the functionality provided by yaml_load,
    this command also preserves the original formatting
    of the file, including comments. Utilizes the ruamel_yaml
    library.

    :param stream: Input stream to parse yaml data from
    :returns: Data based from input stream as a dict
    """
    return ruamel_yaml.load(stream, Utf8RoundTripLoader)

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
    original stream, including comments. Utilizes the
    ruamel_yaml library.

    :param data: Python dict to serialize as YAML
    :param stream: (optional) Stream handle to write
                   the serialized Python object to.
    :returns: Serialized Python object or None
    """
    return ruamel_yaml.dump(
        data, stream, default_flow_style=False,
        Dumper=ruamel_yaml.RoundTripDumper
    )
