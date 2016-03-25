# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import argparse
from datetime import datetime
import os
import tempfile
from .action_base import Action
from ...errors import TankError
from ...platform import validation, bundle, environment
from tank_vendor.shotgun_base import (
    ensure_folder_exists,
    copy_file,
    safe_delete_file
)

class ValidateConfigAction(Action):
    """
    Action that looks at the config and validates all parameters
    """    
    def __init__(self):
        Action.__init__(self, 
                        "validate", 
                        Action.TK_INSTANCE, 
                        ("Validates your current Configuration to check that all "
                        "environments have been correctly configured."), 
                        "Configuration")
        
        # this method can be executed via the API
        self.supports_api = True

        # since the interactive and non-interactive calls run through the same
        # logic, we just keep track of this so that certain things like output
        # can be tweaked depending on the mode of execution.
        self._interactive = False

        self.parameters = {}

        self.parameters["envs"] = {
            "description": ("A list of environment names to process. If not "
                            "specified, process all environments."),
            "type": "list",
            "default": [],
        }

        self.parameters["dump"] = {
            "description": ("Dump fully evaluated copies of each validated "
                            "environment to the location specified by "
                            "dump location or a temp directory if no dump "
                            "location is specified."),
            "type": "bool",
            "default": False,
        }

        self.parameters["dump_sparse"] = {
            "description": ("Dump sparse copies of each validated environment "
                            "to the location specified by the dump location "
                            "or a temp directory if no dump location is "
                            "specified."),
            "type": "bool",
            "default": False,
        }

        self.parameters["dump_debug"] = {
            "description": "Add debug comments to the dumped environments.",
            "type": "bool",
            "default": False,
        }

        self.parameters["dump_location"] = {
            "description": ("The location to dump the environment configs when "
                            "using the 'dump' or 'dump-sparse' arguments."),
            "type": "str",
            "default": "",
        }


    def run_noninteractive(self, log, parameters):
        """
        Tank command API accessor. 
        Called when someone runs a tank command through the core API.
        
        :param log: std python logger
        :param parameters: dictionary with tank command parameters
        """

        # validate params and seed default values
        computed_params = self.__validate_parameters(parameters)

        return self._run(log, computed_params)
    
    def run_interactive(self, log, args):
        """
        Tank command accessor
        
        :param log: std python logger
        :param args: command line args
        """

        self._interactive = True

        parser = argparse.ArgumentParser(
            prog="./tank validate",
            description="Environment validation command."
        )

        # a list of environment names
        parser.add_argument(
            "envs",
            metavar="<env_name>",
            type=str,
            nargs="*",
            help=self.parameters["envs"]["description"],
        )

        # mutually exclusive dump types, full and sparse
        dump_type_group = parser.add_mutually_exclusive_group()
        dump_type_group.add_argument(
            "-f", "--dump",
            action="store_true",
            help=self.parameters["dump"]["description"],
        )
        dump_type_group.add_argument(
            "-s", "--dump-sparse",
            action="store_true",
            help=self.parameters["dump_sparse"]["description"],
        )

        # the output directory for the modified environment files
        parser.add_argument(
            "-l", "--dump-location",
            metavar="<output_directory>",
            type=str,
            help=self.parameters["dump_sparse"]["description"],
        )

        # turn on debug comments in the dumped environments
        parser.add_argument(
            "--dump-debug",
            action="store_true",
            help=self.parameters["dump_debug"]["description"],
        )

        # calling vars() on the returned namespace object essentially
        # translates it into a dictionary. In addition, argparse naturally
        # translates the flags we used to the matching parameters that
        # are defined by the action (ex: "--dump-debug" becomes "dump_debug").
        # so we're left with a dict that should look just like the params
        # supplied to the non-interactive version of this action.
        parsed_args = vars(parser.parse_args(args))

        # validate the parsed args just like the non-interactive params.
        computed_params = self.__validate_parameters(parsed_args)

        # do work.
        return self._run(log, computed_params)
        
    def _run(self, log, params):
        """
        Actual execution payload. Includes validation and optional dumping.

        :param log: A logger instance.
        :param params: A dict of parameters to drive the validation/dumping.
        :return:
        """

        log.info("")
        log.info("")
        log.info("Welcome to the Shotgun Pipeline Toolkit Configuration validator!")
        log.info("")
    
        try:
            env_names = self.tk.pipeline_configuration.get_environments()
        except Exception, e:
            raise TankError(
                "Could not find any environments for config %s: %s"
                % (self.tk, e)
            )

        # filter the envs if any were called out via the params.
        if params["envs"]:
            env_names = [n for n in env_names if n in params["envs"]]
            if not env_names:
                raise TankError(
                    "No matching environments found for '%s'." %
                    (", ".join(params["envs"]))
                )
    
        log.info("Found the following environments:")
        for x in env_names:
            log.info("    %s" % x)
        log.info("")
        log.info("")

        # validate environments
        envs = []
        for env_name in env_names:
            env = self.tk.pipeline_configuration.get_environment(env_name)
            _process_environment(log, self.tk, env)
            envs.append(env)

        if params["dump"] or params["dump_sparse"]:
            self._dump(log, envs, params)

        log.info("")
        log.info("")
        log.info("")
            
        # check templates that are orphaned
        unused_templates = set(self.tk.templates.keys()) - g_templates 
    
        log.info("")
        log.info("------------------------------------------------------------------------")
        log.info("The following templates are not being used directly in any environments:")
        log.info("(they may be used inside complex data structures)")
        for ut in unused_templates:
            log.info(ut)
    
        log.info("")
        log.info("")
        log.info("")
        
        # check hooks that are unused
        all_hooks = []
        # get rid of files not ending with .py and strip extension
        for hook in os.listdir(self.tk.pipeline_configuration.get_hooks_location()):
            if hook.endswith(".py"):
                all_hooks.append( hook[:-3] )
        
        unused_hooks = set(all_hooks) - g_hooks 
    
        log.info("")
        log.info("--------------------------------------------------------------------")
        log.info("The following hooks are not being used directly in any environments:")
        log.info("(they may be used inside complex data structures)")
        for uh in unused_hooks:
            log.info(uh)
        
        log.info("")
        log.info("")
        log.info("")

    def _dump(self, log, envs, params):
        """
        Dump the supplied environments with the specified parameters

        :param log: A logger instance.
        :param envs: list of environment objects
        :param params: parameter dict.
        """

        if params["dump_sparse"]:
            dump_type = environment.UpdateAllSettingsFormat.SPARSE
            dump_display_type = "sparse"
        else:
            dump_type = environment.UpdateAllSettingsFormat.FULL
            dump_display_type = "full"

        for env in envs:

            # build the full output path from the dump location directory
            # and the basename of the source environment file.
            output_path = os.path.abspath(
                os.path.join(params["dump_location"],
                os.path.basename(env.disk_location))
            )

            # make sure the output path doesn't match the environment path.
            # don't allow writing over existing environments.
            if output_path == env.disk_location:
                raise TankError(
                    "Dump locaiton matches the existing environment path. "
                    "Refusing to overwrite existing environment file."
                )

            # build a copy of the environment file that we can use to process.
            (filename, ext) = os.path.splitext(
                os.path.basename(env.disk_location)
            )
            tmp_env_path = os.path.join(
                os.path.dirname(env.disk_location),
                "%s_%s_%s_%s" % (
                    filename,
                    dump_display_type,
                    datetime.now().strftime("%Y_%m_%d_%H_%M_%s_%f"),
                    ext
                )
            )

            # now copy the environment file to the tmp file.
            copy_file(env.disk_location, tmp_env_path, 0666)

            try:
                # In order to dump an environment, we need a WritableEnvironment
                # instance. To prevent writing the current environment, we'll
                # use a copy of the environment file, process it, then copy it
                # to the output location. We'll also need to remove the
                # temporary copy of the environment. The temp copy is made in
                # the same location as the actual environment file in order to
                # allow relative includes to be handled correctly when parsed.
                tmp_env = environment.WritableEnvironment(
                    tmp_env_path,
                    self.tk.pipeline_configuration,
                    self.context
                )

                debug = params["dump_debug"]

                # Make the temp environment full or sparse. Each of these calls
                # will write the environment to disk.
                if dump_type == environment.UpdateAllSettingsFormat.SPARSE:
                    tmp_env.make_sparse(debug)
                else:
                    tmp_env.make_full(debug)

            finally:
                # copy the tmp env file to the output location
                copy_file(tmp_env_path, output_path, 0666)

                # remove the temporary dump file.
                safe_delete_file(tmp_env_path)

            log.info("Dumped modified environment to: %s" % (output_path,))


    def __validate_parameters(self, parameters):
        """
        Do validation of the parameters that arse specific to this action.

        :param parameters: The dict of parameters
        :returns: The validated and fully populated dict of parameters.
        """

        # do the base class default validation
        params = super(ValidateConfigAction, self)._validate_parameters(
            parameters)

        # need to dump something
        if params["dump"] or params["dump_sparse"]:

            # determine the dump location
            if params["dump_location"]:
                dump_dir = params["dump_location"]
            else:
                dump_dir = tempfile.gettempdir()

            # if it exists and is not a directory, that's no good. raise.
            if os.path.exists(dump_dir) and not os.path.isdir(dump_dir):
                raise TankError(
                    "The specified dump location already exists and is not a "
                    "directory. Please try again with a valid dump location."
                )

            # create the dump location if it doesn't exist
            ensure_folder_exists(dump_dir)

            # make sure the dump location is populated
            params["dump_location"] = dump_dir

        return params

g_templates = set()
g_hooks = set()

def _validate_bundle(log, tk, name, settings, descriptor, engine_name=None):
    """
    Given a bundle name and settings, make sure everything looks legit!

    :param log: A logger instance.
    :param tk: Toolkit API instance
    :param name: The name of the bundle.
    :param settings: The bundle's settings from the environment.
    :param descriptor: A descriptor for locating the bundle.
    :param engine_name: The engine Name if there is one.
    """

    log.info("")
    log.info("Validating %s..." % name)

    if not descriptor.exists_local():
        log.info("Please wait, downloading...")
        descriptor.download_local()
    
    # out of date check
    latest_desc = descriptor.find_latest_version()
    if descriptor.get_version() != latest_desc.get_version():
        log.info(  "WARNING: Latest version is %s. You are running %s." % (latest_desc.get_version(), 
                                                                        descriptor.get_version()))

    manifest = descriptor.get_configuration_schema()

    for s in settings.keys():
        if s not in manifest.keys():
            log.info("  WARNING - Parameter not needed: %s" % s)

    for s in manifest.keys():

        default = bundle.resolve_default_value(manifest[s], engine_name=engine_name)

        if s in settings:
            value = settings.get(s)
        else:
            value = default

        try:
            validation.validate_single_setting(name, tk, manifest, s, value)
        except TankError, e:
            log.info("  ERROR - Parameter %s - Invalid value: %s" % (s,e))
        else:
            # validation is ok
            if default is None:
                # no default value
                # don't report this
                pass

            elif manifest[s].get("type") == "hook" and value == "default":
                # don't display when default values are used.
                pass

            elif default == value:
                pass

            else:
                log.info("  Parameter %s - OK [using non-default value]" % s)
                log.info("    |---> Current: %s" % value)
                log.info("    \---> Default: %s" % default)

            # remember templates
            if manifest[s].get("type") == "template":
                g_templates.add(value)
            if manifest[s].get("type") == "hook":
                g_hooks.add(value)

                     
def _process_environment(log, tk, env):
    """Validate the supplied environment.

    :param log: A logger object for logging validation information.
    :param tk: Toolkit api instance
    :param env: An environment object.
    :return:
    """

    log.info("Processing environment %s" % env)

    for engine_name in env.get_engines():

        # get the engine details
        engine_settings = env.get_engine_settings(engine_name)
        engine_descriptor = env.get_engine_descriptor(engine_name)
        engine_display_name = "Engine %s / %s" % (env.name, engine_name)

        # validate the engine settings
        _validate_bundle(log, tk, engine_display_name, engine_settings,
            engine_descriptor, engine_name=engine_name)

        for app_name in env.get_apps(engine_name):

            # get the app details
            app_settings = env.get_app_settings(engine_name, app_name)
            app_descriptor = env.get_app_descriptor(engine_name, app_name)
            app_display_name = "%s / %s / %s" % (env.name, engine_name, app_name)

            # validate the app settings
            _validate_bundle(log, tk, app_display_name, app_settings,
                app_descriptor, engine_name=engine_name)
