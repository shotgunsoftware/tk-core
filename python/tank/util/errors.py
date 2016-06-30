# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from ..errors import TankError

class UnresolvableCoreConfigurationError(TankError):
    """
    Raises when Toolkit is not able to resolve the path
    """

    def __init__(self, full_path_to_file):
        """
        Constructor.
        """
        TankError.__init__(
            self,
            "Cannot resolve the core configuration from the location of the Sgtk Code! "
            "This can happen if you try to move or symlink the Sgtk API. The "
            "Sgtk API is currently picked up from %s which is an "
            "invalid location." % full_path_to_file
        )
