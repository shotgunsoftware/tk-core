# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
--------------------------------------------------------------------------------
NOTE! This module is part of the authentication library internals and should
not be called directly. Interfaces and implementation of this module may change
at any point.
--------------------------------------------------------------------------------
"""

from .. import LogManager

logger = LogManager.get_logger(__name__)

class DeferredShotgun(object):
    """
    Shotgun API wrapper that connects just in time.

    Used in conjunction with the
    """

    def __init__(self, user):
        """
        Constructor

        :param user: :class:`
        :return:
        """

        self._sg = None
        self._user = user

    def __getattr__(self, key):

        if key == "base_url":
            return self._user.host

        if self._sg is None:
            self._sg = self._user.create_sg_connection()
        return getattr(self._sg, key)
