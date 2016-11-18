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
Base class for Abstract classes for Engines, Apps and Frameworks

"""

import os
import sys
import imp
import uuid
from ..errors import TankError
from .errors import TankContextChangeNotSupportedError
from . import constants
from .import_stack import ImportStack
from .bundle_base import TankBundleBase, resolve_default_value


class TankBundle(TankBundleBase):
    """
    Abstract Base class for any engine, framework app etc in tank
    """

    def __init__(self, tk, context, settings, descriptor, env, log):
        """
        Constructor.

        :param tk: :class:`~sgtk.Sgtk` instance
        :param context: A context object to define the context on disk where the engine is operating
        :type context: :class:`~sgtk.Context`
        :param settings: dictionary of settings to associate with this object
        :param descriptor: Descriptor pointing at associated code.
        :param env: An Environment object to associate with this bundle.
        :param log: A python logger to associate with this bundle
        """
        TankBundleBase.__init__(self, tk, context, settings, descriptor, env, log)
        self.__tk = tk
        self.__context = context
        self.__settings = settings
        self.__sg = None
        self.__descriptor = descriptor    
        self.__environment = env
        self.__log = log
        self.__cache_location = {}
        self.__module_uid = None
        self.__frameworks = {}

        # emit an engine started event
        tk.execute_core_hook(constants.TANK_BUNDLE_INIT_HOOK_NAME, bundle=self)
        
    ##########################################################################################
    # properties

    @property
    def icon_256(self):
        """
        Path to a 256x256 pixel png file which describes the item
        """
        return self.__descriptor.icon_256

    @property
    def style_constants(self):
        """
        Returns a dictionary of style constants. These can be used to build
        UIs using standard colors and other style components. All keys returned
        in this dictionary can also be used inside a style.qss that lives 
        at the root level of the app, engine or framework. Use a 
        ``{{DOUBLE_BACKET}}`` syntax in the stylesheet file, for example::
        
            QWidget
            { 
                color: {{SG_FOREGROUND_COLOR}};
            }
        
        This property returns the values for all constants, for example::
        
            { 
              "SG_HIGHLIGHT_COLOR": "#18A7E3",
              "SG_ALERT_COLOR": "#FC6246",
              "SG_FOREGROUND_COLOR": "#C8C8C8"
            }
        
        :returns: Dictionary. See above for example 
        """
        return constants.SG_STYLESHEET_CONSTANTS    

    @property
    def documentation_url(self):
        """
        Return the relevant documentation url for this item.
        
        :returns: url string, None if no documentation was found
        """
        return self.__descriptor.documentation_url

    @property
    def support_url(self):
        """
        Return the relevant support url for this item.
        
        :returns: url string, None if no documentation was found
        """
        return self.__descriptor.support_url

    @property
    def cache_location(self):
        """
        An item-specific location on disk where the app or engine can store
        random cache data. This location is guaranteed to exist on disk.

        This location is configurable via the ``cache_location`` hook.
        It is typically points at a path in the local filesystem, e.g
        on for example on the mac::

            ~/Library/Caches/Shotgun/SITENAME/PROJECT_ID/BUNDLE_NAME

        This can be used to store cache data that the app wants to reuse across
        sessions::

            stored_query_data_path = os.path.join(self.cache_location, "query.dat")

        """
        project_id = self.__tk.pipeline_configuration.get_project_id()
        return self.get_project_cache_location(project_id)

    @property
    def context_change_allowed(self):
        """
        Whether a context change is allowed without the need for a restart.
        If a bundle supports on-the-fly context changing, this property should
        be overridden in the deriving class and forced to return True.

        :returns: bool
        """
        return False

    @property
    def frameworks(self):
        """
        List of all frameworks associated with this item
        
        :returns: List of framework objects
        """
        return self.__frameworks


    ##########################################################################################
    # public methods
    def change_context(self, new_context):
        """
        Abstract method for context changing.

        Implemented by deriving classes that wish to support context changes and
        require specific logic to do so safely.

        :param new_context: The context being changed to.
        :type context: :class:`~sgtk.Context`
        """
        if not self.context_change_allowed:
            self.log_debug("Bundle %r does not allow context changes." % self)
            raise TankContextChangeNotSupportedError()

    def pre_context_change(self, old_context, new_context):
        """
        Called before a context change.

        Implemented by deriving classes.

        :param old_context:     The context being changed away from.
        :type old_context: :class:`~sgtk.Context`
        :param new_context:     The context being changed to.
        :type new_context: :class:`~sgtk.Context`
        """
        pass

    def post_context_change(self, old_context, new_context):
        """
        Called after a context change.

        Implemented by deriving classes.

        :param old_context:     The context being changed away from.
        :type old_context: :class:`~sgtk.Context`
        :param new_context:     The context being changed to.
        :type new_context: :class:`~sgtk.Context`
        """
        pass

    def import_module(self, module_name):
        """
        Special import command for Toolkit bundles. Imports the python folder inside
        an app and returns the specified module name that exists inside the python folder.

        Each Toolkit App or Engine can have a python folder which contains additional
        code. In order to ensure that Toolkit can run multiple versions of the same app,
        as well as being able to reload app code if it changes, it is recommended that
        this method is used whenever you want to access code in the python location.

        For example, imagine you had the following structure::

            tk-multi-mybundle
               |- app.py or engine.py or framework.py
               |- info.yml
               \- python
                   |- __init__.py   <--- Needs to contain 'from . import tk_multi_mybundle'
                   \- tk_multi_mybundle

        The above structure is a standard Toolkit app outline. ``app.py`` is a
        light weight wrapper and the python module
        ``tk_multi_myapp`` module contains the actual code payload.
        In order to import this in a Toolkit friendly way, you need to run
        the following when you want to load the payload module inside of app.py::

            module_obj = self.import_module("tk_multi_myapp")

        """
        # local import to avoid cycles

        # first, set the module we are currently processing
        ImportStack.push_current_bundle(self)
        
        try:
        
            # get the python folder
            python_folder = os.path.join(self.disk_location, constants.BUNDLE_PYTHON_FOLDER)
            if not os.path.exists(python_folder):
                raise TankError("Cannot import - folder %s does not exist!" % python_folder)
            
            # and import
            if self.__module_uid is None:
                self.log_debug("Importing python modules in %s..." % python_folder)
                # alias the python folder with a UID to ensure it is unique every time it is imported
                self.__module_uid = "tkimp%s" % uuid.uuid4().hex
                imp.load_module(self.__module_uid, None, python_folder, ("", "", imp.PKG_DIRECTORY) )
            
            # we can now find our actual module in sys.modules as GUID.module_name
            mod_name = "%s.%s" % (self.__module_uid, module_name)
            if mod_name not in sys.modules:
                raise TankError("Cannot find module %s as part of %s!" % (module_name, python_folder))
            
            # lastly, append our own object to the added module. This is to make it easier to 
            # do elegant imports in the class scope via the tank.platform.import_framework method
            sys.modules[mod_name]._tank_bundle = self
        
        finally:
            # no longer processing this one
            ImportStack.pop_current_bundle()
        
        return sys.modules[mod_name]

    def get_project_cache_location(self, project_id):
        """
        Gets the bundle's cache-location path for the given project id.

        :param project_id:  The project Entity id number.
        :type project_id:   int

        :returns:           Cache location directory path.
        :rtype str:
        """
        # this method is memoized for performance since it is being called a lot!
        if self.__cache_location.get(project_id) is None:

            self.__cache_location[project_id] = self.__tk.execute_core_hook_method(
                constants.CACHE_LOCATION_HOOK_NAME,
                "get_bundle_data_cache_path",
                project_id=project_id,
                plugin_id=self.__tk.pipeline_configuration.get_plugin_id(),
                pipeline_configuration_id=self.__tk.pipeline_configuration.get_shotgun_id(),
                bundle=self
            )

        return self.__cache_location[project_id]

    def ensure_folder_exists(self, path):
        """
        Make sure that the given folder exists on disk.
        Convenience method to make it easy for apps and engines to create folders in a
        standardized fashion. While the creation of high level folder structure such as
        Shot and Asset folders is typically handled by the folder creation system in
        Toolkit, Apps tend to need to create leaf-level folders such as publish folders
        and work areas. These are often created just in time of the operation.

        .. note:: This method calls out to the ``ensure_folder_exists`` core hook, making
                  the I/O operation user configurable. We recommend using this method
                  over the methods provided in ``sgtk.util.filesystem``.

        :param path: path to create
        """        
        try:
            self.__tk.execute_core_hook("ensure_folder_exists", path=path, bundle_obj=self)
        except Exception, e:
            raise TankError("Error creating folder %s: %s" % (path, e))
