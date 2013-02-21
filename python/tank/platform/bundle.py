"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Base class for Abstract classes for Engines, Apps and Frameworks

"""

import os
import sys
import imp
import uuid
from .. import hook
from ..errors import TankError

from . import constants

class TankBundle(object):
    """
    Abstract Base class for any engine, framework app etc in tank
    """

    def __init__(self, tk, context, settings, descriptor):
        """
        Constructor.
        """
        self.__tk = tk
        self.__context = context
        self.__settings = settings
        self.__sg = None
        self.__module_uid = None
        self.__descriptor = descriptor    
        self.__frameworks = {}

        # emit an engine started event
        tk.execute_hook(constants.TANK_BUNDLE_INIT_HOOK_NAME, bundle=self)
        

    ##########################################################################################
    # properties

    @property
    def name(self):
        """
        The short name for the item (e.g. tk-maya)
        
        :returns: name as string
        """
        return self.__descriptor.get_system_name()
    
    @property
    def display_name(self):
        """
        The displayname for the item (e.g. Maya Engine)
        
        :returns: display name as string
        """
        return self.__descriptor.get_display_name()

    @property
    def description(self):
        """
        A short description of the item
        
        :returns: string
        """
        return self.__descriptor.get_description()

    @property
    def version(self):
        """
        The version of the item (e.g. 'v0.2.3')
        
        :returns: string representing the version
        """
        return self.__descriptor.get_version()

    @property
    def documentation_url(self):
        """
        Return the relevant documentation url for this item.
        
        :returns: url string, None if no documentation was found
        """
        return self.__descriptor.get_doc_url()        

    @property
    def disk_location(self):
        """
        The folder on disk where this item is located
        """
        path_to_this_file = os.path.abspath(sys.modules[self.__module__].__file__)
        return os.path.dirname(path_to_this_file)

    @property
    def cache_location(self):
        """
        An item-specific location on disk where the app or engine can store
        random cache data. This location is guaranteed to exist on disk.
        """
        # organize caches by app name
        folder = os.path.join(self.__tk.project_path, "tank", "cache", self.name)
        if not os.path.exists(folder):
            # create it using open permissions (not via hook since we want to be in control
            # of permissions inside the tank folders)
            old_umask = os.umask(0)
            os.makedirs(folder, 0777)
            os.umask(old_umask)                
        
        return folder


    @property
    def context(self):
        """
        The current context associated with this item
        
        :returns: context object
        """
        return self.__context

    @property
    def shotgun(self):
        """
        Delegates to the Tank API instance's shotgun connection, which is lazily
        created the first time it is requested.
        
        :returns: Shotgun API handle
        """
        return self.__tk.shotgun
    
    @property
    def tank(self):
        """
        Returns a Tank API instance associated with this item
        
        :returns: Tank API handle 
        """
        return self.__tk
    
    @property
    def frameworks(self):
        """
        List of all frameworks associated with this item
        
        :returns: List of framework objects
        """
        return self.__frameworks
    
    ##########################################################################################
    # public methods

    def import_module(self, module_name):
        """
        Special Tank import command for app modules. Imports the python folder inside
        an app and returns the specified module name that exists inside the python folder.
        
        For more information, see the API documentation.
        """
        
        # get the python folder
        python_folder = os.path.join(self.disk_location, constants.BUNDLE_PYTHON_FOLDER)
        if not os.path.exists(python_folder):
            raise TankError("Cannot import - folder %s does not exist!" % python_folder)
        
        # and import
        if self.__module_uid is None:
            self.log_debug("Importing python modules in %s..." % python_folder)
            # alias the python folder with a UID to ensure it is unique every time it is imported
            self.__module_uid = uuid.uuid4().hex
            imp.load_module(self.__module_uid, None, python_folder, ("", "", imp.PKG_DIRECTORY) )
        
        # we can now find our actual module in sys.modules as GUID.module_name
        mod_name = "%s.%s" % (self.__module_uid, module_name)
        if mod_name not in sys.modules:
            raise TankError("Cannot find module %s as part of %s!" % (module_name, python_folder))
        
        # lastly, append our own object to the added module. This is to make it easier to 
        # do elegant imports in the class scope via the tank.platform.import_framework method
        sys.modules[mod_name]._tank_bundle = self
        
        return sys.modules[mod_name]


    def get_setting(self, key, default=None):
        """
        Get a value from the item's settings

        :param key: config name
        :param default: default value to return
        """
        return self.__settings.get(key, default)
            
    def get_template(self, key):
        """
        A shortcut for looking up which template is referenced in the given setting, and
        calling get_template_by_name() on it.
        """

        # handle the special form where the template is computed in a hook.
        # 
        # if the template parameter is on the form
        # a) hook|foo_bar
        # b) hook|foo_bar|testing|testing
        #        
        # The following hook will be called
        # a) foo_bar with parameters []
        # b) foo_bar with parameters [testing, testing]
        #
        template_name = self.get_setting(key)
        if template_name.startswith("hook|"):
            # get the template name from a hook
            chunks = template_name.split("|")
            hook_name = chunks[1]
            params = chunks[2:] 
            template_name = self.__tk.execute_hook(hook_name, 
                                                   setting=key, 
                                                   bundle_obj=self, 
                                                   extra_params=params)
        
        return self.get_template_by_name(template_name)
    
    def get_template_by_name(self, template_name):
        """
        Find the named template.
        """
        return self.tank.templates.get(template_name)
            
    def execute_hook(self, key, **kwargs):
        """
        Shortcut for grabbing the hook name used in the settings, 
        then calling execute_hook_by_name() on it.
        """
        hook_name = self.get_setting(key)
        if hook_name == constants.TANK_BUNDLE_DEFAULT_HOOK_SETTING:
            # hook settings points to the default one.
            # find the name of the hook from the manifest
            manifest = self.__descriptor.get_configuration_schema()
            #
            # Entries are on the following form
            #            
            # hook_publish_file:
            #    type: hook
            #    description: Called when a file is published, e.g. copied from a work area to a publish area.
            #    parameters: [source_path, target_path]
            #    default_value: maya_publish_file
            #
            default_hook_name = manifest.get(key).get("default_value", "undefined")
            hook_path = os.path.join(self.disk_location, "hooks", "%s.py" % default_hook_name)  
            ret_val = hook.execute_hook(hook_path, self, **kwargs)
             
        else:
            # use a specific hook in the user hooks folder
            ret_val = self.execute_hook_by_name(hook_name, **kwargs)
        
        return ret_val

    def execute_hook_by_name(self, hook_name, **kwargs):
        """
        Execute an arbitrary hook located in the hooks folder for this project.
        The hook_name is the name of the python file in which the hook resides,
        without the file extension.
        
        In most use cases, the execute_hook method is the preferred way to 
        access a hook from an app.
        
        This method is typically only used when you want to execute an arbitrary
        list of hooks, for example if you want to run a series of arbitrary
        user defined pre-publish validation hooks.  
        """
        hook_folder = constants.get_hooks_folder(self.tank.project_path)
        hook_path = os.path.join(hook_folder, "%s.py" % hook_name)
        return hook.execute_hook(hook_path, self, **kwargs)
    
    def ensure_folder_exists(self, path):
        """
        Convenience method to make it easy for apps and engines to create folders
        in a standardized fashion. While the creation of high level folder structure
        such as Shot and Asset folders is typically handled by the folder creation system
        in Tank, Apps tend to need to create leaf-level folders such as publish folders
        and work areas. These are often created just in time of the operation.
        
        :param path: path to create
        """        
        try:
            self.__tk.execute_hook("ensure_folder_exists", path=path, bundle_obj=self)
        except Exception, e:
            raise TankError("Error creating folder %s: %s" % (path, e))
        
        
