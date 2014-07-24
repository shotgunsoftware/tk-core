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
import glob

from tank_vendor import yaml

from .errors import TankError





def is_localized(pipeline_config_path):
    """
    Returns true if the pipeline configuration contains a localized API
    """
    # look for a localized API by searching for a _core_upgrader.py file
    api_file = os.path.join(pipeline_config_path, "install", "core", "_core_upgrader.py")
    return os.path.exists(api_file)










def get_current_code_install_root():
    """
    Returns the root location of the currently executing code, assuming that this code is 
    located inside a standard toolkit install setup. If the code that is running is part
    of a localized pipeline configuration, its root path will be returned, otherwise 
    a 'studio' root will be returned.
    
    This method may not return valid results if there has been any symlinks set up as part of
    the install structure.
    """
    p = os.path.abspath(os.path.join( os.path.dirname(__file__), "..", "..", "..", ".."))
    if not os.path.exists(p):
        raise TankError("Cannot resolve the install location from the location of the Core Code! "
                        "This can happen if you try to move or symlink the Sgtk API. "
                        "Please contact support.")
    return p
    



def get_current_core_install_location_data():
    """
    Given the location of the running code, find the configuration which holds
    the installation location on all platforms. Return the content of this file.
    Note that some entries may be None in case a core wasn't defined for that platform.
    
    This is similar to get_current_code_install_root() except it returns locations for all three platforms. 
    
    :returns: dict with keys linux2, darwin and win32
    """

    core_api_root = os.path.abspath(os.path.join( os.path.dirname(__file__), "..", "..", "..", "..", "..", ".."))
    core_cfg = os.path.join(core_api_root, "config", "core")

    if not os.path.exists(core_cfg):
        full_path_to_file = os.path.abspath(os.path.dirname(__file__))
        raise TankError("Cannot resolve the core configuration from the location of the Toolkit Code! "
                        "This can happen if you try to move or symlink the Toolkit API. The "
                        "Toolkit API is currently picked up from %s which is an "
                        "invalid location." % full_path_to_file)
    
    location_file = os.path.join(core_cfg, "install_location.yml")
    if not os.path.exists(location_file):
        raise TankError("Cannot find '%s' - please contact support!" % location_file)

    # load the config file
    try:
        open_file = open(location_file)
        try:
            location_data = yaml.load(open_file)
        finally:
            open_file.close()
    except Exception, error:
        raise TankError("Cannot load config file '%s'. Error: %s" % (location_file, error))

    # do some cleanup on this file - sometimes there are entries that say "undefined"
    # or is just an empty string - turn those into null values
    linux_path = location_data.get("Linux")
    macosx_path = location_data.get("Darwin")
    win_path = location_data.get("Windows")
    
    if not linux_path or not linux_path.startswith("/"):
        linux_path = None
    if not macosx_path or not macosx_path.startswith("/"):
        macosx_path = None
    if not win_path or not (win_path.startswith("\\") or win_path[1] == ":"):
        win_path = None

    # return data using sys.platform jargon
        return {"win32": win_path, "darwin": macosx_path, "linux2": linux_path } 















def get_currently_running_api_version():
    """
    Returns the version number string for the core API, 
    based on the code that is currently executing.
    
    :returns: version string, e.g. 'v1.2.3'. 'unknown' if a version number cannot be determined.
    """
    # read this from info.yml
    info_yml_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "info.yml"))
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




def get_core_api_version(core_install_root):
    """
    Returns the version string for the core api associated with this config.
    This method is 'forgiving' and in the case no associated core API can be 
    found for this location, None will be returned rather than 
    an exception raised. 

    :param core_install_root: Path to a core installation root, either the root of a pipeline
                              configuration, or the root of a "bare" studio code location.
    :returns: version str e.g. 'v1.2.3', None if no version could be determined. 
    """
    # now try to get to the info.yml file to get the version number
    info_yml_path = os.path.join(core_install_root, "install", "core", "info.yml")
    
    if os.path.exists(info_yml_path):
        try:
            info_fh = open(info_yml_path, "r")
            try:
                data = yaml.load(info_fh)
            finally:
                info_fh.close()
            data = data.get("version")
        except:
            data = "unknown"
    else:
        data = "unknown"

    return data
    














def get_core_api_install_location(pipeline_config_path):
    """
    Returns the core api install location associated with the given pipeline configuration.
    
    This method will return the root point, so a pipeline config root if running 
    a localized API or a studio location root if running a bare API.
    
    The install location is where toolkit caches engines, apps, frameworks and is
    where it keeps the Core API.       
    
    Use this method whenever a pipeline configuration is available, since it is more
    sophisticated. In cases when no pipeline configuration is available, revert to  
    get_current_code_install_root() which will base the install location
    on the current code.
    
    When a pipeline configuration exists, a specific relationship between the core
    core and that configuration has also been established. This method will follow
    this connection to return the actual associated core API rather than the 
    running API. Usually these two are the same (or so they should be), but this is not
    guaranteed.
    
    :param pipeline_config_path: path to a pipeline configuration
    :returns: Path to the studio location root or pipeline configuration root
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
            
        if install_path is None:
            # no luck determining the location of the core API through our two 
            # established modus operandi. Fall back on the crude legacy
            # approach, which is to grab and return the currently running code.
            install_path = get_current_code_install_root()
                
    return install_path






