# Copyright (c) 2017 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Methods for resolving publish data into local representations
"""

from __future__ import with_statement

import os
import re
import sys
import urlparse
import urllib
import pprint

from .publish_util import get_cached_local_storages
from ...log import LogManager
from ..shotgun_path import ShotgunPath
from ..errors import PublishPathNotDefinedError, PublishPathNotSupported

log = LogManager.get_logger(__name__)


def resolve_publish_path(tk, sg_publish_data):
    """
    Returns a local path on disk given a dictionary of Shotgun publish data.

    This acts as the inverse of :meth:`register_publish` and
    resolves a local path on disk given some Shotgun publish data,
    typically obtained by a Shotgun API ``find()`` call.

    Complex logic is applied in order to turn a publish into a
    valid local path. Several exception types are raised to indicate
    the reason why a path could not be resolved, allowing for workflows
    where the logic can be overridden.

    .. note:: This method is also called by :meth:`sgtk.Hook.get_publish_path`
              which is a common method Toolkit apps use to resolve publishes
              into paths.

    **Resolution Logic**

    The method will attempt to resolve the publish data into a path
    by applying several recipes:

    - First, the ``resolve_publish`` core hook will be called. This hook
      can be used either in order to override any built-in behavior or
      to implement support for url schemes, uploaded files or other modes
      which the default implementation currently doesn't support. The hook
      returns ``None`` by default, indicating that no resolve overrides
      are present.

    - If no path was resolved by the hook, the method will check if the
      publish is associated with a local file link and if so attempt to
      resolve this to a path (for more details see below).

    - Next, it will check if the publish is linked to a ``file://`` url
      and attempt to resolve this.

    - Lastly, if the publish still cannot be resolved, a
      :class:`~sgtk.util.PublishPathNotSupported` is raised.

    **Resolving local file links**

    If the publish is a local file link, its local OS representation
    will be used. Local file links are generated automatically by
    :meth:`register_publish` if the path you are publishing matches
    any local file storage defined in the Shotgun Site Preferences.
    Read more about local file links `here <https://support.shotgunsoftware.com/hc/en-us/articles/219030938-Linking-to-local-files>`_.

    Local file storage mappings in Shotgun are global and affect
    all machines, all users and all projects.

    If a local storage doesn't define the operating system platform
    you are currently using, you can augment it by adding an
    environment variable. For example, if there
    is a local storage named ``Renders`` that is defined on Linux and Windows,
    you can extend to support mac by creating an environment variable named
    ``SHOTGUN_PATH_MAC_RENDERS``. The general syntax for this is
    ``SHOTGUN_PATH_WINDOWS|MAC|LINUX_STORAGENAME``.

    .. note:: If you define a ``SHOTGUN_PATH_MAC_RENDERS`` environment variable
              and there is a local storage ``Renders`` with a mac path set,
              the local storage value will be used and a warning will be logged.

    .. note:: If no storage can be resolved for the current operating system,
              a :class:`~sgtk.util.PublishPathNotDefinedError` is raised.


    **Resolving file urls**

    The method also supports the resolution of ``file://`` urls. Contrary to
    local file storage objects in Shotgun (see above), these paths are not
    stored in a multi-os representation but are just defined on the operating
    system where they were created.

    If you are trying to resolve a ``file://`` url on an os platform different
    from the one where where the url was created, the method will attempt to
    resolve it into a valid path using several different approaches:

    - First, it will look for the three environment variables ``SHOTGUN_PATH_WINDOWS``,
      ``SHOTGUN_PATH_MAC``, and ``SHOTGUN_PATH_LINUX``. If these are defined,
      the method will attempt to translate the path this way. For example, if
      you are trying to resolve ``file:///prod/proj_x/assets/bush/file.txt`` on
      windows, you could set up ``SHOTGUN_PATH_WINDOWS=P:\prod`` and
      ``SHOTGUN_PATH_LINUX=/prod`` in order to hint the way the path should be
      resolved.

    - If you wanted to use more than one environment variable, this is possible
      by extending the above syntax with a name, for example ``SHOTGUN_PATH_LINUX_SECONDARY``.

    - In addition, all existing local storage definitions will be downloaded
      and used in the same way.

    - If a local storage has been defined, but an operating system is missing,
      this can be supplied via an environment variable. For example, if there
      is a local storage named ``Renders`` that is defined on Linux and Windows,
      you can extend to support mac by creating an environment variable named
      ``SHOTGUN_PATH_MAC_RENDERS``. The general syntax for this is
      ``SHOTGUN_PATH_WINDOWS|MAC|LINUX_STORAGENAME``.

    - If no root matches, the file path will be returned as is.

    .. note::   For example, you have published the file ``/projects/some/file.txt`` on Linux
                and a Shotgun publish with the url ``file:///projects/some/file.txt`` was generated.
                The Linux path ``/projects`` equates to ``Q:\projects`` on Windows
                and hence you want the full path to be translated to
                ``Q:\\projects\\some\\file.txt``. All of the setups below would handle this:

                - A general environment based override:

                    - ``SHOTGUN_PATH_LINUX=/projects``
                    - ``SHOTGUN_PATH_WINDOWS=Q:\projects``
                    - ``SHOTGUN_PATH_MAC=/projects``

                - A Shotgun local storage "Projects" set up with:

                    - Linux Path: ``/projects``
                    - Windows Path: ``Q:\projects``
                    - Mac Path: ``/projects``

                - A Shotgun local storage "Projects" augmented with an environment variable:

                    - Linux Path: ``/projects``
                    - Windows Path: ``<blank>``
                    - Mac Path: ``/projects``
                    - ``SHOTGUN_PATH_WINDOWS_PROJECTS=Q:\projects``


    .. note:: If you have a local storage ``Renders`` defined in Shotgun with
       a Linux path set and also a ``SHOTGUN_PATH_LINUX_RENDERS`` environment
       variable defined, the storage will take precedence, the environment
       variable will be ignored and a warning will be logged. Generally speaking,
       local storage definitions always take precedence over environment variables.


    **Customization examples**

    If you want to add support beyond local file links and ``file://`` urls, you can
    customize the ``resolve_publish.py`` core hook. This can for example be used to
    add support for the following customizations:

    - Publishes with associated uploaded files could be automatically downloaded
      into an appropriate cache location by the core hook and the path would be
      be returned.

    - Custom url schemes (such as ``perforce://``) could be resolved into local paths.


    **Parameters**

    :param tk: :class:`~sgtk.Sgtk` instance
    :param sg_publish_data: Dictionary containing Shotgun publish data.
        Needs to at least contain a code, type, id and a path key.

    :returns: A local path to file or file sequence.

    :raises: :class:`~sgtk.util.PublishPathNotDefinedError` if the path isn't defined.
    :raises: :class:`~sgtk.util.PublishPathNotSupported` if the path cannot be resolved.
    """

    path_field = sg_publish_data.get("path")

    log.debug(
        "Publish id %s: Attempting to resolve publish path "
        "to local file on disk: '%s'" % (sg_publish_data["id"], pprint.pformat(path_field))
    )

    # first offer the resolve to the core hook
    #
    # note that we run this before the built-in logic because we want to be able to add support
    # for handling uploaded files (or something else) in the future, yet at the same time,
    # by doing that we don't want to break any client integration. By putting the hook first,
    # this is possible. If we put the hook last, we could affect the conditions under which
    # the hook is being executed by introducing new features.
    custom_path = tk.execute_core_hook_method(
        "resolve_publish",
        "resolve_path",
        sg_publish_data=sg_publish_data
    )
    if custom_path:
        log.debug("Publish resolve core hook returned path '%s'" % custom_path)
        return custom_path

    # core hook did not pick it up - apply default logic
    if path_field is None:
        # no path defined for publish
        raise PublishPathNotDefinedError(
            "Publish %s (id %s) does not have a path set" % (sg_publish_data["code"], sg_publish_data["id"])
        )

    elif path_field["link_type"] == "local":
        # local file link
        path = __resolve_local_file_link(tk, path_field)
        if path is None:
            raise PublishPathNotDefinedError(
                "Publish %s (id %s) has a local file link that could not be resolved "
                "on this os platform." % (sg_publish_data["code"], sg_publish_data["id"])
            )
        return path

    elif path_field["link_type"] == "web":
        # url link
        return __resolve_url_link(tk, path_field)

    else:
        # unknown attachment type
        raise PublishPathNotSupported(
            "Publish %s (id %s): Local file link type '%s' "
            "not supported." % (sg_publish_data["code"], sg_publish_data["id"], path_field["link_type"])
        )


def __resolve_local_file_link(tk, attachment_data):
    """
    Resolves the given local path attachment into a local path.
    For details, see :meth:`resolve_publish_path`.

    :param tk: :class:`~sgtk.Sgtk` instance
    :param attachment_data: Shotgun Attachment dictionary.

    :returns: A local path to file or file sequence or None if it cannot be resolved.
    """
    # local file link data looks like this:
    #
    # {'content_type': 'image/png',
    #  'id': 25826,
    #  'link_type': 'local',
    #  'local_path': '/Users/foo.png',
    #  'local_path_linux': None,
    #  'local_path_mac': '/Users/foo.png',
    #  'local_path_windows': None,
    #  'local_storage': {'id': 39,
    #                    'name': 'home',
    #                    'type': 'LocalStorage'},
    #  'name': 'foo.png',
    #  'type': 'Attachment',
    #  'url': 'file:///Users/foo.png'}

    log.debug("Attempting to resolve local file link attachment data "
              "into a local path: %s" % pprint.pformat(attachment_data))

    # see if we have a path for this storage
    local_path = attachment_data.get("local_path")
    if local_path is None:
        raise PublishPathNotDefinedError(
            "Publish '%s' does not have a path defined "
            "for this platform. Windows Path: '%s', Mac Path: '%s', "
            "Linux Path: '%s'" % (
                attachment_data["name"],
                attachment_data["local_path_windows"],
                attachment_data["local_path_mac"],
                attachment_data["local_path_linux"],
            )
        )

    # Check override env vars:
    #
    # For local storages, it is possible to amend an existing
    # storage using environment variables. For example, if a
    # primary storage exists, but only has paths defined on
    # windows and linux, a mac storage path defined by setting
    # a SHOTGUN_PATH_MAC_PRIMARY.
    #
    # Similarly, if a SHOTGUN_PATH_WINDOWS_PRIMARY path is defined
    # for this storage, it will be ignored and a warning is logged.
    #

    # look for override env var for our local os
    storage_name = attachment_data["local_storage"]["name"].upper()
    storage_id = attachment_data["local_storage"]["id"]
    os_name = {"win32": "WINDOWS", "linux2": "LINUX", "darwin": "MAC"}[sys.platform]
    env_var_name = "SHOTGUN_PATH_%s_%s" % (os_name, storage_name)
    log.debug("Looking for override env var '%s'" % env_var_name)

    if env_var_name in os.environ:

        log.debug(
            "Detected override %s='%s'" % (env_var_name, os.environ[env_var_name])
        )
        # if we already have this set in the local storage,
        # issue a warning
        if local_path:
            log.warning(
                "Discovered environment variable %s, however the operating system root is "
                "already defined in Shotgun and the environment variable will "
                "be ignored." % env_var_name
            )

        else:

            # we have an override
            override_root = os.environ[env_var_name]

            # normalize path
            override_root = ShotgunPath.normalize(override_root)
            log.debug(
                "Applying override '%s' to path '%s' "
                "(storage %s)" % (override_root, local_path, storage_name)
            )

            # get the local storage that we are augmenting
            storage = [s for s in get_cached_local_storages(tk) if s["id"] == storage_id][0]

            # find a storage where the path is defined
            # we know that it must be defined for at least one os :)
            storage_field_map = {
                "windows_path": "local_path_windows",
                "linux_path": "local_path_mac",
                "mac_path": "local_path_linux"
            }

            for (storage_field, path_field) in storage_field_map.iteritems():
                this_os_storage_root = storage[storage_field]
                this_os_full_path = attachment_data[path_field]

                if this_os_full_path:
                    # the path is defined on this os. Normalize it by
                    # chopping off the root

                    # chop off the root from the path and append override root
                    local_path = override_root + os.path.sep + this_os_full_path[len(this_os_storage_root):]
                    log.debug(
                        "Transforming '%s' and root '%s' via env var '%s' into '%s'" % (
                            this_os_full_path,
                            this_os_storage_root,
                            override_root,
                            local_path
                        )
                    )
                    break

    # normalize
    local_path = ShotgunPath.normalize(local_path)
    log.debug("Resolved local file link: '%s'" % local_path)
    return local_path


def __resolve_url_link(tk, attachment_data):
    """
    Resolves the given url attachment into a local path.
    For details, see :meth:`resolve_publish_path`.

    :param tk: :class:`~sgtk.Sgtk` instance
    :param attachment_data: Dictionary containing Shotgun publish data.
        Needs to at least contain a code, type, id and a path key.

    :returns: A local path to file or file sequence.

    :raises: :class:`~sgtk.util.PublishPathNotSupported` if the path cannot be resolved.
    """
    log.debug("Attempting to resolve url attachment data "
              "into a local path: %s" % pprint.pformat(attachment_data))

    # url data looks like this:
    #
    # {'content_type': None,
    #  'id': 25828,
    #  'link_type': 'web',
    #  'name': 'toolkitty.jpg',
    #  'type': 'Attachment',
    #  'url': 'file:///C:/Users/Manne%20Ohrstrom/Downloads/toolkitty.jpg'},

    parsed_url = urlparse.urlparse(attachment_data["url"])

    # url = "file:///path/to/some/file.txt"
    # ParseResult(
    #   scheme='file',
    #   netloc='',
    #   path='/path/to/some/file.txt',
    #   params='',
    #   query='',
    #   fragment=''
    # )

    if parsed_url.scheme != "file":
        # we currently only support file:// style urls
        raise PublishPathNotSupported(
            "Cannot resolve unsupported url '%s' into a local path." % attachment_data["url"]
        )

    # file urls can be on the following standard form:
    #
    # Std unix path
    # /path/to/some/file.txt -> file:///path/to/some/file.txt
    #
    # >>> urlparse.urlparse("file:///path/to/some/file.txt")
    # ParseResult(scheme='file', netloc='', path='/path/to/some/file.txt', params='', query='', fragment='')
    #
    # Windows UNC path
    # \\laptop\My Documents\FileSchemeURIs.doc -> file://laptop/My%20Documents/FileSchemeURIs.doc
    #
    # >>> urlparse.urlparse("file://laptop/My%20Documents/FileSchemeURIs.doc")
    # ParseResult(scheme='file', netloc='laptop', path='/My%20Documents/FileSchemeURIs.doc', params='', query='', fragment='')
    #
    # Windows path with drive letter
    # C:\Documents and Settings\davris\FileSchemeURIs.doc -> file:///C:/Documents%20and%20Settings/davris/FileSchemeURIs.doc
    #
    # >>> urlparse.urlparse("file:///C:/Documents%20and%20Settings/davris/FileSchemeURIs.doc")
    # ParseResult(scheme='file', netloc='', path='/C:/Documents%20and%20Settings/davris/FileSchemeURIs.doc', params='', query='', fragment='')
    #
    # for information about Windows, see
    # https://blogs.msdn.microsoft.com/ie/2006/12/06/file-uris-in-windows/

    if parsed_url.netloc:
        # unc path
        resolved_path = urllib.unquote("//%s%s" % (parsed_url.netloc, parsed_url.path))
    else:
        resolved_path = urllib.unquote(parsed_url.path)

    # python returns drive letter paths incorrectly and need adjusting.
    if re.match("^/[A-Za-z]:/", resolved_path):
        resolved_path = resolved_path[1:]

    # we now have one of the following three forms (with slashes):
    # /path/to/file.ext
    # d:/path/to/file.ext
    # //share/path/to/file.ext
    log.debug("Path extracted from url: '%s'" % resolved_path)

    # create a lookup table of shotgun paths,
    # keyed by upper case storage name
    log.debug("Building cross-platform path resolution lookup table:")
    storage_lookup = {}
    for storage in get_cached_local_storages(tk):
        storage_key = storage["code"].upper()
        storage_lookup[storage_key] = ShotgunPath.from_shotgun_dict(storage)
        log.debug("Added Shotgun Storage %s: %s" % (storage_key, storage_lookup[storage_key]))

    # get default environment variable set
    # note that this may generate a None/None/None entry
    storage_lookup["_DEFAULT_ENV_VAR_OVERRIDE"] = ShotgunPath(
            os.environ.get("SHOTGUN_PATH_WINDOWS"),
            os.environ.get("SHOTGUN_PATH_LINUX"),
            os.environ.get("SHOTGUN_PATH_MAC")
        )
    log.debug("Added default env override: %s" % storage_lookup["_DEFAULT_ENV_VAR_OVERRIDE"])

    # look for storage overrides
    for env_var in os.environ.keys():
        expr = re.match("^SHOTGUN_PATH_(WINDOWS|MAC|LINUX)_(.*)$", env_var)
        if expr:
            platform = expr.group(1)
            storage_name = expr.group(2).upper()
            log.debug(
                "Added %s environment override for %s: %s" % (platform, storage_name, os.environ[env_var])
            )

            if storage_name not in storage_lookup:
                # not in the lookup yet. Add it
                storage_lookup[storage_name] = ShotgunPath()

            if platform == "WINDOWS":
                if storage_lookup[storage_name].windows:
                    # this path was already defined by a sg local storage
                    log.warning(
                        "Discovered env var %s, however a Shotgun local storage already "
                        "defines '%s' to be '%s'. Your environment override "
                        "will be ignored." % (env_var, storage_name, storage_lookup[storage_name].windows)
                    )
                else:
                    storage_lookup[storage_name].windows = os.environ[env_var]

            elif platform == "MAC":
                if storage_lookup[storage_name].macosx:
                    # this path was already defined by a sg local storage
                    log.warning(
                        "Discovered env var %s, however a Shotgun local storage already "
                        "defines '%s' to be '%s'. Your environment override "
                        "will be ignored." % (env_var, storage_name, storage_lookup[storage_name].macosx)
                    )
                else:
                    storage_lookup[storage_name].macosx = os.environ[env_var]

            else:
                if storage_lookup[storage_name].linux:
                    # this path was already defined by a sg local storage
                    log.warning(
                        "Discovered env var %s, however a Shotgun local storage already "
                        "defines '%s' to be '%s'. Your environment override "
                        "will be ignored." % (env_var, storage_name, storage_lookup[storage_name].linux)
                    )
                else:
                    storage_lookup[storage_name].linux = os.environ[env_var]

    # now see if the given url starts with any storage def in our setup
    for storage, sg_path in storage_lookup.iteritems():

        # go through each storage, see if any of the os
        # path defs for the storage matches the beginning of the
        # url path. Compare lower case (most file systems are case preserving).
        adjusted_path = None
        if sg_path.windows and resolved_path.lower().startswith(sg_path.windows.replace("\\", "/").lower()):
            adjusted_path = sg_path.join(resolved_path[len(sg_path.windows):]).current_os

        elif sg_path.linux and resolved_path.lower().startswith(sg_path.linux.lower()):
            adjusted_path = sg_path.join(resolved_path[len(sg_path.linux):]).current_os

        elif sg_path.macosx and resolved_path.lower().startswith(sg_path.macosx.lower()):
            adjusted_path = sg_path.join(resolved_path[len(sg_path.macosx):]).current_os

        if adjusted_path:
            log.debug(
                "Adjusted path '%s' -> '%s' based on override '%s' (%s)" % (
                    resolved_path,
                    adjusted_path,
                    storage,
                    sg_path
                )
            )
            resolved_path = adjusted_path
            break

    # adjust native platform slashes
    resolved_path = resolved_path.replace("/", os.path.sep)
    log.debug("Converted %s -> %s" % (attachment_data["url"], resolved_path))
    return resolved_path

