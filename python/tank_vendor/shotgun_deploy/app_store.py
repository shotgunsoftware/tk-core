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
App store related utilities
"""

import urllib
import urllib2

from . import constants

from .errors import ShotgunAppStoreError

# use api json to cover py 2.5
from .. import shotgun_api3
json = shotgun_api3.shotgun.json

# memoize app store connections for performance
g_app_store_connection = {}


def create_sg_app_store_connection(sg_connection):
    """
    Creates a shotgun connection that can be used to access the Toolkit app store.

    :param sg_connection: Shotgun connection to associated site
    :returns: (sg, dict) where the first item is the shotgun api instance and the second 
              is an sg entity dictionary (keys type/id) corresponding to to the user used
              to connect to the app store.
    """
    global g_app_store_connection

    # maintain a cache for performance
    # cache is keyed by client shotgun site
    # this assumes that there is a strict
    # 1:1 relationship between app store accounts
    # and shotgun sites.
    if sg_connection.base_url not in g_app_store_connection:

        # Connect to associated Shotgun site and retrieve the credentials to use to
        # connect to the app store site
        (script_name, script_key) = __get_app_store_key_from_shotgun(sg_connection)

        # connect to the app store and resolve the script user id we are connecting with
        app_store_sg = shotgun_api3.Shotgun(
            constants.SGTK_APP_STORE,
            script_name=script_name,
            api_key=script_key,
            http_proxy=sg_connection.config.raw_http_proxy
        )

        # determine the script user running currently
        # get the API script user ID from shotgun
        script_user = app_store_sg .find_one(
            "ApiUser",
            [["firstname", "is", script_name]],
            fields=["type", "id"]
        )

        if script_user is None:
            raise ShotgunAppStoreError("Could not evaluate the current App Store User! Please contact support.")

        g_app_store_connection[sg_connection.base_url] = (app_store_sg, script_user)

    return g_app_store_connection[sg_connection.base_url]


def __get_app_store_key_from_shotgun(sg_connection):
    """
    Given a Shotgun url and script credentials, fetch the app store key
    for this shotgun instance using a special controller method.
    Returns a tuple with (app_store_script_name, app_store_auth_key)

    :param sg_connection: SG connection to the client site for which
                          app store credentials should be retrieved.
    :returns: tuple of strings with contents (script_name, script_key)
    """
    # handle proxy setup by pulling the proxy details from the main shotgun connection
    if sg_connection.config.proxy_handler:
        opener = urllib2.build_opener(sg_connection.config.proxy_handler)
        urllib2.install_opener(opener)

    # now connect to our site and use a special url to retrieve the app store script key
    session_token = sg_connection.get_session_token()
    post_data = {"session_token": session_token}
    response = urllib2.urlopen("%s/api3/sgtk_install_script" % sg_connection.base_url, urllib.urlencode(post_data)) 
    html = response.read()
    data = json.loads(html)

    return (data["script_name"], data["script_key"])


