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
By default, yaml constructs Python str objects using 'ascii' encoding.
In order to support localization and non-ascii unicode characters in
environment configuration and/or bundle manifest files, we want to
override that encoding to use 'utf-8' instead.
"""

import sys


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
    try:
        return value.encode("utf-8")
    except UnicodeEncodeError:
        return value

from tank_vendor import yaml
# Set the utf-8 constructor as the default scalar
# constructor in the yaml module
yaml.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_SCALAR_TAG,
    construct_yaml_str_as_utf8
)

# ruamel_yaml is not supported on Python 2.5 and lower.
if not sys.version_info < (2, 6):
    try:
        from tank_vendor import ruamel_yaml
        # Set the utf-8 constructor as the default scalar
        # constructor in the ruamel_yaml module
        ruamel_yaml.add_constructor(
            ruamel_yaml.resolver.BaseResolver.DEFAULT_SCALAR_TAG,
            construct_yaml_str_as_utf8
        )

    except ImportError:
        # This can happen with older versions (<= v1.3.20) of
        # tk-framework-desktopstartup that do not have the ruamel_yaml
        # module added to the local core installation.
        pass
