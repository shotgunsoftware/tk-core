# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.


from .descriptor import Descriptor
from .descriptor_core import CoreDescriptor
from .descriptor_bundle import AppDescriptor, FrameworkDescriptor, EngineDescriptor
from .descriptor_config import ConfigDescriptor

from .errors import (
    TankAppStoreConnectionError, TankAppStoreError, TankDescriptorError,
    InvalidAppStoreCredentialsError, TankInvalidAppStoreCredentialsError,
    CheckVersionConstraintsError, TankCheckVersionConstraintsError,
    TankInvalidInterpreterLocationError, TankMissingManifestError
)

from .descriptor import create_descriptor
from .io_descriptor import descriptor_dict_to_uri, descriptor_uri_to_dict, is_descriptor_version_missing
