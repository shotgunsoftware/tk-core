# Copyright (c) 2018 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Hook which provides advanced customization of context creation.

.. deprecated:: v0.17.26
    This hook should not be used if you aren't already using it.  It probably
    doesn't do what you think it does and it will likely be removed in a future
    release.

    Email support@shotgunsoftware.com if you have any questions about how to
    migrate away from this hook.
"""
from tank import Hook


class ContextAdditionalEntities(Hook):
    def execute(self, **kwargs):
        """
        Provides a list of additional entity types and task fields to be
        used when populating :attr:`sgtk.Context.additional_entities`

        The method should return a dictionary with two lists:

        **entity_types_in_path** (:class:`list`) - A list of Shotgun entity types
        (ie. CustomNonProjectEntity05) that :meth:`sgtk.Sgtk.context_from_path`
        should recognize and insert into :attr:`sgtk.Context.additional_entities`.

        **entity_types_in_path** (:class:`list`) - A list of Shotgun fields on the ``Task`` entity
        that meth:`sgtk.context_from_entity` should query Shotgun for and
        insert the resulting entities into :attr:`sgtk.Context.additional_entities`.

        The default implementation returns empty lists.

        :returns: A dictionary with keys ``entity_types_in_path`` and ``entity_fields_on_task``.
        :rtype dict:
        """
        val = {"entity_types_in_path": [], "entity_fields_on_task": []}
        return val
