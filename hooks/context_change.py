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
    Hook that gets executed every single time there is a context change in Toolkit.

        - If an engine **starts up**, the ``current_context`` passed to the hook
        methods will be ``None`` and the ``next_context`` parameter will be set
        to the context that the engine is starting in.

        - If an engine is being **reloaded**, in the context of an engine restart
        for example, the ``current_context`` and ``next_context`` will usually be
        the same.

        - If a **context switch** is requested, for example when a user switches
        from project to shot mode in Nuke Studio, ``current_context`` and ``next_context``
        will contain two different context.

    .. note::

       These hooks are called whenever the context is being set in Toolkit. It is
       possible that the new context will be the same as the old context. If
       you want to trigger some behaviour only when the new one is different
       from the old one, you'll need to compare the two arguments.
    """

    def pre_context_change(self, current_context, next_context):
        """
        Called before the context has changed.

        :param current_context: The context of the engine.
        :param next_context: The context the engine is switching to.
        """
        pass

    def post_context_change(self, previous_context, current_context):
        """
        Called after the context has changed.

        :param previous_context: The previous context of the engine.
        :param current_context: The current context of the engine.
        """
        pass
