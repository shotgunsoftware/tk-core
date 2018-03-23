# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import optparse
import os

from tank import LogManager
from tank.authentication import ShotgunAuthenticator


logger = LogManager.get_logger("utils.authentication")

automated_setup_documentation = """For automated build setups, you can provide a specific shotgun API script name and
and corresponding script key:

> python populate_bundle_cache.py
            --shotgun-host='https://mysite.shotgunstudio.com'
            --shotgun-script-name='plugin_build'
            --shotgun-script-key='<script-key-here>'
            "sgtk:descriptor:app_store?version=v0.3.6&name=tk-config-basic" /tmp

You can also use the SHOTGUN_HOST, SHOTGUN_SCRIPT_NAME and SHOTGUN_SCRIPT_KEY environment
variables to authenticate."""


def add_authentication_options(parser):
    """
    Adds authentication options to an option parser.

    :param parser: OptionParser to which authentication options will be added.
    """
    group = optparse.OptionGroup(
        parser,
        "Shotgun Authentication",
        "In order to download content from the Toolkit app store, the script will need to authenticate "
        "against any shotgun site. By default, it will use the toolkit authentication APIs stored "
        "credentials, and if such are not found, it will prompt for site, username and password."
    )

    group.add_option(
        "-s",
        "--shotgun-host",
        default=None,
        action="store",
        help="Shotgun host to authenticate with."
    )

    group.add_option(
        "-n",
        "--shotgun-script-name",
        default=None,
        action="store",
        help="Script to use to authenticate with the given host."
    )

    group.add_option(
        "-k",
        "--shotgun-script-key",
        default=None,
        action="store",
        help="Script key to use to authenticate with the given host."
    )

    parser.add_option_group(group)


def authenticate(options):
    """
    Authenticates using the command line arguments or user input.

    :param options: OptionParser instance with values shotgun_host, shotgun_script_key and shotgun_script_name

    :returns: An authenticated ShotgunUser instance.
    """
    # now authenticate to shotgun
    sg_auth = ShotgunAuthenticator()

    shotgun_host = options.shotgun_host or os.environ.get("SHOTGUN_HOST")
    if shotgun_host:
        script_name = options.shotgun_script_name or os.environ.get("SHOTGUN_SCRIPT_NAME")
        script_key = options.shotgun_script_key or os.environ.get("SHOTGUN_SCRIPT_KEY")

        if script_name is None or script_key is None:
            logger.error("Need to provide, host, script name and script key! Run with -h for more info.")
            return 2

        logger.info("Connecting to %s using script user %s..." % (options.shotgun_host, script_name))
        sg_user = sg_auth.create_script_user(script_name, script_key, shotgun_host)

    else:
        logger.info("Connect to any Shotgun site to collect AppStore keys.")
        # get user, prompt if necessary
        sg_user = sg_auth.get_user()

    # Make sure our session is not out of date.
    sg_user.refresh_credentials()

    return sg_user
