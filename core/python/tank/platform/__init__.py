"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------
"""

# Engine management
from .engine import start_engine, current_engine

# base classes to derive from
from .application import Application
from .engine import Engine
from .framework import Framework

def import_framework(framework, module):
    """
    Helper method for frameworks.
    
    This method is intended to replace an import statement.
    Instead of typing 
    
    > from . import foo_bar
    
    You use the following syntax to load a framework module
    
    > foo_bar = tank.platform.import_framework("tk-framework-mystuff", "foo_bar")
    
    In order for this to work, the calling module need to have been imported 
    using Tank's standard reload mechanism.

    :param framework: framework to access
    :param module: module to load from framework
    """
    import sys
    try:
        # get the caller's stack frame
        caller = sys._getframe(1)
        # get the package name from the caller
        # for example: 0b3d7089471e42a998027fa668adfbe4.tk_multi_about.environment_browser
        calling_name_str = caller.f_globals["__name__"]
        # now the module imported by Bundle.import_module is 
        # 0b3d7089471e42a998027fa668adfbe4.tk_multi_about
        # e.g. always the two first items in the name
        chunks = calling_name_str.split(".")
        calling_package_str = "%s.%s" % (chunks[0], chunks[1])
        # get the caller's module from sys.modules
        parent_module = sys.modules[calling_package_str]
    except:
        raise Exception("import_framework could not determine the calling module layout! " 
                        "You can only use this method on items imported using the import_module() "
                        "method!")
    
    # ok we got our module
    try:
        current_bundle = parent_module._tank_bundle
    except:
        raise Exception("import_framework could not access current app/engine on calling module %s. "
                        "You can only use this method on items imported using the import_module() "
                        "method!" % parent_module)

    if framework not in current_bundle.frameworks:
        raise Exception("import_framework: %s does not have a framework %s associated!" % (current_bundle, framework))

    fw = current_bundle.frameworks[framework]
    mod = fw.import_module(module)

    return mod



