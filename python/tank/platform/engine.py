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
import sys
import traceback
import weakref
        
from .. import loader
from .. import hook
from ..errors import TankError, TankEngineInitError
from ..deploy import descriptor

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
        self.__commands = {}
        self.__currently_initializing_app = None
        
        self._qt_widget_trash = []
        self.__created_qt_dialogs = []
        self.__qt_debug_info = {}
        
        self.__commands_that_need_prefixing = []
        
        # get the engine settings
        settings = self.__env.get_engine_settings(self.__engine_instance_name)
        
        # get the descriptor representing the engine        
        descriptor = self.__env.get_engine_descriptor(self.__engine_instance_name)        
        
        # init base class
        TankBundle.__init__(self, tk, context, settings, descriptor)

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
            # only append to python path if __init__.py does not exist
            # if __init__ exists, we should use the special tank import instead
            init_path = os.path.join(python_path, "__init__.py")
            if not os.path.exists(init_path):
                self.log_debug("Appending to PYTHONPATH: %s" % python_path)
                sys.path.append(python_path)


        # initial init pass on engine
        self.init_engine()

        # try to pull in QT classes and assign to tank.platform.qt.XYZ
        base_def = self._define_qt_base()
        qt.QtCore = base_def.get("qt_core")
        qt.QtGui = base_def.get("qt_gui")
        qt.TankDialogBase = base_def.get("dialog_base")
        
        # now load all apps and their settings
        self.__load_apps()
        
        # now run the post app init
        self.post_app_init()
        
        # emit an engine started event
        tk.execute_hook(constants.TANK_ENGINE_INIT_HOOK_NAME, engine=self)
        
        
        self.log_debug("Init complete: %s" % self)
        
        
        
        
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
    
    ##########################################################################################
    # init and destroy
    
    def init_engine(self):
        """
        Sets up the engine into an operational state.
        
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
        for fw in self.frameworks.values():
            fw._destroy_framework()

        self.__destroy_apps()
        
        self.log_debug("Destroying %s" % self)
        self.destroy_engine()
        
        # finally remove the current engine reference
        set_current_engine(None)
        
        # now clear the hooks cache to make sure fresh hooks are loaded the 
        # next time an engine is initialized
        hook.clear_hooks_cache()
    
    def destroy_engine(self):
        """
        Called when the engine should tear down itself and all its apps.
        Implemented by deriving classes.
        """
        pass
    
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
            
        self.__commands[name] = { "callback": callback, "properties": properties }
        
                
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
    # private and protected methods
    
    def _debug_track_qt_widget(self, widget):
        """
        Add the qt widget to a list of objects to be tracked. 
        """
        if widget:
            self.__qt_debug_info[widget.__repr__()] = weakref.ref(widget)
                
    def get_debug_tracked_qt_widgets(self):
        """
        Print debug info about created Qt dialogs and widgets
        """
        return self.__qt_debug_info                

    def _get_dialog_parent(self):
        """
        Get the QWidget parent for all dialogs created through
        show_dialog & show_modal.
        """
        # By default, this will return the QApplication's active window:
        from .qt import QtGui
        return QtGui.QApplication.activeWindow()
                
    def _create_dialog(self, title, bundle, widget, parent):
        """
        Create a TankQDialog with the specified widget embedded.
        This also connects to the dialogs dialog_closed event so
        that it can clean up when the dialog is closed.
        """
        from .qt import tankqdialog
        
        # create a dialog to put it inside
        dialog = tankqdialog.TankQDialog(title, bundle, widget, parent)

        # keep a reference to all created dialogs to make GC happy
        self.__created_qt_dialogs.append(dialog)
        
        # watch for the dialog closing so that we can clean up
        dialog.dialog_closed.connect(self._on_dialog_closed)
        
        # keep track of some info for debugging object lifetime
        self._debug_track_qt_widget(dialog)
        
        return dialog

    def _create_widget(self, widget_class, *args, **kwargs):
        """
        Create an instance of the specified widget_class.  This 
        wraps the widget_class so that the TankQDialog it is
        embedded in can connect to it more easily in order to
        handle the close event
        """
        from .qt import tankqdialog
                
        # construct the widget object
        derived_widget_class = tankqdialog.TankQDialog.wrap_widget_class(widget_class)
        widget = derived_widget_class(*args, **kwargs)
        
        # keep track of some info for debugging object lifetime
        self._debug_track_qt_widget(widget)
        
        return widget
    
    def _create_dialog_with_widget(self, title, bundle, widget_class, *args, **kwargs):
        """
        Create an sgtk TankQDialog with a widget instantiated from widget_class
        embeded in the main section.
        """
        # get the parent for the dialog:
        parent = self._get_dialog_parent()
        
        # create the widget:
        widget = self._create_widget(widget_class, *args, **kwargs)
        
        # create the dialog:
        dialog = self._create_dialog(title, bundle, widget, parent)
        return (dialog, widget)
    
    def _on_dialog_closed(self, dlg):
        """
        Called when a dialog created by this engine is
        closed.
        """
        # first, detach the widget from the dialog.  This allows
        # the two objects to be cleaned up seperately menaing the
        # lifetime of the widget can be better managed
        widget = dlg.detach_widget()
        
        # add the dlg and it's contained widget to the list
        # of widgets to delete at some point!
        self._qt_widget_trash.append(dlg)
        self._qt_widget_trash.append(widget)
        
        if dlg in self.__created_qt_dialogs:
            # don't need to track this dialog any longer
            self.__created_qt_dialogs.remove(dlg)
            
        # disconnect from the dialog:
        dlg.dialog_closed.disconnect(self._on_dialog_closed)
        
        # clear temps
        dlg = None
        widget = None
        
        # finally, clean up the widget trash:
        self._cleanup_widget_trash()
        

    def _cleanup_widget_trash(self):
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
        for widget in self._qt_widget_trash:
            # There should be 3 references:
            # 1. self._qt_widget_trash[n]
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
        self._qt_widget_trash = still_trash
        self.log_debug("Widget trash contains %d widgets" % (len(self._qt_widget_trash)))

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
        
            
    ##########################################################################################
    # private         
        
    def __load_apps(self):
        """
        Populate the __applications dictionary, skip over apps that fail to initialize.
        """
        for app_instance_name in self.__env.get_apps(self.__engine_instance_name):
            
            # get a handle to the app bundle
            descriptor = self.__env.get_app_descriptor(self.__engine_instance_name, app_instance_name)
            if not descriptor.exists_local():
                self.log_error("Cannot start app! %s does not exist on disk." % descriptor)
                continue
            
            # Load settings for app - skip over the ones that don't validate
            try:
                # get the app settings data and validate it.
                app_schema = descriptor.get_configuration_schema()
                app_settings = self.__env.get_app_settings(self.__engine_instance_name, app_instance_name)

                # check that the context contains all the info that the app needs
                if self.__engine_instance_name != constants.SHOTGUN_ENGINE_NAME: 
                    # special case! The shotgun engine is special and does not have a 
                    # context until you actually run a command, so disable the valiation
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
                validation.validate_settings(app_instance_name, self.tank, self.context, app_schema, app_settings)
                
                    
            except TankError, e:
                # validation error - probably some issue with the settings!
                # report this as an error message.
                self.log_error("App configuration Error for %s. It will not be loaded: %s" % (app_instance_name, e))
                continue
            
            except Exception:
                # code execution error in the validation. Report this as an error 
                # with the engire call stack!
                self.log_exception("A general exception was caught while trying to " 
                                   "validate the configuration for app %s. "
                                   "The app will not be loaded." % app_instance_name)
                continue
            
                                    
            # load the app
            try:
                # now get the app location and resolve it into a version object
                app_dir = descriptor.get_path()

                # create the object, run the constructor
                app = application.get_application(self, app_dir, descriptor, app_settings, app_instance_name)
                
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
                
            

    def __destroy_apps(self):
        """
        Call the destroy_app method on all loaded apps
        """
        
        for app in self.__applications.values():
            app._destroy_frameworks()
            self.log_debug("Destroying %s" % app)
            app.destroy_app()


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
        (env, engine_descriptor) = __get_env_and_descriptor_for_engine(engine_name, tk, context)
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
    (env, engine_descriptor) = __get_env_and_descriptor_for_engine(engine_name, tk, context)

    # make sure it exists locally
    if not engine_descriptor.exists_local():
        raise TankEngineInitError("Cannot start engine! %s does not exist on disk" % engine_descriptor)

    # get path to engine code
    engine_path = engine_descriptor.get_path()
    plugin_file = os.path.join(engine_path, constants.ENGINE_FILE)

    # Instantiate the engine
    class_obj = loader.load_plugin(plugin_file, Engine)
    obj = class_obj(tk, context, engine_name, env)

    # register this engine as the current engine
    set_current_engine(obj)

    return obj

def find_app_settings(engine_name, app_name, tk, context):
    """
    Utility method to find the settings for an app in an engine in the
    environment determined for the context by pick environment hook.
    
    :param engine_name: system name of the engine to look for
    :param app_name: system name of the app to look for
    :param tk: tank instance
    :param context: context to use when picking environment
    
    :returns: list of dictionaries containing the engine name, 
              application name and settings for any matching
              applications that are found and that have valid
              settings
    """ 
    app_settings = []
    
    # get the environment via the pick_environment hook
    env_name = __pick_environment(engine_name, tk, context)

    env = tk.pipeline_configuration.get_environment(env_name, context)
    
    # now find all engines whose descriptor matches the engine_name:
    for eng in env.get_engines():
        eng_desc = env.get_engine_descriptor(eng)
        if eng_desc.get_system_name() != engine_name:
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
    

def start_shotgun_engine(tk, entity_type, context=None):
    """
    Special, internal method that handles the shotgun engine.
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
        env_name = tk.execute_hook(constants.PICK_ENVIRONMENT_CORE_HOOK_NAME, context=context)
    except Exception, e:
        raise TankError("Could not resolve an environment for context '%s'. The pick "
                        "environment hook reported the following error: %s" % (context, e))
    
    if env_name is None:
        return None
    
    return tk.pipeline_configuration.get_environment(env_name, context)


##########################################################################################
# utilities

def __get_env_and_descriptor_for_engine(engine_name, tk, context):
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
        env_name = tk.execute_hook(constants.PICK_ENVIRONMENT_CORE_HOOK_NAME, context=context)
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

