from tank import Hook
import os

class DescriptorTypeCheck(Hook):
    
    def execute(self, descriptor_type, project_root, location_dict, app_or_engine, **kwargs):
        """
        Gets executed when trying to resolve a descriptor.
        """
        return None
