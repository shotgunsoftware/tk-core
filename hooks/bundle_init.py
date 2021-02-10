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
Hook that gets executed every time a bundle is fully initialized.
"""

from tank import Hook


class BundleInit(Hook):
    def execute(self, bundle, **kwargs):
        """
        Executed when the Toolkit bundle is fully initialized.

        The default implementation does nothing.

        :param bundle: The Toolkit bundle that has been initialized.
        :type bundle: :class:`~sgtk.platform.Engine`, :class:`~sgtk.platform.Framework`
            or :class:`~sgtk.platform.Application`
        """
        pass
