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
    regardless of Shotgun site.

    The following paths will be computed:

    - macosx: ~/Library/Caches/Shotgun
    - windows: %APPDATA%\Shotgun
    - linux: ~/.shotgun

    :returns: The calculated location for the cache root
    """
    if sys.platform == "darwin":
        root = os.path.expanduser("~/Library/Caches/Shotgun")

    elif sys.platform == "win32":
        root = os.path.join(os.environ.get("APPDATA", "APPDATA_NOT_SET"), "Shotgun")

    elif sys.platform.startswith("linux"):
        root = os.path.expanduser("~/.shotgun")

    else:
        raise NotImplementedError("Unknown platform: %s" % sys.platform)

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
                                      store caches for. Can be None to indicate
                                      a configuration that doesn't have a corresponding
                                      pipeline configuration entry in Shotgun.
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


def get_cache_bundle_folder_name(bundle):
    """
    Returns the modified bundle name as used the cache root.

    :param bundle: The bundle to return a folder name for.

    :rtype: str
    :return: The name of the bundle folder.
    """

    # in the interest of trying to minimize path lengths (to avoid
    # the MAX_PATH limit on windows, we apply some shortcuts

    # if the bundle is a framework, we shorten it:
    # tk-framework-shotgunutils --> fw-shotgunutils
    # if the bundle is a multi-app, we shorten it:
    # tk-multi-workfiles2 --> tm-workfiles2
    bundle_name = bundle.name
    bundle_name = bundle_name.replace("tk-framework-", "fw-")
    bundle_name = bundle_name.replace("tk-multi-", "tm-")

    return bundle_name


def get_logs_root():
    """
    Returns a root folder suitable for all shotgun log files,
    regardless of Shotgun site.

    The following paths will be computed:

    - macosx: ~/Library/Logs/Shotgun
    - windows: %APPDATA%\Shotgun\logs
    - linux: ~/.shotgun/logs

    :returns: The calculated location for the cache root

    """
    if sys.platform == "darwin":
        root = os.path.join(os.path.expanduser("~"), "Library", "Logs", "Shotgun")
    elif sys.platform == "win32":
        root = os.path.join(os.environ.get("APPDATA", "APPDATA_NOT_SET"), "Shotgun", "logs")
    elif sys.platform.startswith("linux"):
        root = os.path.join(os.path.expanduser("~"), ".shotgun", "logs")
    else:
        raise NotImplementedError("Unknown platform: %s" % sys.platform)
    return root


def get_legacy_pipeline_config_cache_root(site_url, project_id, pipeline_configuration_id):
    """
    Calculates the legacy cache root for the current project and configuration.

    The following paths will be generated:

    - macosx: ~/Library/Caches/Shotgun/SITE_NAME/project_xxx/config_yyy
    - windows: $APPDATA/Shotgun/SITE_NAME/project_xxx/config_yyy
    - linux: ~/.shotgun/SITE_NAME/project_xxx/config_yyy

    :param site_url: Shotgun site url string, e.g. 'https://mysite.shotgunstudio.com'
    :param project_id: The shotgun id of the project to store caches for
    :param pipeline_configuration_id: The shotgun pipeline config id to
                                      store caches for. Can be None.
    :rtype: str
    :return: The v0.17.x cache root

    """

    # get site only; https://www.foo.com:8080 -> www.foo.com
    base_url = urlparse.urlparse(site_url)[1].split(":")[0]

    if pipeline_configuration_id is None:
        pc_suffix = ""
    else:
        pc_suffix = "_%d" % (pipeline_configuration_id,)

    if project_id is None:
        proj_suffix = ""
    else:
        proj_suffix = "_%d" % (project_id,)

    # now structure things by site, project id, and pipeline config id
    return os.path.join(
        get_cache_root(),
        base_url,
        "project%s" % proj_suffix,
        "config%s" % pc_suffix,
    )


def get_legacy_bundle_install_folder(
    descriptor_name,
    install_cache_root,
    bundle_type,
    bundle_name,
    bundle_version
):
    """Return the path to the legacy bundle install dir for the supplied info.

    :param descriptor_name: The name of the descriptor. ex: "app_store" or "git"
    :param install_cache_root: The root path to the bundle cache.
    :param bundle_type: The type of the bundle. Should be one of:
        Descriptor.APP, Descriptor.ENGINE, or Descriptor.FRAMEWORK.
    :param bundle_name: The display name for the resolved descriptor resource.
        ex: "tk-multi-shotgunpanel"
    :param bundle_version: The version of the bundle on disk. ex: "v1.2.5"
    :rtype: str
    :return: The path to the cache in the legacy bundle structure.
    :raises: RuntimeError - if the bundle_type is not recognized.

    This method is provided for compatibility with older versions of core,
    prior to v0.18.x. As of v0.18.x, the bundle cache subdirectory names
    were shortened and otherwise modified to help prevent MAX_PATH issues
    on windows. This method is used to add the old style path as a fallback
    for cases like core having been upgraded to v0.18.x on an existing project.

    New style cache path:
        <root>/app_store/tk-multi-shotgunpanel/v1.2.5

    Legacy style cache path:
        <root>/apps/app_store/tk-multi-shotgunpanel/v1.2.5

    For reference, this method emulates: `tank.deploy.descriptor._get_local_location`
    in the pre-v0.18.x core.

    """

    from tank_vendor.shotgun_deploy import Descriptor

    if bundle_type == Descriptor.APP:
        legacy_dir = "apps"
    elif bundle_type == Descriptor.ENGINE:
        legacy_dir = "engines"
    elif bundle_type == Descriptor.FRAMEWORK:
        legacy_dir = "frameworks"
    else:
        raise RuntimeError(
            "Unknown bundle type '%s'. Can not determine legacy cache path." %
            (bundle_type,)
        )

    # build and return the path.
    # example: <root>/apps/app_store/tk-multi-shotgunpanel/v1.2.5
    return os.path.join(
        install_cache_root,
        legacy_dir,
        descriptor_name,
        bundle_name,
        bundle_version,
    )

