# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import sys
import urlparse

def get_cache_root():
    """
    Returns a cache root suitable for all Shotgun related data,
    regardless of site.

    The following paths will be generated:

    - macosx: ~/Library/Caches/Shotgun
    - windows: %APPDATA%\Shotgun
    - linux: ~/.shotgun

    :returns: The calculated location for the cache root
    """
    if sys.platform == "darwin":
        root = os.path.expanduser("~/Library/Caches/Shotgun")

    elif sys.platform == "win32":
        root = os.path.join(os.environ["APPDATA"], "Shotgun")

    elif sys.platform.startswith("linux"):
        root = os.path.expanduser("~/.shotgun")

    else:
        raise RuntimeError("Unsupported operating system!")

    return root


def get_site_cache_root(site_url):
    """
    Returns a cache root suitable for all Shotgun related data for a given shotgun site.

    The following paths will be generated:

    - macosx: ~/Library/Caches/Shotgun/SITE_NAME
    - windows: %APPDATA%\Shotgun\SITE_NAME
    - linux: ~/.shotgun/SITE_NAME

    :param site_url: Shotgun site url string, eg 'https://mysite.shotgunstudio.com'
    :returns: The calculated location for the cache root
    """

    # get site only; https://www.FOO.com:8080 -> www.foo.com
    base_url = urlparse.urlparse(site_url).netloc.split(":")[0].lower()

    # in order to apply further shortcuts to avoid hitting
    # MAX_PATH on windows, strip shotgunstudio.com from all
    # hosted sites
    #
    # mysite.shotgunstudio.com -> mysite
    # shotgun.internal.int     -> shotgun.internal.int
    #
    base_url = base_url.replace(".shotgunstudio.com", "")
    return os.path.join(get_cache_root(), base_url)


def get_pipeline_config_cache_root(site_url, project_id, pipeline_configuration_id):
    """
    Calculates the cache root for the current project and configuration.

    The following paths will be generated:

    - macosx: ~/Library/Caches/Shotgun/SITE_NAME/proj123_cfg12
    - windows: %APPDATA%\Shotgun\SITE_NAME\proj123_cfg12
    - linux: ~/.shotgun/SITE_NAME/proj123_cfg12

    Alternatively, the following syntaxes are also possible:

    - site config: ~/Library/Caches/Shotgun/SITE_NAME/site_cfg12
    - unmanaged site config: ~/Library/Caches/Shotgun/SITE_NAME/site
    - unmanaged project config: ~/Library/Caches/Shotgun/SITE_NAME/proj123

    :param site_url: Shotgun site url string, e.g. 'https://mysite.shotgunstudio.com'
    :param project_id: The shotgun id of the project to store caches for
    :param pipeline_configuration_id: The shotgun pipeline config id to
                                      store caches for. Can be None.
    :returns: The calculated location for the cache root
    """
    if pipeline_configuration_id is None:
        # unmanaged config
        pc_suffix = ""
    else:
        pc_suffix = "_cfg%d" % pipeline_configuration_id

    if project_id is None:
        # site configuration
        project_config_folder = "site%s" % pc_suffix
    else:
        project_config_folder = "proj%d%s" % (project_id, pc_suffix)

    cache_root = os.path.join(get_site_cache_root(site_url), project_config_folder)
    return cache_root


def get_logs_root():
    """
    Returns the platform specific location of the logfiles.

    :returns: Path to the logfile.
    """
    if sys.platform == "darwin":
        fname = os.path.join(os.path.expanduser("~"), "Library", "Logs", "Shotgun")
    elif sys.platform == "win32":
        fname = os.path.join(os.environ.get("APPDATA", "APPDATA_NOT_SET"), "Shotgun")
    elif sys.platform.startswith("linux"):
        fname = os.path.join(os.path.expanduser("~"), ".shotgun", "logs")
    else:
        raise NotImplementedError("Unknown platform: %s" % sys.platform)
    return fname
