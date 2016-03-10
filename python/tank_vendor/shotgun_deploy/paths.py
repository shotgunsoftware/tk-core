# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
from .. import shotgun_base
from . import util

def get_bundle_cache_root():
    """
    Returns the cache location for the default bundle cache.
    Ensures that this folder exists.

    :returns: path on disk
    """
    bundle_cache_root = os.path.join(shotgun_base.get_cache_root(), "bundle_cache")
    shotgun_base.ensure_folder_exists(bundle_cache_root)
    return bundle_cache_root


def get_configuration_cache_root(site_url, project_id, pipeline_configuration_id, namespace):
    """
    Calculates the location of a cached configuration.
    Ensures that this folder exists.

    :param site_url: Shotgun site url string, eg 'https://mysite.shotgunstudio.com'
    :param project_id: The shotgun id of the project to store caches for
    :param pipeline_configuration_id: The shotgun pipeline config id to store caches for
    :param namespace: name space string, typically one short word,
                      e.g. 'maya', 'rv', 'desktop'.
    :returns: path on disk
    """
    config_cache_root = os.path.join(
        shotgun_base.get_pipeline_config_cache_root(
            site_url,
            project_id,
            pipeline_configuration_id
        ),
        "cfg",
        util.create_valid_filename(namespace)
    )
    shotgun_base.ensure_folder_exists(config_cache_root)
    return config_cache_root

def get_configuration_info_path(site_url, project_id, pipeline_configuration_id, namespace):
    """
    Calculates the location of the configuration info metadata cache file.
    Ensures that this folder in which this file resides exists.

    The configuration info file contains metadata about the configuration itself
    and is used by the bootstrap to determine if a config is up to date or not.

    :param site_url: Shotgun site url string, eg 'https://mysite.shotgunstudio.com'
    :param project_id: The shotgun id of the project to store caches for
    :param pipeline_configuration_id: The shotgun pipeline config id to store caches for
    :param namespace: name space string, typically one short word,
                      e.g. 'maya', 'rv', 'desktop'.
    :returns: path on disk to file
    """
    sanitized_namespace = util.create_valid_filename(namespace)
    cache_filename = "%s_info.yml" % sanitized_namespace

    config_info_path = os.path.join(
        shotgun_base.get_pipeline_config_cache_root(
            site_url,
            project_id,
            pipeline_configuration_id
        ),
        "cfg",
        cache_filename
    )
    shotgun_base.ensure_folder_exists(os.path.dirname(config_info_path))
    return config_info_path

