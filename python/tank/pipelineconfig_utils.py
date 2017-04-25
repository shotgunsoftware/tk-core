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
Encapsulates the pipeline configuration and helps navigate and resolve paths
across storages, configurations etc.
"""

from __future__ import with_statement

import os
import sys

from .errors import (
    TankError,
    TankNotPipelineConfigurationError,
    TankInvalidInterpreterLocationError,
    TankFileDoesNotExistError,
    TankInvalidCoreLocationError
)

from . import constants
from . import LogManager
from .util import yaml_cache
from .util import ShotgunPath

log = LogManager.get_logger(__name__)


def is_localized(pipeline_config_path):
    """
    Returns true if the pipeline configuration contains a localized API
    
    :param pipeline_config_path: path to a pipeline configuration root folder
    :returns: true if localized, false if not
    """
    # first, make sure that this path is actually a pipeline configuration
    # path. otherwise, it cannot be localized :)
    if not is_pipeline_config(pipeline_config_path):
        return False

    # look for a localized API by searching for a _core_upgrader.py file
    api_file = os.path.join(pipeline_config_path, "install", "core", "_core_upgrader.py")
    return os.path.exists(api_file)

def is_pipeline_config(pipeline_config_path):
    """
    Returns true if the path points to the root of a pipeline configuration
    
    :param pipeline_config_path: path to a pipeline configuration root folder
    :returns: true if pipeline config, false if not
    """
    # probe by looking for the existence of a key config file.
    pc_file = os.path.join(pipeline_config_path, "config", "core", constants.STORAGE_ROOTS_FILE)
    return os.path.exists(pc_file)

def get_metadata(pipeline_config_path):
    """
    Loads the pipeline config metadata (the pipeline_configuration.yml) file from disk.
    
    :param pipeline_config_path: path to a pipeline configuration root folder
    :returns: deserialized content of the file in the form of a dict.
    """

    # now read in the pipeline_configuration.yml file
    cfg_yml = os.path.join(
        pipeline_config_path,
        "config",
        "core",
        constants.PIPELINECONFIG_FILE
    )

    try:
        data = yaml_cache.g_yaml_cache.get(cfg_yml, deepcopy_data=False)
        if data is None:
            raise Exception("File contains no data!")
    except Exception, e:
        raise TankError("Looks like a config file is corrupt. Please contact "
                        "support! File: '%s' Error: %s" % (cfg_yml, e))
    return data


def get_roots_metadata(pipeline_config_path):
    """
    Loads and validates the roots metadata file.
    
    The roots.yml file is a reflection of the local storages setup in Shotgun
    at project setup time and may contain anomalies in the path layout structure.
    
    The roots data will be prepended to paths and used for comparison so it is 
    critical that the paths are on a correct normalized form once they have been 
    loaded into the system.
    
    :param pipeline_config_path: Path to the root of a pipeline configuration,
                                 (excluding the "config" folder).  
    
    :returns: A dictionary structure with an entry for each storage defined. Each
              storage will have three keys mac_path, windows_path and linux_path, 
              for example
              { "primary"  : <ShotgunPath>,
                "textures" : <ShotgunPath>
              }
    """
    # now read in the roots.yml file
    # this will contain something like
    # {'primary': {'mac_path': '/studio', 'windows_path': None, 'linux_path': '/studio'}}
    roots_yml = os.path.join(
        pipeline_config_path,
        "config",
        "core",
        constants.STORAGE_ROOTS_FILE
    )

    try:
        # if file is empty, initialize with empty dict...
        data = yaml_cache.g_yaml_cache.get(roots_yml, deepcopy_data=False) or {}
    except Exception, e:
        raise TankError("Looks like the roots file is corrupt. Please contact "
                        "support! File: '%s' Error: %s" % (roots_yml, e))

    # if there are more than zero storages defined, ensure one of them is the primary storage
    if len(data) > 0 and constants.PRIMARY_STORAGE_NAME not in data:
        raise TankError("Could not find a primary storage in roots file "
                        "for configuration %s!" % pipeline_config_path)

    # sanitize path data by passing it through the ShotgunPath
    shotgun_paths = {}
    for storage_name in data:
        shotgun_paths[storage_name] = ShotgunPath.from_shotgun_dict(data[storage_name])

    return shotgun_paths




####################################################################################################################
# Core API resolve utils 

def get_path_to_current_core():
    """
    Returns the local path of the currently executing code, assuming that this code is 
    located inside a standard toolkit install setup. If the code that is running is part
    of a localized pipeline configuration, the pipeline config root path
    will be returned, otherwise a 'studio' root will be returned.
    
    This method may not return valid results if there has been any symlinks set up as part of
    the install structure.
    
    :returns: string with path
    """
    curr_os_core_root = os.path.abspath(os.path.join( os.path.dirname(__file__), "..", "..", "..", ".."))
    if not os.path.exists(curr_os_core_root):
        full_path_to_file = os.path.abspath(os.path.dirname(__file__))
        raise TankError("Cannot resolve the core configuration from the location of the Toolkit Code! "
                        "This can happen if you try to move or symlink the Toolkit API. The "
                        "Toolkit API is currently picked up from %s which is an "
                        "invalid location." % full_path_to_file)
    return curr_os_core_root    


def get_core_path_for_config(pipeline_config_path):
    """
    Returns the core api install location associated with the given pipeline configuration.
    In the case of a localized PC, it just returns the given path.
    Otherwise, it resolves the location via the core_xxxx.cfg files.
    
    :param pipeline_config_path: path to a pipeline configuration
    :returns: Path to the studio location root or pipeline configuration root or None if not resolved
    """
    try:
        return _get_core_path_for_config(pipeline_config_path)
    except:
        return None

def _get_core_path_for_config(pipeline_config_path):
    """
    Returns the core api install location associated with the given pipeline configuration.
    In the case of a localized PC, it just returns the given path.
    Otherwise, it resolves the location via the core_xxxx.cfg files.

    :param str pipeline_config_path: path to a pipeline configuration

    :returns: Path to the studio location root or pipeline configuration root or None if not resolved
    :rtype: str

    :raises TankFileDoesNotExistError: Raised if the core_xxxx.cfg file is missing for the
        pipeline configuration.
    :raises TankNotPipelineConfigurationError: Raised if the path is not referencing a pipeline configuration.
    :raises TankInvalidCoreLocationError: Raised if the core location specified in core_xxxx.cfg
        does not exist.
    """
    if is_localized(pipeline_config_path):
        # first, try to locate an install local to this pipeline configuration.
        # this would find any localized APIs.
        install_path = pipeline_config_path

    else:
        # this pipeline config is associated with a shared API (studio install)
        # follow the links defined in the configuration to establish which
        # setup it has been associated with.
        studio_linkback_file = _get_current_platform_core_location_file_name(pipeline_config_path)

        if not os.path.exists(studio_linkback_file):
            raise TankFileDoesNotExistError(
                "Configuration at '%s' without a localized core is missing a core location file at '%s'" %
                (pipeline_config_path, studio_linkback_file)
            )

        # this file will contain the path to the API which is meant to be used with this PC.
        install_path = None
        with open(studio_linkback_file, "rt") as fh:
            data = fh.read().strip() # remove any whitespace, keep text

        # expand any env vars that are used in the files. For example, you could have
        # an env variable $STUDIO_TANK_PATH=/sgtk/software/shotgun/studio and your
        # linkback file may just contain "$STUDIO_TANK_PATH" instead of an explicit path.
        data = os.path.expanduser(os.path.expandvars(data))
        if data not in ["None", "undefined"] and os.path.exists(data):
            install_path = data
        else:
            raise TankInvalidCoreLocationError(
                "Cannot find core location '%s' defined in "
                "config file '%s'." %
                (data, studio_linkback_file)
            )

    return install_path


def _get_current_platform_file_suffix():
    """
    Find the suffix for the current platform's configuration file.

    :returns: Suffix for the current platform's configuration file.
    :rtype: str
    """
    # Now find out the appropriate python interpreter file to search for
    if sys.platform == "darwin":
        return "Darwin"
    elif sys.platform == "win32":
        return "Windows"
    elif sys.platform.startswith("linux"):
        return "Linux"
    else:
        raise TankError("Unknown platform: %s." % sys.platform)


def _get_current_platform_interpreter_file_name(install_root):
    """
    Retrieves the path to the interpreter file for a given install root.

    :param str install_root: This can be the root to a studio install for a core
        or a pipeline configuration root.

    :returns: Path for the current platform's interpreter file.
    :rtype: str
    """
    return os.path.join(
        install_root, "config", "core", "interpreter_%s.cfg" % _get_current_platform_file_suffix()
    )


def _get_current_platform_core_location_file_name(install_root):
    """
    Retrieves the path to the core location file for a given install root.

    :param str install_root: This can be the root to a studio install for a core
        or a pipeline configuration root.

    :returns: Path for the current platform's core location file.
    :rtype: str
    """
    return os.path.join(
        install_root, "install", "core", "core_%s.cfg" % _get_current_platform_file_suffix()
    )


def _find_interpreter_location(pipeline_config_path):
    """
    Looks for a Python interpreter associated with this config.

    :param str pipeline_config_path: Config root to look for the interpreter.

    :raises TankInvalidInterpreterLocationError: Raised if the interpreter in the interpreter file doesn't
        exist.
    :raises TankFileDoesNotExistError: Raised if the interpreter file can't be found.

    :returns: Path to the interpreter or None if the interpreter file was missing.
    """
    interpreter_config_file = _get_current_platform_interpreter_file_name(pipeline_config_path)
    if os.path.exists(interpreter_config_file):
        with open(interpreter_config_file, "r") as f:
            path_to_python = f.read().strip()

        if not path_to_python or not os.path.exists(path_to_python):
            raise TankInvalidInterpreterLocationError(
                "Cannot find interpreter '%s' defined in "
                "config file '%s'." % (path_to_python, interpreter_config_file)
            )
        else:
            return path_to_python
    else:
        raise TankFileDoesNotExistError(
            "No interpreter file for the current platform found at '%s'." % interpreter_config_file
        )


def get_python_interpreter_for_config(pipeline_config_path):
    """
    Retrieves the path to the Python interpreter for a given pipeline configuration
    path.

    Each pipeline configuration has three (one for Windows, one for macOS and one for Linux) interpreter
    files that provide a path to the Python interpreter used to launch the ``tank``
    command.

    If you require a `python` executable to launch a script that will use a pipeline configuration, it is
    recommended its associated Python interpreter.

    :param str pipeline_config_path: Path to the pipeline configuration root.

    :returns: Path to the Python interpreter for that configuration.
    :rtype: str

    :raises TankInvalidInterpreterLocationError: Raised if the interpreter in the interpreter file doesn't
        exist.
    :raises TankFileDoesNotExistError: Raised if the interpreter file can't be found.
    :raises TankNotPipelineConfigurationError: Raised if the pipeline configuration path is not
        a pipeline configuration.
    :raises TankInvalidCoreLocationError: Raised if the core location specified in core_xxxx.cfg
        does not exist.
    """
    if not is_pipeline_config(pipeline_config_path):
        raise TankNotPipelineConfigurationError(
            "The folder at '%s' does not contain a pipeline configuration." % pipeline_config_path
        )
    # Config is localized, we're supposed to find an interpreter file in it.
    if is_localized(pipeline_config_path):
        return _find_interpreter_location(pipeline_config_path)
    else:
        studio_path = _get_core_path_for_config(pipeline_config_path)
        return _find_interpreter_location(studio_path)


def resolve_all_os_paths_to_core(core_path):
    """
    Given a core path on the current os platform, 
    return paths for all platforms, 
    as cached in the install_locations system file

    :returns: dictionary with keys linux2, darwin and win32
    """
    # @todo - refactor this to return a ShotgunPath
    return _get_install_locations(core_path).as_system_dict()

def resolve_all_os_paths_to_config(pc_path):
    """
    Given a pipeline configuration path on the current os platform, 
    return paths for all platforms, as cached in the install_locations system file

    :returns: ShotgunPath object
    """
    return _get_install_locations(pc_path)

def get_config_install_location(path):
    """
    Given a pipeline configuration, return the location
    on the current platform.
    
    Loads the location metadata file from install_location.yml
    This contains a reflection of the paths given in the pipeline config entity.

    Returns the path that has been registered for this pipeline configuration 
    for the current OS. This is the path that has been defined in shotgun.
    
    This is useful when drive letter mappings or symlinks are being used to ensure
    a correct path resolution.
    
    This may return None if no path has been registered for the current os.
    
    :param path: Path to a pipeline configuration on disk.
    :returns: registered path, may be None.
    """
    return _get_install_locations(path).current_os

def _get_install_locations(path):
    """
    Given a pipeline configuration OR core location, return paths on all platforms.
    
    :param path: Path to a pipeline configuration on disk.
    :returns: ShotgunPath object
    """
    # basic sanity check
    if not os.path.exists(path):
        raise TankError("The core path '%s' does not exist on disk!" % path)
    
    # for other platforms, read in install_location
    location_file = os.path.join(path, "config", "core", "install_location.yml")

    # load the config file
    try:
        location_data = yaml_cache.g_yaml_cache.get(location_file, deepcopy_data=False)
    except Exception, error:
        raise TankError("Cannot load core config file '%s'. Error: %s" % (location_file, error))

    # do some cleanup on this file - sometimes there are entries that say "undefined"
    # or is just an empty string - turn those into null values
    linux_path = location_data.get("Linux")
    macosx_path = location_data.get("Darwin")
    win_path = location_data.get("Windows")
    
    # this file may contain environment variables. Try to expand these.
    if linux_path:
        linux_path = os.path.expandvars(linux_path)     
    if macosx_path:
        macosx_path = os.path.expandvars(macosx_path) 
    if win_path:
        win_path = os.path.expandvars(win_path) 

    # lastly, sanity check the paths - sometimes these files contain non-path
    # values such as "None" or "unknown"
    if not linux_path or not linux_path.startswith("/"):
        linux_path = None
    if not macosx_path or not macosx_path.startswith("/"):
        macosx_path = None
    if not win_path or not (win_path.startswith("\\") or win_path[1] == ":"):
        win_path = None

    # sanitize data into a ShotgunPath and return data
    return ShotgunPath(win_path, linux_path, macosx_path)




####################################################################################################################
# utils for determining core version numbers

def get_currently_running_api_version():
    """
    Returns the version number string for the core API, 
    based on the code that is currently executing.
    
    :returns: version string, e.g. 'v1.2.3'. 'unknown' if a version number cannot be determined.
    """
    # read this from info.yml
    info_yml_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "info.yml"))
    return _get_version_from_manifest(info_yml_path)


def get_core_api_version(core_install_root):
    """
    Returns the version string for the core api associated with this config.
    This method is 'forgiving' and in the case no associated core API can be 
    found for this location, 'unknown' will be returned rather than 
    an exception raised. 

    :param core_install_root: Path to a core installation root, either the root of a pipeline
                              configuration, or the root of a "bare" studio code location.
    :returns: version str e.g. 'v1.2.3', 'unknown' if no version could be determined. 
    """
    # now try to get to the info.yml file to get the version number
    info_yml_path = os.path.join(core_install_root, "install", "core", "info.yml")
    return _get_version_from_manifest(info_yml_path)
    
def _get_version_from_manifest(info_yml_path):
    """
    Helper method. 
    Returns the version given a manifest.
    
    :param info_yml_path: path to manifest file.
    :returns: Always a string, 'unknown' if data cannot be found
    """
    try:
        data = yaml_cache.g_yaml_cache.get(info_yml_path, deepcopy_data=False)
        data = str(data.get("version", "unknown"))
    except Exception:
        data = "unknown"

    return data


