"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------
"""
import os
import zipfile

from ..platform import constants

def unzip_file(tk, zip_tmp, target):
    zip_file = zipfile.ZipFile(zip_tmp, "r")
    if hasattr(zip_file, "extractall"):
        # py 2.6+
        zip_file.extractall(target)
    else:
        # based on:
        # http://forums.devshed.com/python-programming-11/unzipping-a-zip-file-having-folders-and-subfolders-534487.html

        names = zip_file.namelist()

        def dir_names(names):
            # identify paths ending in a directory
            return [x for x in names if os.path.split(x)[0] and not os.path.split(x)[1]]

        def file_names(names):
            # identify paths ending in a file
            return [x for x in names if os.path.split(x)[1]]


        for dir_name in dir_names(names):
            # create directories
            dir_path = os.path.join(target, dir_name)
            if not os.path.exists(dir_path):
                tk.execute_hook(constants.CREATE_FOLDERS_CORE_HOOK_NAME, path=dir_path, sg_entity=None)
    
        for name in file_names(names):
            # unzip files
            output_path = os.path.join(target, name)
            outfile = file(output_path, 'wb')
            outfile.write(zip_file.read(name))
            outfile.close()

