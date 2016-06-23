# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import StringIO

from ..errors import TankError
from .action_base import Action
from ..util import filesystem

class DumpConfigAction(Action):
    """
    Action that dumps configs as full or sparse representations.
    """
    def __init__(self):
        Action.__init__(
            self,
            "dump_config",
            Action.TK_INSTANCE,
            ("Dump the specified config to a file or <stdout>."
             "If the `--file` option is not specified, the config will be "
             "written to stdout. The tank command itself also writes to "
             "<stdout> so be careful of redirecting to a file and expecting "
             "to use the config immediately. "
            ),
            "Configuration"
        )

        # this method can be executed via the API
        self.supports_api = True

        self._is_interactive = False

        self.parameters = {}

        self.parameters["env"] = {
            "description": "The name of environment to dump. (Required)",
            "type": "str",
            "default": [],
        }

        self.parameters["file"] = {
            "description": (
                "The path to a file to dump to. If not supplied, the command "
                "will write ot <stdout>."
            ),
            "type": "str",
            "default": "",
        }

        self.parameters["full"] = {
            "description": (
                "Dump the environment fully evaluated. All settings from the "
                "manifest will be included with a value."
            ),
            "type": "bool",
            "default": False,
        }

        self.parameters["sparse"] = {
            "description": (
                "Dump the environment sparsely. Settings from the manifest "
                "with default values will not be included."
            ),
            "type": "bool",
            "default": False,
        }

        self.parameters["no_debug_comments"] = {
            "description": (
                "Prevents debug comments from being included in the dumped "
                "environment (the default behavior). Note the debug comments "
                "only show up when using the new style yaml parser introduced "
                "in toolkit core v0.16.30."
            ),
            "type": "bool",
            "default": False,
        }

    def run_noninteractive(self, log, parameters):
        """
        Tank command API accessor.
        Called when someone runs a tank command through the core API.

        :param log: std python logger
        :param parameters: dictionary with tank command parameters
        """

        # validate params and seed default values
        return self._run(log, self._validate_parameters(parameters))

    def run_interactive(self, log, args):
        """
        Tank command accessor

        :param log: std python logger
        :param args: command line args
        """

        self._is_interactive = True

        parameters = {}

        # look for a --file argument
        parameters["file"] = ""
        for arg in args:
            if arg == "--file":
                print "\nUsage: %s\n" % (self._usage(),)
                raise TankError(
                    "Must specify a path: --file=/path/to/write/to.yml"
                )
            elif arg.startswith("--file="):
                # remove it from args list
                args.remove(arg)
                # from '--file=/path/to/my config' get '/path/to/my config'
                parameters["file"] = arg[len("--file="):]
                if parameters["file"] == "":
                    print "\nUsage: %s\n" % (self._usage(),)
                    raise TankError(
                        "Must specify a path: --file=/path/to/write/to.yml"
                    )

        # look for the full flag
        if "--full" in args:
            parameters["full"] = True
            args.remove("--full")
        else:
            parameters["full"] = False

        # look for the sparse flag
        if "--sparse" in args:
            parameters["sparse"] = True
            args.remove("--sparse")
        else:
            parameters["sparse"] = False

        # debug
        if "--no-debug-comments" in args:
            parameters["no_debug_comments"] = True
            args.remove("--no-debug-comments")
        else:
            parameters["no_debug_comments"] = False

        # if there are any options left, bail
        for arg in args:
            if arg.startswith("-"):
                print "\nUsage: %s\n" % (self._usage(),)
                raise TankError("Unknown argument: %s" % (arg,))

        # everything left should be the env argument
        parameters["env"] = " ".join(args)

        # do work after validating
        return self._run(log, self._validate_parameters(parameters))

    def _run(self, log, params):
        """
        Dump the supplied environment with the specified parameters

        :param log: A logger instance.
        :param params: parameter dict.
        """

        log.info("Dumping config...")

        # the env to dump
        env = self.tk.pipeline_configuration.get_environment(
            params["env"],
            writable=True
        )

        # make sure the environment file doesn't match the output file.
        # at some point we may want to make this possible, but dump_config is
        # more about debugging, so for now just error out if they're the same file.
        if params["file"]:
            out_file = os.path.realpath(params["file"])
            env_file = os.path.realpath(env.disk_location)

            if out_file == env_file:
                raise TankError(
                    "The specified output file matches the environment configuration.\n"
                    "As a precaution, writing to the source configuration is not allowed.\n"
                    "Please specify a different output path."
                )

        # get a file to write to
        env_fh = self._get_file_handle(params)

        # determine the transform to use when dumping
        if params["sparse"]:
            transform = env.STRIP_DEFAULTS
        elif params["full"]:
            transform = env.INCLUDE_DEFAULTS
        else:
            transform = env.NONE

        # map the command line debug comments arg to the expected arg.
        if params["no_debug_comments"]:
            include_debug_comments = False
        else:
            include_debug_comments = True

        try:
            env.dump(env_fh, transform, include_debug_comments)
            if not params["file"]:
                # no file, write the in-memory file contents to <stdout>
                print env_fh.getvalue()
        except Exception, e:
            import traceback
            traceback.print_exc()
            raise TankError(
                "There was a problem dumping the config: '%s'" % (e,)
            )
        finally:
            # all done, close the file handle
            env_fh.close()

    def _get_file_handle(self, params):
        """
        Returns a file handle to use for dumping.

        :param params: The command parameters dict.
        :return: An open file handle object.
        """

        if params["file"]:
            # open a real file handle to write to
            path = params["file"]
            dir = os.path.dirname(path)
            if not os.path.isdir(dir):
                try:
                    filesystem.ensure_folder_exists(dir)
                except OSError, e:
                    raise TankError(
                        "Unable to create directory: %s\n"
                        "  Error reported: %s" % (dir, e)
                    )
            try:
                fh = open(path, "w")
            except Exception, e:
                raise TankError(
                    "Unable to open file: %s\n"
                    "  Error reported: %s" % (path, e)
                )
        else:
            # get an in-memory file handle
            fh = StringIO.StringIO()

        return fh

    def _validate_parameters(self, parameters):
        """
        Do validation of the parameters that arse specific to this action.

        :param parameters: The dict of parameters
        :returns: The validated and fully populated dict of parameters.
        """

        # do the base class default validation
        parameters = super(DumpConfigAction, self)._validate_parameters(
            parameters)

        # make sure we don't have too many dump types
        if parameters["full"] and parameters["sparse"]:
            if self._is_interactive:
                print "\nUsage: %s\n" % (self._usage(),)
            raise TankError(
                "The 'full' and 'sparse' options are mutually exclusive.")

        # get a list of valid env names
        valid_env_names = self.tk.pipeline_configuration.get_environments()

        if parameters["env"] not in valid_env_names:
            if self._is_interactive:
                print "\nUsage: %s\n" % (self._usage(),)

            raise TankError(
                "Could not find an environment named: '%s'. "
                "Available environments are: %s." % (parameters["env"], ", ".join(valid_env_names)))

        return parameters

    def _usage(self):
        """Return a string displaying the usage of this command."""
        return "./tank dump_config env_name [--sparse | --full] [--debug-comments] [--file=/path/to/output/file.yml]"

