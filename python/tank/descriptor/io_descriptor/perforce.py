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
import subprocess

from .downloadable import IODescriptorDownloadable
from ... import LogManager
from ...util.process import subprocess_check_output, SubprocessCalledProcessError

from ..errors import TankError
from ...util import filesystem
from ...util import is_windows

log = LogManager.get_logger(__name__)


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
    except Exception:
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


class TankPerforceError(TankError):
    """
    Errors related to p4 communication
    """

    pass


class IODescriptorPerforce(IODescriptorDownloadable):
    """
    Base class for perforce descriptors.

    Abstracts operations around depots, since all p4
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

        self._cache_type = "perforce"

        super(IODescriptorPerforce, self).__init__(
            descriptor_dict, sg_connection, bundle_type
        )

        self._path = descriptor_dict.get("path")
        # Expand environment variables for depot roots
        self._path = os.path.expandvars(self._path)
        self._path = os.path.expanduser(self._path)

        # strip trailing slashes - this is so that when we build
        # the name later (using os.basename) we construct it correctly.
        if self._path.endswith("/") or self._path.endswith("\\"):
            self._path = self._path[:-1]

    @LogManager.log_timing
    def execute_p4_commands(self, target_path, commands):
        """
        Downloads the depot path into the given location

        The initial sync operation happens via the subprocess module, ensuring
        there is no terminal that will pop for credentials, leading to a more
        seamless experience. If the operation failed, we try a second time with
        os.system, ensuring that there is an initialized shell environment

        :param target_path: path to clone into
        :param commands: list p4 commands to execute, e.g. ['p4 x']
        :returns: stdout and stderr of the last command executed as a string
        :raises: TankPerforceError on p4 failure
        """
        # ensure *parent* folder exists
        parent_folder = os.path.dirname(target_path)

        filesystem.ensure_folder_exists(parent_folder)

        # first probe to check that p4 exists in our PATH
        log.debug("Checking that p4 exists and can be executed...")
        try:
            output = _check_output(["p4", "info"])
        except:
            log.exception("Unexpected error:")
            raise TankPerforceError(
                "Cannot execute the 'p4' command. Please make sure that p4 is "
                "installed on your system."
            )

        run_with_os_system = True

        output = None
        if is_windows() and _can_hide_terminal():
            log.debug("Executing command '%s' using subprocess module." % commands)
            try:
                environ = {}
                environ.update(os.environ)
                output = _check_output(commands, env=environ)

                log.debug(f"p4 output {output}")

                # If that works, we're done and we don't need to use os.system.
                run_with_os_system = False
                status = 0
            except SubprocessCalledProcessError:
                log.debug("Subprocess call failed.")

        if run_with_os_system:
            # Make sure path and repo path are quoted.
            log.debug("Executing command '%s' using os.system" % commands)
            log.debug(
                "Note: in a terminal environment, this may prompt for authentication"
            )
            status = os.system(" ".join(commands))

        log.debug("Command returned exit code %s" % status)
        if status != 0:
            raise TankPerforceError(
                "Error executing p4 operation. The p4 command '%s' "
                "returned error code %s." % (commands, status)
            )
        log.debug("P4 print into '%s' successful." % target_path)

        # return the last returned stdout/stderr
        return output

    def _download_local(self, destination_path):
        """
        Retrieves this version to from the depot
        Will exit early if app already exists local.

        This will connect to p4 depot.
        The p4 depot path will be downloaded at the descriptor version (changelist or label)

        :param destination_path: The destination path on disk to which
        the p4 depot path is to be downloaded to.
        """
        try:
            # Use perforce print to download the files without requiring
            # workspace setup. Applies the path format to download from
            # a depot path to a folder at the specified change or label.
            destination_path = destination_path.replace("\\", "/")
            commands = ["p4", "print", "-o", destination_path + "/...", f"{self._path}/...@{self._version}"]
            self.execute_p4_commands(destination_path, commands)

        except Exception as e:
            raise TankPerforceError(
                "Could not download %s, "
                "commit %s: %s" % (self._path, self._version, e)
            )

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
            log.debug("%r: Probing if a connection to p4 can be established..." % self)
            # clone repo into temp folder
            subprocess.check_output(["p4", "info"])
            log.debug("...connection established")
        except Exception as e:
            log.debug("...could not establish connection: %s" % e)
            can_connect = False
        return can_connect

    def _get_bundle_cache_path(self, bundle_cache_root):
        """
        Given a cache root, compute a cache path suitable
        for this descriptor, using the 0.18+ path format.

        :param bundle_cache_root: Bundle cache root path
        :return: Path to bundle cache location
        """
        # If the descriptor is an integer change the version to a string type
        if isinstance(self._version, int):
            self._version = str(self._version)

        name = os.path.basename(self._path)

        return os.path.join(bundle_cache_root, self._cache_type, name, self._version)
