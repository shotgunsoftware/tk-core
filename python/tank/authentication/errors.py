# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
All custom exceptions that this module emits are defined here.
"""

# @todo - what should ShotgunAuthenticationError derive from? TankError?


class ShotgunAuthenticationError(Exception):
    """
    Base class for all exceptions coming out from this module.
    """


class AuthenticationError(ShotgunAuthenticationError):
    """
    Thrown when credentials are rejected by the server.
    """


class IncompleteCredentials(ShotgunAuthenticationError):
    """
    Thrown when credentials are provided but are incomplete.
    """

    def __init__(self, msg):
        """
        :param str msg: Reason why the credentials are incomplete.
        """
        ShotgunAuthenticationError.__init__(
            self, "Incomplete credentials: %s" % msg
        )


class AuthenticationCancelled(ShotgunAuthenticationError):
    """
    Thrown when the user cancels authentication or session renewal.
    """

    def __init__(self):
        """
        Constructor.
        """
        ShotgunAuthenticationError.__init__(
            self, "Authentication was cancelled by the user."
        )


class AuthenticationSSOError(ShotgunAuthenticationError):
    """
    Base class for all SSO-related exceptions coming out from this module.
    """


class ConsoleLoginWithSSONotSupportedError(AuthenticationSSOError):
    """
    Thrown when attempting to use Username/Password pair to login onto
    a SSO-enabled site.
    """

    def __init__(self, url):
        """
        :param str url: Url of the site where login was attempted.
        """
        ShotgunAuthenticationError.__init__(
            self, "Authentication using username/password is not supported on the console for %s, an SSO-enabled site." % url
        )
