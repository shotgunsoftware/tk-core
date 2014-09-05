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
This hook is called to determine the cache location for a particular configuration.
The cache location is  

"""

from tank import Hook
import os
import errno
import urlparse
import sys

class CacheLocation(Hook):
    
    def execute(self, project_id, pipeline_configuration_id, mode, parameters, **kwargs):
        """
        Handle folder creation issued from an app, framework or engine.
        
        :param path: path to create
        
        """
        
        tk = self.parent
        
        # first establish the root location
        if sys.platform == "darwin":
            root = os.path.expanduser("~/Library/Application Support/Shotgun")
        elif sys.platform == "win32":
            root = os.path.join(os.environ["APPDATA"], "Shotgun")
        elif sys.platform.startswith("linux"):
            root = os.path.expanduser("~/.shotgun")
        
        # get site only; https://www.foo.com:8080 -> www.foo.com
        base_url = urlparse.urlparse(tk.shotgun.base_url)[1].split(":")[0]
        
        # now structure things by site, project id, and pipeline config id
        cache_path = os.path.join(root, 
                                  base_url, 
                                  "project_%d" % project_id,
                                  "config_%d" % pipeline_configuration_id)
        
        # now establish the sub structure, this is done differently for different cache items
        if mode == "path_cache":
            pass
        elif mode == "bundle_cache":
            bundle = parameters["bundle"]
        
        
        return cache_path
        
