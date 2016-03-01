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
import sys
import errno
import stat
import shutil

from .log import get_shotgun_base_logger
log = get_shotgun_base_logger()

def get_shotgun_storage_key(platform=sys.platform):
    """
    Given a sys.platform, resolve a Shotgun storage key

    Shotgun local storages handle operating systems using
    the three keys 'windows_path, 'mac_path' and 'linux_path'.
    This method resolves the right key given a std. python
    sys.platform::

        get_shotgun_storage_key('win32') -> 'windows_path'
        get_shotgun_storage_key() -> 'mac_path' # if on mac

    :param platform: sys.platform style string, e.g 'linux2',
                     'win32' or 'darwin'.
    :returns: Shotgun storage path as string.
    """
    if platform == "win32":
        return "windows_path"
    elif platform == "darwin":
        return "mac_path"
    elif platform.startswith("linux"):
        return "linux_path"
    else:
        raise ValueError(
            "Cannot resolve Shotgun storage - unsupported "
            "os platform '%s'" % platform
        )

def append_folder_to_path(os_name, base, folder_name):
    """
    Multi-os method that appends a folder to an existing path.

    This is effectively os.path.join() that can be executed on
    an alternative platform.

    base Paths that are None will return None

    :param os_name: Operating system, sys.platform style, e.g. win32, linux2, darwin
    :param base: Base path
    :param folder_name: Name of folder to append
    :returns: Full path
    """
    if base is None:
        return None

    # get the valid separator for this path
    separators = {"linux2": "/", "win32": "\\", "darwin": "/"}
    separator = separators[os_name]

    # get rid of any slashes at the end
    root_value = base.rstrip("/\\")
    # now root value is "/foo/bar", "c:" or "\\hello"

    # concat the full path.
    full_path = root_value + separator + folder_name

    return full_path


def sanitize_path(path, separator=os.path.sep):
    """
    Multi-platform sanitize and clean up of paths.

    The following modifications will be carried out:

    None returns None

    Trailing slashes are removed:
    1. /foo/bar      - unchanged
    2. /foo/bar/     - /foo/bar
    3. z:/foo/       - z:\foo
    4. z:/           - z:\
    5. z:\           - z:\
    6. \\foo\bar\    - \\foo\bar

    Double slashes are removed:
    1. //foo//bar    - /foo/bar
    2. \\foo\\bar    - \\foo\bar

    Leading and trailing spaces are removed:
    1. "   Z:\foo  " - "Z:\foo"

    :param path: the path to clean up
    :param separator: the os.sep to adjust the path for. / on nix, \ on win.
    :returns: cleaned up path
    """
    if path is None:
        return None

    # ensure there is no white space around the path
    path = path.strip()

    # get rid of any slashes at the end
    # after this step, path value will be "/foo/bar", "c:" or "\\hello"
    path = path.rstrip("/\\")

    # add slash for drive letters: c: --> c:/
    if len(path) == 2 and path.endswith(":"):
        path += "/"

    # and convert to the right separators
    # after this we have a path with the correct slashes and no end slash
    local_path = path.replace("\\", separator).replace("/", separator)

    # now weed out any duplicated slashes. iterate until done
    while True:
        new_path = local_path.replace("//", "/")
        if new_path == local_path:
            break
        else:
            local_path = new_path

    # for windows, remove duplicated backslashes, except if they are
    # at the beginning of the path
    while True:
        new_path = local_path[0] + local_path[1:].replace("\\\\", "\\")
        if new_path == local_path:
            break
        else:
            local_path = new_path

    return local_path



def ensure_folder_exists(path, permissions=0775, create_placeholder_file=False):
    """
    Helper method - creates a folder and parent folders if such do not already exist.

    :param path: path to create
    :param permissions: Permissions to use when folder is created
    :param create_placeholder_file: If true, a placeholder file will be generated.
    """
    if not os.path.exists(path):
        old_umask = os.umask(0)
        try:
            log.debug("Creating folder %s [%o].." % (path, permissions))
            os.makedirs(path, permissions)

            if create_placeholder_file:
                ph_path = os.path.join(path, "placeholder")
                if not os.path.exists(ph_path):
                    fh = open(ph_path, "wt")
                    fh.write("This file was automatically generated by Shotgun.\n\n")
                    fh.close()

        except OSError, e:
            # Race conditions are perfectly possible on some network storage setups
            # so make sure that we ignore any file already exists errors, as they
            # are not really errors!
            if e.errno != errno.EEXIST:
                # re-raise
                raise
        finally:
            os.umask(old_umask)


def copy_file(src, dst, permissions=0555):
    """
    Copy file with permissions

    :param src: Source file
    :param dst: Target destination
    :param permissions: Permissions to use for target file
    """
    old_umask = os.umask(0)
    try:
        shutil.copy(src, dst)
        os.chmod(dst, permissions)
    finally:
        os.umask(old_umask)

def safe_delete_file(path):
    """
    Deletes the given file if it exists.
    Ignores any errors raised in the process.
    If the user does not have sufficent permissions to
    remove the file, nothing will happen, it will simply
    be skipped over.

    :param path: Full path to file to remove
    """
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception, e:
        log.warning("File '%s' could not be deleted, skipping: %s" % (path, e))


def copy_folder(src, dst, folder_permissions=0775):
    """
    Alternative implementation to shutil.copytree
    Copies recursively and creates folders if they don't already exist.
    Skips a fixed list of system files such as .svn, .git, etc.
    Files will the extension .sh, .bat or .exe will be given
    executable permissions.

    Returns a list of files that were copied.

    :param src: Source path to copy from
    :param dst: Destination to copy to
    :param folder_permissions: permissions to use for new folders
    :returns: List of files copied
    """
    old_umask = os.umask(0)
    try:
        return _copy_folder_r(src, dst, folder_permissions)
    finally:
        os.umask(old_umask)

def _copy_folder_r(src, dst, folder_permissions):
    """
    Recursive helper and implementation of copy_folder()

    :param src: Source path to copy from
    :param dst: Destination to copy to
    :param folder_permissions: permissions to use for new folders
    :returns: List of source files copied
    """
    SKIP_LIST = [".svn", ".git", ".gitignore", "__MACOSX", ".DS_Store"]

    files = []

    if not os.path.exists(dst):
        log.debug("Creating folder %s [%o].." % (dst, folder_permissions))
        os.mkdir(dst, folder_permissions)

    names = os.listdir(src)
    for name in names:

        srcname = os.path.join(src, name)
        dstname = os.path.join(dst, name)

        # get rid of system files
        if name in SKIP_LIST:
            continue

        try:
            if os.path.isdir(srcname):
                files.extend(_copy_folder_r(srcname, dstname, folder_permissions))
            else:
                shutil.copy(srcname, dstname)
                files.append(srcname)
                # if the file extension is sh, set executable permissions
                if dstname.endswith(".sh") or dstname.endswith(".bat") or dstname.endswith(".exe"):
                    try:
                        # make it readable and executable for everybody
                        os.chmod(dstname, 0775)
                    except Exception, e:
                        log.error("Can't set executable permissions on %s: %s" % (dstname, e))

        except (IOError, os.error), e:
            raise IOError("Can't copy %s to %s: %s" % (srcname, dstname, e))

    return files


def move_folder(src, dst, folder_permissions=0775):
    """
    Move a directory.

    First copies all content into target. Then deletes
    all content from sources. Skip files that won't delete.

    :param src: Source path to copy from
    :param dst: Destination to copy to
    :param folder_permissions: permissions to use for new folders
    """
    if os.path.exists(src):
        log.debug("Moving directory: %s -> %s" % (src, dst))

        # first copy the content in the core folder
        src_files = copy_folder(src, dst, folder_permissions)

        # now clear out the install location
        log.debug("Clearing out source location...")
        for f in src_files:
            try:
                # on windows, ensure all files are writable
                if sys.platform == "win32":
                    attr = os.stat(f)[0]
                    if (not attr & stat.S_IWRITE):
                        # file is readonly! - turn off this attribute
                        os.chmod(f, stat.S_IWRITE)
                os.remove(f)
            except Exception, e:
                log.error("Could not delete file %s: %s" % (f, e))
