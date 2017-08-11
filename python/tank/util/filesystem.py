﻿# Copyright (c) 2016 Shotgun Software Inc.
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Utility methods for manipulating files and folders
"""

import os
import re
import sys
import errno
import stat
import shutil
import datetime
import functools
from .. import LogManager

log = LogManager.get_logger(__name__)


def with_cleared_umask(func):
    """
    Decorator which clears the umask for a method.

    The umask is a permissions mask that gets applied
    whenever new files or folders are created. For I/O methods
    that have a permissions parameter, it is important that the
    umask is cleared prior to execution, otherwise the default
    umask may alter the resulting permissions, for example::

        def create_folders(path, permissions=0777):
            log.debug("Creating folder %s..." % path)
            os.makedirs(path, permissions)

    The 0777 permissions indicate that we want folders to be
    completely open for all users (a+rwx). However, the umask
    overrides this, so if the umask for example is set to 0777,
    meaning that I/O operations are not allowed to create files
    that are readable, executable or writable for users, groups
    or others, the resulting permissions on folders created
    by create folders will be 0, despite passing in 0777 permissions.

    By adding this decorator to the method, we temporarily reset
    the umask to 0, thereby giving full control to
    any permissions operation to take place without any restriction
    by the umask::

        @with_cleared_umask
        def create_folders(path, permissions=0777):
            # Creates folders with the given permissions,
            # regardless of umask setting.
            log.debug("Creating folder %s..." % path)
            os.makedirs(path, permissions)
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # set umask to zero, store old umask
        old_umask = os.umask(0)
        try:
            # execute method payload
            return func(*args, **kwargs)
        finally:
            # set mask back to previous value
            os.umask(old_umask)
    return wrapper


def compute_folder_size(path):
    """
    Computes and returns the size of the given folder.

    :param path: folder to compute size for
    :return: size in bytes
    """
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total_size += os.path.getsize(fp)
    return total_size


@with_cleared_umask
def touch_file(path, permissions=0666):
    """
    Touch a file and optionally set its permissions.

    :param path: path to touch
    :param permissions: Optional permissions to set on the file. Default value is 0666,
                        creating a file that is readable and writable for all users.

    :raises: OSError - if there was a problem reading/writing the file
    """
    if not os.path.exists(path):
        try:
            fh = open(path, "wb")
            fh.close()
            os.chmod(path, permissions)
        except OSError, e:
            # Race conditions are perfectly possible on some network storage
            # setups so make sure that we ignore any file already exists errors,
            # as they are not really errors!
            if e.errno != errno.EEXIST:
                raise


@with_cleared_umask
def ensure_folder_exists(path, permissions=0775, create_placeholder_file=False):
    """
    Helper method - creates a folder and parent folders if such do not already exist.

    :param path: path to create
    :param permissions: Permissions to use when folder is created
    :param create_placeholder_file: If true, a placeholder file will be generated.

    :raises: OSError - if there was a problem creating the folder
    """
    if not os.path.exists(path):
        try:
            os.makedirs(path, permissions)

            if create_placeholder_file:
                ph_path = os.path.join(path, "placeholder")
                if not os.path.exists(ph_path):
                    fh = open(ph_path, "wt")
                    fh.write("This file was automatically generated by Shotgun.\n\n")
                    fh.write("The placeholder file is needed when managing toolkit configurations\n")
                    fh.write("in source control packages such as git and perforce. These systems\n")
                    fh.write("do not handle empty folders so a placeholder file is required for the \n")
                    fh.write("folder to be tracked and managed properly.\n")
                    fh.close()

        except OSError, e:
            # Race conditions are perfectly possible on some network storage setups
            # so make sure that we ignore any file already exists errors, as they
            # are not really errors!
            if e.errno != errno.EEXIST:
                # re-raise
                raise


@with_cleared_umask
def copy_file(src, dst, permissions=0666):
    """
    Copy file and sets its permissions.

    :param src: Source file
    :param dst: Target destination
    :param permissions: Permissions to use for target file. Default permissions will
                        be readable and writable for all users.
    """
    shutil.copy(src, dst)
    os.chmod(dst, permissions)


def safe_delete_file(path):
    """
    Deletes the given file if it exists.

    Ignores any errors raised in the process and logs them as warnings.
    If the user does not have sufficient permissions to
    remove the file, nothing will happen, it will simply
    be skipped over.

    :param path: Full path to file to remove
    """
    try:
        if os.path.exists(path):
            # on windows, make sure file is not read-only
            if sys.platform == "win32":
                # make sure we have write permission
                attr = os.stat(path)[0]
                if not attr & stat.S_IWRITE:
                    os.chmod(path, stat.S_IWRITE)
            os.remove(path)
    except Exception, e:
        log.warning("File '%s' could not be deleted, skipping: %s" % (path, e))


@with_cleared_umask
def copy_folder(src, dst, folder_permissions=0775, skip_list=None):
    """
    Alternative implementation to ``shutil.copytree``

    Copies recursively and creates folders if they don't already exist.
    Always skips system files such as ``"__MACOSX"``, ``".DS_Store"``, etc.
    Files will the extension ``.sh``, ``.bat`` or ``.exe`` will be given
    executable permissions.

    Returns a list of files that were copied.

    :param src: Source path to copy from
    :param dst: Destination to copy to
    :param folder_permissions: permissions to use for new folders
    :param skip_list: List of file names to skip. If this parameter is
                      omitted or set to None, common files such as ``.git``,
                      ``.gitignore`` etc will be ignored.
    :returns: List of files copied
    """
    # files or directories to always skip
    SKIP_LIST_ALWAYS = ["__MACOSX", ".DS_Store"]

    # files or directories to skip if no skip_list is specified
    SKIP_LIST_DEFAULT = [".svn", ".git", ".gitignore", ".hg", ".hgignore"]

    # compute full skip list
    # note: we don't do
    # actual_skip_list = skip_list or SKIP_LIST_DEFAULT
    # because we want users to be able to pass in
    # skip_list=[] in order to clear the default skip list.
    if skip_list is None:
        actual_skip_list = SKIP_LIST_DEFAULT
    else:
        actual_skip_list = skip_list

    # add the items we always want to skip
    actual_skip_list.extend(SKIP_LIST_ALWAYS)

    files = []

    if not os.path.exists(dst):
        os.mkdir(dst, folder_permissions)

    names = os.listdir(src)
    for name in names:

        # get rid of system files
        if name in actual_skip_list:
            continue

        srcname = os.path.join(src, name)
        dstname = os.path.join(dst, name)

        try:
            if os.path.isdir(srcname):
                files.extend(copy_folder(srcname, dstname, folder_permissions))
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


@with_cleared_umask
def move_folder(src, dst, folder_permissions=0775):
    """
    Moves a directory.

    First copies all content into target. Then deletes
    all content from sources. Skips files that won't delete.

    .. note::
        The source folder itself is not deleted, it is just emptied, if possible.

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


@with_cleared_umask
def backup_folder(src, dst=None):
    """
    Moves the given directory into a backup location.

    By default, the folder will be renamed by simply giving it a
    timestamp based suffix. Optionally, it can be moved into a different
    location.

    - ``backup_folder("/foo/bar")`` will move ``/foo/bar`` to ``/foo/bar.20160912_200426``
    - ``backup_folder("/foo/bar", "/tmp")`` will move ``/foo/bar`` to ``/tmp/bar.20160912_200426``

    :param src: Folder to move
    :param dst: Optional backup folder
    """
    if os.path.exists(src):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        if dst is None:
            backup_path = "%s.%s" % (src, timestamp)
        else:
            backup_path = os.path.join(dst, "%s.%s" % (os.path.basename(src), timestamp))
        move_folder(src, backup_path)


def create_valid_filename(value):
    """
    Create a sanitized file name given a string.
    Replaces spaces and other characters with underscores

    'my lovely name ' -> 'my_lovely_name'

    :param value: String value to sanitize
    :returns: sanitized string
    """
    # regex to find non-word characters - in ascii land, that is [^A-Za-z0-9_-.]
    # note that we use a unicode expression, meaning that it will include other
    # "word" characters, not just A-Z.
    exp = re.compile(u"[^\w\.-]", re.UNICODE)

    # strip trailing whitespace
    value = value.strip()

    if isinstance(value, unicode):
        # src is unicode, so return unicode
        return exp.sub("_", value)
    else:
        # source is non-unicode.
        # assume utf-8 encoding so decode, replace
        # and re-encode the returned result
        # so that we return a string
        u_src = value.decode("utf-8")
        return exp.sub("_", u_src).encode("utf-8")

def get_permissions(path):
    """
    Retrieve the file system permissions for the file or folder in the
    given path.

    :param filename: Path to the file to be queried for permissions
    :returns: permissions bits of the file 
    :raises: OSError - if there was a problem retrieving permissions for the path
    """
    return stat.S_IMODE(os.stat(path)[stat.ST_MODE])

def safe_delete_folder(path):
    """
    Deletes a folder and all of its contents recursively, even if it has read-only
    items. 

    .. note::
        Problems deleting any items will be reported as warnings in the log 
        output but otherwise ignored and skipped; meaning the function will continue
        deleting as much as it can.

    :param path: File system path to location to the folder to be deleted
    """

    def _on_rm_error(func, path, exc_info):
        """
        Error function called whenever shutil.rmtree fails to remove a file system
        item. Exceptions raised by this function will not be caught.
        
        :param func: The function which raised the exception; it will be: 
                     os.path.islink(), os.listdir(), os.remove() or os.rmdir().
        :param path: The path name passed to function.
        :param exc_info: The exception information return by sys.exc_info().
        """
        if func == os.unlink or func == os.remove or func == os.rmdir:
            try:
                attr = get_permissions(path)
                if not (attr & stat.S_IWRITE):
                    os.chmod(path, stat.S_IWRITE | attr)
                    try:
                        func(path)
                    except Exception, e:
                        log.warning("Could not delete %s: %s. Skipping" % (path, e))
                else:
                    log.warning("Could not delete %s: Skipping" % path)
            except Exception, e:
                log.warning("Could not delete %s: %s. Skipping" % (path, e))
        else:
            log.warning("Could not delete %s. Skipping." % path)

    if os.path.exists(path):
        try:
            # On Windows, Python's shutil can't delete read-only files, so if we were trying to delete one,
            # remove the flag.
            # Inspired by http://stackoverflow.com/a/4829285/1074536
            shutil.rmtree(path, onerror=_on_rm_error)
        except Exception, e:
            log.warning("Could not delete %s: %s" % (path, e))
    else:
        log.warning("Could not delete: %s. Folder does not exist" % path)

def get_unused_path(base_path):
    """
    Return an unused file path from the given base path by appending if needed
    a number at the end of the basename of the path, right before the first ".",
    if any.
    
    For example, "/tmp/foo_1.bar.blah" would be returned for "/tmp/foo.bar.blah"
    if it already exists.

    If the given path does not exist, the original path is returned.

    .. note::
        The returned path is not _reserved_, so it is possible that other processes
        could create the returned path before it is used by the caller.

    :param str base_path: Target path.
    :returns: A string.
    """
    if not os.path.exists(base_path):
        # Bail out quickly if everything is fine with the path
        return base_path

    # Split the base path and find an unused path
    folder, basename = os.path.split(base_path)
    # Split the basename at the first ".", if any. Make sure we always have at least
    # two entries.
    base_parts = basename.split(".", 1) + [""]
    numbering = 0
    while True:
        numbering += 1
        name = "%s_%d%s" % (
            base_parts[0], numbering, ".%s" % base_parts[1] if base_parts[1] else ""
        )
        path = os.path.join(folder, name)
        log.debug("Checking if %s exists..." % path)
        if not os.path.exists(path):
            break
    return path


