# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

from .action_base import Action
from . import console_utils


class AppUpdatesAction(Action):
    """
    Action that updates apps and engines.
    """    
    def __init__(self):
        Action.__init__(self, 
                        "updates", 
                        Action.TK_INSTANCE, 
                        "Checks if there are any app or engine updates for the current configuration.", 
                        "Configuration")
    
    
        # this method can be executed via the API
        self.supports_api = True
        
        self.parameters = {}
        
        self.parameters["environment_filter"] = { "description": "Name of environment to check.",
                                                  "default": "ALL",
                                                  "type": "str" }
        self.parameters["engine_filter"] = { "description": "Name of engine to check.",
                                             "default": "ALL",
                                             "type": "str" }
        self.parameters["app_filter"] = { "description": "Name of app to check.",
                                          "default": "ALL",
                                          "type": "str" }
        
        
        
        
    def run_noninteractive(self, log, parameters):
        """
        API accessor
        """
        # validate params and seed default values
        computed_params = self._validate_parameters(parameters) 
        
        if computed_params["environment_filter"] == "ALL":
            computed_params["environment_filter"] = None
        if computed_params["engine_filter"] == "ALL":
            computed_params["engine_filter"] = None
        if computed_params["app_filter"] == "ALL":
            computed_params["app_filter"] = None
        
        return check_for_updates(log, 
                                 self.tk,
                                 computed_params["environment_filter"], 
                                 computed_params["engine_filter"],
                                 computed_params["app_filter"],
                                 True )


    def run_interactive(self, log, args):
        """
        Tank command accessor
        """
                
        if len(args) == 0:
            # update EVERYTHING!
            
            log.info("This command will go through your current configuration and check if there "
                     "are any updates available. If there are updates, you will be asked if you "
                     "want to perform an upgrade. If settings has been added to the new version "
                     "that you are installing, you may be prompted to specified values for these.")
            log.info("")
            log.info("Running this command with no parameters will check all environments, engines "
                     "and app. This may take a long time. You can also run the updater on a subset "
                     "of your installed apps and engines.")
            log.info("")
            log.info("General syntax:")
            log.info("> tank updates [environment_name] [engine_name] [app_name]")
            log.info("")
            log.info("The special keyword ALL can be used to denote all items in a category.")
            log.info("")
            log.info("Examples:")
            log.info("")
            log.info("Check everything:")
            log.info("> tank updates")
            log.info("")
            log.info("Check the Shot environment:")
            log.info("> tank updates Shot")
            log.info("")
            log.info("Check all maya apps in all environments:")
            log.info("> tank updates ALL tk-maya")
            log.info("")
            log.info("Check all maya apps in the Shot environment:")
            log.info("> tank updates Shot tk-maya")
            log.info("")
            log.info("Make sure the loader app is up to date everywhere:")
            log.info("> tank updates ALL ALL tk-multi-loader")
            log.info("")
            log.info("Make sure the loader app is up to date in maya:")
            log.info("> tank updates ALL tk-maya tk-multi-loader")
            log.info("")
            log.info("")
            
            if console_utils.ask_yn_question("Continue with full update?"):
                check_for_updates(log, self.tk)
            
            return
        
        env_filter = None
        engine_filter = None
        app_filter = None        
        
        if len(args) > 0:
            env_filter = args[0]
            if env_filter == "ALL":
                log.info("- Update will check all environments.")
                env_filter = None
            else:
                log.info("- Update will only check the %s environment." % env_filter)
        
        if len(args) > 1:
            engine_filter = args[1]
            if engine_filter == "ALL":
                log.info("- Update will check all engines.")
                engine_filter = None
            else:
                log.info("- Update will only check the %s engine." % engine_filter)
        
        if len(args) > 2:
            app_filter = args[2]
            if app_filter == "ALL":
                log.info("- Update will check all apps.")
                app_filter = None
            else:
                log.info("- Update will only check the %s app." % app_filter)

        check_for_updates(log, self.tk, env_filter, engine_filter, app_filter)    
        
            

################################################################################################
# helper methods for update
    
    
def check_for_updates(log, tk, env_name=None, engine_instance_name=None, app_instance_name=None, suppress_prompts=False):
    """
    Runs the update checker.
    """
    pc = tk.pipeline_configuration

    if env_name is None:
        env_names_to_process = pc.get_environments()
    else:
        env_names_to_process = [env_name]

    # check engines and apps
    items = []
    for env_name in env_names_to_process:
        
        # (AD) - Previously all environments were loaded before processing but 
        # this could lead to errors if an update doesn't know about previous 
        # updates to the same share files (includes)
        env = pc.get_environment(env_name)
        
        log.info("")
        log.info("")
        log.info("======================================================================")
        log.info("Environment %s..." % env.name)
        log.info("======================================================================")
        log.info("")
        
        if engine_instance_name is None:
            # process all engines
            engines_to_process = env.get_engines()
        else:
            # there is a filter! Ensure the filter matches something
            # in this environment
            if engine_instance_name in env.get_engines():
                # the filter matches something in this environment
                engines_to_process = [engine_instance_name] 
            else:
                # the item we are filtering on does not exist in this env
                engines_to_process = []
        
        for engine in engines_to_process:
            items.append( _process_item(log, suppress_prompts, tk, env, engine) )
            log.info("")
            
            if app_instance_name is None:
                # no filter - process all apps
                apps_to_process = env.get_apps(engine)
            else:
                # there is a filter! Ensure the filter matches
                # something in the current engine apps listing
                if app_instance_name in env.get_apps(engine):
                    # the filter matches something!
                    apps_to_process = [app_instance_name]
                else:
                    # the app filter does not match anything in this engine
                    apps_to_process = []
            
            for app in apps_to_process:
                items.append( _process_item(log, suppress_prompts, tk, env, engine, app) )
                log.info("")
        
        if len(env.get_frameworks()) > 0:
            log.info("")
            log.info("Frameworks:")
            log.info("-" * 70)

            for framework in env.get_frameworks():
                items.append( _process_item(log, suppress_prompts, tk, env, framework_name=framework) )
        

    # display summary
    log.info("")
    summary = []
    for x in items:
        if x["was_updated"]:

            summary.append("%s was updated from %s to %s" % (x["new_descriptor"],
                                                             x["old_descriptor"].get_version(),
                                                             x["new_descriptor"].get_version()))
            (_, url) = x["new_descriptor"].get_changelog()
            if url:
                summary.append("Change Log: %s" % url)
            summary.append("")

    if len(summary) > 0:
        log.info("Items were updated. Details follow below:")
        log.info("-" * 70)
        for x in summary:
            log.info(x)
        log.info("-" * 70)

    log.info("")
    
    # generate return data for api access
    ret_val = []
    for x in items:
        d = {}
        d["engine_instance"] = x["engine_name"]
        d["app_instance"] = x["app_name"]
        d["environment"] = x["env_name"].name
        d["updated"] = x["was_updated"]
        if x["was_updated"]:
            d["new_version"] = x["new_descriptor"].get_version()
        ret_val.append(d)
    
    return ret_val
        
    

def _update_item(log, suppress_prompts, tk, env, old_descriptor, new_descriptor, engine_name=None, app_name=None, framework_name=None):
    """
    Performs an upgrade of an engine/app/framework.
    """
    # note! Some of these methods further down are likely to pull the apps local
    # in order to do deep introspection. In order to provide better error reporting,
    # pull the apps local before we start
    if not new_descriptor.exists_local():
        log.info("Downloading %s..." % new_descriptor)
        new_descriptor.download_local()

    # create required shotgun fields
    new_descriptor.ensure_shotgun_fields_exist()

    # run post install hook
    new_descriptor.run_post_install()

    # ensure that all required frameworks have been installed
    # find the file where our item is being installed
    if framework_name:
        (_, yml_file) = env.find_location_for_framework(framework_name)
    elif app_name:
        (_, yml_file) = env.find_location_for_app(engine_name, app_name)
    else:
        (_, yml_file) = env.find_location_for_engine(engine_name)
        
    console_utils.ensure_frameworks_installed(log, tk, yml_file, new_descriptor, env, suppress_prompts)

    # if we are updating an app, we pass the engine system name to the configuration method
    # so that it can resolve engine based defaults
    parent_engine_system_name = None
    if app_name: 
        parent_engine_system_name = env.get_engine_descriptor(engine_name).get_system_name()

    # now get data for all new settings values in the config
    params = console_utils.get_configuration(log, 
                                             tk, 
                                             new_descriptor, 
                                             old_descriptor, 
                                             suppress_prompts,
                                             parent_engine_system_name)

    # awesome. got all the values we need.
    log.info("")
    log.info("")

    # next step is to add the new configuration values to the environment
    if framework_name:
        env.update_framework_settings(framework_name, params, new_descriptor.get_location())    
    elif app_name:
        env.update_app_settings(engine_name, app_name, params, new_descriptor.get_location())
    else:
        env.update_engine_settings(engine_name, params, new_descriptor.get_location())
        
            
        


def _process_item(log, suppress_prompts, tk, env, engine_name=None, app_name=None, framework_name=None):
    """
    Checks if an app/engine/framework is up to date and potentially upgrades it.

    Returns a dictionary with keys:
    - was_updated (bool)
    - old_descriptor
    - new_descriptor (may be None if was_updated is False)
    - app_name
    - engine_name
    - env_name
    """

    if framework_name:
        log.info("Framework %s (Environment %s)" % (framework_name, env.name))

    elif app_name:
        log.info("App %s (Engine %s, Environment %s)" % (app_name, engine_name, env.name))
        
    else:
        log.info("")
        log.info("-" * 70)
        log.info("Engine %s (Environment %s)" % (engine_name, env.name))
        

    status = _check_item_update_status(env, engine_name, app_name, framework_name)
    item_was_updated = False

    if status["can_update"]:
        
        # print summary of changes
        console_utils.format_bundle_info(log, status["latest"])
        
        # ask user
        if suppress_prompts or console_utils.ask_question("Update to the above version?"):
            new_descriptor = status["latest"]
            curr_descriptor = status["current"]            
            _update_item(log, 
                         suppress_prompts, 
                         tk, 
                         env, 
                         curr_descriptor, 
                         new_descriptor, 
                         engine_name, 
                         app_name, 
                         framework_name)
            item_was_updated = True

    elif status["out_of_date"] == False and not status["current"].exists_local():
        # app does not exist in the local app download cache area 
        if suppress_prompts or console_utils.ask_question("Current version does not exist locally - download it now?"):
            log.info("Downloading %s..." % status["current"])
            status["current"].download_local()

    elif status["out_of_date"] == False:
        log.info(" \-- You are running version %s which is the most recent release." % status["latest"].get_version())

    else:
        # cannot update for some reason
        log.warning(status["update_status"])

    # return data
    d = {}
    d["was_updated"] = item_was_updated
    d["old_descriptor"] = status["current"]
    d["new_descriptor"] = status["latest"]
    d["app_name"] = app_name
    d["engine_name"] = engine_name
    d["env_name"] = env
    return d


def _check_item_update_status(environment_obj, engine_name=None, app_name=None, framework_name=None):
    """
    Checks if an engine or app or framework is up to date.
    Will locate the latest version of the item and run a comparison.
    Will check for constraints and report about these 
    (if the new version requires minimum version of shotgun, the core API, etc.)
    
    Returns a dictionary with the following keys:
    - current:       Current engine descriptor
    - latest:        Latest engine descriptor
    - out_of_date:   Is the current version out of date?
    - deprecated:    Is this item deprecated?
    - can_update:    Can we update?
    - update_status: String with details describing the status.  
    """
    
    parent_engine_desc = None
    
    if framework_name:
        curr_desc = environment_obj.get_framework_descriptor(framework_name)
        # framework_name follows a convention and is on the form 'frameworkname_version', 
        # where version is on the form v1.2.3, v1.2.x, v1.x.x
        version_pattern = framework_name.split("_")[-1]
        # use this pattern as a constraint as we check for updates
        latest_desc = curr_desc.find_latest_version(version_pattern)
        
    
    elif app_name:
        curr_desc = environment_obj.get_app_descriptor(engine_name, app_name)
        # for apps, also get the descriptor for their parent engine
        parent_engine_desc = environment_obj.get_engine_descriptor(engine_name)
        # and get potential upgrades
        latest_desc = curr_desc.find_latest_version()

    else:
        curr_desc = environment_obj.get_engine_descriptor(engine_name)
        # and get potential upgrades
        latest_desc = curr_desc.find_latest_version()


    # out of date check
    out_of_date = (latest_desc.get_version() != curr_desc.get_version())
    
    # check deprecation
    (is_dep, dep_msg) = latest_desc.get_deprecation_status()
    
    if is_dep:
        # we treat deprecation as an out of date that cannot be upgraded!
        out_of_date = True
        can_update = False
        status = "This item has been flagged as deprecated with the following status: %s" % dep_msg 

    elif not out_of_date:
        can_update = False
        status = "Item is up to date!"
    
    else:
        # maybe we can update!
        # look at constraints
        (can_update, reasons) = console_utils._check_constraints(latest_desc, parent_engine_desc)
        
        # create status message
        if can_update:
            status = "A new version (%s) of the item is available for installation." % latest_desc.get_version()
        else:
            reasons.insert(0, "The latest version (%s) of the item requires an upgrade to one "
                           "or more of your installed components." % latest_desc.get_version())
            status = " ".join(reasons)
            
    # prepare return data
    data = {}
    data["current"] = curr_desc
    data["latest"] = latest_desc
    data["out_of_date"] = out_of_date
    data["can_update"] = can_update
    data["update_status"] = status

    return data

