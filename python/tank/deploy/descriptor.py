# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Functionality for managing versions of apps.
"""

from tank_vendor.shotgun_deploy import create_descriptor


def get_from_location_and_paths(app_or_engine, pc_path, bundle_install_path, location_dict):
    """
    Factory method.
    
    LEGACY - Use descriptor_factory() instead.

    :param app_or_engine: Either AppDescriptor.APP ENGINE CORE or FRAMEWORK
    :param pc_path: Path to the root of the pipeline configuration. 
                    Legacy parameter and no longer used. This value will be ignored.
    :param bundle_install_path: Path to the root of the apps, frameworks and engines bundles.
    :param location_dict: A tank location dict
    :returns: an AppDescriptor object
    """
    return create_descriptor(app_or_engine, location_dict, bundle_install_path)
