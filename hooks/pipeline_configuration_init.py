"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Hook that gets executed every time a new PipelineConfiguration
instance is created.

"""

import os
import sys

from tank import Hook

# Actual hook class.
#
class PipelineConfigurationInit(Hook):

    def execute(self, **kwargs):
        """
        Gets executed when a new PipelineConfiguration instance is initialized.
        """
        pass

