# Copyright (c) 2016 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

"""Hook that gets executed every time Toolkit logs a user metric."""

from tank import Hook
 

class LogMetrics(Hook):
    
    def execute(self, metrics):
        """Called when Toolkit logs a user metric.
        
        :param list metrics: list of dictionaries with logged data.

        The metrics dictionaries will take one of two forms:

        1. A user attribute metric. These typically log the version of
           an app, engine, framework, DCC, etc.

        {
            "type": "user_attribute",
            "attr_name": <attr name>
            "attr_value": <attr value>
        }

        2. A user activity metric. These metrics are more common and
           log the usage of a particular api, hook, engine, app, framework,
           method, etc.

        {
            "type": "user_activity",
            "module": <module name>
            "action": <action name>
        }

        """
        pass
