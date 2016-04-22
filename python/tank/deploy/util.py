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
Utility methods that are specific to tank commands
"""

import os
import shutil
from . import constants


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

