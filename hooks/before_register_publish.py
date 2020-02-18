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
Hook that gets executed before a publish record is created in Shotgun.
This hook makes it possible to add custom fields to a publish before it gets created
as well as modifying the content that is being pushed to Shotgun.
"""

from tank import Hook


class BeforeRegisterPublish(Hook):
    def execute(self, shotgun_data, context, **kwargs):
        """
        Executed just before a new publish entity is created in Shotgun.

        The default implementation returns ``shotgun_data`` untouched.

        :param dict shotgun_data: All the data which will be passed to the Shotgun create call
        :param context: The context of the publish
        :type context: :class:`~sgtk.Context`

        :returns: return (potentially) modified data dictionary
        :rtype: dict
        """
        # default implementation is just a pass-through.
        return shotgun_data
