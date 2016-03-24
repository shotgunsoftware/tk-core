# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import errno
import os
import tempfile
from .action_base import Action
from ...errors import TankError
from ...platform import validation, bundle


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

        self.parameters = {}

        self.parameters["dump"] = {
            "description": ("Dump fully evaluated copies of each validated "
                            "environment to the location specified by "
                            "'dump-location' or a temp directory if no dump "
                            "location is specified."),
            "type": "bool",
            "default": False,
        }

        self.parameters["dump_sparse"] = {
            "description": ("Dump sparse copies of each validated environment "
                            "to the location specified by the 'dump-location' "
                            "or a temp directory if no dump location is "
                            "specified."),
            "type": "bool",
            "default": False,
        }

        self.parameters["dump_location"] = {
            "description": ("The location to dump the environment configs when "
                            "using the 'dump' or 'dump-sparse' arguments."),
            "type": "str",
            "default": "",
        }

        # XXX specify the envs to validate



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

        # 0-2 args.
        if len(args) not in range(0, 3):
            self._print_usage()
            raise TankError("Invalid number of arguments.\n"
                            "See the command usage above.")

        params = {}

        if "--dump" in args:
            params["dump"] = True
            args.pop(args.index("--dump"))

        if "--dump-sparse" in args:
            params["dump_sparse"] = True
            args.pop(args.index("--dump-sparse"))

        # look through the remaining args for known values.
        for (i, arg) in enumerate(args):
            if arg.startswith("--dump-location"):
                if not "=" in arg:
                    self._print_usage()
                    raise TankError(
                        "Dump location must be specified like this: "
                        "'--dump-location=/path/to/env/output/directory'.\n"
                        "See the command usage above."
                    )
                (flag, dump_loc) = arg.split("=")
                params["dump_location"] = dump_loc
                args.pop(i)

        # if there are any args left, then we don't know how to process them.
        if len(args):
            self._print_usage()
            raise TankError(
                "Unknown arguments in validate command: '%s'\n"
                "See the command usage above."
                % (", ".join(args),)
            )

        computed_params = self.__validate_parameters(params)
        return self._run(log, computed_params)
        
    def _run(self, log, params):
        """
        Actual execution payload
        """ 
        
        log.info("")
        log.info("")
        log.info("Welcome to the Shotgun Pipeline Toolkit Configuration validator!")
        log.info("")
    
        try:
            envs = self.tk.pipeline_configuration.get_environments()
        except Exception, e:
            raise TankError("Could not find any environments for config %s: %s" % (self.tk, e))
    
        log.info("Found the following environments:")
        for x in envs:
            log.info("    %s" % x)
        log.info("")
        log.info("")

        should_dump = False
        if params["dump"] or params["dump_sparse"]:
            should_dump = True

        # validate environments
        for env_name in envs:
            env = self.tk.pipeline_configuration.get_environment(env_name)
            #_process_environment(log, self.tk, env)
            if should_dump:
                output_path = os.path.join(params["dump_location"],
                    os.path.basename(env.disk_location))
                if params["dump_sparse"]:
                    env.dump_sparse(output_path)
                else:
                    env.dump_full(output_path)

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


    def __validate_parameters(self, parameters):
        """Validate the params."""

        # do the base class default validation
        params = super(ValidateConfigAction, self)._validate_parameters(parameters)

        # check for mutually exclusive arguments
        if params["dump"] and params["dump_sparse"]:
            raise TankError(
                "The 'dump' and 'dump sparse' options are mutually exclusive. "
                "Please run again with only one of these options specified."
            )

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
            if not os.path.exists(dump_dir):
                old_umask = os.umask(0)
                try:
                    os.makedirs(dump_dir, 0775)
                except OSError, e:
                    if e.errno != errno.EEXIST:
                        raise
                finally:
                    os.umask(old_umask)

            params["dump_location"] = dump_dir

        return params

    def _print_usage(self):

        example_usage = (
            "Syntax: validate [--dump|--dump-sparse] "
            "[--dump-location=/path/to/env/output/directory]"
        )

        print "Validate command usage:\n"
        for (param, settings) in self.parameters.iteritems():
            param_display = "--" + param.replace("_", "-")
            print "  %s (%s): %s [default=%s]" % (
                param_display,
                settings["type"],
                settings["description"],
                settings["default"]
            )
        print "\n%s" % (example_usage,)


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
