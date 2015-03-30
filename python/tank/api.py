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
Classes for the main Sgtk API.

"""
import os
import glob
import threading

from tank_vendor import yaml

from . import folder
from . import context
from .util import shotgun
from .errors import TankError
from .path_cache import PathCache
from .template import read_templates
from .platform import constants as platform_constants
from . import pipelineconfig
from . import pipelineconfig_utils
from . import pipelineconfig_factory

class Tank(object):
    """
    Object with presenting interface to tank.
    """
    def __init__(self, project_path):
        """
        :param project_path: Any path inside one of the data locations
        """
        
        self.__threadlocal_storage = threading.local()

        # special stuff to make sure we maintain backwards compatibility in the constructor
        # if the 'project_path' parameter contains a pipeline config object,
        # just use this straight away. If the param contains a string, assume
        # this is a path and try to construct a pc from the path

        if isinstance(project_path, pipelineconfig.PipelineConfiguration):
            # this is actually a pc object
            self.__pipeline_config = project_path
        else:
            self.__pipeline_config = pipelineconfig_factory.from_path(project_path)
            
        try:
            self.templates = read_templates(self.__pipeline_config)
        except TankError, e:
            raise TankError("Could not read templates configuration: %s" % e)

        # execute a tank_init hook for developers to use.
        self.execute_core_hook(platform_constants.TANK_INIT_HOOK_NAME)

    def __repr__(self):
        return "<Sgtk Core %s@0x%08x Config %s>" % (self.version, id(self), self.__pipeline_config.get_path())

    def __str__(self):
        return "Sgtk Core %s, config %s" % (self.version, self.__pipeline_config.get_path())

    ################################################################################################
    # internal API

    @property
    def pipeline_configuration(self):
        """
        Internal Use Only - We provide no guarantees that this method
        will be backwards compatible. The returned objects are also
        subject to change and are not part of the public Sgtk API.
        """
        return self.__pipeline_config

    def reload_templates(self):
        """
        Reloads the template definitions. If reload fails, the previous 
        template definitions will be preserved.
        
        Internal Use Only - We provide no guarantees that this method
        will be backwards compatible.        
        """
        try:
            self.templates = read_templates(self.__pipeline_config)
        except TankError, e:
            raise TankError("Templates could not be reloaded: %s" % e)

    def execute_core_hook(self, hook_name, **kwargs):
        """
        Executes a core level hook, passing it any keyword arguments supplied.

        Internal Use Only - We provide no guarantees that this method
        will be backwards compatible.
        
        :param hook_name: Name of hook to execute.
        :param **kwargs:  Additional named parameters will be passed to the hook.
        :returns:         Return value of the hook.
        """
        return self.pipeline_configuration.execute_core_hook_internal(hook_name, parent=self, **kwargs)

    # compatibility alias - previously the name of this *internal method* was named execute_hook.
    # in order to try to avoid breaking client code that uses these *internal methods*, let's
    # provide a backwards compatibility alias.
    execute_hook = execute_core_hook

    def execute_core_hook_method(self, hook_name, method_name, **kwargs):
        """
        Executes a specific method on a core level hook, 
        passing it any keyword arguments supplied.

        Internal Use Only - We provide no guarantees that this method
        will be backwards compatible.
        
        :param hook_name:   Name of hook to execute.
        :param method_name: Name of method to execute.
        :param **kwargs:    Additional named parameters will be passed to the hook.
        :returns:           Return value of the hook.
        """
        return self.pipeline_configuration.execute_core_hook_method_internal(hook_name, 
                                                                             method_name, 
                                                                             parent=self, 
                                                                             **kwargs)

    ################################################################################################
    # properties

    @property
    def project_path(self):
        """
        Path to the primary root directory for a project.
        If no primary root directory exists, an exception is raised.
        """
        return self.__pipeline_config.get_primary_data_root()

    @property
    def roots(self):
        """
        Returns a dictionary of root names to root paths. 
        In the case of a single project root, there will only be one entry. 
        """
        return self.__pipeline_config.get_data_roots()

    @property
    def shotgun(self):
        """
        Lazily create a Shotgun API handle.
        This Shotgun API is threadlocal, meaning that each thread will get
        a separate instance of the Shotgun API. This is in order to prevent
        concurrency issues and add a layer of basic protection around the 
        Shotgun API, which isn't threadsafe.
        """
        
        sg = getattr(self.__threadlocal_storage, "sg", None)
        
        if sg is None:
            sg = shotgun.create_sg_connection()
            self.__threadlocal_storage.sg = sg

        # pass on information to the user agent manager which core version is returning
        # this sg handle. This information will be passed to the web server logs
        # in the shotgun data centre and makes it easy to track which core versions
        # are being used by clients
        try:
            sg.tk_user_agent_handler.set_current_core(self.version)
        except AttributeError:
            # looks like this sg instance for some reason does not have a
            # tk user agent handler associated.
            pass

        return sg

    @property
    def version(self):
        """
        The version of the tank Core API (e.g. v0.2.3)

        :returns: string representing the version
        """
        return pipelineconfig_utils.get_currently_running_api_version()

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
        except:
            data = None

        return data

    @property
    def configuration_name(self):
        """
        Returns the name of the currently running pipeline configuration
        
        :returns: pipeline configuration name as string, e.g. 'primary'
        """
        return self.__pipeline_config.get_name()

    ##########################################################################################
    # public methods

    def list_commands(self):
        """
        Lists the system commands registered with the system.
        
        This method will return all system commands which 
        are available in the context of a project configuration will be returned.
        This includes for example commands for configuration management, 
        anything app or engine related and validation and overview functionality.
        In addition to these commands, the global commands such as project setup
        and core API check commands will also be returned.
    
        :returns: list of command names
        """
        # avoid cyclic dependencies
        from .deploy import tank_command
        return tank_command.list_commands(self) 

    def get_command(self, command_name):
        """
        Returns an instance of a command object that can be used to execute a command.
        
        Once you have retrieved the command instance, you can perform introspection to 
        check for example the required parameters for the command, name, description etc.
        Lastly, you can execute the command by running the execute() method.
        
        In order to get a list of the available commands, use the list_commands() method.
                
        :param command_name: Name of command to execute. Get a list of all available commands
                             using the tk.list_commands() method.
        
        :returns: SgtkSystemCommand object instance
        """
        # avoid cyclic dependencies
        from .deploy import tank_command
        return tank_command.get_command(command_name, self) 
        
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
            msg = "%d templates are matching the path '%s'.\n" % (len(matched), path)
            msg += "The overlapping templates are:\n"
            msg += "\n".join([str(x) for x in matched])
            raise TankError(msg)

    def paths_from_template(self, template, fields, skip_keys=None, skip_missing_optional_keys=False):
        """
        Finds paths that match a template using field values passed.

        By omitting fields, you are effectively adding wild cards to the search.
        So if a template requires Shot, Sequence, Name and Version, and you
        omit the version fields from the fields dictionary, the method
        will return paths to all the different versions you can find.
        
        If an optional key is specified in skip_keys then all paths that
        contain a match for that key as well as paths that don't contain
        a value for the key will be returned.
        
        If skip_missing_optional_keys is True then all optional keys not
        included in the fields dictionary will be considered as skip keys.

        For more information and examples, see the API documentation.

        :param template: Template against whom to match.
        :type  template: Tank.Template instance.
        :param fields: Fields and values to use.
        :type  fields: Dictionary.
        :param skip_keys: Keys whose values should be ignored from the fields parameter.
        :type  skip_keys: List of key names.
        :param skip_missing_optional_keys: Specify if optional keys should be skipped if they 
                                        aren't found in the fields collection
        :type skip_missing_optional_keys: Boolean
        
        :returns: Matching file paths
        :rtype: List of strings.
        """
        skip_keys = skip_keys or []
        if isinstance(skip_keys, basestring):
            skip_keys = [skip_keys]
        
        # construct local fields dictionary that doesn't include any skip keys:
        local_fields = dict((field, value) for field, value in fields.iteritems() if field not in skip_keys)
        
        # we always want to automatically skip 'required' keys that weren't
        # specified so add wildcards for them to the local fields
        for key in template.missing_keys(local_fields):
            if key not in skip_keys:
                skip_keys.append(key)
            local_fields[key] = "*"
            
        # iterate for each set of keys in the template:
        found_files = set()
        globs_searched = set()
        for keys in template._keys:
            # create fields and skip keys with those that 
            # are relevant for this key set:
            current_local_fields = local_fields.copy()
            current_skip_keys = []
            for key in skip_keys:
                if key in keys:
                    current_skip_keys.append(key)
                    current_local_fields[key] = "*"
            
            # find remaining missing keys - these will all be optional keys:
            missing_optional_keys = template._missing_keys(current_local_fields, keys, False)
            if missing_optional_keys:
                if skip_missing_optional_keys:
                    # Add wildcard for each optional key missing from the input fields
                    for missing_key in missing_optional_keys:
                        current_local_fields[missing_key] = "*"
                        current_skip_keys.append(missing_key)
                else:
                    # if there are missing fields then we won't be able to
                    # form a valid path from them so skip this key set
                    continue
            
            # Apply the fields to build the glob string to search with:
            glob_str = template._apply_fields(current_local_fields, ignore_types=current_skip_keys)
            if glob_str in globs_searched:
                # it's possible that multiple key sets return the same search
                # string depending on the fields and skip-keys passed in
                continue
            globs_searched.add(glob_str)
            
            # Find all files which are valid for this key set
            found_files.update([found_file for found_file in glob.iglob(glob_str) if template.validate(found_file)])
                    
        return list(found_files) 


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
        path_cache = PathCache(self)
        paths = path_cache.get_paths(entity_type, entity_id, primary_only=True)
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
        path_cache = PathCache(self)
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

    def synchronize_filesystem_structure(self, full_sync=False):
        """
        Ensures that the filesystem structure on this machine is in sync
        with Shotgun. This synchronization is implicitly carried out as part of the 
        normal folder creation process, however sometimes it is useful to
        be able to call it on its own.
        
        Note that this method is equivalent to the synchronize_folders tank command.
        
        :param full_sync: If set to true, a complete sync will be carried out.
                          By default, the sync is incremental.
        :returns: List of folders that were synchronized.
        """
        return folder.synchronize_folders(self, full_sync)

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
                       Folders marked as deferred will be processed. Note that this is 
                       just a string following a convention - typically, we recommend that
                       the engine name (e.g. 'tk-nuke') is passed in, however all this metod
                       is doing is to relay this string on to the folder creation (schema)
                       setup so that it is compared with any deferred entries there. In case
                       of a match, the folder creation will recurse down into the subtree 
                       marked as deferred.
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
                       Folders marked as deferred will be processed. Note that this is 
                       just a string following a convention - typically, we recommend that
                       the engine name (e.g. 'tk-nuke') is passed in, however all this metod
                       is doing is to relay this string on to the folder creation (schema)
                       setup so that it is compared with any deferred entries there. In case
                       of a match, the folder creation will recurse down into the subtree 
                       marked as deferred.
        :type engine: String.

        :returns: List of items processed.
        """
        folders = folder.process_filesystem_structure(self,
                                                      entity_type,
                                                      entity_id,
                                                      True,
                                                      engine)
        return folders


##########################################################################################
# module methods

def tank_from_path(path):
    """
    Create an Sgtk API instance based on a path inside a project.
    """
    return Tank(path)

def tank_from_entity(entity_type, entity_id):
    """
    Create a Sgtk API instance based on a path inside a project.
    """
    pc = pipelineconfig_factory.from_entity(entity_type, entity_id)
    return Tank(pc)


_current_user = None


def set_current_user(user):
    """
    Sets the current Shotgun user.
    :params user: a shotgun_authentication.ShotgunUser derived object. Can be None to clear the
                  current user.
    """
    global _current_user
    _current_user = user


def get_current_user():
    """
    Returns the current Shotgun user.
    :returns: A shotgun_authentication.ShotgunUser derived object if set, None otherwise.
    """
    global _current_user
    return _current_user

##########################################################################################
# sgtk API aliases

Sgtk = Tank
sgtk_from_path = tank_from_path
sgtk_from_entity = tank_from_entity
