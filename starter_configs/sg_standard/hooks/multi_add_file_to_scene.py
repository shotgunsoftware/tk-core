"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Hook that loads items into the current scene. 

This hook supports a number of different platforms and the behaviour on each platform is
different. See code comments for details.


"""
import tank
import os

class MayaAddFileToScene(tank.Hook):
    
    def execute(self, engine_name, file_path, shotgun_data, **kwargs):
        """
        Hook entry point and app-specific code dispatcher
        """
        if engine_name=="tk-maya":
            self.add_file_to_maya(file_path, shotgun_data)
            
        elif engine_name=="tk-nuke":
            self.add_file_to_nuke(file_path, shotgun_data)
            
        elif engine_name=="tk-motionbuilder":
            self.add_file_to_motionbuilder(file_path, shotgun_data)
            
        else:
            raise Exception("Don't know how to load file into unknown engine %s" % engine_name)
        
    ###############################################################################################
    # app specific implementations
    
    def add_file_to_maya(self, file_path, shotgun_data):
        """
        Load file into Maya.
        
        This implementation creates a standard maya reference file for any item.
        """
        
        import pymel.core as pm
        import maya.cmds as cmds
        
        # get the slashes right
        file_path = file_path.replace(os.path.sep, "/")
        
        (path, ext) = os.path.splitext(file_path)
        
        texture_extensions = [".png", ".jpg", ".jpeg", ".exr", ".cin", ".dpx",
                              ".psd", ".tiff", ".tga"]
        
        if ext in [".ma", ".mb"]:
            # maya file - load it as a reference
            pm.system.createReference(file_path)
            
        if ext in texture_extensions:
            # create a file texture read node
            x = cmds.shadingNode('file', asTexture=True)
            cmds.setAttr( "%s.fileTextureName" % x, file_path, type="string" )

        else:
            self.parent.log_error("Unsupported file extension! Nothing will be loaded.")
        
    def add_file_to_nuke(self, file_path, shotgun_data):
        """
        Load item into Nuke.
        
        This implementation will create a read node and associate the given path with 
        the read node's file input.
        """
        
        import nuke
        
        # get the slashes right
        file_path = file_path.replace(os.path.sep, "/")

        (path, ext) = os.path.splitext(file_path)

        valid_extensions = [".png", ".jpg", ".jpeg", ".exr", ".cin", ".dpx", ".tiff", ".mov"]

        if ext in valid_extensions:
            # create the read node
            nuke.nodes.Read(file=file_path)
        else:
            self.parent.log_error("Unsupported file extension - no read node will be created.")        



    def add_file_to_motionbuilder(self, file_path, shotgun_data):
        """
        Load item into motionbuilder.
        
        This will attempt to merge the loaded file with the scene.
        """
        from pyfbsdk import FBApplication

        # get the slashes right
        file_path = file_path.replace(os.path.sep, "/")
        
        (path, ext) = os.path.splitext(file_path)
        
        if ext != ".fbx":
            self.parent.log_error("Unsupported file extension. Only FBX files are supported.")
        else:
            app = FBApplication()
            app.FileMerge(file_path)
