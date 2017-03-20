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

# global variables
g_entity_display_name_lookup = None
g_local_storage_cache = None


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
    all machines, all users and all projects. Sometimes there are cases
    when you want to override these globals to behave differently on a
    specific machine or for a user. This can be done by defining an environment
    variable named on the form ``SHOTGUN_PATH_OS_STORAGENAME``. For example, if
    you are running windows and your ``PRIMARY`` storage has been set up in
    Shotgun to be ``F:\`` and you want paths on your machine to resolve to ``G:\``
    instead, set an environment variable ``SHOTGUN_PATH_WINDOWS_PRIMARY=G:\``.
    The corresponding variables on Linux and Mac would be ``SHOTGUN_PATH_LINUX_PRIMARY``
    and ``SHOTGUN_PATH_MAC_PRIMARY``.

    .. note:: If no storage has been defined for the current operating system,
              a :class:`~sgtk.util.PublishPathNotDefinedError` is raised.

    **Resolving file urls**

    The method also supports the resolution of ``file://`` urls. Such urls
    are not multi platform and the local storages and environment variables
    will therefore be used to try to resolve such paths in case of ambiguity.

    - First, local storage settings will be downloaded from Shotgun and added to
      a path translation table.

    - Next, similar to the local file linking above, any environment variables
      on the form ``SHOTGUN_PATH_WINDOWS|MAC|LINUX`` or ``SHOTGUN_PATH_WINDOWS|MAC|LINUX_STORAGENAME``
      will be added to the translation table.

    - The ``file://`` path will be resolved compared against all the existing roots
      for all operating systems. The first match detected will be used to translate
      the path into the current operating system platform.

    - If there is no against any storage, the file path be returned.

    For example, you have published the file ``/projects/some/file.txt`` on Linux
    and generated a publish with the url ``file:///projects/some/file.txt``. You have
    either a local storage or environment variable set up with the following paths:

    - Linux Path: ``/projects``
    - Windows Path: ``Q:\projects``
    - Mac Path: ``/projects``

    When running on windows, the ``file://`` url will therefore be translated to
    ``Q:\\projects\\some\\file.txt``.

    .. note:: If no value has been defined for the current operating system,
              a :class:`~sgtk.util.PublishPathNotDefinedError` is raised.

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

    # first offer it to the core hook
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
        return __resolve_local_file_link(tk, path_field)

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
    Resolves the a given local path attachment into a local path.

    Will look for an override environment variable named on the
    form ``SHOTGUN_PATH_OS_STORAGENAME``. For example, if
    you are running windows and your ``PRIMARY`` storage has been set up in
    Shotgun to be ``F:\`` and you want paths on your machine to resolve to ``G:\``
    instead, set an environment variable ``SHOTGUN_PATH_WINDOWS_PRIMARY=G:\``.
    The corresponding variables on Linux and Mac would be ``SHOTGUN_PATH_LINUX_PRIMARY``
    and ``SHOTGUN_PATH_MAC_PRIMARY``.

    If no storage has been defined for the current operating system,
    a :class:`~sgtk.util.PublishPathNotDefinedError` is raised.

    :param tk: :class:`~sgtk.Sgtk` instance
    :param attachment_data: Shotgun Attachment dictionary.

    :returns: A local path to file or file sequence.

    :raises: :class:`~sgtk.util.PublishPathNotDefinedError` if the path isn't defined.
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

    # normalize
    local_path = ShotgunPath.from_current_os_path(local_path).current_os

    # check override env var
    storage_name = attachment_data["local_storage"]["name"].upper()
    storage_id = attachment_data["local_storage"]["id"]
    os_name = {"win32": "WINDOWS", "linux2": "LINUX", "darwin": "MAC"}[sys.platform]
    env_var_name = "SHOTGUN_PATH_%s_%s" % (os_name, storage_name)
    log.debug("Looking for override env var '%s'" % env_var_name)

    if env_var_name in os.environ:
        # we have an override
        override_root = os.environ[env_var_name]
        # normalize path
        override_root = ShotgunPath.from_current_os_path(override_root).current_os
        log.debug("Applying override '%s' to path '%s'" % (override_root, local_path))

        # get local storages to get path prefix to replace
        storage = [s for s in get_cached_local_storages(tk) if s['id'] == storage_id][0]
        # normalize and compare
        local_storage_root = ShotgunPath.from_shotgun_dict(storage).current_os
        # apply modification
        local_path = override_root + local_path[len(local_storage_root):]
        log.debug("Overridden path: '%s'" % local_path)

    log.debug("Resolved local file link: '%s'" % local_path)
    return local_path


def __resolve_url_link(tk, attachment_data):
    """
    Resolves the a given url attachment into a local path.

    The supports the resolution of ``file://`` urls into paths. Such urls
    are not multi platform and Shotgun local storages and environment variables
    will be used to try to resolve such paths in case of ambiguity.

    - First, local storage settings will be downloaded from Shotgun and added to
      a path translation table.

    - Next, any environment variables on the form ``SHOTGUN_PATH_WINDOWS|MAC|LINUX``
      will be added to the translation table.

    - Override environment variables on the form ``SHOTGUN_PATH_WINDOWS|MAC|LINUX_STORAGENAME``
      will override any local storage paths.

    - The ``file://`` path will be resolved compared against all the existing roots
      for all operating systems. The first match detected will be used to translate
      the path into the current operating system platform.

    - If there is no match against any storage, the file path be returned.

    For example, you have published the file ``/projects/some/file.txt`` on Linux
    and generated a publish with the url ``file:///projects/some/file.txt``. You have
    either a local storage or environment variable set up with the following paths:

    - Linux Path: ``/projects``
    - Windows Path: ``Q:\projects``
    - Mac Path: ``/projects``

    When running on windows, the ``file://`` url will therefore be translated to
    ``Q:\\projects\\some\\file.txt``.

    If no value has been defined for the current operating system,
    a :class:`~sgtk.util.PublishPathNotDefinedError` is raised.

    :param tk: :class:`~sgtk.Sgtk` instance
    :param sg_publish_data: Dictionary containing Shotgun publish data.
        Needs to at least contain a code, type, id and a path key.

    :returns: A local path to file or file sequence.

    :raises: :class:`~sgtk.util.PublishPathNotDefinedError` if the path isn't defined.
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
    # windows UNC path
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
    # for information about windows, see
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
                storage_lookup[storage_name].windows = os.environ[env_var]
            elif platform == "MAC":
                storage_lookup[storage_name].macosx = os.environ[env_var]
            else:
                storage_lookup[storage_name].linux = os.environ[env_var]

    # now see if the given url starts with any storage def in our setup
    for storage, sg_path in storage_lookup.iteritems():

        adjusted_path = None
        if sg_path.windows and resolved_path.lower().startswith(sg_path.windows.replace("\\", "/").lower()):
            # note: there is a special case with windows storages
            # where drive letters are retuned as X:\ whereas no other
            # paths are returned with a trailing separator
            if sg_path.windows.endswith("\\"):
                preamble_to_cut = len(sg_path.windows) - 1
            else:
                preamble_to_cut = len(sg_path.windows)
            adjusted_path = sg_path.current_os + resolved_path[preamble_to_cut:]

        elif sg_path.linux and resolved_path.lower().startswith(sg_path.linux.lower()):
            adjusted_path = sg_path.current_os + resolved_path[len(sg_path.linux):]

        elif sg_path.macosx and resolved_path.lower().startswith(sg_path.macosx.lower()):
            adjusted_path = sg_path.current_os + resolved_path[len(sg_path.macosx):]

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





