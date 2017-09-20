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
import uuid
import shutil
import tempfile
import subprocess

from .base import IODescriptorBase
from ... import LogManager
from ...util.process import subprocess_check_output, SubprocessCalledProcessError

from ..errors import TankError
from ...util import filesystem

log = LogManager.get_logger(__name__)

class TankGitError(TankError):
    """
    Errors related to git communication
    """
    pass


class IODescriptorGit(IODescriptorBase):
    """
    Base class for git descriptors.

    Abstracts operations around repositories, since all git
    descriptors have a repository associated (via the 'path'
    parameter).
    """

    def __init__(self, descriptor_dict):
        """
        Constructor

        :param descriptor_dict: descriptor dictionary describing the bundle
        :return: Descriptor instance
        """
        super(IODescriptorGit, self).__init__(descriptor_dict)

        self._path = descriptor_dict.get("path")
        # strip trailing slashes - this is so that when we build
        # the name later (using os.basename) we construct it correctly.
        if self._path.endswith("/") or self._path.endswith("\\"):
            self._path = self._path[:-1]

        # Note: the git command always uses forward slashes
        self._sanitized_repo_path = self._path.replace(os.path.sep, "/")

    @LogManager.log_timing
    def _clone_then_execute_git_commands(self, target_path, commands):
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

        The initial clone operation happens via an `os.system` call, ensuring
        that there is an initialized shell environment, allowing git
        to potentially request shell based authentication for repositories
        which require credentials.

        The subsequent list of commands are intended to be executed on the
        recently cloned repository and will the cwd will be set so that they
        are executed in the directory scope of the newly cloned repository.

        :param target_path: path to clone into
        :param commands: list git commands to execute, e.g. ['checkout x']
        :returns: stdout and stderr of the last command executed as a string
        :raises: TankGitError on git failure
        """
        # ensure *parent* folder exists
        parent_folder = os.path.dirname(target_path)
        filesystem.ensure_folder_exists(parent_folder)

        # first probe to check that git exists in our PATH
        log.debug("Checking that git exists and can be executed...")
        try:
            output = subprocess_check_output(["git", "--version"])
        except:
            raise TankGitError(
                "Cannot execute the 'git' command. Please make sure that git is "
                "installed on your system and that the git executable has been added to the PATH."
            )
        log.debug("Git installed: %s" % output)

        # Note: git doesn't like paths in single quotes when running on
        # windows - it also prefers to use forward slashes
        log.debug("Git Cloning %r into %s" % (self, target_path))
        cmd = "git clone -q \"%s\" \"%s\"" % (self._path, target_path)

        # Note that we use os.system here to allow for git to pop up (in a terminal
        # if necessary) authentication prompting. This DOES NOT seem to be possible
        # with subprocess.
        status = os.system(cmd)
        if status != 0:
            raise TankGitError(
                "Error executing git operation. The git command '%s' "
                "returned error code %s." % (cmd, status)
            )
        log.debug("Git clone into '%s' successful." % target_path)

        # clone worked ok! Now execute git commands on this repo
        cwd = os.getcwd()
        output = None
        try:
            log.debug("Setting cwd to '%s'" % target_path)
            os.chdir(target_path)
            for command in commands:

                full_command = "git %s" % command
                log.debug("Executing '%s'" % full_command)

                try:
                    output = subprocess_check_output(
                        full_command,
                        shell=True
                    )

                    # note: it seems on windows, the result is sometimes wrapped in single quotes.
                    output = output.strip().strip("'")

                except SubprocessCalledProcessError, e:
                    raise TankGitError(
                        "Error executing git operation '%s': %s (Return code %s)" % (full_command, e.output, e.returncode)
                    )
                log.debug("Execution successful. stderr/stdout: '%s'" % output)

        finally:
            log.debug("Restoring cwd (to '%s')" % cwd)
            os.chdir(cwd)

        # return the last returned stdout/stderr
        return output

    def _tmp_clone_then_execute_git_commands(self, commands):
        """
        Clone into a temp location and executes the given
        list of git commands.

        For more details, see :meth:`_clone_then_execute_git_commands`.

        :param commands: list git commands to execute, e.g. ['checkout x']
        :returns: stdout and stderr of the last command executed as a string
        """
        clone_tmp = os.path.join(tempfile.gettempdir(), "sgtk_clone_%s" % uuid.uuid4().hex)
        filesystem.ensure_folder_exists(clone_tmp)
        try:
            return self._clone_then_execute_git_commands(clone_tmp, commands)
        finally:
            log.debug("Cleaning up temp location '%s'" % clone_tmp)
            shutil.rmtree(clone_tmp, ignore_errors=True)

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
            # clone repo into temp folder
            self._tmp_clone_then_execute_git_commands([])
            log.debug("...connection established")
        except Exception, e:
            log.debug("...could not establish connection: %s" % e)
            can_connect = False
        return can_connect

    def _copy(self, target_path):
        """
        Copy the contents of the descriptor to an external location

        Subclassed git implementation which includes .git folders
        in the copy.

        :param target_path: target path to copy the descriptor to.
        """
        log.debug("Copying %r -> %s" % (self, target_path))
        # make sure item exists locally
        self.ensure_local()
        # copy descriptor into target.
        # the skip list contains .git folders by default, so pass in []
        # to turn that restriction off. In the case of the git descriptor,
        # we want to transfer this folder as well.
        filesystem.copy_folder(
            self.get_path(),
            target_path,
            skip_list=[]
        )
