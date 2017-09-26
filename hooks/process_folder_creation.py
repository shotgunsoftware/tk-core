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
I/O Hook which creates folders on disk.

"""

from tank import Hook
import os
import sys
import shutil

class ProcessFolderCreation(Hook):
    
    def execute(self, items, preview_mode, **kwargs):
        """
        The default implementation creates folders recursively using open permissions.
        
        This hook should return a list of created items.
        
        Items is a list of dictionaries. Each dictionary can be of the following type:
        
        Standard Folder
        ---------------
        This represents a standard folder in the file system which is not associated
        with anything in Shotgun. It contains the following keys:
        
        * "action": "folder"
        * "metadata": The configuration yaml data for this item
        * "path": path on disk to the item
        
        Entity Folder
        -------------
        This represents a folder in the file system which is associated with a 
        shotgun entity. It contains the following keys:
        
        * "action": "entity_folder"
        * "metadata": The configuration yaml data for this item
        * "path": path on disk to the item
        * "entity": Shotgun entity link dict with keys type, id and name.
        
        Remote Entity Folder
        --------------------
        This is the same as an entity folder, except that it was originally
        created in another location. A remote folder request means that your
        local toolkit instance has detected that folders have been created by
        a different file system setup. It contains the following keys:
        
        * "action": "remote_entity_folder"
        * "metadata": The configuration yaml data for this item
        * "path": path on disk to the item
        * "entity": Shotgun entity link dict with keys type, id and name.

        File Copy
        ---------
        This represents a file copy operation which should be carried out.
        It contains the following keys:
        
        * "action": "copy"
        * "metadata": The configuration yaml data associated with the directory level 
                      on which this object exists.
        * "source_path": location of the file that should be copied
        * "target_path": target location to where the file should be copied.
        
        File Creation
        -------------
        This is similar to the file copy, but instead of a source path, a chunk
        of data is specified. It contains the following keys:
        
        * "action": "create_file"
        * "metadata": The configuration yaml data associated with the directory level 
                      on which this object exists.
        * "content": file content
        * "target_path": target location to where the file should be copied.
 
        Symbolic Links
        -------------
        This represents a request that a symbolic link is created. Note that symbolic links are not 
        supported in the same way on all operating systems. The default hook therefore does not
        implement symbolic link support on Windows systems. If you want to add symbolic link support
        on windows, simply copy this hook to your project configuration and make the necessary
        modifications.
        
        * "action": "symlink"
        * "metadata": The raw configuration yaml data associated with symlink yml config file.
        * "path": the path to the symbolic link
        * "target": the target to which the symbolic link should point
        """
        
        # set the umask so that we get true permissions
        old_umask = os.umask(0)
        folders = []
        try:

            # loop through our list of items
            for i in items:
                
                action = i.get("action")
                
                if action in ["entity_folder", "folder"]:
                    # folder creation
                    path = i.get("path")    
                    if not os.path.exists(path):
                        if not preview_mode:
                            # create the folder using open permissions
                            os.makedirs(path, 0777)
                        folders.append(path)
                        
                elif action == "remote_entity_folder":
                    # Remote folder creation
                    #
                    # NOTE! This action happens when another user has created
                    # a folder on their machine and we are syncing our local path 
                    # cache to be aware of this folder's existance.
                    # 
                    # For a traditional setup, where the project storage is shared,
                    # there is no need to do I/O for remote folders - these folders
                    # have already been created on the remote storage so you have access
                    # to them already. 
                    # 
                    # On a setup where each user or group of users is attached to
                    # different, independendent file storages, which are synced, 
                    # it may be meaningful to "replay" the remote folder creation
                    # on the local system. This would result in the same folder
                    # scaffold on each disk which is storing project data.
                    # 
                    # path = i.get("path")    
                    # if not os.path.exists(path):
                    #     if not preview_mode:
                    #         # create the folder using open permissions
                    #         os.makedirs(path, 0777)
                    #     folders.append(path)
                    pass
                
                elif action == "symlink":
                    # symbolic link
                    if sys.platform == "win32":
                        # no windows support
                        continue
                    path = i.get("path")
                    target = i.get("target")
                    # note use of lexists to check existance of symlink
                    # rather than what symlink is pointing at
                    if not os.path.lexists(path):
                        if not preview_mode:
                            os.symlink(target, path)
                        folders.append(path)

                elif action == "copy":
                    # a file copy
                    source_path = i.get("source_path")
                    target_path = i.get("target_path")
                    if not os.path.exists(target_path):
                        if not preview_mode:
                            # do a standard file copy
                            shutil.copy(source_path, target_path)
                            # set permissions to open
                            os.chmod(target_path, 0666)
                        folders.append(target_path)
    
                elif action == "create_file":
                    # create a new file based on content
                    path = i.get("path")
                    parent_folder = os.path.dirname(path)
                    content = i.get("content")
                    if not os.path.exists(parent_folder) and not preview_mode:
                        os.makedirs(parent_folder, 0777)
                    if not os.path.exists(path):
                        if not preview_mode:
                            # create the file
                            fp = open(path, "wb")
                            fp.write(content)
                            fp.close()
                            # and set permissions to open
                            os.chmod(path, 0666)
                        folders.append(path)
                    
        
        finally:
            # reset umask
            os.umask(old_umask)

        return folders
