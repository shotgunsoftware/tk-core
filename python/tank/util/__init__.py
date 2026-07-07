# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from . import filesystem, json, pickle
from .environment import append_path_to_env_var, prepend_path_to_env_var
from .errors import (
    EnvironmentVariableFileLookupError,
    PublishPathNotDefinedError,
    PublishPathNotSupported,
    PublishResolveError,
    ShotgunAttachmentDownloadError,
    ShotgunPublishError,
    UnresolvableCoreConfigurationError,
)
from .local_file_storage import LocalFileStorageManager
from .login import get_current_user, get_shotgun_user

# DO keep the following two log_user_*_metric to preserve retro
# compatibility and prevent exception in legacy engine code.
from .metrics import EventMetric, log_user_activity_metric, log_user_attribute_metric
from .platforms import is_linux, is_macos, is_windows
from .shotgun import (
    create_event_log_entry,
    download_url,
    find_publish,
    get_entity_type_display_name,
    get_published_file_entity_type,
    register_publish,
    resolve_publish_path,
)
from .shotgun_entity import get_sg_entity_name_field
from .shotgun_path import ShotgunPath
from .storage_roots import StorageRoots
from .user_settings import UserSettings
from .version import (
    is_version_newer,
    is_version_newer_or_equal,
    is_version_older,
    is_version_older_or_equal,
    suppress_known_deprecation,
    version_parse,
)
