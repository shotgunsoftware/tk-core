"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

This hook is called when an engine, app or framework calls 

> self.ensure_folder_exists(path)

Typcially, apps, engines and frameworks call this method
when they want to ensure that leaf-level folder structure
exists on disk. The default implementation just creates these
folders with very open permissions, and will typically not need
to be customized.

In case customization is required, the hook is passed the app/engine/framework
that issued the original request - this gives access to configuration,
app methods, environment etc. and should allow for some sophisticated
introspection inside the hook.
"""

from tank import Hook
import os

class EnsureFolderExists(Hook):
    
    def execute(self, path, bundle_obj, **kwargs):
        """
        Handle folder creation issued from an app, framework or engine.
        
        :param path: path to create
        :param bundle_object: object requesting the creation
        """
        if not os.path.exists(path):
            old_umask = os.umask(0)
            os.makedirs(path, 0777)
            os.umask(old_umask)
            
            