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

from tank_vendor import yaml
from tank_vendor import ruamel_yaml

from tank_vendor.yaml.reader import Reader
from tank_vendor.yaml.scanner import Scanner
from tank_vendor.yaml.parser import Parser
from tank_vendor.yaml.composer import Composer 
from tank_vendor.yaml.constructor import Constructor
from tank_vendor.yaml.resolver import Resolver

from tank_vendor.ruamel_yaml.reader import Reader as RYReader
from tank_vendor.ruamel_yaml.scanner import RoundTripScanner
from tank_vendor.ruamel_yaml.parser_ import Parser as RYParser
from tank_vendor.ruamel_yaml.composer import Composer as RYComposer
from tank_vendor.ruamel_yaml.constructor import RoundTripConstructor
from tank_vendor.ruamel_yaml.resolver import Resolver as RYResolver

class Utf8Constructor(Constructor):
    def construct_yaml_str_utf8(self, node):
        value = self.construct_scalar(node)
        try:
            return value.encode("utf-8")
        except UnicodeEncodeError:
            return value

Utf8Constructor.add_constructor(
    u'tag:yaml.org,2002:str',
    Utf8Constructor.construct_yaml_str_utf8
)

class Utf8Loader(Reader, Scanner, Parser, Composer, Utf8Constructor, Resolver):
    def __init__(self, stream):
        Reader.__init__(self, stream)
        Scanner.__init__(self)
        Parser.__init__(self)
        Composer.__init__(self)
        Utf8Constructor.__init__(self)
        Resolver.__init__(self)

class Utf8RoundTripConstructor(RoundTripConstructor):
    def construct_yaml_str_utf8(self, node):
        value = self.construct_scalar(node)
        if PY3:
            return value
        try:
            return value.encode("utf-8")
        except UnicodeEncodeError:
            return value

Utf8RoundTripConstructor.add_constructor(
    u'tag:yaml.org,2002:str',
    Utf8RoundTripConstructor.construct_yaml_str_utf8
)

class Utf8RoundTripLoader(
    RYReader, RoundTripScanner, RYParser, RYComposer,
    Utf8RoundTripConstructor, RYResolver
):
    def __init__(self, stream):
        RYReader.__init__(self, stream)
        RoundTripScanner.__init__(self)
        RYParser.__init__(self)
        RYComposer.__init__(self)
        Utf8RoundTripConstructor.__init__(self)
        RYResolver.__init__(self)

def yaml_load(stream):
    return yaml.load(stream, Utf8Loader)

def yaml_load_preserve(stream):
    return ruamel_yaml.load(stream, Utf8RoundTripLoader)

def yaml_dump(data, stream=None):
    return yaml.dump(data, stream)

def yaml_dump_preserve(data, stream=None):
    return ruamel_yaml.dump(
        data, stream, default_flow_style=False, 
        Dumper=ruamel_yaml.RoundTripDumper
    ) 

def yaml_safe_dump(data, stream=None):
    return yaml.safe_dump(data, stream)
