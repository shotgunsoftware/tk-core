"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Core hook which gets called when context.from_path is called.

This hook can be used to manipulate context data used to resolve a Context
from a path. This hook is called right before the Context object
instantiation occurs and any modifications to the context argument will affect
the instantiation of the Context object.

"""

from tank import Hook
from tank import TankError

class ContextFromPath(Hook):

    def execute(self, path, context, previous_context, **kwargs):
        """
        Default implementation. The following parameters are passed:

        * path: The path the context is being generated for.
        * context: Dictionary containing the resolved context data.  Any
                   manipulation of this dictionary will be used to generate
                   the final Context.
        * previous_context: The previous Context object.
        """
        pass
