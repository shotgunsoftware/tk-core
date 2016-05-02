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
This hook is called when an engine, app or framework calls 

> self.ensure_folder_exists(path)

Typically apps, engines and frameworks call this method
when they want to ensure that leaf-level folder structure
exists on disk. The default implementation just creates these
folders with very open permissions, and will typically not need
to be customized.

In case customization is required, the hook is passed the app/engine/framework
that issued the original request - this gives access to configuration,
app methods, environment etc. and should allow for some sophisticated
introspection inside the hook.
"""

from sgtk.util import filesystem
from sgtk import Hook

class EnsureFolderExists(Hook):
    
    def execute(self, path, bundle_obj, **kwargs):
        """
        Handle folder creation issued from an app, framework or engine.
        
        :param path: path to create
        :param bundle_object: object requesting the creation. This is a legacy
                              parameter and we recommend using self.parent instead.
        """
        filesystem.ensure_folder_exists(path, permissions=0777)

