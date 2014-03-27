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



################################################################################################
# py26 compatible subprocess.check_output call
# from http://stackoverflow.com/questions/2924310/whats-a-good-equivalent-to-pythons-subprocess-check-call-that-returns-the-cont

import subprocess

class SubprocessCalledProcessError(Exception):
    def __init__(self, returncode, cmd, output=None):
        self.returncode = returncode
        self.cmd = cmd
        self.output = output
    def __str__(self):
        return "Command '%s' returned non-zero exit status %d" % (self.cmd, self.returncode)

def subprocess_check_output(*popenargs, **kwargs):
    if 'stdout' in kwargs:
        raise ValueError('stdout argument not allowed, it will be overridden.')
    process = subprocess.Popen(stdout=subprocess.PIPE, *popenargs, **kwargs)
    output, unused_err = process.communicate()
    retcode = process.poll()
    if retcode:
        cmd = kwargs.get("args")
        if cmd is None:
            cmd = popenargs[0]
        raise SubprocessCalledProcessError(retcode, cmd, output=output)
    return output

################################################################################################

def is_version_newer(a, b):
    """
    Is the version number string a newer than b?
    
    a=v0.12.1 b=0.13.4 -- Returns False
    a=v0.13.1 b=0.13.1 -- Returns True
    a=HEAD b=0.13.4 -- Returns False
    a=master b=0.13.4 -- Returns False

    """
    if a.lower() in ["head", "master"]:
        # our version is latest
        return True
    
    if b.lower() in ["head", "master"]:
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
    if a.lower() in ["head", "master"]:
        # other version is latest
        return False
    
    if b.lower() in ["head", "master"]:
        # comparing against HEAD - our version is always old
        return True

    if a.startswith("v"):
        a = a[1:]
    if b.startswith("v"):
        b = b[1:]

    return LooseVersion(a) < LooseVersion(b)
