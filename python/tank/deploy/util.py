# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.


from distutils.version import LooseVersion
import os
import sys
import shutil
from ..platform import constants
from ..errors import TankError

def should_use_legacy_yaml_parser(args):
    """
    Given a set of command line args, determine if the
    legacy yaml parser should be used.

    :param args: list of arg strings
    :returns: (use_legacy, adjusted_args) - tuple with bool to indicate
              if the legacy parser should be used and a list of args where
              the legacy flag has been removed.
    """
    # look for a legacy parser flag
    if constants.LEGACY_YAML_PARSER_FLAG in args:
        legacy_parser = True
        args.remove(constants.LEGACY_YAML_PARSER_FLAG)
    else:
        legacy_parser = False

    return (legacy_parser, args)

def execute_tank_command(pipeline_config_path, args):
    """
    Wrapper around execution of the tank command of a specified pipeline
    configuration.

    :raises: Will raise a SubprocessCalledProcessError if the tank command
             returns a non-zero error code.
             Will raise a TankError if the tank command could not be
             executed.
    :param pipeline_config_path: the path to the pipeline configuration that
                                 contains the tank command
    :param args:                 list of arguments to pass to the tank command
    :returns:                    text output of the command
    """
    if not os.path.isdir(pipeline_config_path):
        raise TankError("Could not find the Pipeline Configuration on disk: %s"
                        % pipeline_config_path)

    command_path = os.path.join(pipeline_config_path,
                                _get_tank_command_name())

    if not os.path.isfile(command_path):
        raise TankError("Could not find the tank command on disk: %s"
                        % command_path)

    return subprocess_check_output([command_path] + args)

def _get_tank_command_name():
    """ Returns the name of the tank command executable. """
    return "tank" if sys.platform != "win32" else "tank.bat"

def _copy_folder(log, src, dst, skip_list=None): 
    """
    Alternative implementation to shutil.copytree
    Copies recursively with very open permissions.
    Creates folders if they don't already exist.
    """
    files = []
    
    if not os.path.exists(dst):
        log.debug("mkdir 0777 %s" % dst)
        os.mkdir(dst, 0777)

    names = os.listdir(src) 
    for name in names:

        if skip_list and name in skip_list:
            # skip!
            continue

        srcname = os.path.join(src, name) 
        dstname = os.path.join(dst, name) 
                
        try: 
            if os.path.isdir(srcname): 
                files.extend( _copy_folder(log, srcname, dstname) )             
            else: 
                shutil.copy(srcname, dstname)
                log.debug("Copy %s -> %s" % (srcname, dstname))
                files.append(srcname)
                # if the file extension is sh, set executable permissions
                if dstname.endswith(".sh") or dstname.endswith(".bat"):
                    try:
                        # make it readable and executable for everybody
                        os.chmod(dstname, 0777)
                        log.debug("CHMOD 777 %s" % dstname)
                    except Exception, e:
                        log.error("Can't set executable permissions on %s: %s" % (dstname, e))
        
        except Exception, e: 
            log.error("Can't copy %s to %s: %s" % (srcname, dstname, e)) 
    
    return files

def is_version_head(version):
    """
    Returns if the specified version is HEAD or MASTER. The comparison is case insensitive.

    :param version: Version to test.

    :returns: True if version is HEAD or MASTER, false otherwise.
    """
    return version.lower() in ["head", "master"]


def is_version_newer(a, b):
    """
    Is the version number string a newer than b?
    
    a=v0.12.1 b=0.13.4 -- Returns False
    a=v0.13.1 b=0.13.1 -- Returns True
    a=HEAD b=0.13.4 -- Returns False
    a=master b=0.13.4 -- Returns False

    """
    if is_version_head(a):
        # our version is latest
        return True
    
    if is_version_head(b):
        # comparing against HEAD - our version is always old
        return False

    if a.startswith("v"):
        a = a[1:]
    if b.startswith("v"):
        b = b[1:]

    return LooseVersion(a) > LooseVersion(b)


def is_version_older(a, b):
    """
    Is the version number string a older than b?
    
    a=v0.12.1 b=0.13.4 -- Returns False
    a=v0.13.1 b=0.13.1 -- Returns True
    a=HEAD b=0.13.4 -- Returns False
    a=master b=0.13.4 -- Returns False

    """
    if is_version_head(a):
        # other version is latest
        return False
    
    if is_version_head(b):
        # comparing against HEAD - our version is always old
        return True

    if a.startswith("v"):
        a = a[1:]
    if b.startswith("v"):
        b = b[1:]

    return LooseVersion(a) < LooseVersion(b)
