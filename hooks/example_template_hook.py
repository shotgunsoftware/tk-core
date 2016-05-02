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
This hook is a simple example to illustrate how template settings in an app
can be evaluated at runtime based on complex conditions.

If you have an app which has a template parameter, you would typically use a setting
which points to one of your templates. So in the environment config, you would have:

template_snapshot: maya_shot_publish

However if you want more complex behaviour, it is possible to specify that a hook
should be used to evaluate the setting at runtime rather than just set it. 
For example:

template_snapshot: "hook:example_template_hook:maya_shot_publish"

This setting would look for a core hook named example_template_hook and execute it.
See below for an example implementation and parameter descriptions.
"""

from tank import Hook
import os

class ProceduralTemplateEvaluator(Hook):
    
    def execute(self, setting, bundle_obj, extra_params, **kwargs):
        """
        Example pass-through implementation. One option is expected in extra_params,
        and this will be returned.
        
        So the following two things will evaluate to the same thing:
        
        > template_snapshot: maya_shot_publish
        > template_snapshot: hook:example_template_hook:maya_shot_publish
        
        
        
        :param setting: The name of the setting for which we are evaluating 
                        In our example above, it would be template_snapshot.
                         
        :param bundle_obj: The app, engine or framework object that the setting
                           is associated with.
        
        :param extra_params: List of options passed from the setting. If the settings
                             string is "hook:hook_name:foo:bar", extra_params would
                             be ['foo', 'bar'] 
                             
        returns: needs to return the name of a template, as a string.
        """
        template_name = extra_params[0]
        return template_name
        
