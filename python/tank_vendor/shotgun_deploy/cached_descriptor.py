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


class CachedDescriptor(Descriptor):
    """
    Mixin class that caches descriptor instances.

    The cache keys based on the bundle storage root path and
    the locator dictionary.
    """
    _instances = dict()

    def __new__(cls, bundle_cache_root, location_dict, *args, **kwargs):
        """
        Handles caching of descriptors.

        Executed prior to __init__ being executed.

        Since all our normal descriptors are immutable - they represent a specific,
        read only and cached version of an app, engine or framework on disk, we can
        also cache their wrapper objects.

        :param bundle_cache_root: Root location for bundle cache
        :param location_dict: Location dictionary describing the bundle
        :return: Descriptor instance
        """
        instance_cache = cls._instances

        # The cache is keyed based on the location dict and the bundle install root
        cache_key = (bundle_cache_root, str(location_dict))

        # Instantiate and cache if we need to, otherwise just return what we
        # already have stored away.
        if cache_key not in instance_cache:
            # If the bundle install path isn't in the cache, then we are
            # starting fresh. Otherwise, check to see if the app (by name)
            # is cached, and if not initialize its specific cache. After
            # that we instantiate and store by version.
            instance_cache[cache_key] = super(CachedDescriptor, cls).__new__(
                cls,
                bundle_cache_root,
                location_dict,
                *args,
                **kwargs
            )

        return instance_cache[cache_key]

