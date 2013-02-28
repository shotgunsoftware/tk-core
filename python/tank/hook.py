"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Defines the base class for all Tank Hooks.

"""
import os
from . import loader
from .platform import constants

_HOOKS_CACHE = {}

class Hook(object):
    """
    Base class for a "hook", a simple extension mechanism that is used in the core,
    engines and apps. The "parent" of the hook is the object that executed the hook,
    which presently could be an instance of the Tank API for core hooks, or an Engine
    or Application instance.
    """
    
    def __init__(self, parent):
        self.__parent = parent
    
    @property
    def parent(self):
        return self.__parent
    
    def execute(self):
        return None

def clear_hooks_cache():
    """
    Clears the cache where tank keeps hook classes
    """
    global _HOOKS_CACHE
    _HOOKS_CACHE = {}

def execute_hook(hook_path, parent, **kwargs):
    hook_class = _get_hook_class(hook_path)
    hook = hook_class(parent)
    return hook.execute(**kwargs)

def _get_hook_class(hook_path):
    """
    Returns a hook class given its path
    """
    
    if hook_path not in _HOOKS_CACHE:
        # cache it
        _HOOKS_CACHE[hook_path] = loader.load_plugin(hook_path, Hook)
    
    return _HOOKS_CACHE[hook_path]
