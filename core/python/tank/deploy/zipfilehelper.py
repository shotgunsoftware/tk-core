"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------
"""
import os
import zipfile

def _process_item(zip_obj, item_path, targetpath):
    """
    Modified version of _extract_member in http://hg.python.org/cpython/file/538f4e774c18/Lib/zipfile.py
    
    """
    # build the destination pathname, replacing
    # forward slashes to platform specific separators.
    # Strip trailing path separator, unless it represents the root.
    if (targetpath[-1:] in (os.path.sep, os.path.altsep)
        and len(os.path.splitdrive(targetpath)[1]) > 1):
        targetpath = targetpath[:-1]
    
    # don't include leading "/" from file name if present
    if item_path[0] == '/':
        targetpath = os.path.join(targetpath, item_path[1:])
    else:
        targetpath = os.path.join(targetpath, item_path)
    
    targetpath = os.path.normpath(targetpath)
    
    # Create all upper directories if necessary.
    upperdirs = os.path.dirname(targetpath)
    if upperdirs and not os.path.exists(upperdirs):
        os.makedirs(upperdirs, 0777)
    
    if item_path[-1] == '/':
        # this is a directory!
        if not os.path.isdir(targetpath):
            os.mkdir(targetpath, 0777)
    
    else:
        # this is a file! - write it in a way which is compatible
        # with py25 zipfile library interface
        target_obj = open(targetpath, "wb")
        target_obj.write(zip_obj.read(item_path))
        target_obj.close()
        
    return targetpath
    
    

def unzip_file(zip_file, target_folder):
    """
    Does the following command, but in a way which works with 
    Python 2.5 and Python2.6.2

    z = zipfile.ZipFile(zip_file, "r")
    z.extractall(target_folder)    
    
    works around http://bugs.python.org/issue6050
    
    """
        
    zip_obj = zipfile.ZipFile(zip_file, "r")
    
    # loosely based on:
    # http://forums.devshed.com/python-programming-11/unzipping-a-zip-file-having-folders-and-subfolders-534487.html

    # make sure we are using consistent permissions    
    old_umask = os.umask(0)
    try:
        # get list of filenames contained in archinve
        for x in zip_obj.namelist(): 
            # process them one by one
            _process_item(zip_obj, x, target_folder)
    finally:
        os.umask(old_umask)
