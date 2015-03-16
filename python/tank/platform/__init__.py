# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.


# Engine management
from .engine import start_engine, current_engine, get_engine_path, find_app_settings

# base classes to derive from
from .application import Application
from .engine import Engine
from .framework import Framework

from ..errors import TankError

################################################################################################
# internal methods

def _get_current_bundle():

    import sys
    from .framework import CURRENT_BUNDLE_DOING_IMPORT
    
    if len(CURRENT_BUNDLE_DOING_IMPORT) > 0:
        # this special variable is set by bundle.import_module() and 
        # and is a way to defuse the chicken/egg situtation which happens
        # when trying to do an import_framework inside a module that is being
        # loaded by import_module. The crux is that the module._tank_bundle reference
        # that import_module() sets is constructed at the end of the call,
        # meaning that the frameworks import cannot find this during the import
        # this variable is the fallback in this case and it contains a reference 
        # to the current bundle.
        
        # this variable is a stack, so grab the last element
        current_bundle = CURRENT_BUNDLE_DOING_IMPORT[-1]
        
    else:
        # try to figure out the associated bundle using module trickery, 
        # looking for the module which called this command and looking for 
        # a ._tank_module property on the module object.
    
        try:
            # get the caller's stack frame
            caller = sys._getframe(2)
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
 
    return current_bundle


################################################################################################
# Public API methods

def restart():
    """
    Running restart will shut down any currently running engine, then refresh the templates
    definitions and finally start up the engine again. 
    
    The template configuration, environment configuration and the actual app and engine code
    will be reloaded.
    
    Any open windows will remain open and will use the old code base and settings. In order to
    access any changes that have happened as part of a reload, you need to launch new app
    windows and these will use the fresh code and configs.
    """

    engine = current_engine()
    
    if engine is None:
        raise TankError("No engine is currently running! Run start_engine instead.")

    try:
        # first, reload the template defs
        engine.tank.reload_templates()
        engine.log_debug("Template definitions were reloaded.")
    except TankError, e:
        engine.log_error(e)

    try:
        # now restart the engine            
        current_context = engine.context            
        current_engine_name = engine.name
        engine.destroy()
        start_engine(current_engine_name, current_context.tank, current_context)
    except TankError, e:
        engine.log_error("Could not restart the engine: %s" % e)
    except Exception:
        engine.log_exception("Could not restart the engine!")
    
    engine.log_info("Toolkit platform was restarted.")



def current_bundle():
    """
    Returns the bundle (app, engine or framework) instance for the
    app that the calling code is associated with. This is a special method, designed to 
    be used inside python modules that belong to apps, engines or frameworks.
    
    The calling code needs to have been imported using toolkit's standard import 
    mechanism, import_module(), otherwise an exception will be raised.
    
    This special helper method can be useful when code deep inside an app needs
    to reach out to for example grab a configuration value. Then you can simply do
    
    app = sgtk.platform.current_bundle()
    app.get_setting("frame_range")

    :returns: app, engine or framework instance
    """ 
    return _get_current_bundle()


def get_framework(framework):
    """
    Convenience method that returns a framework instance given a framework name.
    
    This is a special method, designed to 
    be used inside python modules that belong to apps, engines or frameworks.
    
    The calling code needs to have been imported using toolkit's standard import 
    mechanism, import_module(), otherwise an exception will be raised.    
    
    For example, if your app code requires the tk-framework-helpers framework, and you
    need to retrieve a configuration setting from this framework, then you can 
    simply do
    
    fw = sgtk.platform.get_framework("tk-framework-helpers")
    fw.get_setting("frame_range")

    :param framework: name of the framework object to access, as defined in the app's
                      info.yml manifest.
    :returns: framework instance
    """

    current_bundle = _get_current_bundle()
    
    if framework not in current_bundle.frameworks:
        raise Exception("import_framework: %s does not have a framework %s associated!" % (current_bundle, framework))

    fw = current_bundle.frameworks[framework]
    
    return fw


def import_framework(framework, module):
    """
    Convenience method for using frameworks code inside of apps, engines and other frameworks.
    
    This method is intended to replace an import statement.
    Instead of typing 
    
    > from . import foo_bar
    
    You use the following syntax to load a framework module
    
    > foo_bar = tank.platform.import_framework("tk-framework-mystuff", "foo_bar")
    
    This is a special method, designed to 
    be used inside python modules that belong to apps, engines or frameworks.
    
    The calling code needs to have been imported using toolkit's standard import 
    mechanism, import_module(), otherwise an exception will be raised.    

    :param framework: name of the framework object to access, as defined in the app's
                      info.yml manifest.
    :param module: module to load from framework
    """
    
    current_bundle = _get_current_bundle()

    if framework not in current_bundle.frameworks:
        raise Exception("import_framework: %s does not have a framework %s associated!" % (current_bundle, framework))

    fw = current_bundle.frameworks[framework]    
    
    mod = fw.import_module(module)

    return mod



