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

        self.parameters = {}

        self.parameters["envs"] = {
            "description": ("A list of environment names to process. If not "
                            "specified, process all environments."),
            "type": "list",
            "default": [],
        }
        
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
        return self._run(log, self._validate_parameters(parameters))
    
    def run_interactive(self, log, args):
        """
        Tank command accessor
        
        :param log: std python logger
        :param args: command line args
        """

        # currently, environment names are passed in as arguments for
        # validation. Just translate the args to the env list and validate them
        return self._run(log, self._validate_parameters({"envs": args}))

    def _run(self, log, parameters):
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
    
        log.info("Found the following environments:")
        for x in parameters["envs"]:
            log.info("    %s" % x)
        log.info("")
        log.info("")

        # validate environments
        for env_name in parameters["envs"]:
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

    def _validate_parameters(self, parameters):
        """
        Do validation of the parameters that are specific to this action.

        :param parameters: The dict of parameters
        :returns: The validated and fully populated dict of parameters.
        """

        # do the base class default validation
        params = super(ValidateConfigAction, self)._validate_parameters(
            parameters)

        # get a list of valid env names
        valid_env_names = self.tk.pipeline_configuration.get_environments()

        bad_env_names = []
        env_names_to_process = []
        if parameters["envs"]:
            # some environment names supplied on the command line
            for env_param in parameters["envs"]:
                # see if this is a comma separated list
                for env_name in env_param.split(","):
                    env_name = env_name.strip()
                    if env_name in valid_env_names:
                        env_names_to_process.append(env_name)
                    else:
                        bad_env_names.append(env_name)
        else:
            # nothing specified. process all
            env_names_to_process = valid_env_names

        # bail if any bad env names
        if bad_env_names:
            raise TankError(
                "Error retrieving environments mathing supplied arguments: %s"
                % (", ".join(bad_env_names),)
            )

        parameters["envs"] = sorted(env_names_to_process)

        return params
        
g_templates = set()
g_hooks = set()


def _validate_bundle(log, tk, name, settings, descriptor, engine_name=None):
    """Validate the supplied bundle including the descriptor and all settings.
    :param log: A logger instance for logging validation output.
    :param tk: A toolkit api instance.
    :param name: The bundle's name.
    :param settings: The bundle's settings dict.
    :param descriptor: A descriptor object for the bundle.
    :param engine_name: The name of the containing engine or None.
        This is used when the bundle is an app and needs to validate engine-
        specific settings.
    """

    log.info("")
    log.info("Validating %s..." % name)

    if not descriptor.exists_local():
        log.info("Please wait, downloading...")
        descriptor.download_local()

    #if len(descriptor.get_required_frameworks()) > 0:
    #    log.info("  Using frameworks: %s" % descriptor.get_required_frameworks())

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
    """Process an environment by validating each of its bundles.
    :param log: A logger instance for logging validation output.
    :param tk: A toolkit api instance.
    :param env: An environment instance.
    """

    log.info("Processing environment %s" % env)

    for e in env.get_engines():
        s = env.get_engine_settings(e)
        descriptor = env.get_engine_descriptor(e)
        name = "Engine %s / %s" % (env.name, e)
        _validate_bundle(log, tk, name, s, descriptor, engine_name=e)
        for a in env.get_apps(e):
            s = env.get_app_settings(e, a)
            descriptor = env.get_app_descriptor(e, a)
            name = "%s / %s / %s" % (env.name, e, a)
            _validate_bundle(log, tk, name, s, descriptor, engine_name=e)

