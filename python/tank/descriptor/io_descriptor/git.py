# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.
import json
import os
import shlex
import subprocess
import urllib.parse
from time import time
from typing import Optional, Union

from ... import LogManager
from ...util import filesystem, is_windows
from ...util.process import SubprocessCalledProcessError, subprocess_check_output
from ..errors import TankDescriptorError, TankError
from .downloadable import IODescriptorDownloadable

log = LogManager.get_logger(__name__)

# Seconds a `git ls-remote` result is reused before querying the remote again.
_LS_REMOTE_CACHE_TTL = 120
_ls_remote_cache = {}


def _check_output(*args, **kwargs):
    """
    Wraps the call to subprocess_check_output so it can run headless on Windows.
    """
    if is_windows():
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        kwargs["startupinfo"] = startupinfo

    return subprocess_check_output(*args, **kwargs)


def _sanitize_url(url: Optional[str]) -> Optional[str]:
    """
    Sanitizes a git URL by removing embedded credentials (username, password, or token).

    Examples:
        https://ghp_token123@github.com/org/repo.git
            -> https://***@github.com/org/repo.git

        https://user:pass@example.com/repo.git
            -> https://***@example.com/repo.git

        git@github.com:org/repo.git
            -> git@github.com:org/repo.git (no change for SSH URLs)

    :param url: Git URL that may contain embedded credentials
    :return: Sanitized URL with credentials replaced by ***
    """
    if not url:
        return url

    try:
        parsed = urllib.parse.urlparse(url)

        # If the URL has a username or password, replace them with ***
        if parsed.username or parsed.password:
            # Reconstruct the netloc with sanitized credentials
            sanitized_netloc = "***@" + parsed.hostname
            if parsed.port:
                sanitized_netloc += ":" + str(parsed.port)

            # Rebuild the URL with the sanitized netloc
            sanitized_url = urllib.parse.urlunparse(
                (
                    parsed.scheme,
                    sanitized_netloc,
                    parsed.path,
                    parsed.params,
                    parsed.query,
                    parsed.fragment,
                )
            )
            return sanitized_url
    except Exception:
        # Best-effort sanitization for malformed URLs that still contain userinfo
        if "://" in url:
            scheme, rest = url.split("://", 1)
            if "@" in rest:
                # Only sanitize if '@' appears before any '/'
                at_pos = rest.find("@")
                slash_pos = rest.find("/")
                if slash_pos == -1 or at_pos < slash_pos:
                    after_at = rest.split("@", 1)[1]
                    return "%s://***@%s" % (scheme, after_at)

    return url


def _sanitize_command(cmd: Union[str, list]) -> Union[str, list]:
    """
    Sanitizes a git command (string or list) by replacing credentials in any URLs.

    :param cmd: Command as a string or list of arguments
    :return: Sanitized command in the same format as input
    """
    if isinstance(cmd, list):
        return [_sanitize_url(arg) if isinstance(arg, str) else arg for arg in cmd]
    elif isinstance(cmd, str):
        # For string commands, we need to be more careful
        # Split on spaces but preserve quoted strings

        try:
            # Try to parse as shell command
            parts = shlex.split(cmd)
            sanitized_parts = [_sanitize_url(part) for part in parts]
            # Rebuild with proper quoting
            return " ".join(
                '"%s"' % part if " " in part else part for part in sanitized_parts
            )
        except Exception:
            # If parsing fails, do simple replacement
            # This is a fallback for malformed commands
            words = cmd.split()
            return " ".join(_sanitize_url(word) for word in words)
    return cmd


def _sanitize_exception(
    exc: SubprocessCalledProcessError, url_to_sanitize: Optional[str] = None
) -> SubprocessCalledProcessError:
    """
    Sanitizes a SubprocessCalledProcessError by replacing credentials in the command and output.

    :param exc: SubprocessCalledProcessError exception
    :param url_to_sanitize: Optional URL to specifically sanitize (if known)
    :return: New exception with sanitized command and output
    """
    if not isinstance(exc, SubprocessCalledProcessError):
        return exc

    sanitized_cmd = _sanitize_command(exc.cmd)

    # Sanitize the output as well, as it may contain URLs with credentials
    sanitized_output = exc.output
    if exc.output:
        if isinstance(exc.output, bytes):
            try:
                output_str = exc.output.decode("utf-8")
                # Sanitize any URLs in the output
                if url_to_sanitize:
                    output_str = output_str.replace(
                        url_to_sanitize, _sanitize_url(url_to_sanitize)
                    )
                # Also try to find and sanitize any URL patterns
                import re

                output_str = re.sub(
                    r"https?://[^@\s]+@[^\s]+",
                    lambda m: _sanitize_url(m.group(0)),
                    output_str,
                )
                sanitized_output = output_str.encode("utf-8")
            except (UnicodeDecodeError, AttributeError):
                sanitized_output = exc.output
        elif isinstance(exc.output, str):
            output_str = exc.output
            if url_to_sanitize:
                output_str = output_str.replace(
                    url_to_sanitize, _sanitize_url(url_to_sanitize)
                )
            # Also try to find and sanitize any URL patterns
            import re

            output_str = re.sub(
                r"https?://[^@\s]+@[^\s]+",
                lambda m: _sanitize_url(m.group(0)),
                output_str,
            )
            sanitized_output = output_str

    # Create a new exception with the sanitized command and output
    new_exc = SubprocessCalledProcessError(
        exc.returncode, sanitized_cmd, output=sanitized_output
    )
    return new_exc


class TankGitError(TankError):
    """
    Errors related to git communication
    """

    pass


class IODescriptorGit(IODescriptorDownloadable):
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
        super().__init__(descriptor_dict, sg_connection, bundle_type)

        # strip trailing slashes so os.path.basename builds the name correctly
        self._path = descriptor_dict.get("path").rstrip("/\\")

        if "version" not in descriptor_dict:
            local_repo = self._normalize_path(self._path)
            if self._path_is_local(local_repo):
                descriptor_dict.update(
                    {
                        k: v
                        for k, v in self._fetch_local_data(local_repo).items()
                        if k not in descriptor_dict
                    }
                )

    def is_git_available(self):
        log.debug("Checking that git exists and can be executed...")

        if is_windows():
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

        log.debug(
            "Executing command '%s' using subprocess module."
            % _sanitize_command(commands)
        )

        # It's important to pass GIT_TERMINAL_PROMPT=0 or the git subprocess will
        # just hang waiting for credentials to be entered on the missing terminal.
        # I would have expected Windows to give an error about stdin being close and
        # aborting the git command but at least on Windows 10 that is not the case.
        environ = os.environ.copy()
        environ["GIT_TERMINAL_PROMPT"] = "0"

        try:
            output = _check_output(commands, env=environ)
        except SubprocessCalledProcessError as e:
            sanitized_exc = _sanitize_exception(e, self._path)
            raise TankGitError(
                "Error executing git operation '%s': %s (Return code %s)"
                % (
                    sanitized_exc.cmd,
                    sanitized_exc.output,
                    sanitized_exc.returncode,
                )
            ) from sanitized_exc
        else:
            output = output.strip().strip("'")
            log.debug("Execution successful.")
            return output

    def _ls_remote(
        self, options: list, refs: Optional[list] = None, use_cache: bool = True
    ) -> str:
        """
        Runs ``git ls-remote`` against this repository, reusing a recent result
        for the same query instead of contacting the remote again.

        :param options: Options passed to ``git ls-remote``, e.g. ``["--tags"]``.
        :param refs: Optional ref patterns to restrict the query to.
        :param use_cache: Whether a recent result may be reused.
        :returns: The command output.
        """
        cmd = ["git", "ls-remote", *options, self._path, *(refs or [])]
        key = tuple(cmd)
        cached = _ls_remote_cache.get(key)
        if use_cache and cached and time() - cached[0] < _LS_REMOTE_CACHE_TTL:
            return cached[1]

        output = self._execute_git_commands(cmd)
        _ls_remote_cache[key] = (time(), output)
        return output

    def __repr__(self):
        """
        Low level representation with sanitized credentials.
        """
        class_name = self.__class__.__name__
        # Create a sanitized copy of the descriptor dict with credentials removed
        sanitized_dict = self._descriptor_dict.copy()
        if "path" in sanitized_dict:
            sanitized_dict["path"] = _sanitize_url(sanitized_dict["path"])
        sanitized_uri = self.uri_from_dict(sanitized_dict)
        return "<%s %s>" % (class_name, sanitized_uri)

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
        filesystem.ensure_folder_exists(parent_folder)

        # Make sure all git commands are correct according to the descriptor type
        cmd = self._get_git_clone_commands(
            target_path, depth=depth, ref=ref, is_latest_commit=is_latest_commit
        )
        self._execute_git_commands(cmd)

        output = None
        if commands:
            full_commands = ["git", "-C", os.path.normpath(target_path)]
            full_commands.extend(commands)
            output = self._execute_git_commands(full_commands)

        self._validate_lfs_content(target_path)

        return output

    def _validate_lfs_content(self, repo_path: str) -> None:
        """
        Checks that Git LFS tracked files in the checked out repo were
        actually resolved to their real content, rather than left as
        literal pointer text. This happens silently when git-lfs isn't
        installed/registered on this machine - git checks out the pointer
        text with no error of its own.

        :param repo_path: path to a checked out git repository.
        :raises TankGitError: if the repo uses Git LFS but git-lfs isn't
            available, or some LFS content wasn't downloaded.
        """
        gitattributes_path = os.path.join(repo_path, ".gitattributes")
        try:
            with open(gitattributes_path, "r") as fh:
                uses_lfs = "filter=lfs" in fh.read()
        except OSError:
            uses_lfs = False

        if not uses_lfs:
            return

        try:
            output = _check_output(
                "git lfs ls-files --json",
                cwd=repo_path,
                shell=True,
            )
        except SubprocessCalledProcessError as err:
            raise TankGitError(
                f"{self} uses Git LFS to store some of its files, but git-lfs "
                "does not appear to be installed on this machine. Install "
                "it from https://git-lfs.com, run `git lfs install`, and "
                "try again."
            ) from err

        files = json.loads(output).get("files") or []
        missing = [f["name"] for f in files if not f.get("checkout")]
        if missing:
            raise TankGitError(
                "Git LFS content for the following file(s) in %s was not "
                "downloaded correctly - they still contain pointer text "
                "instead of their real content: %s. Make sure git-lfs is "
                "installed (https://git-lfs.com) and run `git lfs install`, "
                "then try again." % (self, ", ".join(missing))
            )

    def get_system_name(self):
        """
        Returns a short name, suitable for use in configuration files
        and for folders on disk, e.g. 'tk-maya'
        """
        bn = os.path.basename(self._path)
        name, ext = os.path.splitext(bn)
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
        except Exception as e:
            # Sanitize any credentials that might be in the exception
            if isinstance(e, SubprocessCalledProcessError):
                e = _sanitize_exception(e, self._path)
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
        filesystem.copy_folder(self.get_path(), target_path, skip_list=skip_list or [])

    def _normalize_path(self, path):
        if path.endswith("/") or path.endswith("\\"):
            new_path = path[:-1]
        else:
            new_path = path

        if os.path.isdir(new_path):
            if not new_path.endswith(".git"):
                new_path = os.path.join(new_path, ".git")

        return new_path

    def _path_is_local(self, path):
        """
        Check if path value is an existing folder, and if contain a .git folder.
        """
        if os.path.isdir(path):
            output = self._execute_git_commands(
                [
                    "git",
                    "-C",
                    os.path.normpath(path),
                    "rev-parse",
                    "--git-dir",
                ]
            )
            if output.startswith("fatal: not a git repository"):
                raise TankDescriptorError(
                    "Folder is not a git repository: {}".format(path)
                )
            elif output == ".":
                return True

        return False

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
            depth = None

        cmd = ["git", "clone", "--no-hardlinks", "-q"]

        if ref:
            cmd.extend(["-b", str(ref)])

        if depth:
            cmd.extend(["--depth", str(depth)])

        cmd.append(self._path)
        cmd.append(os.path.normpath(target_path))

        return cmd

    def _fetch_local_data(self, path):
        return {}
