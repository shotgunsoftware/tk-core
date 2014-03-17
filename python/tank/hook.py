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
    Executes a hook. A hook is a python file which 
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
    return execute_hook_method(hook_path, parent, constants.DEFAULT_HOOK_METHOD, **kwargs)

def execute_hook_method(hook_path, parent, method_name, **kwargs):
    """
    Exactly the same as execute_hook() but instead of 
    executing the execute() method, the method given in 
    method_name is executed
    """
    if not os.path.exists(hook_path):
        raise TankError("Cannot execute hook '%s' - this file does not exist on disk!" % hook_path)
    
    if hook_path not in _HOOKS_CACHE:
        # cache it
        _HOOKS_CACHE[hook_path] = loader.load_plugin(hook_path, Hook)
    
    # get the class
    hook_class = _HOOKS_CACHE[hook_path]
    
    # instantiate the class
    hook = hook_class(parent)
    
    # get the method
    try:
        hook_method = getattr(hook, method_name)
    except AttributeError:
        raise TankError("Cannot execute hook '%s' - the hook class does not "
                        "have a '%s' method!" % (hook_path, method_name))
    
    # execute the method
    ret_val = hook_method(**kwargs)
    
    return ret_val

def get_hook_baseclass():
    """
    Returns the base class for a hook
    """
    return Hook
