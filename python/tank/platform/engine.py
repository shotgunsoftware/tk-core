# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Defines the base class for all Tank Engines.

"""

import os
import re
import sys
import traceback
import inspect
import weakref
import threading
        
from .. import loader
from .. import hook

from ..errors import TankError, TankEngineInitError, TankContextChangeNotSupportedError
from ..deploy import descriptor
from ..deploy.dev_descriptor import TankDevDescriptor
from ..util import log_user_activity_metric, log_user_attribute_metric
from ..util.metrics import MetricsDispatcher

from . import application
from . import constants
from . import validation
from . import qt
from . import black_list
from .bundle import TankBundle
from .framework import setup_frameworks

class Engine(TankBundle):
    """
    Base class for an engine in Tank.
    """

    _ASYNC_INVOKER, _SYNC_INVOKER = range(2)

    def __init__(self, tk, context, engine_instance_name, env):
        """
        Constructor. Takes the following parameters:
        
        :param tk: Sgtk API handle
        :param context: A context object to define the context on disk where the engine is operating
        :param engine_instance_name: The name of the engine as it has been defined in the environment.
        :param env: An Environment object to associate with this engine
        """
        
        self.__env = env
        self.__engine_instance_name = engine_instance_name
        self.__applications = {}
        self.__application_pool = {}
        self.__shared_frameworks = {}
        self.__commands = {}
        self.__command_pool = {}
        self.__panels = {}
        self.__currently_initializing_app = None
        
        self.__qt_widget_trash = []
        self.__created_qt_dialogs = []
        self.__qt_debug_info = {}
        
        self.__commands_that_need_prefixing = []
        
        self.__global_progress_widget = None

        self._metrics_dispatcher = None

        # Initialize these early on so that methods implemented in the derived class and trying
        # to access the invoker don't trip on undefined variables.
        self._invoker = None
        self._async_invoker = None
        
        # get the engine settings
        settings = self.__env.get_engine_settings(self.__engine_instance_name)
        
        # get the descriptor representing the engine        
        descriptor = self.__env.get_engine_descriptor(self.__engine_instance_name)        
        
        # init base class
        TankBundle.__init__(self, tk, context, settings, descriptor, env)

        # check that the context contains all the info that the app needs
        validation.validate_context(descriptor, context)
        
        # make sure the current operating system platform is supported
        validation.validate_platform(descriptor)

        # Get the settings for the engine and then validate them
        engine_schema = descriptor.get_configuration_schema()
        validation.validate_settings(self.__engine_instance_name, tk, context, engine_schema, settings)
        
        # set up any frameworks defined
        setup_frameworks(self, self, self.__env, descriptor)
        
        # run the engine init
        self.log_debug("Engine init: Instantiating %s" % self)
        self.log_debug("Engine init: Current Context: %s" % context)

        # now if a folder named python is defined in the engine, add it to the pythonpath
        my_path = os.path.dirname(sys.modules[self.__module__].__file__)
        python_path = os.path.join(my_path, constants.BUNDLE_PYTHON_FOLDER)
        if os.path.exists(python_path):
            # Only append if __init__.py doesn't exist. If it does then we
            # should use the special tank import instead.
            init_path = os.path.join(python_path, "__init__.py")
            if not os.path.exists(init_path):
                self.log_debug("Appending to PYTHONPATH: %s" % python_path)
                sys.path.append(python_path)


        # Note, 'init_engine()' is now deprecated and all derived initialisation should be
        # done in either 'pre_app_init()' or 'post_app_init()'.  'init_engine()' is left
        # in here to provide backwards compatibility with any legacy code. 
        self.init_engine()

        # try to pull in QT classes and assign to tank.platform.qt.XYZ
        base_def = self._define_qt_base()
        qt.QtCore = base_def.get("qt_core")
        qt.QtGui = base_def.get("qt_gui")
        qt.TankDialogBase = base_def.get("dialog_base")

        # Update the authentication module to use the engine's Qt.
        from tank_vendor.shotgun_authentication.ui import qt_abstraction
        qt_abstraction.QtCore = qt.QtCore
        qt_abstraction.QtGui = qt.QtGui
        
        # create invoker to allow execution of functions on the
        # main thread:
        self._invoker, self._async_invoker = self.__create_invokers()
        
        # run any init that needs to be done before the apps are loaded:
        self.pre_app_init()
        
        # now load all apps and their settings
        self.__load_apps()
        
        # execute the post engine init for all apps
        # note that this is executed before the post_app_init
        # in the engine - this is because typically the post app
        # init in the engine will contain code which captures the
        # state of the apps - for example creates a menu, so at that 
        # point we want to try and have all app initialization complete.
        self.__run_post_engine_inits()
        
        # Useful dev helpers: If there is one or more dev descriptors in the 
        # loaded environment, add a reload button to the menu!
        self.__register_reload_command()
        
        # now run the post app init
        self.post_app_init()
        
        # emit an engine started event
        tk.execute_core_hook(constants.TANK_ENGINE_INIT_HOOK_NAME, engine=self)

        self.log_debug("Init complete: %s" % self)
        self.log_metric("Init")

        # log the core and engine versions being used by the current user
        log_user_attribute_metric("tk-core version", tk.version)
        log_user_attribute_metric("%s version" % (self.name,), self.version)

        # check if there are any compatibility warnings:
        # do this now in case the engine fails to load!
        messages = black_list.compare_against_black_list(descriptor)
        if len(messages) > 0:
            self.log_warning("Compatibility warnings were issued for %s:" % descriptor)
            for msg in messages:
                self.log_warning("")
                self.log_warning(msg)

        # if the engine supports logging metrics, begin dispatching logged metrics
        if self.metrics_dispatch_allowed:
            self._metrics_dispatcher = MetricsDispatcher(self)
            self.log_debug("Starting metrics dispatcher...")
            self._metrics_dispatcher.start()
            self.log_debug("Metrics dispatcher started.")
        
    def __repr__(self):
        return "<Sgtk Engine 0x%08x: %s, env: %s>" % (id(self),  
                                                      self.name, 
                                                      self.__env.name)

    def get_env(self):
        """
        Returns the environment object associated with this engine.
        This is a private method which is internal to tank and should
        not be used by external code. This method signature may change at any point
        and the object returned may also change. Do not use outside of the core api.
        """
        return self.__env

    ##########################################################################################
    # properties used by internal classes, not part of the public interface
    
    def __show_busy(self, title, details):
        """
        Payload for the show_busy method.

        For details, see the main show_busy documentation.
        
        :params title: Short descriptive title of what is happening
        :params details: Detailed message describing what is going on.
        """
        if self.has_ui:
            # we cannot import QT until here as non-ui engines don't have QT defined.
            try:
                from .qt.busy_dialog import BusyDialog 
                from .qt import QtGui, QtCore
                
            except:
                # QT import failed. This may be because someone has upgraded the core
                # to the latest but are still running a earlier version of the 
                # Shotgun or Shell engine where the self.has_ui method is not
                # correctly implemented. In that case, absorb the error and  
                # emit a log message
                self.log_info("[%s] %s" % (title, details))
                
            else:
                # our qt import worked!
                if not self.__global_progress_widget:
                    
                    # no window exists - create one!
                    (window, self.__global_progress_widget) = self._create_dialog_with_widget(title="Toolkit is busy", 
                                                                                              bundle=self, 
                                                                                              widget_class=BusyDialog)
                    
                    # make it a splashscreen that sits on top
                    window.setWindowFlags(QtCore.Qt.SplashScreen | QtCore.Qt.WindowStaysOnTopHint)
    
                    # set the message before the window is raised to avoid briefly
                    # showing default values
                    self.__global_progress_widget.set_contents(title, details)
                    
                    # kick it off        
                    window.show()
        
                else:
                                            
                    # just update the message for the existing window 
                    self.__global_progress_widget.set_contents(title, details)

                # make sure events are properly processed and the window is updated
                QtCore.QCoreApplication.processEvents()
        
        else:
            # no UI support! Instead, just emit a log message
            self.log_info("[%s] %s" % (title, details))
        
    def __clear_busy(self):
        """
        Payload for clear_busy method. 
        For details, see the main clear_busy documentation.
        """
        if self.__global_progress_widget:
            self.__global_progress_widget.close()
            self.__global_progress_widget = None
    
    def show_busy(self, title, details):
        """
        Displays or updates a global "busy window" tied to this engine. The window
        is a splash screen type window, floats on top and contains details of what
        is currently being processed.
        
        This is currently an internal method and not meant to be be used by anything
        outside the core API. Later on, as things settle, we may consider exposing this.
        
        This method pops up a splash screen with a message and the idea is that 
        long running core processes can use this as a way to communicate their intent
        to the user and keep the user informed as slow processes are executed. If the engine
        has a UI present, this will be used to display the progress message. If the engine
        does not have UI support, a message will be logged. The UI always appears in the 
        main thread for safety.

        Only one global progress window can exist per engine at a time, so if you want to 
        push several updates one after the other, just keep calling this method.
        
        When you want to remove the window, call clear_busy().

        Note! If you are calling this from the Core API you typically don't have 
        access to the current engine object. In this case you can use the 
        convenience method tank.platform.engine.show_global_busy() which will
        attempt to broadcast the request to the currently active engine.
        
        :params title: Short descriptive title of what is happening
        :params details: Detailed message describing what is going on.
        """
        # make sure that the UI is always shown in the main thread
        self.execute_in_main_thread(self.__show_busy, title, details)
    
    def clear_busy(self):
        """
        Closes any active busy window.
        
        For more details, see the show_busy() documentation.
        """
        if self.__global_progress_widget:
            self.execute_in_main_thread(self.__clear_busy)

    def log_metric(self, action):
        """Log an engine metric.

        :param action: Action string to log, e.g. 'Init'

        Logs a user activity metric as performed within an engine. This is
        a convenience method that auto-populates the module portion of
        `tank.util.log_user_activity_metric()`

        Internal Use Only - We provide no guarantees that this method
        will be backwards compatible.

        """

        # the action contains the engine and app name, e.g.
        # module: tk-maya
        # action: tk-maya - Init
        full_action = "%s %s" % (self.name, action)
        log_user_activity_metric(self.name, full_action)

    def log_user_attribute_metric(self, attr_name, attr_value):
        """Convenience class. Logs a user attribute metric.

        :param attr_name: The name of the attribute to set for the user.
        :param attr_value: The value of the attribute to set for the user.

        This is a convenience wrapper around
        `tank.util.log_user_activity_metric()` that prevents engine subclasses
        from having to import from `tank.util`.

        Internal Use Only - We provide no guarantees that this method
        will be backwards compatible.

        """
        log_user_attribute_metric(attr_name, attr_value)


    ##########################################################################################
    # properties

    @property
    def shotgun(self):
        """
        Delegates to the Sgtk API instance's shotgun connection, which is lazily
        created the first time it is requested.
        
        :returns: Shotgun API handle
        """
        # pass on information to the user agent manager which bundle is returning
        # this sg handle. This information will be passed to the web server logs
        # in the shotgun data centre and makes it easy to track which app and engine versions
        # are being used by clients
        try:
            self.tank.shotgun.tk_user_agent_handler.set_current_engine(self.name, self.version)
        except AttributeError:
            # looks like this sg instance for some reason does not have a
            # tk user agent handler associated.
            pass
        
        return self.tank.shotgun        

    @property
    def environment(self):
        """
        A dictionary with information about the environment.
        Returns keys name, description and disk_location.
         
        :returns: dictionary
        """
        data = {}
        data["name"] = self.__env.name
        data["description"] = self.__env.description
        data["disk_location"] = self.__env.disk_location
        
        return data

    @property
    def instance_name(self):
        """
        The instance name for this engine. The instance name
        is the entry that is defined in the environment file.
        
        :returns: instance name as string
        """
        return self.__engine_instance_name

    @property
    def apps(self):
        """
        Dictionary of apps associated with this engine
        
        :returns: dictionary with keys being app name and values being app objects
        """
        return self.__applications
    
    @property
    def commands(self):
        """
        Returns a dictionary representing all the commands that have been registered
        by apps in this engine. Each dictionary item contains the following keys:
        
        * callback - function pointer to function to execute for this command
        * properties - dictionary with free form options - these are typically
          engine specific and driven by convention.
        
        :returns: commands dictionary, keyed by command name
        """
        return self.__commands
    
    @property
    def panels(self):
        """
        Returns all the panels which have been registered with the engine.
        
        :returns: A dictionary keyed by panel unqiue ids. Each value is a dictionary
                  with keys 'callback' and 'properties'
        """
        return self.__panels
    
    @property
    def has_ui(self):
        """
        Indicates that the host application that the engine is connected to has a UI enabled.
        This always returns False for some engines (such as the shell engine) and may vary 
        for some engines, depending if the host application for example is in batch mode or
        UI mode.
        
        :returns: boolean value indicating if a UI currently exists
        """
        # default implementation is to assume a UI exists
        # this is since most engines are supporting a graphical application
        return True

    @property
    def metrics_dispatch_allowed(self):
        """
        Inidicates this engine will allow the metrics worker threads to forward
        the user metrics logged via core, this engine, or registered apps to
        SG.

        :returns: boolean value indicating that the engine allows user metrics
            to be forwarded to SG.
        """
        return True

    ##########################################################################################
    # init and destroy
    
    def init_engine(self):
        """
        Note: Now deprecated - Please use pre_app_init instead.
        """
        pass
    
    def pre_app_init(self):
        """
        Runs after the engine is set up but before any apps have been initialized.
        
        Implemented by deriving classes.
        """
        pass
    
    def post_app_init(self):
        """
        Runs after all apps have been initialized.
        
        Implemented by deriving classes.
        """
        pass
    
    def destroy(self):
        """
        Destroy all apps, then call destroy_engine so subclasses can add their own tear down code.

        This method should not be subclassed.
        """
        self.__destroy_frameworks()
        self.__destroy_apps()

        self.log_debug("Destroying %s" % self)
        self.destroy_engine()

        # finally remove the current engine reference
        set_current_engine(None)

        # now clear the hooks cache to make sure fresh hooks are loaded the 
        # next time an engine is initialized
        hook.clear_hooks_cache()

        # clean up the main thread invoker - it's a QObject so it's important we
        # explicitly set the value to None!
        self._invoker = None
        self._async_invoker = None

        # halt metrics dispatching
        if self._metrics_dispatcher and self._metrics_dispatcher.dispatching:
            self.log_debug("Stopping metrics dispatcher.")
            self._metrics_dispatcher.stop()
            self.log_debug("Metrics dispatcher stopped.")

    def destroy_engine(self):
        """
        Called when the engine should tear down itself and all its apps.
        Implemented by deriving classes.
        """
        pass

    def change_context(self, new_context):
        """
        Called when the engine is being asked to change contexts. This
        will only be allowed if the engine explicitly suppose on-the-fly
        context changes by way of its context_change_allowed property. Any
        apps that do not support context changing will be restarted instead.
        Custom behavior at the engine level should be handled by overriding
        one or both of pre_context_change and post_context_change methods.

        :param new_context:     The context to change to.
        """
        # Make sure we're allowed to change context at the engine level.
        if not self.context_change_allowed:
            self.log_debug("Engine %r does not allow context changes." % self)
            raise TankContextChangeNotSupportedError()

        # Make sure that this engine is configured to run in the new context,
        # and that it's the EXACT same engine. This can be handled by comparing
        # the current engine's descriptor to the one coming from the new environment.
        # If this fails then it's more than just the engine not supporting the
        # context change, it's that the target context isn't configured properly.
        # As such, we'll let any exceptions (mostly TankEngineInitError) bubble
        # up since it's a critical error case.
        (new_env, engine_descriptor) = _get_env_and_descriptor_for_engine(
            engine_name=self.instance_name,
            tk=self.tank,
            context=new_context,
        )

        # Make sure that the engine in the target context is the same as the current
        # engine. In the case of git or app_store descriptors, the equality check
        # is an "is" check to see if they're references to the same object due to the
        # fact that those descriptor types are singletons. For dev descriptors, the
        # check is going to compare the paths of the descriptors to see if they're
        # referencing the same data on disk, in which case they are equivalent.
        if engine_descriptor != self.descriptor:
            self.log_debug("Engine %r does not match descriptors between %r and %r." % (
                self,
                self.context,
                new_context
            ))
            raise TankContextChangeNotSupportedError()

        # Run the pre_context_change method to allow for any engine-specific
        # prep work to happen.
        self.log_debug(
            "Executing pre_context_change for %r, changing from %r to %r." % (
                self,
                self.context,
                new_context
            )
        )
        self.pre_context_change(self.context, new_context)
        self.log_debug("Execution of pre_context_change for engine %r is complete." % self)

        # Check to see if all of our apps are capable of accepting
        # a context change. If one of them is not, then we remove it
        # from the persistent app pool, which will force it to be
        # rebuilt when apps are loaded later on.
        non_compliant_app_paths = []
        for install_path, app_instances in self.__application_pool.iteritems():
            for instance_name, app in app_instances.iteritems():
                self.log_debug(
                    "Executing pre_context_change for %r, changing from %r to %r." % (
                        app,
                        self.context,
                        new_context
                    )
                )
                app.pre_context_change(self.context, new_context)
                self.log_debug("Execution of pre_context_change for app %r is complete." % app)

        # Now that we're certain we can perform a context change,
        # we can tell the environment what the new context is, update
        # our own context property, and load the apps. The app load
        # will repopulate the __applications dict to contain the appropriate
        # apps for the new context, and will pull apps that have already
        # been loaded from the __application_pool, which is persistent.
        old_context = self.context
        self.__env = new_env
        self._set_context(new_context)
        self.__load_apps(reuse_existing_apps=True, old_context=old_context)

        # Call the post_context_change method to allow for any engine
        # specific post-change logic to be run.
        self.log_debug(
            "Executing post_context_change for %r, changing from %r to %r." % (
                self,
                self.context,
                new_context
            )
        )

        self.post_context_change(old_context, new_context)
        self.log_debug("Execution of post_context_change for engine %r is complete." % self)

        # Last, now that we're otherwise done, we can run the
        # apps' post_engine_init methods.
        self.__run_post_engine_inits()
    
    ##########################################################################################
    # public methods

    def register_command(self, name, callback, properties=None):
        """
        Register a command with a name and a callback function. Properties can store
        implementation specific configuration, like if a tooltip is supported.
        Typically called from the init_app() method of an app.
        """
        if properties is None:
            properties = {}
        
        # uniqueness prefix, populated when there are several instances of the same app
        properties["prefix"] = None
        
        # try to add an app key to the dict with the app requesting the command
        if self.__currently_initializing_app is not None:
            # track which apps this request came from
            properties["app"] = self.__currently_initializing_app
        
        # add some defaults. If there isn't a description key, add it from the app's manifest
        if "description" not in properties and self.__currently_initializing_app:
            properties["description"] = self.__currently_initializing_app.description
        
        if "icon" not in properties and self.__currently_initializing_app:
            properties["icon"] = self.__currently_initializing_app.descriptor.get_icon_256()

        # check for duplicates!
        if name in self.__commands:
            # already something in the dict with this name
            existing_item = self.__commands[name]
            if existing_item["properties"].get("app"):
                # we know the app for the existing item.
                # so prefix with app name
                prefix = existing_item["properties"].get("app").instance_name
                new_name_for_existing = "%s:%s" % (prefix, name)
                self.__commands[new_name_for_existing] = existing_item
                self.__commands[new_name_for_existing]["properties"]["prefix"] = prefix 
                del(self.__commands[name])
                # add it to our list
                self.__commands_that_need_prefixing.append(name)
                      
        if name in self.__commands_that_need_prefixing:
            # try to append a prefix if possible
            if properties.get("app"):
                prefix = properties.get("app").instance_name
                name = "%s:%s" % (prefix, name)
                # also add a prefix key in the properties dict
                properties["prefix"] = prefix

        # now define command wrappers to capture metrics logging
        # on command execution. The toolkit callback system supports
        # two different callback styles:
        #
        # - A legacy type which is only used by Shotgun Apps which
        #   utilize multi select. These callbacks are always on the
        #   form callback(entity_type, entity_ids)
        #
        # - The standard type, which does not pass any arguments:
        #   callback()
        #

        # introspect the arg list to determine this and set a flag
        # to highlight this state. This is used by the tank_command
        # execution logic to correctly dispatch the callback during
        # runtime.
        arg_spec = inspect.getargspec(callback)
        # note - cannot use named tuple form because it is py2.6+
        arg_list = arg_spec[0]

        if "entity_type" in arg_list and "entity_ids" in arg_list:
            # add property flag
            properties[constants.LEGACY_MULTI_SELECT_ACTION_FLAG] = True

        # define a generic callback wrapper for metrics logging
        def callback_wrapper(*args, **kwargs):

            if properties.get("app"):
                # track which app command is being launched
                properties["app"].log_metric("'%s'" % name)

                # specify which app version is being used
                log_user_attribute_metric(
                    "%s version" % properties["app"].name,
                    properties["app"].version
                )
            # run the actual payload callback
            return callback(*args, **kwargs)

        self.__commands[name] = {
            "callback": callback_wrapper,
            "properties": properties,
        }


    def register_panel(self, callback, panel_name="main", properties=None):
        """
        Similar to register_command, but instead of registering a menu item in the form of a
        command, this method registers a UI panel. A register_panel call should
        be used in conjunction with a register_command call.
        
        Panels need to be registered if they should persist between DCC sessions (e.g. 
        for example 'saved layouts').
        
        Just like with the register_command() method, panel registration should be executed 
        from within the init phase of the app. Once a panel has been registered, it is possible
        for the engine to correctly restore panel UIs at startup and profile switches. 
        
        Not all engines support this feature, but in for example Nuke, a panel can be added to 
        a saved layout. Apps wanting to be able to take advantage of the persistence given by
        these saved layouts will need to call register_panel as part of their init_app phase.
        
        In order to show or focus on a panel, use the show_panel() method instead.
        
        :param callback: Callback to a factory method that creates the panel and returns a panel widget.
        :param panel_name: A string to distinguish this panel from other panels created by 
                           the app. This will be used as part of the unique id for the panel.
        :param properties: Properties dictionary. Reserved for future use.
        :returns: A unique identifier that can be used to consistently identify the 
                  panel across sessions. This identifier should be used to identify the panel
                  in all subsequent calls, e.g. for example show_panel().
        """
        properties = properties or {}
        
        if self.__currently_initializing_app is None:
            # register_panel is called from outside of init_app
            raise TankError("register_panel must be called from inside of the init_app() method!")
        
        current_app = self.__currently_initializing_app
        
        # similar to register_command, track which app this request came from
        properties["app"] = current_app 
        
        # now compose a unique id for this panel.
        # This is done based on the app instance name plus the given panel name.
        # By using the instance name rather than the app name, we support the
        # use case where more than one instance of an app exists within a
        # config.
        panel_id = "%s_%s" % (current_app.instance_name, panel_name)
        # to ensure the string is safe to use in most engines,
        # sanitize to simple alpha-numeric form
        panel_id = re.sub("\W", "_", panel_id)
        panel_id = panel_id.lower()

        # add it to the list of registered panels
        self.__panels[panel_id] = {"callback": callback, "properties": properties}
        
        self.log_debug("Registered panel %s" % panel_id)
        
        return panel_id
        
    def execute_in_main_thread(self, func, *args, **kwargs):
        """
        Execute the specified function in the main thread when called from a non-main
        thread.  This will block the calling thread until the function returns. Note that this
        method can introduce a deadlock if the main thread is waiting for a background thread
        and the background thread is invoking this method. Since the main thread is waiting
        for the background thread to finish, Qt's event loop won't be able to process the request
        to execute in the main thread.

        Note, this currently only works if Qt is available, otherwise it just
        executes immediately on the current thread.

        :param func: function to call
        :param args: arguments to pass to the function
        :param kwargs: named arguments to pass to the function

        :returns: the result of the function call
        """
        return self._execute_in_main_thread(self._SYNC_INVOKER, func, *args, **kwargs)

    def async_execute_in_main_thread(self, func, *args, **kwargs):
        """
        Execute the specified function in the main thread when called from a non-main
        thread.  This call will return immediately and will not wait for the code to be
        executed in the main thread.

        Note, this currently only works if Qt is available, otherwise it just
        executes immediately on the current thread.

        :param func: function to call
        :param args: arguments to pass to the function
        :param kwargs: named arguments to pass to the function
        """
        self._execute_in_main_thread(self._ASYNC_INVOKER, func, *args, **kwargs)

    def _execute_in_main_thread(self, invoker_id, func, *args, **kwargs):
        """
        Executes the given method and arguments with the specified invoker.
        If the invoker is not ready or if the calling thread is the main thread,
        the method is called immediately with it's arguments.

        :param invoker_id: Either _ASYNC_INVOKER or _SYNC_INVOKER.
        :param func: function to call
        :param args: arguments to pass to the function
        :param kwargs: named arguments to pass to the function

        :returns: The return value from the invoker.
        """
        # Execute in main thread might be called before the invoker is ready.
        # For example, an engine might use the invoker for logging to the main
        # thread.
        invoker = self._invoker if invoker_id == self._SYNC_INVOKER else self._async_invoker
        if invoker:
            from .qt import QtGui, QtCore
            if (QtGui.QApplication.instance()
                and QtCore.QThread.currentThread() != QtGui.QApplication.instance().thread()):
                # invoke the function on the thread that the QtGui.QApplication was created on.
                return invoker.invoke(func, *args, **kwargs)
            else:
                # we're already on the main thread so lets just call our function:
                return func(*args, **kwargs)
        else:
            # we don't have an invoker so just call the function:
            return func(*args, **kwargs)

    def get_matching_commands(self, command_selectors):
        """
        Finds all the commands that match the given selectors.

        Command selector structures are typically found in engine configurations
        and are typically defined on the following form in yaml:

        menu_favourites:
        - {app_instance: tk-multi-workfiles, name: Shotgun File Manager...}
        - {app_instance: tk-multi-snapshot,  name: Snapshot...}
        - {app_instance: tk-multi-workfiles, name: Shotgun Save As...}
        - {app_instance: tk-multi-publish,   name: Publish...}

        Note that selectors that do not match a command will output a warning.

        :param command_selectors: A list of command selectors, with each
                                  selector having the following structure:
                                    {
                                      name: command-name,
                                      app_instance: instance-name
                                    }
                                  An empty name ('') will select all the
                                  commands of the given instance-name.

        :returns:                 A list of tuples for all commands that match
                                  the selectors. Each tuple has the format:
                                    (instance-name, command-name, callback)
        """
        # return a dictionary grouping all the commands by instance name
        commands_by_instance = {}
        for (name, value) in self.commands.iteritems():
            app_instance = value["properties"].get("app")
            if app_instance is None:
                continue
            instance_name = app_instance.instance_name
            commands_by_instance.setdefault(instance_name, []).append(
                (name, value["callback"]))

        # go through the selectors and return any matching commands
        ret_value = []
        for selector in command_selectors:
            command_name = selector["name"]
            instance_name = selector["app_instance"]
            instance_commands = commands_by_instance.get(instance_name, [])

            # add the commands if the name of the settings is ''
            # or the name matches
            matching_commands = [(instance_name, name, callback)
                                 for (name, callback) in instance_commands
                                 if not command_name or (command_name == name)]
            ret_value.extend(matching_commands)

            # give feedback if no commands were found
            if not matching_commands:
                self._engine.log_warning(
                    "The requested command '%s' from app instance '%s' could "
                    "not be matched.\nPlease make sure that you have the app "
                    "installed and that it has successfully initialized." %
                    (command_name, instance_name))

        return ret_value

    ##########################################################################################
    # logging interfaces

    def log_debug(self, msg):
        """
        Debug logging.
        Implemented in deriving class.
        """
        pass
    
    def log_info(self, msg):
        """
        Info logging.
        Implemented in deriving class.
        """
        pass
        
    def log_warning(self, msg):
        """
        Warning logging.
        Implemented in deriving class.
        """
        pass
    
    def log_error(self, msg):
        """
        Debug logging.
        Implemented in deriving class - however we provide a basic implementation here.
        """        
        # fall back to std out error reporting if deriving class does not implement this.
        sys.stderr.write("Shotgun Error: %s\n" % msg)
    
    def log_exception(self, msg):
        """
        Helper method. Typically not overridden by deriving classes.
        This method is called inside an except clause and it creates an formatted error message
        which is logged as an error.
        """
        (exc_type, exc_value, exc_traceback) = sys.exc_info()
        
        if exc_traceback is None:
            # we are not inside an exception handler right now.
            # someone is calling log_exception from the running code.
            # in this case, present the current stack frame
            # and a sensible message
            stack_frame = traceback.extract_stack()
            traceback_str = "".join(traceback.format_list(stack_frame))
            exc_value = "No error details available."
        
        else:    
            traceback_str = "".join( traceback.format_tb(exc_traceback))
        
        
        message = []
        message.append(msg)
        message.append("")
        message.append("%s" % exc_value)
        message.append("The current environment is %s." % self.__env.name)
        message.append("")
        message.append("Code Traceback:")
        message.extend(traceback_str.split("\n"))
        
        self.log_error("\n".join(message))


    ##########################################################################################
    # debug for tracking Qt Widgets & Dialogs created by the provided methods      

    def get_debug_tracked_qt_widgets(self):
        """
        Print debug info about created Qt dialogs and widgets
        """
        return self.__qt_debug_info                

    def __debug_track_qt_widget(self, widget):
        """
        Add the qt widget to a list of objects to be tracked. 
        """
        if widget:
            self.__qt_debug_info[widget.__repr__()] = weakref.ref(widget)
        
    ##########################################################################################
    # private and protected methods

    def _get_dialog_parent(self):
        """
        Get the QWidget parent for all dialogs created through show_dialog & show_modal.
        
        Can be overriden in derived classes to return the QWidget to be used as the parent 
        for all TankQDialog's 
        """
        # By default, this will return the QApplication's active window:
        from .qt import QtGui
        return QtGui.QApplication.activeWindow()
                
    def _create_dialog(self, title, bundle, widget, parent):
        """
        Create a TankQDialog with the specified widget embedded. This also connects to the 
        dialogs dialog_closed event so that it can clean up when the dialog is closed.
        
        :param title: The title of the window
        :param bundle: The app, engine or framework object that is associated with this window
        :param widget: A QWidget instance to be embedded in the newly created dialog.
        
        """
        from .qt import tankqdialog
        
        # create a dialog to put it inside
        dialog = tankqdialog.TankQDialog(title, bundle, widget, parent)

        # keep a reference to all created dialogs to make GC happy
        self.__created_qt_dialogs.append(dialog)
        
        # watch for the dialog closing so that we can clean up
        dialog.dialog_closed.connect(self._on_dialog_closed)
        
        # keep track of some info for debugging object lifetime
        self.__debug_track_qt_widget(dialog)
        
        return dialog

    def _create_widget(self, widget_class, *args, **kwargs):
        """
        Create an instance of the specified widget_class.  This wraps the widget_class so that 
        the TankQDialog it is embedded in can connect to it more easily in order to handle the 
        close event
        
        :param widget_class: The class of the UI to be constructed. This must derive from QWidget.    
            
        Additional parameters specified will be passed through to the widget_class constructor.
        """
        from .qt import tankqdialog
                
        # construct the widget object
        derived_widget_class = tankqdialog.TankQDialog.wrap_widget_class(widget_class)
        widget = derived_widget_class(*args, **kwargs)
        
        # keep track of some info for debugging object lifetime
        self.__debug_track_qt_widget(widget)
        
        return widget
    
    def _create_dialog_with_widget(self, title, bundle, widget_class, *args, **kwargs):
        """
        Convenience method to create an sgtk TankQDialog with a widget instantiated from 
        widget_class embedded in the main section.
        
        :param title: The title of the window
        :param bundle: The app, engine or framework object that is associated with this window
        :param widget_class: The class of the UI to be constructed. This must derive from QWidget.    
            
        Additional parameters specified will be passed through to the widget_class constructor.
        """
        # get the parent for the dialog:
        parent = self._get_dialog_parent()
        
        # create the widget:
        widget = self._create_widget(widget_class, *args, **kwargs)
        
        # apply style sheet
        self._apply_external_styleshet(bundle, widget)        
        
        # create the dialog:
        dialog = self._create_dialog(title, bundle, widget, parent)
        return (dialog, widget)
    
    def _on_dialog_closed(self, dlg):
        """
        Called when a dialog created by this engine is closed.
        
        :param dlg: The dialog being closed
        
        Derived implementations of this method should be sure to call
        the base implementation
        """
        # first, detach the widget from the dialog.  This allows
        # the two objects to be cleaned up seperately menaing the
        # lifetime of the widget can be better managed
        widget = dlg.detach_widget()
        
        # add the dlg and it's contained widget to the list
        # of widgets to delete at some point!
        self.__qt_widget_trash.append(dlg)
        self.__qt_widget_trash.append(widget)
        
        if dlg in self.__created_qt_dialogs:
            # don't need to track this dialog any longer
            self.__created_qt_dialogs.remove(dlg)
            
        # disconnect from the dialog:
        dlg.dialog_closed.disconnect(self._on_dialog_closed)
        
        # clear temps
        dlg = None
        widget = None
        
        # finally, clean up the widget trash:
        self.__cleanup_widget_trash()
        

    def __cleanup_widget_trash(self):
        """
        Run through the widget trash and clean up any widgets
        that are no longer referenced by anything else.
        
        Notes:  This is pretty dumb and only looks at reference
        counts.  This means that if a widget has cyclic references
        then it will never get released.
        
        Better to be safe though as deleting/releasing a widget that
        still has events in the event queue will cause a hard crash!
        """
        still_trash = []
        for widget in self.__qt_widget_trash:
            # There should be 3 references:
            # 1. self.__qt_widget_trash[n]
            # 2. widget temporary
            # 3. temporary used by sys.getrefcount
            if sys.getrefcount(widget) <= 3:
                # we have the only references to the widget
                # so lets delete it!
                try:
                    widget.deleteLater()
                except RuntimeError:
                    # this is most likely because the Qt C++ widget has 
                    # already been deleted elsewhere so we can safely 
                    # ignore it!
                    pass
            else:
                # there are still other references to this widget 
                # out there so we should still keep track of it
                still_trash.append(widget)
    
        # update widget trash
        self.__qt_widget_trash = still_trash
        self.log_debug("Widget trash contains %d widgets" % (len(self.__qt_widget_trash)))

    def show_dialog(self, title, bundle, widget_class, *args, **kwargs):
        """
        Shows a non-modal dialog window in a way suitable for this engine. 
        The engine will attempt to parent the dialog nicely to the host application.
        
        :param title: The title of the window
        :param bundle: The app, engine or framework object that is associated with this window
        :param widget_class: The class of the UI to be constructed. This must derive from QWidget.
        
        Additional parameters specified will be passed through to the widget_class constructor.
        
        :returns: the created widget_class instance
        """
        if not self.has_ui:
            self.log_error("Sorry, this environment does not support UI display! Cannot show "
                           "the requested window '%s'." % title)
            return None
        
        # create the dialog:
        dialog, widget = self._create_dialog_with_widget(title, bundle, widget_class, *args, **kwargs)
        
        # show the dialog        
        dialog.show()
        
        # lastly, return the instantiated widget
        return widget
    
    def show_modal(self, title, bundle, widget_class, *args, **kwargs):
        """
        Shows a modal dialog window in a way suitable for this engine. The engine will attempt to
        integrate it as seamlessly as possible into the host application. This call is blocking 
        until the user closes the dialog.
        
        :param title: The title of the window
        :param bundle: The app, engine or framework object that is associated with this window
        :param widget_class: The class of the UI to be constructed. This must derive from QWidget.
        
        Additional parameters specified will be passed through to the widget_class constructor.

        :returns: (a standard QT dialog status return code, the created widget_class instance)
        """
        if not self.has_ui:
            self.log_error("Sorry, this environment does not support UI display! Cannot show "
                           "the requested window '%s'." % title)
            return None
        
        # create the dialog:
        dialog, widget = self._create_dialog_with_widget(title, bundle, widget_class, *args, **kwargs)
        
        # finally launch it, modal state
        status = dialog.exec_()
        
        # lastly, return the instantiated widget
        return (status, widget)
    

    def show_panel(self, panel_id, title, bundle, widget_class, *args, **kwargs):
        """
        Shows a panel in a way suitable for this engine. Engines should attempt to
        integrate panel support as seamlessly as possible into the host application. 
        Some engines have extensive panel support and workflows, others have none at all.
        
        If the engine does not specifically implement panel support, the window will 
        be shown as a modeless dialog instead and the call is equivalent to 
        calling show_dialog().
        
        :param panel_id: Unique identifier for the panel, as obtained by register_panel().
        :param title: The title of the panel
        :param bundle: The app, engine or framework object that is associated with this window
        :param widget_class: The class of the UI to be constructed. This must derive from QWidget.
        
        Additional parameters specified will be passed through to the widget_class constructor.
        
        :returns: the created widget_class instance
        """
        # engines implementing panel support should subclass this method.
        # the core implementation falls back on a modeless window.
        self.log_warning("Panel functionality not implemented. Falling back to showing "
                         "panel '%s' in a modeless dialog" % panel_id)
        return self.show_dialog(title, bundle, widget_class, *args, **kwargs)        


    def _resolve_sg_stylesheet_tokens(self, style_sheet):
        """
        Given a string containing a qt style sheet,
        perform replacements of key toolkit tokens.
        
        For example, "{{SG_HIGHLIGHT_COLOR}}" is converted to "#30A7E3"
        
        :param style_sheet: Stylesheet string to process
        :returns: Stylesheet string with replacements applied
        """
        processed_style_sheet = style_sheet
        for (token, value) in constants.SG_STYLESHEET_CONSTANTS.iteritems():
            processed_style_sheet = processed_style_sheet.replace("{{%s}}" % token, value)
        return processed_style_sheet
    
    def _apply_external_styleshet(self, bundle, widget):
        """
        Apply an std external stylesheet, associated with a bundle, to a widget.
        
        This will check if a standard style.css file exists in the
        app/engine/framework root location on disk and if so load it from 
        disk and apply to the given widget. The style sheet is cascading, meaning 
        that it will affect all children of the given widget. Typically this is used
        at window creation in order to allow newly created dialogs to apply app specific
        styles easily.
        
        :param bundle: app/engine/framework instance to load style sheet from
        :param widget: widget to apply stylesheet to 
        """
        qss_file = os.path.join(bundle.disk_location, constants.BUNDLE_STYLESHEET_FILE)
        try:
            f = open(qss_file, "rt")
            try:
                # Read css file
                self.log_debug("Detected std style sheet file '%s' - applying to widget %s" % (qss_file, widget))
                qss_data = f.read()
                # resolve tokens
                qss_data = self._resolve_sg_stylesheet_tokens(qss_data)
                # apply to widget (and all its children)
                widget.setStyleSheet(qss_data)
            except Exception, e:
                # catch-all and issue a warning and continue.
                self.log_warning("Could not apply stylesheet '%s': %s" % (qss_file, e))
            finally:
                f.close()
        except IOError:
            # The file didn't exist, so nothing to do.
            pass

    def _define_qt_base(self):
        """
        This will be called at initialisation time and will allow 
        a user to control various aspects of how QT is being used
        by Tank. The method should return a dictionary with a number
        of specific keys, outlined below. 
        
        * qt_core - the QtCore module to use
        * qt_gui - the QtGui module to use
        * dialog_base - base class for to use for Tank's dialog factory
        
        :returns: dict
        """
        # default to None
        base = {"qt_core": None, "qt_gui": None, "dialog_base": None}
        try:
            from PySide import QtCore, QtGui
            base["qt_core"] = QtCore
            base["qt_gui"] = QtGui
            base["dialog_base"] = QtGui.QDialog
        except:
            self.log_debug("Default engine QT definition failed to find QT. "
                           "This may need to be subclassed.")
        
        return base
        
    def _initialize_dark_look_and_feel(self):
        """
        Initializes a standard toolkit look and feel using a combination of
        QPalette and stylesheets.
        
        If your engine is running inside an environment which already has
        a dark style defined, do not call this method. The Toolkit apps are 
        designed to work well with most dark themes.
        
        However, if you are for example creating your own QApplication instance
        you can execute this method to but the session into Toolkit's 
        standard dark mode.
        
        This will initialize the plastique style and set it up with a standard
        dark palette and supporting stylesheet.
        
        Apps and UIs can then extend this further by using further css.
        
        Due to restrictions in QT, this needs to run after a QApplication object
        has been instantiated.
        """
        from .qt import QtGui, QtCore
        
        this_folder = os.path.abspath(os.path.dirname(__file__))
        
        # initialize our style
        QtGui.QApplication.setStyle("plastique")
        
        # Read in a serialized version of a palette
        # this file was generated in the following way:
        #
        # Inside of maya 2014, the following code was executed:
        #
        # from PySide import QtGui, QtCore
        # app = QtCore.QCoreApplication.instance()
        # fh = QtCore.QFile("/tmp/palette.dump")
        # fh.open(QtCore.QIODevice.WriteOnly)
        # out = QtCore.QDataStream(fh)
        # out.__lshift__( app.palette() )
        # fh.close()
        #
        # When we load this up in our engine, we will get a look
        # and feel similar to that of maya.

        try:
            # open palette file
            palette_file = os.path.join(this_folder, "qt", "dark_palette.qpalette")
            fh = QtCore.QFile(palette_file)
            fh.open(QtCore.QIODevice.ReadOnly);
            file_in = QtCore.QDataStream(fh)
    
            # deserialize the palette
            # (store it for GC purposes)
            self._dark_palette = QtGui.QPalette()
            file_in.__rshift__(self._dark_palette)
            fh.close()
            
            # set the std selection bg color to be 'shotgun blue'
            highlight_color = QtGui.QBrush(QtGui.QColor(constants.SG_STYLESHEET_CONSTANTS["SG_HIGHLIGHT_COLOR"]))
            self._dark_palette.setBrush(QtGui.QPalette.Highlight, highlight_color)

            # update link colors
            fg_color = self._dark_palette.color(QtGui.QPalette.Text)
            self._dark_palette.setColor(QtGui.QPalette.Link, fg_color)
            self._dark_palette.setColor(QtGui.QPalette.LinkVisited, fg_color)

            self._dark_palette.setBrush(QtGui.QPalette.HighlightedText, QtGui.QBrush(QtGui.QColor("#FFFFFF")))
            
            # and associate it with the qapplication
            QtGui.QApplication.setPalette(self._dark_palette)

        except Exception, e:
            self.log_error("The standard toolkit dark palette could not be set up! The look and feel of your "
                           "toolkit apps may be sub standard. Please contact support. Details: %s" % e)
            
        try:
            # read css
            css_file = os.path.join(this_folder, "qt", "dark_palette.css")
            f = open(css_file)
            css_data = f.read()
            f.close()
            css_data = self._resolve_sg_stylesheet_tokens(css_data)
            app = QtCore.QCoreApplication.instance()
            
            app.setStyleSheet(css_data)
        except Exception, e:
            self.log_error("The standard toolkit dark stylesheet could not be set up! The look and feel of your "
                           "toolkit apps may be sub standard. Please contact support. Details: %s" % e)
        
    
    def _get_standard_qt_stylesheet(self):
        """
        **********************************************************************
        THIS METHOD HAS BEEN DEPRECATED AND SHOULD NOT BE USED!
        Instead, call _initialize_standard_look_and_feel()
        **********************************************************************
        
        For environments which do not have a well defined QT style sheet,
        Toolkit maintains a "standard style" which is similar to the look and
        feel that Maya and Nuke has. 
        
        This is intended to be used in conjunction with QTs cleanlooks mode.
        The init code inside an engine would typically look something like this:
        
            QtGui.QApplication.setStyle("cleanlooks")
            qt_application = QtGui.QApplication([])
            qt_application.setStyleSheet( self._get_standard_qt_stylesheet() )         
        
        :returns: The style sheet data, as a string.
        """
        this_folder = os.path.abspath(os.path.dirname(__file__))
        css_file = os.path.join(this_folder, "qt", "toolkit_std_dark.css")
        f = open(css_file)
        css_data = f.read()
        f.close()
        return css_data

    def _register_shared_framework(self, instance_name, fw_obj):
        """
        Registers a framework with the specified instance name.
        This allows framework instances to be shared between bundles.
        This method is exposed for use by the platform.framework module.
        
        :param instance_name: Name of framework instance, as defined in the
                              environment. For example 'tk-framework-widget_v1.x.x'  
        :param fw_obj: Framework object.
        """
        self.__shared_frameworks[instance_name] = fw_obj

    def _get_shared_framework(self, instance_name):
        """
        Get a framework instance by name. If no framework with the specified
        name has been loaded yet, None is returned.
        This method is exposed for use by the platform.framework module.
        
        :param instance_name: Name of framework instance, as defined in the
                              environment. For example 'tk-framework-widget_v1.x.x'        
        """
        return self.__shared_frameworks.get(instance_name, None)

    def __create_invokers(self):
        """
        Create the object used to invoke function calls on the main thread when
        called from a different thread.
        """
        invoker = None
        async_invoker = None
        if self.has_ui:
            from .qt import QtGui, QtCore
            # Classes are defined locally since Qt might not be available.
            if QtGui and QtCore:
                class Invoker(QtCore.QObject):
                    """
                    Invoker class - implements a mechanism to execute a function with arbitrary
                    args in the main thread.
                    """
                    def __init__(self):
                        """
                        Construction
                        """
                        QtCore.QObject.__init__(self)
                        self._lock = threading.Lock()
                        self._fn = None
                        self._res = None

                    def invoke(self, fn, *args, **kwargs):
                        """
                        Invoke the specified function with the specified args in the main thread

                        :param fn:          The function to execute in the main thread
                        :param *args:       Args for the function
                        :param **kwargs:    Named arguments for the function
                        :returns:           The result returned by the function
                        """
                        # acquire lock to ensure that the function and result are not overwritten
                        # by syncrounous calls to this method from different threads
                        self._lock.acquire()
                        try:
                            self._fn = lambda: fn(*args, **kwargs)
                            self._res = None

                            # invoke the internal _do_invoke method that will actually run the function.  Note that
                            # we are unable to pass/return arguments through invokeMethod as this isn't properly
                            # supported by PySide.
                            QtCore.QMetaObject.invokeMethod(self, "_do_invoke", QtCore.Qt.BlockingQueuedConnection)

                            return self._res
                        finally:
                            self._lock.release()

                    @qt.QtCore.Slot()
                    def _do_invoke(self):
                        """
                        Execute the function
                        """
                        self._res = self._fn()

                class AsyncInvoker(QtCore.QObject):
                    """
                    Invoker class - implements a mechanism to execute a function with arbitrary
                    args in the main thread asynchronously.
                    """
                    __signal = QtCore.Signal(object)

                    def __init__(self):
                        """
                        Construction
                        """
                        QtCore.QObject.__init__(self)
                        self.__signal.connect(self.__execute_in_main_thread)

                    def invoke(self, fn, *args, **kwargs):
                        """
                        Invoke the specified function with the specified args in the main thread

                        :param fn:          The function to execute in the main thread
                        :param *args:       Args for the function
                        :param **kwargs:    Named arguments for the function
                        :returns:           The result returned by the function
                        """

                        self.__signal.emit(lambda: fn(*args, **kwargs))

                    def __execute_in_main_thread(self, fn):
                        fn()

                # Make sure that the invoker exists in the main thread:
                invoker = Invoker()
                async_invoker = AsyncInvoker()
                if QtCore.QCoreApplication.instance():
                    invoker.moveToThread(QtCore.QCoreApplication.instance().thread())
                    async_invoker.moveToThread(QtCore.QCoreApplication.instance().thread())

        return invoker, async_invoker

    ##########################################################################################
    # private         
        
    def __load_apps(self, reuse_existing_apps=False, old_context=None):
        """
        Populate the __applications dictionary, skip over apps that fail to initialize.

        :param reuse_existing_apps:     Whether to use already-running apps rather than
                                        starting up a new instance. This is primarily
                                        used during context changes. Default is False.
        :param old_context:             In the event of a context change occurring, this
                                        represents the context being changed away from,
                                        which will be provided along with the current
                                        context to each reused app's post_context_change
                                        method.
        """
        # If this is a load as part of a context change, the applications
        # dict will already have stuff in it. We can explicitly clean that
        # out here since those apps also exist in self.__application_pool,
        # which is persistent.
        self.__applications = dict()

        # The commands dict will be repopulated either by new app inits,
        # or by pulling existing commands for reused apps from the persistant
        # cache of commands.
        self.__commands = dict()
        self.__register_reload_command()

        for app_instance_name in self.__env.get_apps(self.__engine_instance_name):
            # Get a handle to the app bundle.
            descriptor = self.__env.get_app_descriptor(
                self.__engine_instance_name,
                app_instance_name,
            )

            if not descriptor.exists_local():
                self.log_error("Cannot start app! %s does not exist on disk." % descriptor)
                continue

            # Load settings for app - skip over the ones that don't validate
            try:
                # get the app settings data and validate it.
                app_schema = descriptor.get_configuration_schema()
                app_settings = self.__env.get_app_settings(
                    self.__engine_instance_name,
                    app_instance_name,
                )

                # check that the context contains all the info that the app needs
                if self.__engine_instance_name != constants.SHOTGUN_ENGINE_NAME: 
                    # special case! The shotgun engine is special and does not have a 
                    # context until you actually run a command, so disable the validation.
                    validation.validate_context(descriptor, self.context)
                
                # make sure the current operating system platform is supported
                validation.validate_platform(descriptor)
                                
                # for multi engine apps, make sure our engine is supported
                supported_engines = descriptor.get_supported_engines()
                if supported_engines and self.name not in supported_engines:
                    raise TankError("The app could not be loaded since it only supports "
                                    "the following engines: %s. Your current engine has been "
                                    "identified as '%s'" % (supported_engines, self.name))
                
                # now validate the configuration                
                validation.validate_settings(
                    app_instance_name,
                    self.tank,
                    self.context,
                    app_schema,
                    app_settings,
                )

            except TankError, e:
                # validation error - probably some issue with the settings!
                # report this as an error message.
                self.log_error("App configuration Error for %s (configured in environment '%s'). "
                               "It will not be loaded: %s" % (app_instance_name, self.__env.disk_location, e))
                continue
            
            except Exception:
                # code execution error in the validation. Report this as an error 
                # with the engire call stack!
                self.log_exception("A general exception was caught while trying to "
                                   "validate the configuration loaded from '%s' for app %s. "
                                   "The app will not be loaded." % (self.__env.disk_location, app_instance_name))
                continue

            # If we're told to reuse existing app instances, check for it and
            # continue if it's already there. This is most likely a context
            # change that's in progress, which means we only want to load apps
            # that aren't already up and running.
            install_path = descriptor.get_path()
            app_pool = self.__application_pool

            if reuse_existing_apps and install_path in app_pool:
                # If we were given an "old" context that's being switched away
                # from, we can run the post change method and do a bit of
                # reinitialization of certain portions of the app.
                if old_context is not None and app_instance_name in app_pool[install_path]:
                    app = self.__application_pool[install_path][app_instance_name]

                    try:
                        # Update the app's internal context pointer.
                        app._set_context(self.context)

                        # Update the app settings.
                        app._set_settings(app_settings)

                        # Set the instance name.
                        app.instance_name = app_instance_name

                        # Make sure our frameworks are up and running properly for
                        # the new context.
                        setup_frameworks(self, app, self.__env, descriptor)

                        # Repopulate the app's commands into the engine.
                        for command_name, command in self.__command_pool.iteritems():
                            if app is command.get("properties", dict()).get("app"):
                                self.__commands[command_name] = command

                        # Run the post method in case there's custom logic implemented
                        # for the app.
                        app.post_context_change(old_context, self.context)
                    except Exception:
                        # If any of the reinitialization failed we will warn and
                        # continue on to a restart of the app via the normal means.
                        self.log_warning(
                            "App %r failed to change context and will be restarted: %s" % (
                                app,
                                traceback.format_exc()
                            )
                        )
                    else:
                        # If the reinitialization of the reused app succeeded, we
                        # just have to add it to the apps list and continue on to
                        # the next app.
                        self.log_debug("App %s successfully reinitialized for new context %s." % (
                            app_instance_name,
                            str(self.context)
                        ))
                        self.__applications[app_instance_name] = app
                        continue
            
            # load the app
            try:
                # now get the app location and resolve it into a version object
                app_dir = descriptor.get_path()

                # create the object, run the constructor
                app = application.get_application(self, 
                                                  app_dir, 
                                                  descriptor, 
                                                  app_settings, 
                                                  app_instance_name, 
                                                  self.__env)
                
                # load any frameworks required
                setup_frameworks(self, app, self.__env, descriptor)
                
                # track the init of the app
                self.__currently_initializing_app = app
                try:
                    app.init_app()
                finally:
                    self.__currently_initializing_app = None
            
            except TankError, e:
                self.log_error("App %s failed to initialize. It will not be loaded: %s" % (app_dir, e))
                
            except Exception:
                self.log_exception("App %s failed to initialize. It will not be loaded." % app_dir)
            else:
                # note! Apps are keyed by their instance name, meaning that we 
                # could theoretically have multiple instances of the same app.
                self.__applications[app_instance_name] = app
                
            # lastly check if there are any compatibility warnings
            messages = black_list.compare_against_black_list(descriptor)
            if len(messages) > 0:
                self.log_warning("Compatibility warnings were issued for %s:" % descriptor)
                for msg in messages:
                    self.log_warning("")
                    self.log_warning(msg)

            # For the sake of potetial context changes, apps and commands are cached
            # into a persistent pool such that they can be reused at some later time.
            # This is required because, during context changes, some apps that were
            # active in the old context might not be active in the new context. Because
            # we might then switch BACK to the old context at some later time, or some
            # future context might simply make use of some of the same apps, we want
            # to keep a running cache of everything that's been initialized over time.
            # This will allow us to reuse those (assuming they support on-the-fly
            # context changes) rather than having to import and instantiate the same
            # app(s) all over again, thereby hurting performance.

            # Likewise, with commands, those from the old context that are not associated
            # with apps that are active in the new context are filtered out of the engine's
            # list of commands. When switching back to the old context, or any time the
            # associated app is reused, we can then add back in the commands that the app
            # had previously registered. With that, we're not required to re-run the init
            # process for the app.

            # Update the persistent application pool for use in context changes.
            for app in self.__applications.values():
                # We will only track apps that we know can handle a context
                # change. Any that do not will not be treated as a persistent
                # app.
                if app.context_change_allowed:
                    app_path = app.descriptor.get_path()

                    if app_path not in self.__application_pool:
                        self.__application_pool[app_path] = dict()

                    self.__application_pool[app.descriptor.get_path()][app_instance_name] = app

            # Update the persistent commands pool for use in context changes.
            for command_name, command in self.__commands.iteritems():
                self.__command_pool[command_name] = command
            
    def __destroy_frameworks(self):
        """
        Destroy frameworks
        """
        # Destroy engine's frameworks
        for fw in self.frameworks.values():
            if not fw.is_shared:
                fw._destroy_framework()
        
        # Destroy shared frameworks
        for fw in self.__shared_frameworks.values():
            fw._destroy_framework()
        self.__shared_frameworks = {}

    def __destroy_apps(self):
        """
        Call the destroy_app method on all loaded apps
        """
        
        for app in self.__applications.values():
            app._destroy_frameworks()
            self.log_debug("Destroying %s" % app)
            app.destroy_app()

    def __register_reload_command(self):
        """
        Registers a "Reload and Restart" command with the engine if any
        running apps are registered via a dev descriptor.
        """
        for app in self.__applications.values():
            if isinstance(app.descriptor, TankDevDescriptor):
                self.log_debug("App %s is registered via a dev descriptor. Will add a reload "
                               "button to the actions listings."  % app)
                from . import restart 
                self.register_command("Reload and Restart", restart, {"short_name": "restart", "type": "context_menu"})                
                # only need one reload button, so don't keep iterating :)
                break

    def __run_post_engine_inits(self):
        """
        Executes the post_engine_init method for all running apps.
        """
        for app in self.__applications.values():
            try:
                app.post_engine_init()
            except TankError, e:
                self.log_error("App %s Failed to run its post_engine_init. It is loaded, but"
                               "may not operate in its desired state! Details: %s" % (app, e))
            except Exception:
                self.log_exception("App %s failed run its post_engine_init. It is loaded, but"
                                   "may not operate in its desired state!" % app)


##########################################################################################
# Engine management

g_current_engine = None

def set_current_engine(eng):
    """
    Sets the current engine
    """
    global g_current_engine
    g_current_engine = eng

def current_engine():
    """
    Returns the current engine
    """
    global g_current_engine
    return g_current_engine


def get_engine_path(engine_name, tk, context):
    """
    Returns the path to the engine corresponding to the given engine name or
    None if the engine could not be found.
    """
    # get environment and engine location
    try:
        (env, engine_descriptor) = _get_env_and_descriptor_for_engine(engine_name, tk, context)
    except TankEngineInitError:
        return None

    # return path to engine code
    engine_path = engine_descriptor.get_path()
    return engine_path


def start_engine(engine_name, tk, context):
    """
    Creates an engine and makes it the current engine.
    Returns the newly created engine object.

    Raises TankEngineInitError if an engine could not be started
    for the passed context.
    """
    # first ensure that an engine is not currently running
    if current_engine():
        raise TankError("An engine (%s) is already running! Before you can start a new engine, "
                        "please shut down the previous one using the command "
                        "tank.platform.current_engine().destroy()." % current_engine())

    # get environment and engine location
    (env, engine_descriptor) = _get_env_and_descriptor_for_engine(engine_name, tk, context)

    # make sure it exists locally
    if not engine_descriptor.exists_local():
        raise TankEngineInitError("Cannot start engine! %s does not exist on disk" % engine_descriptor)

    # get path to engine code
    engine_path = engine_descriptor.get_path()
    plugin_file = os.path.join(engine_path, constants.ENGINE_FILE)

    # Instantiate the engine
    class_obj = loader.load_plugin(plugin_file, Engine)
    engine = class_obj(tk, context, engine_name, env)

    # register this engine as the current engine
    set_current_engine(engine)

    return engine

def find_app_settings(engine_name, app_name, tk, context, engine_instance_name=None):
    """
    Utility method to find the settings for an app in an engine in the
    environment determined for the context by pick environment hook.
    
    :param engine_name: system name of the engine to look for
    :param app_name: system name of the app to look for
    :param tk: tank instance
    :param context: context to use when picking environment
    :param engine_instance_name: The instance name of the engine to look for.
    
    :returns: list of dictionaries containing the engine name, 
              application name and settings for any matching
              applications that are found and that have valid
              settings
    """ 
    app_settings = []
    
    # get the environment via the pick_environment hook
    env_name = __pick_environment(engine_name, tk, context)
    env = tk.pipeline_configuration.get_environment(env_name, context)
    
    # now find all engines whose names match the engine_name:
    for eng in env.get_engines():
        eng_desc = env.get_engine_descriptor(eng)
        eng_sys_name = eng_desc.get_system_name()

        # Make sure that we get the right engine by comparing engine
        # name and instance name, if provided.
        if eng_sys_name != engine_name:
            continue
        if engine_instance_name and engine_instance_name != eng:
            continue
        
        # ok, found engine so look for app:
        for app in env.get_apps(eng):
            app_desc = env.get_app_descriptor(eng, app)
            if app_desc.get_system_name() != app_name:
                continue
            
            # ok, found an app - lets validate the settings as
            # we want to ignore them if they're not valid
            try:
                schema = app_desc.get_configuration_schema()
                settings = env.get_app_settings(eng, app)
                
                # check that the context contains all the info that the app needs
                validation.validate_context(app_desc, context)
                
                # make sure the current operating system platform is supported
                validation.validate_platform(app_desc)
                                
                # for multi engine apps, make sure our engine is supported
                supported_engines = app_desc.get_supported_engines()
                if supported_engines and engine_name not in supported_engines:
                    raise TankError("The app could not be loaded since it only supports "
                                    "the following engines: %s" % supported_engines)
                
                # finally validate the configuration.  
                # Note: context is set to None as we don't 
                # want to fail validation because of an 
                # incomplete context at this stage!
                validation.validate_settings(app, tk, None, schema, settings)
            except TankError:
                # ignore any Tank exceptions to skip invalid apps
                continue

            # settings are valid so add them to return list:
            app_settings.append({"engine_instance":eng, "app_instance":app, "settings":settings})
                    
    return app_settings
    

def start_shotgun_engine(tk, entity_type, context):
    """
    Special, internal method that handles the shotgun engine.

    :param tk:          tank instance
    :param entity_type: type of the entity to use as a target for picking our
                        shotgun environment
    :param context:     context to use for the shotgun engine and its apps.

                        If some apps require a specific context to extract
                        information (e.g. they call a pick_environment hook to
                        get the environment to use based on the context), this
                        should be set to something other than the empty
                        context.
    """

    # bypass the get_environment hook and use a fixed set of environments
    # for this shotgun engine. This is required because of the action caching.
    env = tk.pipeline_configuration.get_environment("shotgun_%s" % entity_type.lower(), context)

    # get the location for our engine
    if not constants.SHOTGUN_ENGINE_NAME in env.get_engines():
        raise TankEngineInitError("Cannot find a shotgun engine in %s. Please contact support." % env)
    
    engine_descriptor = env.get_engine_descriptor(constants.SHOTGUN_ENGINE_NAME)

    # make sure it exists locally
    if not engine_descriptor.exists_local():
        raise TankEngineInitError("Cannot start engine! %s does not exist on disk" % engine_descriptor)

    # get path to engine code
    engine_path = engine_descriptor.get_path()
    plugin_file = os.path.join(engine_path, constants.ENGINE_FILE)

    # Instantiate the engine
    class_obj = loader.load_plugin(plugin_file, Engine)
    obj = class_obj(tk, context, constants.SHOTGUN_ENGINE_NAME, env)

    # register this engine as the current engine
    set_current_engine(obj)

    return obj

def get_environment_from_context(tk, context):
    """
    Returns an environment object given a context. 
    Returns None if no environment was found. 
    """
    try:
        env_name = tk.execute_core_hook(constants.PICK_ENVIRONMENT_CORE_HOOK_NAME, context=context)
    except Exception, e:
        raise TankError("Could not resolve an environment for context '%s'. The pick "
                        "environment hook reported the following error: %s" % (context, e))
    
    if env_name is None:
        return None
    
    return tk.pipeline_configuration.get_environment(env_name, context)

def show_global_busy(title, details):
    """
    Convenience method.
    
    Displays or updates a global busy/progress indicator window tied to the currently running engine.
    For more details and documentation, see the engine class documentation of this method.

    :params title: Short descriptive title of what is happening
    :params details: Detailed message describing what is going on.
    """
    engine = current_engine()
    if engine:
        engine.show_busy(title, details)        
    
def clear_global_busy():
    """
    Convenience method.
    
    Closes any open global progress indicator window tied to the currently running engine.
    For more details and documentation, see engine class documentation of this method.
    """
    engine = current_engine()
    if engine:
        engine.clear_busy()

##########################################################################################
# utilities

def _get_env_and_descriptor_for_engine(engine_name, tk, context):
    """
    Utility method to return commonly needed objects when instantiating engines.

    Raises TankEngineInitError if the engine name cannot be found.
    """
    # get the environment via the pick_environment hook
    env_name = __pick_environment(engine_name, tk, context)

    # get the env object based on the name in the pick env hook
    env = tk.pipeline_configuration.get_environment(env_name, context)
    
    # make sure that the environment has an engine instance with that name
    if not engine_name in env.get_engines():
        raise TankEngineInitError("Cannot find an engine instance %s in %s." % (engine_name, env))

    # get the location for our engine
    engine_descriptor = env.get_engine_descriptor(engine_name)

    return (env, engine_descriptor)


def __pick_environment(engine_name, tk, context):
    """
    Call out to the pick_environment core hook to determine which environment we should load
    based on the current context. The Shotgun engine provides its own implementation.
    """

    try:
        env_name = tk.execute_core_hook(constants.PICK_ENVIRONMENT_CORE_HOOK_NAME, context=context)
    except Exception, e:
        raise TankEngineInitError("Engine %s cannot initialize - the pick environment hook "
                                 "reported the following error: %s" % (engine_name, e))

    if env_name is None:
        # the pick_environment hook could not determine an environment
        # this may be because an incomplete Context was passed.
        # without an environment, engine creation cannot succeed.
        # raise an exception with a message
        raise TankEngineInitError("Engine %s cannot initialize - the pick environment hook was not "
                                  "able to return an environment to use, given the context %s. "
                                  "Usually this is because the context contains insufficient information "
                                  "for an environment to be determined." % (engine_name, context))

    return env_name

