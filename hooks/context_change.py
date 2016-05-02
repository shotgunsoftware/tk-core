# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Context change hook.
"""

from tank import get_hook_baseclass


class ContextChangeHook(get_hook_baseclass()):
    """
    Hook that gets executed every time there is a context change, once before
    the change and once after.
    """

    def pre_context_change(self, current_context, next_context):
        """
        Called before the context has changed.

        :param current_context: The current context.
        :param next_context: The context being switching to.
        """
        pass

    def post_context_change(self, previous_context, current_context):
        """
        Called after the context has changed.

        :param previous_context: The previous current context.
        :param current_context: The new current context.
        """
        pass
