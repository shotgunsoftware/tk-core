"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Classes for the main Tank API.

"""
import os
import glob

from tank_vendor import yaml

from . import hook
from . import folder
from . import constants
from . import context
from . import root
from .util import shotgun
from .errors import TankError
from .folder.folder_io import folder_preflight_checks
from .path_cache import PathCache
from .template import read_templates, TemplatePath
from .platform import constants as platform_constants

class Tank(object):
    """
    Object with presenting interface to tank.
    """
    def __init__(self, project_path):
        """
        :param project_path: Path to root of project containing tank configuration.
        """
        # TODO: validate this really is a valid project path
        self.__project_path = os.path.abspath(project_path)
        self.__sg = None
        self.roots = root.get_project_roots(self.project_path)
        self.templates = read_templates(project_path, self.roots)
        
        # execute a tank_init hook for developers to use.
        self.execute_hook(platform_constants.TANK_INIT_HOOK_NAME)

    ################################################################################################
    # properties
    
    @property
    def project_path(self):
        """
        Path to the primary root directory for a project.
        """
        return self.__project_path
    
    @property
    def shotgun(self):
        """
        Lazily create a Shotgun API handle
        """
        if self.__sg is None:
            self.__sg = shotgun.create_sg_connection(self.project_path)
        
        return self.__sg
        
    @property
    def version(self):
        """
        The version of the tank Core API (e.g. v0.2.3)

        :returns: string representing the version
        """
        # read this from info.yml
        info_yml_path = os.path.abspath(os.path.join( os.path.dirname(__file__), "..", "..", "info.yml"))
        try:
            info_fh = open(info_yml_path, "r")
            try:
                data = yaml.load(info_fh)
            finally:
                info_fh.close()
            data = str(data.get("version", "unknown"))
        # NOTE! REALLY WANT THIS TO BEHAVE NICELY WHEN AN ERROR OCCURS
        # PLEASE DO NOT LIMIT THIS CATCH-ALL EXCEPTION
        except:
            data = "unknown"

        return data

    @property
    def documentation_url(self):
        """
        Return the relevant documentation url for this app.

        :returns: url string, None if no documentation was found
        """
        # read this from info.yml
        info_yml_path = os.path.abspath(os.path.join( os.path.dirname(__file__), "..", "..", "info.yml"))
        try:
            info_fh = open(info_yml_path, "r")
            try:
                data = yaml.load(info_fh)
            finally:
                info_fh.close()
            data = str(data.get("documentation_url"))
            if data == "":
                data = None
        # NOTE! REALLY WANT THIS TO BEHAVE NICELY WHEN AN ERROR OCCURS
        # PLEASE DO NOT LIMIT THIS CATCH-ALL EXCEPTION
        except:
            data = None

        return data
    
    ##########################################################################################
    # public methods
    
    def template_from_path(self, path):
        """Finds a template that matches the input path.

        :param input_path: path against which to match a template. 
        :type  input_path: string representation of a path
        
        :returns: Template matching this path
        :rtype: Template instance or None
        """
        matched = []
        for key, template in self.templates.items():
            if template.validate(path):
                matched.append(template)

        if len(matched) == 0:
            return None
        elif len(matched) == 1:
            return matched[0]
        else:
            # ambiguity!
            msg = "%d Tank templates are matching the path '%s'.\n" % (len(matched), path)
            msg += "The overlapping templates are:\n"
            msg += "\n".join([str(x) for x in matched])         
            raise TankError(msg)        
    
    def paths_from_template(self, template, fields, skip_keys=None):
        """
        Finds paths that match a template using field values passed.
        
        By omitting fields, you are effectively adding wild cards to the search.
        So if a template requires Shot, Sequence, Name and Version, and you 
        omit the version fields from the fields dictionary, the method 
        will return paths to all the different versions you can find.
        
        For more information and examples, see the API documentation.

        :param template: Template against whom to match.
        :type  template: Tank.Template instance.
        :param fields: Fields and values to use.
        :type  fields: Dictionary.
        :param skip_keys: Keys whose values should be ignored from the fields parameter.
        :type  skip_keys: List of key names.

        :returns: Matching file paths
        :rtype: List of strings.
        """
        skip_keys = skip_keys or []
        if isinstance(skip_keys, basestring):
            skip_keys = [skip_keys]
        local_fields = fields.copy()
        # Add wildcard for each key to skip
        for skip_key in skip_keys:
            local_fields[skip_key] = "*"
        # Add wildcard for each field missing from the input fields
        for missing_key in template.missing_keys(local_fields):
            local_fields[missing_key] = "*"
            skip_keys.append(missing_key)
        glob_str = template._apply_fields(local_fields, ignore_types=skip_keys)
        # Return all files which are valid for this template
        found_files = glob.iglob(glob_str)
        return [found_file for found_file in found_files if template.validate(found_file)]

    def abstract_paths_from_template(self, template, fields):
        """Returns an abstract path based on a template.

        This method is similar to paths_from_template with the addition that 
        abstract fields (such as sequence fields and any other field that is 
        marked as being abstract) is returned as their abstract value by default.
        
        So rather than returning a value for every single frame in an image sequence,
        this method will return a single path representing all the frames and using the
        abstract value '%04d' for the sequence key. Similarly, it may be useful to return
        %V to represent an eye (assuming an eye template has been defined and marked as abstract) 

        For more information and examples, see the API documentation.

        :param template: Template with which to search.
        :param fields: Mapping of keys to values with which to assemble the abstract path.

        :returns: A list of paths whose abstract keys use their abstract(default) value unless
                  a value is specified for them in the fields parameter.
        """
        search_template = template
        
        # the logic is as follows:
        # do a glob and collapse abstract fields down into their abstract patterns
        # unless they are specified with values in the fields dictionary
        #
        # if the leaf level can be avoided, do so. 
        # the leaf level can be avoided if it contains 
        # a combination of non-abstract templates with values in the fields dict
        # and abstract templates.
        
        # can we avoid the leaf level?
        leaf_keys = set(template.keys.keys()) - set(template.parent.keys.keys())
        
        abstract_key_names = [k.name for k in template.keys.values() if k.is_abstract]
        
        skip_leaf_level = True
        for k in leaf_keys:
            if k not in abstract_key_names:
                # a non-abstract key
                if k not in fields:
                    # with no value
                    skip_leaf_level = False
                    break

        if skip_leaf_level:
            search_template = template.parent
            
        # now carry out a regular search based on the template 
        found_files = self.paths_from_template(search_template, fields)
        
        st_abstract_key_names = [k.name for k in search_template.keys.values() if k.is_abstract]
        
        # now collapse down the search matches for any abstract fields, 
        # and add the leaf level if necessary
        abstract_paths = set()
        for found_file in found_files:
            
            cur_fields = search_template.get_fields(found_file)
            
            # pass 1 - go through the fields for this file and
            # zero out the abstract fields - this way, apply
            # fields will pick up defaults for those fields
            #
            # if the system found matches for eye=left and eye=right,
            # by deleting all eye values they will be replaced by %V
            # as the template is applied.
            #
            for abstract_key_name in st_abstract_key_names:
                del cur_fields[abstract_key_name]
            
            # pass 2 - if we ignored the leaf level, add those fields back
            # note that there is no risk that we add abstract fields at this point
            # since the fields dictionary should only ever contain "real" values.
            # also, we may have deleted actual fields in the pass above and now we
            # want to put them back again. 
            for f in fields:
                if f not in cur_fields:
                    cur_fields[f] = fields[f]
            
            # now we have all the fields we need to compose the full template
            abstract_path = template.apply_fields(cur_fields)                
            abstract_paths.add(abstract_path)
                
        return list(abstract_paths)


    def paths_from_entity(self, entity_type, entity_id):
        """
        Finds paths associated with an entity.
        
        :param entity_type: a Shotgun entity type
        :params entity_id: a Shotgun entity id
        
        :returns: Matching file paths
        :rtype: List of strings.
        """

        # Use the path cache to look up all paths associated with this entity
        path_cache = PathCache(self.project_path)
        paths = path_cache.get_paths(entity_type, entity_id)
        path_cache.close()
        
        return paths

    def entity_from_path(self, path):
        """
        Returns the shotgun entity associated with a path
        
        :param path: A path to a folder or file
        
        :returns: Shotgun dictionary containing name, type and id or None 
                  if no path was associated.
        """
        # Use the path cache to look up all paths associated with this entity
        path_cache = PathCache(self.project_path)
        entity = path_cache.get_entity(path)
        path_cache.close()
        
        return entity

    def context_empty(self):
        """
        Creates an empty context.

        :returns: Context object.
        """
        return context.create_empty(self)
    
    def context_from_path(self, path, previous_context=None):
        """
        Derive a context from a path.

        :param path: a file system path
        :param previous_context: a context object to use to try to automatically extend the generated
                                 context if it is incomplete when extracted from the path. For example,
                                 the Task may be carried across from the previous context if it is 
                                 suitable and if the task wasn't already expressed in the file system
                                 path passed in via the path argument.
        :returns: Context object.
        """
        return context.from_path(self, path, previous_context)
    
    def context_from_entity(self, entity_type, entity_id):
        """
        Derives a context from a Shotgun entity.

        :param entity_type: The name of the entity type.
        :type  entity_type: String.
        :param entity_id: Shotgun id of the entity upon which to base the context.
        :type  entity_id: Integer.

        :returns: Context object.
        """
        return context.from_entity(self, entity_type, entity_id)
    
    def create_filesystem_structure(self, entity_type, entity_id, engine=None):
        """
        Create folders and associated data on disk to reflect branches in the project tree
        related to a specific entity.
    
        :param entity_type: The name of the entity type.
        :type  entity_type: String.
        :param entity_id: Shotgun id of the entity or list of ids if more than one. 
        :type  entity_id: Integer or list of integers.
        :param engine: Optional engine name to indicate that a second, engine specific 
                       folder creation pass should be executed for a particular engine.
                       Folders marked as deferred will be processed.
        :type engine: String.

        :returns: The number of folders processed
        """
        folders = folder.process_filesystem_structure(self, 
                                                      entity_type, 
                                                      entity_id, 
                                                      False,
                                                      engine)
        return len(folders)
        
    def preview_filesystem_structure(self, entity_type, entity_id, engine=None):
        """
        Previews folders that would be created by create_filesystem_structure.

        :param entity_type: The name of the entity type.
        :type  entity_type: String.
        :param entity_id: Shotgun id of the entity or list of ids if more than one.
        :type  entity_id: Integer or list of integers.
        :param engine: Optional engine name to indicate that a second, engine specific 
                       folder creation pass should be executed for a particular engine.
                       Folders marked as deferred will be processed.
        :type engine: String.

        :returns: List of items processed. 
        """
        folders = folder.process_filesystem_structure(self, 
                                                      entity_type, 
                                                      entity_id, 
                                                      True,
                                                      engine)
        return folders

    def execute_hook(self, hook_name, **kwargs):
        """
        Executes a core level hook, passing it any keyword arguments supplied.
        
        Note! This is part of the private Tank API and should not be called from ouside
        the core API. 

        :param hook_name: Name of hook to execute.

        :returns: Return value of the hook.
        """
        hook_path = _get_hook_path(hook_name, self.project_path)
        return hook.execute_hook(hook_path, self, **kwargs)

        

##########################################################################################
# module methods

def tank_from_path(path):
    """
    Create a Tank API instance based on a path inside a project.
    """
    project_path = root.get_primary_root(path)
    return Tank(project_path)

def _get_hook_path(hook_name, project_path):
    hook_folder = constants.get_core_hooks_folder(project_path)
    file_name = "%s.py" % hook_name
    # use project level hook if available
    hook_path = os.path.join(hook_folder, file_name)
    if not os.path.exists(hook_path):
        # construct install hooks path if no project(override) hook
        hooks_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "hooks"))
        hook_path = os.path.join(hooks_path, file_name)
    return hook_path
