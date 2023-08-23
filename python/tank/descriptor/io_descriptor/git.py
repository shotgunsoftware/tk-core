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
import platform
import shutil
import subprocess

from time import time

from .downloadable import IODescriptorDownloadable
from ... import LogManager
from ...util.process import subprocess_check_output, SubprocessCalledProcessError

from ..errors import TankError
from ...util import is_windows

log = LogManager.get_logger(__name__)
IS_WINDOWS = platform.system() == "Windows"


def _can_hide_terminal():
    """
    Ensures this version of Python can hide the terminal of a subprocess
    launched with the subprocess module.
    """
    try:
        # These values are not defined between Python 2.6.6 and 2.7.1 inclusively.
        subprocess.STARTF_USESHOWWINDOW
        subprocess.SW_HIDE
        return True
    except AttributeError as e:
        log.debug("Terminal cant be hidden: %s" % e)
        return False


def _check_output(*args, **kwargs):
    """
    Wraps the call to subprocess_check_output so it can run headless on Windows.
    """
    if is_windows() and _can_hide_terminal():
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        kwargs["startupinfo"] = startupinfo

    return subprocess_check_output(*args, **kwargs)


class TankGitError(TankError):
    """
    Errors related to git communication
    """

    pass


class _IODescriptorGitCache(type):
    """Use as metaclass. Caches object instances for 2min."""

    _instances = {}

    def __call__(cls, descriptor_dict, sg_connection, bundle_type):
        now = int(time() / 100)
        floored_time = now - now % 2  # Cache is valid for 2min

        if (
            descriptor_dict["type"] == "git_branch"
        ):  # cant fetch last commit here, too soon
            version = descriptor_dict.get("version") or descriptor_dict["branch"]
        else:
            version = descriptor_dict["version"]

        id_ = "{}-{}-{}".format(
            descriptor_dict["type"], descriptor_dict["path"], version
        )

        cached_time, self = cls._instances.get(id_, (-1, None))
        if cached_time < floored_time:
            log.debug(
                "{} {} cache expired: cachedTime:{}".format(self, id_, cached_time)
            )
            self = super().__call__(descriptor_dict, sg_connection, bundle_type)
            cls._instances[id_] = (floored_time, self)

        return self


class IODescriptorGit(IODescriptorDownloadable, metaclass=_IODescriptorGitCache):
    """
    Base class for git descriptors.

    Abstracts operations around repositories, since all git
    descriptors have a repository associated (via the 'path'
    parameter).
    """

    def __init__(self, descriptor_dict, sg_connection, bundle_type):
        """
        Constructor

        :param descriptor_dict: descriptor dictionary describing the bundle
        :param sg_connection: Shotgun connection to associated site.
        :param bundle_type: Either AppDescriptor.APP, CORE, ENGINE or FRAMEWORK.
        :return: Descriptor instance
        """
        super(IODescriptorGit, self).__init__(
            descriptor_dict, sg_connection, bundle_type
        )

        self._path = descriptor_dict.get("path")
        # strip trailing slashes - this is so that when we build
        # the name later (using os.basename) we construct it correctly.
        if self._path.endswith("/") or self._path.endswith("\\"):
            self._path = self._path[:-1]

    def is_git_available(self):
        log.debug("Checking that git exists and can be executed...")

        if IS_WINDOWS:
            cmd = "where"
        else:
            cmd = "which"

        try:
            output = _check_output([cmd, "git"])
        except SubprocessCalledProcessError:
            raise TankGitError(
                "Cannot execute the 'git' command. Please make sure that git is "
                "installed on your system and that the git executable has been added to the PATH."
            )
        else:
            log.debug("Git installed: %s" % output)
            return True

    def _execute_git_commands(self, commands):
        # first probe to check that git exists in our PATH
        self.is_git_available()

        if not isinstance(commands, str):
            str_cmd = " ".join(commands)
        else:
            str_cmd = commands

        log.debug("Executing command '%s' using subprocess module." % str_cmd)

        # It's important to pass GIT_TERMINAL_PROMPT=0 or the git subprocess will
        # just hang waiting for credentials to be entered on the missing terminal.
        # I would have expected Windows to give an error about stdin being close and
        # aborting the git command but at least on Windows 10 that is not the case.
        environ = os.environ.copy()
        environ["GIT_TERMINAL_PROMPT"] = "0"

        try:
            output = _check_output(commands, env=environ)
        except SubprocessCalledProcessError as e:
            raise TankGitError(
                "Error executing git operation '%s': %s (Return code %s)"
                % (str_cmd, e.output, e.returncode)
            )
        else:
            output = output.strip().strip("'")
            log.debug("Execution successful. stderr/stdout: '%s'" % output)
            return output

    @LogManager.log_timing
    def _clone_then_execute_git_commands(
        self, target_path, commands, depth=None, ref=None, is_latest_commit=None
    ):
        """
        Clones the git repository into the given location and
        executes the given list of git commands::

            # this will clone the associated git repo into
            # /tmp/foo and then execute the given commands
            # in order in a shell environment
            commands = [
                "checkout -q my_feature_branch",
                "reset -q --hard -q a6512356a"
            ]
            self._clone_then_execute_git_commands("/tmp/foo", commands)

        The initial clone operation happens via the subprocess module, ensuring
        there is no terminal that will pop for credentials, leading to a more
        seamless experience. If the operation failed, we try a second time with
        os.system, ensuring that there is an initialized shell environment, allowing
        git to potentially request shell based authentication for repositories
        which require credentials.

        The subsequent list of commands are intended to be executed on the
        recently cloned repository and will the cwd will be set so that they
        are executed in the directory scope of the newly cloned repository.

        :param target_path: path to clone into
        :param commands: list git commands to execute, e.g. ['checkout x']
        :param depth: depth of the clone, allows shallow clone
        :param ref: git ref to checkout - it can be commit, tag or branch
        :returns: stdout and stderr of the last command executed as a string
        :raises: TankGitError on git failure
        """
        # ensure *parent* folder exists
        parent_folder = os.path.dirname(target_path)
        os.makedirs(parent_folder, exist_ok=True)

        # Make sure all git commands are correct according to the descriptor type
        cmd = self._get_git_clone_commands(
            target_path, depth=depth, ref=ref, is_latest_commit=is_latest_commit
        )
        self._execute_git_commands(cmd)

        if commands:
            full_commands = ["git", "-C", os.path.normpath(target_path)]
            full_commands.extend(commands)

            return self._execute_git_commands(full_commands)

    def get_system_name(self):
        """
        Returns a short name, suitable for use in configuration files
        and for folders on disk, e.g. 'tk-maya'
        """
        bn = os.path.basename(self._path)
        (name, ext) = os.path.splitext(bn)
        return name

    def has_remote_access(self):
        """
        Probes if the current descriptor is able to handle
        remote requests. If this method returns, true, operations
        such as :meth:`download_local` and :meth:`get_latest_version`
        can be expected to succeed.

        :return: True if a remote is accessible, false if not.
        """
        # check if we can clone the repo
        can_connect = True
        try:
            log.debug("%r: Probing if a connection to git can be established..." % self)
            self._execute_git_commands(["git", "ls-remote", "--heads", self._path])
            log.debug("...connection established")
        except (OSError, SubprocessCalledProcessError) as e:
            log.debug("...could not establish connection: %s" % e)
            can_connect = False
        return can_connect

    def _copy(self, target_path, skip_list=None):
        """
        Copy the contents of the descriptor to an external location

        Subclassed git implementation which includes .git folders
        in the copy, unless they are specifically skipped by the skip_list.

        :param target_path: target path to copy the descriptor to.
        :param skip_list: List of folders or files that should not be copied into the destination.

        .. note::
            The folders or files specified must be at the root of the bundle.
        """
        log.debug("Copying %r -> %s" % (self, target_path))
        # make sure item exists locally
        self.ensure_local()
        # copy descriptor into target.
        shutil.copytree(self.get_path(),
                        target_path,
                        ignore=shutil.ignore_patterns(*(skip_list or [])),
                        dirs_exist_ok=True)

    def _get_git_clone_commands(
        self, target_path, depth=None, ref=None, is_latest_commit=None
    ):
        """
        Validate that git commands are correct according to the descriptor type
        avoiding shallow git clones when tracking against commits in a git branch.
        :param target_path: path to clone into
        :param depth: depth of the clone, allows shallow clone
        :param ref: git ref to checkout - it can be commit, tag or branch
        :returns: str git commands to execute
        """
        # Note: git doesn't like paths in single quotes when running on
        # windows - it also prefers to use forward slashes
        #
        # Also note - we are adding a --no-hardlinks flag here to ensure that
        # when a github repo resides locally on a drive, git isn't trying
        # to be clever and utilize hard links to save space - this can cause
        # complications in cleanup scenarios and with file copying. We want
        # each repo that we clone to be completely independent on a filesystem level.
        log.debug("Git Cloning %r into %s" % (self, target_path))

        if self._descriptor_dict.get("type") == "git_branch" and not is_latest_commit:
            depth = ""
        else:
            depth = "--depth {}".format(depth) if depth else ""

        ref = "-b {}".format(ref) if ref else ""
        cmd = 'git clone --no-hardlinks -q "{}" {} "{}" {}'.format(
            self._path, ref, target_path, depth
        )

        return cmd
