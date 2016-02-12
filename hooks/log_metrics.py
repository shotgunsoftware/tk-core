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
        
        """
        pass

