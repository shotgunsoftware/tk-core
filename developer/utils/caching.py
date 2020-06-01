# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import glob
import shutil
import stat

from tank.util import filesystem
from tank.platform import environment
from tank.descriptor import Descriptor, create_descriptor

from tank import LogManager

logger = LogManager.get_logger("utils.caching")


def _cache_descriptor(sg, desc_type, desc_dict, target_path):
    """
    Cache the given descriptor into a new bundle cache.

    :param sg: Shotgun API instance
    :param desc_type: Descriptor.ENGINE | Descriptor.APP | Descriptor.FRAMEWORK
    :param desc_dict: descriptor dict or uri
    :param target_path: bundle cache root to cache into
    """
    desc = create_descriptor(sg, desc_type, desc_dict, fallback_roots=[target_path])
    desc.ensure_local()
    desc_size_kb = filesystem.compute_folder_size(desc.get_path()) // 1024
    logger.info(
        "Caching %s into plugin bundle cache (size %d KiB)" % (desc, desc_size_kb)
    )
    if not desc._io_descriptor.is_immutable():
        logger.warning(
            "Descriptor %r may not work for other users using the plugin!" % desc
        )
    desc.clone_cache(target_path)


def _should_skip_caching(desc):
    """
    By default, everything is cached.
    """
    return False


def cache_apps(
    sg_connection, cfg_descriptor, bundle_cache_root, should_skip_caching_callable=None
):
    """
    Iterates over all environments within the given configuration descriptor
    and caches all items into the bundle cache root.

    :param sg_connection: Shotgun connection
    :param cfg_descriptor: Config descriptor
    :param bundle_cache_root: Root where to cache payload
    :param should_skip_caching_callable: Optional callable that will check the descriptor
        and return `True` or `False` to indicate whether it should be cached.
        Callable must accept a single parameter, the descriptor as a `dict`, and
        return a `bool`. If `None`, the default :func:`_should_skip_caching()` will be used
    """
    # introspect the config and cache everything
    logger.info("Introspecting environments...")
    env_path = os.path.join(cfg_descriptor.get_path(), "env")

    # set the function to call when checking whether to cache the bundle
    if should_skip_caching_callable:
        _skip_caching = should_skip_caching_callable
    else:
        _skip_caching = _should_skip_caching

    # find all environment files
    env_filenames = []
    for filename in os.listdir(env_path):
        if filename.endswith(".yml"):
            # matching the env filter (or no filter set)
            logger.info("> found %s" % filename)
            env_filenames.append(os.path.join(env_path, filename))

    processed = set()
    for desc, bundle_type in _iterate_environment(env_filenames):
        # This will avoid us from attempting to process
        # the same descriptor twice.
        if repr(desc) in processed:
            continue
        # Mark it as processed now, so we don't have to evaluate skip caching
        # multiple times
        processed.add(repr(desc))

        # We should not attempt to cache descriptors that are path-based. Not only don't they
        # need to be cached, but they might be using special tokens like CONFIG_FOLDER
        # that can't be understood outside a pipeline configuration. We also skip caching
        # app_store descriptors in sparse configs since SG Desktop will take care of downloading
        # these automatically from the app store at runtime.

        if desc["type"] in ["dev", "path"]:
            logger.warning("'%s' will not be cached inside the configuration.", desc)
            continue

        if desc["type"] == "manual":
            logger.warning(
                "'%s' will not be cached because they are deprecated. "
                "We recommend you convert them to a git-based or path/dev descriptors.",
                desc,
            )
            continue

        if _skip_caching(desc):
            continue

        _cache_descriptor(sg_connection, bundle_type, desc, bundle_cache_root)

    logger.info(
        "Total size of bundle cache: %d KiB"
        % (filesystem.compute_folder_size(bundle_cache_root) // 1024)
    )


def _iterate_environment(env_filenames):
    """
    Iterates over the environment files and yields each descriptor
    found.

    :param list env_filenames: List of environment files to search for descriptors.

    :returns: A generator of descriptor ``dict``.
    """
    # traverse and cache
    for env_path in env_filenames:
        logger.info("Processing %s..." % env_path)
        env = environment.Environment(env_path)

        for eng in env.get_engines():
            desc = env.get_engine_descriptor_dict(eng)

            yield desc, Descriptor.ENGINE

            for app in env.get_apps(eng):
                desc = env.get_app_descriptor_dict(eng, app)
                # resolve descriptor and clone cache into bundle cache
                yield desc, Descriptor.APP

        for framework in env.get_frameworks():
            desc = env.get_framework_descriptor_dict(framework)
            yield desc, Descriptor.FRAMEWORK


def _on_rm_error(func, path, exc_info):
    # On Windows, Python's shutil can't delete read-only files, so if we were trying to delete one,
    # remove the flag.
    # Inspired by http://stackoverflow.com/a/4829285/1074536
    if func == os.unlink:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    else:
        # Raise the exception, something else went wrong.
        raise exc_info[1]


def wipe_folder(folder):
    """
    Deletes all folders recursively.

    This will take care of wiping any permissions that might prevent from deleting a file.

    :param str bundle_cache_root: Path to the bundle cache.
    """
    shutil.rmtree(folder, onerror=_on_rm_error)


def cleanup_bundle_cache(bundle_cache_root):
    """
    Cleans up the bundle cache from any stray files that should not be shipped.

    This includes:
        - .git folders.
    """
    logger.info("")
    glob_patterns = [
        os.path.join(
            bundle_cache_root,
            "git*",  # Grabs all git descriptors
            "*",  # Grabs all bundles inside those descriptors
            "*",  # Grabs all commits inside those bundles
            ".git",  # Grabs all git files inside those commits.
        ),
        os.path.join(
            bundle_cache_root,
            "*",  # Grabs all descriptor types
            "*",  # Grabs all bundles inside those descriptors
            "*",  # Grabs all commits inside those bundles
            "tests",  # Grabs all tests folders.
        ),
        os.path.join(bundle_cache_root, "tmp"),
    ]
    for glob_pattern in glob_patterns:
        for folder_to_remove in glob.glob(glob_pattern):
            logger.info("Removing %s...", folder_to_remove)
            wipe_folder(folder_to_remove)
