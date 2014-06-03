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
Defines the base class for all Tank Hooks.

"""
import os
from . import loader
from .platform import constants
from .errors import TankError

_HOOKS_CACHE = {}
g_current_hook_baseclass = None

class Hook(object):
    """
    Base class for a "hook", a simple extension mechanism that is used in the core,
    engines and apps. The "parent" of the hook is the object that executed the hook,
    which presently could be an instance of the Sgtk API for core hooks, or an Engine
    or Application instance.
    """
    
    def __init__(self, parent):
        self.__parent = parent
    
    @property
    def parent(self):
        return self.__parent
    
    def get_publish_path(self, sg_publish_data):
        """
        Resolves a local path on disk given a shotgun 
        data dictionary representing a publish.
        
        :param sg_publish_data: Shotgun dictionary containing
                                information about a publish. Needs to at least 
                                contain a type, id and a path key. 
        :returns: String representing a local path on disk.
        """
        return self.get_publish_paths([ sg_publish_data ])[0]
        
    def get_publish_paths(self, sg_publish_data_list):
        """
        Returns several local paths on disk given a
        list of shotgun data dictionaries representing publishes.
        
        :param sg_publish_data_list: List of shotgun data dictionaries 
                                     containing publish data. Each dictionary 
                                     needs to at least contain a type, id and 
                                     a path key.
        :returns: List of strings representing local paths on disk.
        """
        paths = []
        for sg_data in sg_publish_data_list:
            path_field = sg_data.get("path")
            if path_field is None:
                raise TankError("Cannot resolve path from publish! The shotgun dictionary %s does "
                                "not contain a valid path definition" % sg_data)
            
            local_path = path_field.get("local_path")
            if local_path is None:
                raise TankError("Cannot resolve path from publish! The shotgun dictionary %s does "
                                "not contain a valid path definition" % sg_data)
            paths.append(local_path)
        
        return paths
    
    def load_framework(self, framework_instance_name):
        """
        Loads and returns a framework given an environment instance name.
        Only works for hooks that are executed from apps and frameworks.
        """
        # avoid circular refs
        from .platform import framework
        try:
            engine = self.__parent.engine
        except:
            raise TankError("Cannot load framework %s for %r - it does not have a "
                            "valid engine property!" % (framework_instance_name, self.__parent))
            
        return framework.load_framework(engine, engine.get_env(), framework_instance_name)
    
    def execute(self):
        return None

def clear_hooks_cache():
    """
    Clears the cache where tank keeps hook classes
    """
    global _HOOKS_CACHE
    _HOOKS_CACHE = {}


def execute_hook(hook_path, parent, **kwargs):
    """
    Executes a hook, old-school style. 
    
    A hook is a python file which 
    contains exactly one class which derives (at some point 
    in its inheritance tree) from the Hook base class.
    
    Once the file has been loaded (and cached), the execute()
    method will be called and any optional arguments pass to 
    this method will be forwarded on to that execute() method.
    
    :param hook_path: Full path to the hook python file
    :param parent: Parent object. This will be accessible inside
                   the hook as self.parent, and is typically an 
                   app, engine or core object.
    :returns: Whatever the hook returns.
    """
    return execute_hook_method([hook_path], parent, None, **kwargs)

def execute_hook_method(hook_paths, parent, method_name, **kwargs):
    """
    New style hook execution, with method arguments and support for inheritance.
    
    This method takes a list of hook paths and will load each of the classes
    in, while maintaining the correct state of the class returned via 
    get_hook_baseclass(). Once all classes have been successfully loaded, 
    the last class in the list is instantiated and the specified method
    is executed.
    
        Example: ["/tmp/a.py", "/tmp/b.py", "/tmp/c.py"]
        
        1. The code in a.py is loaded in. get_hook_baseclass() will return Hook
           at this point. class HookA is returned from our plugin loader.
        
        2. /tmp/b.py is loaded in. get_hook_baseclass() now returns HookA, so 
           if the hook code in B utilises get_hook_baseclass, this will will
           set up an inheritance relationship with A
        
        3. /tmp/c.py is finally loaded in, get_hook_baseclass() now returns HookB.
        
        4. HookC class is instantiated and method method_name is executed.
    
    :param hook_paths: List of full paths to hooks, in inheritance order.
    :param parent: Parent object. This will be accessible inside
                   the hook as self.parent, and is typically an 
                   app, engine or core object.
    :param method_name: method to execute. If None, the default method will be executed.
    :returns: Whatever the hook returns.
    """    
    global g_current_hook_baseclass
    
    if method_name is None:
        method_name = constants.DEFAULT_HOOK_METHOD
    
    g_current_hook_baseclass = Hook
    
    for hook_path in hook_paths:

        if not os.path.exists(hook_path):
            raise TankError("Cannot execute hook '%s' - this file does not exist on disk!" % hook_path)
    
        if hook_path not in _HOOKS_CACHE:
            # cache it
            _HOOKS_CACHE[hook_path] = loader.load_plugin(hook_path, Hook)

        # set current state
        g_current_hook_baseclass = _HOOKS_CACHE[hook_path] 
            
    
    # all class construction done. g_current_hook_baseclass contains
    # the last class we iterated over. This is the one we want to 
    # instantiate.
    
    # instantiate the class
    hook = g_current_hook_baseclass(parent)
    
    # get the method
    try:
        hook_method = getattr(hook, method_name)
    except AttributeError:
        raise TankError("Cannot execute hook '%s' - the hook class does not "
                        "have a '%s' method!" % (hook, method_name))
    
    # execute the method
    ret_val = hook_method(**kwargs)
    
    return ret_val

def get_hook_baseclass():
    """
    Returns the base class for a hook
    """
    return g_current_hook_baseclass
