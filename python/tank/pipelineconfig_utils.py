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
import os
import sys

from tank_vendor import yaml

from .errors import TankError
from .platform import constants


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
    cfg_yml = os.path.join(pipeline_config_path, "config", "core", "pipeline_configuration.yml")

    if not os.path.exists(cfg_yml):
        raise TankError("Configuration metadata file '%s' missing! Please contact support." % cfg_yml)

    fh = open(cfg_yml, "rt")
    try:
        data = yaml.load(fh)
        if data is None:
            raise Exception("File contains no data!")
    except Exception, e:
        raise TankError("Looks like a config file is corrupt. Please contact "
                        "support! File: '%s' Error: %s" % (cfg_yml, e))
    finally:
        fh.close()

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
              { "primary"  : { "mac_path": "/tmp/foo", 
                               "linux_path": None, 
                               "windows_path": "z:\tmp\foo" },
                "textures" : { "mac_path": "/tmp/textures", 
                               "linux_path": None, 
                               "windows_path": "z:\tmp\textures" },
              }
    """
    # now read in the roots.yml file
    # this will contain something like
    # {'primary': {'mac_path': '/studio', 'windows_path': None, 'linux_path': '/studio'}}
    roots_yml = os.path.join(pipeline_config_path, "config", "core", constants.STORAGE_ROOTS_FILE)

    if not os.path.exists(roots_yml):
        raise TankError("Roots metadata file '%s' missing! Please contact support." % roots_yml)

    fh = open(roots_yml, "rt")
    try:
        # if file is empty, initializae with empty dict...
        data = yaml.load(fh) or {}
    except Exception, e:
        raise TankError("Looks like the roots file is corrupt. Please contact "
                        "support! File: '%s' Error: %s" % (roots_yml, e))
    finally:
        fh.close()

    # if there are more than zero storages defined, ensure one of them is the primary storage
    if len(data) > 0 and constants.PRIMARY_STORAGE_NAME not in data:
        raise TankError("Could not find a primary storage in roots file "
                        "for configuration %s!" % pipeline_config_path)

    # now use our helper function to process the paths    
    for s in data:
        data[s]["mac_path"] = sanitize_path(data[s]["mac_path"], "/")
        data[s]["linux_path"] = sanitize_path(data[s]["linux_path"], "/")
        data[s]["windows_path"] = sanitize_path(data[s]["windows_path"], "\\")

    return data


def sanitize_path(path, separator=os.path.sep):
    """
    Sanitize and clean up paths that may be incorrect.
    
    The following modifications will be carried out:
    
    None returns None
    
    Trailing slashes are removed:
    1. /foo/bar      - unchanged
    2. /foo/bar/     - /foo/bar
    3. z:/foo/       - z:\foo
    4. z:/           - z:\
    5. z:\           - z:\
    6. \\foo\bar\    - \\foo\bar

    Double slashes are removed:
    1. //foo//bar    - /foo/bar
    2. \\foo\\bar    - \\foo\bar

    Leading and trailing spaces are removed:
    1. "   z:\foo  " - "Z:\foo"

    :param path: the path to clean up
    :param separator: the os.sep to adjust the path for. / on nix, \ on win.
    :returns: cleaned up path
    """
    if path is None:
        return None

    # ensure there is no white space around the path
    path = path.strip()

    # get rid of any slashes at the end
    # after this step, path value will be "/foo/bar", "c:" or "\\hello"
    path = path.rstrip("/\\")
    
    # add slash for drive letters: c: --> c:/
    if len(path) == 2 and path.endswith(":"):
        path += "/"
    
    # and convert to the right separators
    # after this we have a path with the correct slashes and no end slash
    local_path = path.replace("\\", separator).replace("/", separator)

    # now weed out any duplicated slashes. iterate until done
    while True:
        new_path = local_path.replace("//", "/")
        if new_path == local_path:
            break
        else:
            local_path = new_path
    
    # for windows, remove duplicated backslashes, except if they are 
    # at the beginning of the path
    while True:
        new_path = local_path[0] + local_path[1:].replace("\\\\", "\\")
        if new_path == local_path:
            break
        else:
            local_path = new_path

    return local_path



####################################################################################################################
# Core API resolve utils 

def get_path_to_current_core():
    """
    Returns the local path of the currently executing code, assuming that this code is 
    located inside a standard toolkit install setup. If the code that is running is part
    of a localized pipeline configuration, the PC root path will be returned, otherwise 
    a 'studio' root will be returned.
    
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

    if is_localized(pipeline_config_path):
        # first, try to locate an install local to this pipeline configuration.
        # this would find any localized APIs.
        install_path = pipeline_config_path

    else:
        # this PC is associated with a shared API (studio install)
        # follow the links defined in the configuration to establish which 
        # setup it has been associated with.
        studio_linkback_files = {"win32": os.path.join(pipeline_config_path, "install", "core", "core_Windows.cfg"), 
                                 "linux2": os.path.join(pipeline_config_path, "install", "core", "core_Linux.cfg"), 
                                 "darwin": os.path.join(pipeline_config_path, "install", "core", "core_Darwin.cfg")}
        
        curr_linkback_file = studio_linkback_files[sys.platform]
        
        # this file will contain the path to the API which is meant to be used with this PC.
        install_path = None
        try:
            fh = open(curr_linkback_file, "rt")
            data = fh.read().strip() # remove any whitespace, keep text
            # expand any env vars that are used in the files. For example, you could have 
            # an env variable $STUDIO_TANK_PATH=/sgtk/software/shotgun/studio and your 
            # linkback file may just contain "$STUDIO_TANK_PATH" instead of an explicit path.
            data = os.path.expandvars(data)
            if data not in ["None", "undefined"] and os.path.exists(data):
                install_path = data
            fh.close()  
        except:
            pass
                
    return install_path
    
def resolve_all_os_paths_to_core(core_path):
    """
    Given a core path on the current os platform, 
    return paths for all platforms, 
    as cached in the install_locations system file
    
    :returns: dictionary with keys linux2, darwin and win32
    """
    return _get_install_locations(core_path)

def resolve_all_os_paths_to_config(pc_path):
    """
    Given a pipeline configuration path on the current os platform, 
    return paths for all platforms, as cached in the install_locations system file
    
    :returns: dictionary with keys linux2, darwin and win32
    """
    return _get_install_locations(pc_path)

def get_config_install_location(path):
    """
    Given a pipeline configuration, return the location
    on the current platform.
    
    Loads the location metadata file from install_location.yml
    This contains a reflection of the paths given in the pc entity.

    Returns the path that has been registered for this pipeline configuration 
    for the current OS. This is the path that has been defined in shotgun.
    
    This is useful when drive letter mappings or symlinks are being used to ensure
    a correct path resolution.
    
    This may return None if no path has been registered for the current os.
    
    :param path: Path to a pipeline configuration on disk.
    :returns: registered path, may be None.
    """
    # resolve
    locations = _get_install_locations(path)
    # do a bit of cleanup of the input data
    return sanitize_path(locations[sys.platform])

def _get_install_locations(path):
    """
    Given a pipeline configuration OR core location, return paths on all platforms.
    
    :param path: Path to a pipeline configuration on disk.
    :returns: dictionary with keys linux2, darwin and win32
    """
    # basic sanity check
    if not os.path.exists(path):
        raise TankError("The core path '%s' does not exist on disk!" % path)
    
    # for other platforms, read in install_location
    location_file = os.path.join(path, "config", "core", "install_location.yml")
    if not os.path.exists(location_file):
        raise TankError("Cannot find core config file '%s' - please contact support!" % location_file)

    # load the config file
    try:
        open_file = open(location_file)
        try:
            location_data = yaml.load(open_file)
        finally:
            open_file.close()
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

    # return data
    return {"win32": win_path, "darwin": macosx_path, "linux2": linux_path }
        



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
        info_fh = open(info_yml_path, "r")
        try:
            data = yaml.load(info_fh)
        finally:
            info_fh.close()
        data = str(data.get("version", "unknown"))
    except:
        data = "unknown"

    return data
    
