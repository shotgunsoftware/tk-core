"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

I/O Hook which creates folders on disk.

"""

from tank import Hook
import os
import shutil

class ProcessFolderCreation(Hook):
    
    def execute(self, items, **kwargs):
        """
        The default implementation creates folders recursively using open permissions.
        
        Items is a list of dictionaries. Each dictionary can be of the following type:
        
        Standard Folder
        ---------------
        This represents a standard folder in the file system which is not associated
        with anything in Shotgun. It contains the following keys:
        
        * "action": "folder"
        * "metadata": The configuration yaml file for this item
        * "path": path on disk to the item
        
        Entity Folder
        -------------
        This represents a folder in the file system which is associated with a 
        shotgun entity. It contains the following keys:
        
        * "action": "entity_folder"
        * "metadata": The configuration yaml file for this item
        * "path": path on disk to the item
        * "entity": Shotgun entity link dict with keys type, id and name.
        
        File Copy
        ---------
        This represents a file copy operation which should be carried out.
        It contains the following keys:
        
        * "action": "copy"
        * "metadata": The configuration yaml file associated with the directory level 
                      on which this object exists.
        * "source_path": location of the file that should be copied
        * "target_path": target location to where the file should be copied.
                
        
        File Creation
        -------------
        This is similar to the file copy, but instead of a source path, a chunk
        of data is specified. It contains the following keys:
        
        * "action": "create_file"
        * "metadata": The configuration yaml file associated with the directory level 
                      on which this object exists.
        * "content": file content
        * "target_path": target location to where the file should be copied.
 
        """

        # set the umask so that we get true permissions
        old_umask = os.umask(0)
        try:

            # loop through our list of items
            for i in items:
                
                action = i.get("action")
                
                if action == "entity_folder" or action == "folder":
                    # folder creation
                    path = i.get("path")    
                    if not os.path.exists(path):
                        # create the folder using open permissions
                        os.makedirs(path, 0777)
                    
                elif action == "copy":
                    # a file copy
                    source_path = i.get("source_path")
                    target_path = i.get("target_path")
                    if not os.path.exists(target_path):
                        # do a standard file copy with open permissions
                        shutil.copy(source_path, target_path)
    
                elif action == "create_file":
                    # create a new file based on content
                    path = i.get("path")
                    parent_folder = os.path.dirname(path)
                    content = i.get("content")
                    if not os.path.exists(parent_folder):
                        os.makedirs(parent_folder, 0777)
                    if not os.path.exists(path):
                        # create the file
                        fp = open(path, "wb")
                        fp.write(content)
                        fp.close()
                    
                else:
                    raise Exception("Unknown folder hook action '%s'" % action)
        
        finally:
            # reset umask
            os.umask(old_umask)

        