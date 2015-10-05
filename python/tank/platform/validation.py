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
App configuration and schema validation.

"""
import os
import re
import sys

from . import constants
from ..errors import TankError
from ..template import TemplateString

def validate_schema(app_or_engine_display_name, schema):
    """
    Validates the schema definition (info.yml) of an app or engine.
    
    Will raise a TankError if validation fails, will return None
    if validation suceeds.
    """
    v = _SchemaValidator(app_or_engine_display_name, schema)
    v.validate()

def validate_settings(app_or_engine_display_name, tank_api, context, schema, settings):
    """
    Validates the settings of an app or engine against its
    schema definition (info.yml).
    
    Will raise a TankError if validation fails, will return None
    if validation succeeds.
    """
    v = _SettingsValidator(app_or_engine_display_name, tank_api, schema, context)
    v.validate(settings)
    
    
def validate_context(descriptor, context):
    """
    Validates a bundle to check that the given context
    will work with it. Raises a tankerror if not.
    """
    # check that the context contains all the info that the app needs
    context_check_ok = True
    req_ctx = descriptor.get_required_context()
    for req_ctx_item in req_ctx:
        context_check_ok &= (req_ctx_item == "user" and context.user is None)
        context_check_ok &= (req_ctx_item == "entity" and context.entity is None)
        context_check_ok &= (req_ctx_item == "project" and context.project is None)
        context_check_ok &= (req_ctx_item == "step" and context.step is None)
        context_check_ok &= (req_ctx_item == "task" and context.task is None)
    if not context_check_ok:
        raise TankError("The item requires the following "
                        "items in the context: %s. The current context is missing one "
                        "or more of these items: %s" % (req_ctx, context) )
    
def validate_platform(descriptor):
    """
    Validates that the given bundle is compatible with the 
    current operating system
    """
    # make sure the current operating system platform is supported
    supported_platforms = descriptor.get_supported_platforms()
    if len(supported_platforms) > 0:
        # supported platforms defined in manifest
        # get a human friendly mapping of current platform: linux/mac/windows 
        nice_system_name = {"linux2": "linux", "darwin": "mac", "win32": "windows"}[sys.platform]
        if nice_system_name not in supported_platforms:
            raise TankError("The current operating system '%s' is not supported."
                            "Supported platforms are: %s" % (nice_system_name, supported_platforms))

    
def get_missing_frameworks(descriptor, environment):
    """
    Returns a list of framework descriptors by the given descriptor required but not present 
    in the given environment.
    
    returns items on the following form:
    [{'version': 'v0.1.0', 'name': 'tk-framework-widget'}]
    
    :returns: list dictionaries, each with a name and a version key.
    """
    required_frameworks = descriptor.get_required_frameworks()
    current_framework_instances = environment.get_frameworks()
    
    if len(required_frameworks) == 0:
        return []

    missing_fws = []
    for fw in required_frameworks:
        # the required_frameworks structure in the info.yml
        # is a list of dicts, each dict having a name and a version key
        name = fw.get("name")
        version = fw.get("version")

        # find it by naming convention based on the instance name        
        desired_fw_instance = "%s_%s" % (name, version)

        if desired_fw_instance not in current_framework_instances:
            missing_fws.append(fw)

    return missing_fws

    
    
def validate_and_return_frameworks(descriptor, environment):
    """
    Validates the frameworks needed for an given descriptor.
    
    Returns a list of the instance names for each of the frameworks needed by the input descriptor.
    
    Will raise exceptions if there are frameworks missing from the environment. 
    """
    required_frameworks = descriptor.get_required_frameworks()
    
    if len(required_frameworks) == 0:
        return []

    # make dictionary of all frameworks declared in the environment.
    # key is the instance name in the environment
    # value is the descriptor object
    fw_descriptors = {}
    fw_instances = environment.get_frameworks()
    for x in fw_instances:
        fw_descriptors[x] = environment.get_framework_descriptor(x)
    
    # check that each framework required by this app is defined in the environment
    required_fw_instance_names = []
    for fw in required_frameworks:
        # the required_frameworks structure in the info.yml
        # is a list of dicts, each dict having a name and a version key
        name = fw.get("name")
        version = fw.get("version")
        found = False

        # find it by naming convention based on the instance name
        # this is to support the new auto-updating syntax. The info.yml
        # manifest for an app can have two different syntaxes declared:
        #
        # (old) - {"name": "tk-framework-shotgunutils", "version": "v2.1.1"}
        # (new) - {"name": "tk-framework-qtwidgets", "version": "v1.x.x"}
        # 
        # The new syntax requires a floating version number, meaning that 
        # the framework instance defined in the environment needs to be on the form  
        # 
        # frameworks:
        #   tk-framework-qtwidgets_v1.x.x:
        #     location: {name: tk-framework-qtwidgets, type: app_store, version: v1.3.34}
        #
        desired_fw_instance = "%s_%s" % (name, version)
        for fw_instance_name in fw_instances:
            if fw_instance_name == desired_fw_instance:
                found = True
                required_fw_instance_names.append(fw_instance_name)
                break
        
        # backwards compatibility pass - prior to the new syntax, we also technically accepted 
        # (however never used as part of toolkit itself) a different convention where the instance
        # name was independent from the actual framework name. 
        #
        # frameworks:
        #   some_totally_random_name:
        #     location: {name: tk-framework-qtwidgets, type: app_store, version: v1.3.34}
        #
        # note: this old form does not handle the 1.x.x syntax, only exact version numbers
        for (fw_instance_name, fw_instance) in fw_descriptors.items():
            if fw_instance.get_version() == version and fw_instance.get_system_name() == name:
                found = True
                required_fw_instance_names.append(fw_instance_name)
                break
        
        # display nicely formatted error message
        if not found:
            msg =  "The framework instance %s required by %s " % (desired_fw_instance, descriptor)
            msg += "can not be found in environment %s. \n" % str(environment)
            if len(fw_descriptors) == 0:
                msg += "No frameworks are currently installed!"
            else:
                msg += "The currently installed frameworks are: \n"
                fw_strings = []
                for x in fw_descriptors:
                    fw_strings.append("Name: '%s', Version: '%s'" % (fw_descriptors[x].get_system_name(), 
                                                                     fw_descriptors[x].get_version()))
                msg += "\n".join(fw_strings)
                
            raise TankError(msg) 
        
    return required_fw_instance_names
                

def validate_single_setting(app_or_engine_display_name, tank_api, schema, setting_name, setting_value):
    """
    Validates a single setting for an app or engine against its 
    schema definition (info.yml).
    
    Will raise a TankError if validation fails, will return None if validation succeeds.
    
    Note that this method does not require a context to be present in order to 
    perform the validation, however it will not be able to fully validate some 
    template types, since a full validaton would require a context.
    """
    v = _SettingsValidator(app_or_engine_display_name, tank_api, schema)
    v.validate_setting(setting_name, setting_value)
    
def convert_string_to_type(string_value, schema_type):
    """
    Attempts to convert a string value into a schema type.
    This method may evaluate code in order to do the conversion
    and is therefore not safe!
    """
    # assume that the value is a string unless otherwise stated.
    
    if schema_type == "float":
        evaluated_value = float(string_value)
    
    elif schema_type == "int":
        evaluated_value = int(string_value)
    
    elif schema_type == "bool":
        if string_value == "False":
            evaluated_value = False
        elif string_value == "True":
            evaluated_value = True
        else:
            raise TankError("Invalid boolean value %s! Valid values are True and False" % string_value)
    
    elif schema_type == "list":
        evaluated_value = eval(string_value)
        
    elif schema_type == "dict":
        evaluated_value = eval(string_value)

    else:
        # assume string-like
        evaluated_value = string_value
        
    return evaluated_value
    
# Helper used by both schema and settings validators
def _validate_expected_data_type(expected_type, value):
    value_type_name = type(value).__name__

    expected_type_name = expected_type
    if expected_type in constants.TANK_SCHEMA_STRING_TYPES:
        expected_type_name = "str"
    else:
        expected_type_name = expected_type

    return expected_type_name == value_type_name
        
class _SchemaValidator:

    def __init__(self, display_name, schema):
        self._display_name = display_name
        self._schema = schema
    
    def validate(self):
        for settings_key in self._schema:
            value_schema = self._schema.get(settings_key, {})
            self.__validate_schema_value(settings_key, value_schema)
            
    def __validate_schema_type(self, settings_key, data_type):
        if not data_type:
            raise TankError("Missing type in schema '%s' for '%s'!" % (settings_key, self._display_name))

        if not data_type in constants.TANK_SCHEMA_VALID_TYPES:
            params = (data_type, settings_key, self._display_name)
            raise TankError("Invalid type '%s' in schema '%s' for '%s'!" % params)

    def __validate_schema_value(self, settings_key, schema):
        data_type = schema.get("type")
        self.__validate_schema_type(settings_key, data_type)

        if "default_value" in schema:
            # validate the default value:
            default_value = schema["default_value"]

            # handle template setting with default_value == null            
            if data_type == 'template' and default_value is None and schema.get('allows_empty', False):
                # no more validation required
                return

            if not _validate_expected_data_type(data_type, default_value):
                params = (settings_key, 
                          self._display_name, 
                          type(default_value).__name__, data_type)
                err_msg = "Invalid type for default value in schema '%s' for '%s' - found '%s', expected '%s'" % params
                raise TankError(err_msg)

        if data_type == "list":
            self.__validate_schema_list(settings_key, schema)
        elif data_type == "dict":
            self.__validate_schema_dict(settings_key, schema)
        elif data_type == "template":
            self.__validate_schema_template(settings_key, schema)

    def __validate_schema_list(self, settings_key, schema):
        # Check that the schema contains "values"
        if not "values" in schema or type(schema["values"]) != dict:
            params = (settings_key, self._display_name)
            raise TankError("Missing or invalid 'values' dict in schema '%s' for '%s'!" % params)

        # If there's an "allows_empty" key, it should be a bool
        if "allows_empty" in schema and type(schema["allows_empty"]) != bool:
            params = (settings_key, self._display_name)
            raise TankError("Invalid 'allows_empty' bool in schema '%s' for '%s'!" % params)

        self.__validate_schema_value(settings_key, schema["values"])

    def __validate_schema_dict(self, settings_key, schema):
        # Check that if the schema contains "items" then it must be a dict
        if "items" in schema and type(schema["items"]) != dict:
            params = (settings_key, self._display_name)
            raise TankError("Invalid 'items' dict in schema '%s' for '%s'!" % params)

        for key,value_schema in schema.get("items",{}).items():
            # Check that the value is a dict, and validate it...
            if type(value_schema) != dict:
                params = (key, settings_key, self._display_name)
                raise TankError("Invalid '%s' dict in schema '%s' for '%s'" % params)

            self.__validate_schema_value(settings_key, value_schema)

    def __validate_schema_template(self, settings_key, schema):
        
        # new style template def: if there is a fields key, it should be a str
        if "fields" in schema and type(schema["fields"]) != str:
            params = (settings_key, self._display_name)
            raise TankError("Invalid 'fields' string in schema '%s' for '%s'!" % params)
        
        # old-style - if there's a required_fields key, it should contain a list of strs.
        if "required_fields" in schema and type(schema["required_fields"]) != list:
            params = (settings_key, self._display_name)
            raise TankError("Invalid 'required_fields' list in schema '%s' for '%s'!" % params)

        for field in schema.get("required_fields",[]):
            if type(field) != str:
                params = (field, settings_key, self._display_name)
                raise TankError("Invalid 'required_fields' value '%s' in schema '%s' for '%s'!" % params)

        # old-style - if there's an optional_fields key, it should contain a list of strs or be "*"
        if "optional_fields" in schema and type(schema["optional_fields"]) == list:
            for field in schema.get("optional_fields",[]):
                if type(field) != str:
                    params = (field, settings_key, self._display_name)
                    raise TankError("Invalid 'optional_fields' value '%s' in schema '%s' for '%s'!" % params)
        elif "optional_fields" in schema and schema["optional_fields"] != "*":
            params = (settings_key, self._display_name)
            raise TankError("Invalid 'optional_fields' list in schema '%s' for '%s'!" % params)

        # If there's an "allows_empty" key, it should be a bool
        if "allows_empty" in schema and type(schema["allows_empty"]) != bool:
            params = (settings_key, self._display_name)
            raise TankError("Invalid 'allows_empty' bool in schema '%s' for '%s'!" % params)

class _SettingsValidator:
    def __init__(self, display_name, tank_api, schema, context=None):
        # note! if context is None, context-specific validation will be skipped.
        self._display_name = display_name
        self._tank_api = tank_api
        self._context = context
        self._schema = schema
        
    def validate(self, settings):
        # first sanity check that the schema is correct
        validate_schema(self._display_name, self._schema)
        
        # Ensure that all required keys are in the settings and that the
        # values are appropriate.
        for settings_key in self._schema:
            value_schema = self._schema.get(settings_key, {})
            
            # make sure the required key exists in the environment settings
            if settings_key not in settings:
                raise TankError("Missing required key '%s' in settings!" % settings_key)
            
            self.__validate_settings_value(settings_key, value_schema, settings[settings_key])
    
    def validate_setting(self, setting_name, setting_value):
        # first sanity check that the schema is correct
        validate_schema(self._display_name, self._schema)
        
        # make sure the required key exists in the settings
        value_schema = self._schema.get(setting_name, {})
        self.__validate_settings_value(setting_name, value_schema, setting_value)
        
        
    def __validate_settings_value(self, settings_key, schema, value):
        data_type = schema.get("type")

        # functor values which refer to a hook are never validated
        if type(value) == str and value.startswith("hook:"):
            return

        # shotgun filters can be a variety of formats so assume it is
        # valid and don't do any further validation:
        if data_type == 'shotgun_filter':
            return

        # For templates, if the value is None and it is allowed to be so,
        # validation can be skipped otherwise type validation would fail.
        if data_type == 'template' and value is None and schema.get('allows_empty', False):
            return

        # Check that the value is of a compatible Python type
        if not _validate_expected_data_type(data_type, value):
            params = (settings_key, self._display_name, type(value).__name__, data_type)
            err_msg = "Invalid type for value in setting '%s' for '%s' - found '%s', expected '%s'" % params
            raise TankError(err_msg)

        # Now do type-specific validation where possible...
        if data_type == "list":
            self.__validate_settings_list(settings_key, schema, value)
        elif data_type == "dict":
            self.__validate_settings_dict(settings_key, schema, value)
        elif data_type == "template":
            self.__validate_settings_template(settings_key, schema, value)
        elif data_type == "hook":
            self.__validate_settings_hook(settings_key, schema, value)
        elif data_type == "config_path":
            self.__validate_settings_config_path(settings_key, schema, value)


    def __validate_settings_list(self, settings_key, schema, value):
        value_schema = schema["values"]

        # By default all lists should have at least one item in that. Use allows_empty = True in the schema
        # to override this behaviour.
        allows_empty = False
        if "allows_empty" in schema:
            allows_empty = schema["allows_empty"]

        if not allows_empty and not value:
            err_msg = "The list in setting '%s' for '%s' can not be empty!" % (settings_key, self._display_name)
            raise TankError(err_msg)

        # Validate each list item against the schema in "values"
        for v in value:
            self.__validate_settings_value(settings_key, value_schema, v)

    def __validate_settings_dict(self, settings_key, schema, value):
        items = schema.get("items", {})
        for (key, value_schema) in items.items():            
            # Check for required keys
            if not key in value:
                params = (key, settings_key, self._display_name)
                raise TankError("Missing required key '%s' in setting '%s' for '%s'" % params)

            # Validate the values
            self.__validate_settings_value(settings_key, value_schema, value[key])

    def __validate_settings_template(self, settings_key, schema, template_name):
        
        # look it up in the master file
        cur_template = self._tank_api.templates.get(template_name) 
        if cur_template is None:
            # this was not found in the master config!
            raise TankError("The Template '%s' referred to by the setting '%s' does "
                            "not exist in the master template config file!" % (template_name, settings_key))


        if "fields" in schema:
            
            #################################################################################
            # NEW SCHOOL VALIDATION USING fields: context, foo, bar, [baz]
            #
            
            problems = self.__validate_new_style_template(cur_template, str(schema.get("fields")) )
            
            if len(problems) > 0:
                msg = ("%s: The Template '%s' referred to by the setting '%s' "
                       "does not validate. The following problems were "
                       "reported: " % (self._display_name, template_name, settings_key))
                for p in problems:
                    msg += "%s " % p
                
                raise TankError(msg)

        
        else:
            
            #################################################################################
            # OLD SCHOOL VALIDATION USING required_fields, optional_fields etc.
    
            if isinstance(cur_template, TemplateString):
                # Don't validate template strings
                return
    
            # Check fields 
            required_fields = set(schema.get("required_fields", []))
            # All template fields
            template_fields = set(cur_template.keys)
            # Template field without default values
            no_default_fields = set(cur_template.missing_keys({}, skip_defaults=True))
            optional_fields = schema.get("optional_fields", [])
    
            # check required fields exist in template
            missing_fields = required_fields - template_fields
            if missing_fields:
                raise TankError("The Template '%s' referred to by the setting '%s' does "
                                "not contain required fields '%s'!" % (template_name, settings_key, list(missing_fields)))
    
    
            # If optional_fields is "*" then we're done. If optional_fields is a list, then validate 
            # that all keys in the template are satisfied by a required, optional or context field.
            
            # note - only perform this context based valiation if context is not None.
            # this means that it is possible to run a partial (yet extensive) validation 
            # without having access to the context.
            #
            # NOTE!!!!! This special validate_context flag checked below is something that is
            # only used by the unit tests...
            #
            if self._context:        
                if optional_fields != "*" and schema.get("validate_context", True):
                    optional_fields = set(optional_fields)
                    
                    # collect all fields that will be covered by the context object. 
                    context_fields = set( self._context.as_template_fields(cur_template).keys() )
                    
                    # check template fields (keys) not in required are available through context
                    missing_fields = ((no_default_fields - required_fields) - optional_fields) - context_fields
                    if missing_fields:
                        raise TankError(
                            "Context %s can not determine value for fields %s needed by template %s" % \
                            (self._context, list(missing_fields), cur_template)
                        )

    def __validate_settings_hook(self, settings_key, schema, hook_name):
        """
        Validate that the value for a setting of type hook corresponds to a file in the hooks
        directory.
        """
        
        hooks_folder = self._tank_api.pipeline_configuration.get_hooks_location()
        
        # if setting is default, assume everything is fine
        if hook_name == constants.TANK_BUNDLE_DEFAULT_HOOK_SETTING:
            # assume that each app contains its correct hooks
            return
        
        elif hook_name.startswith("{self}"):
            # assume that each app contains its correct hooks
            return
        
        elif hook_name.startswith("{config}"):
            # config hook 
            path = hook_name.replace("{config}", hooks_folder)
            hook_path = path.replace("/", os.path.sep)
        
        elif hook_name.startswith("{$") and "}" in hook_name:
            # environment variable: {$HOOK_PATH}/path/to/foo.py
            # lazy (runtime) validation for this - it may be beneficial
            # not to actually set the environment variable until later
            # in the life cycle of the engine 
            return
        
        elif hook_name.startswith("{") and "}" in hook_name:
            # referencing other instances of items
            # this cannot be easily validated at this point since
            # no well defined runtime state exists at the time of validation
            return

        else:
            # our standard case
            hook_path = os.path.join(hooks_folder, "%s.py" % hook_name)

        if not os.path.exists(hook_path):
            msg = ("Invalid configuration setting '%s' for %s: "
                   "The specified hook file '%s' does not exist." % (settings_key, 
                                                                     self._display_name,
                                                                     hook_path) ) 
            raise TankError(msg)
            

    def __validate_settings_config_path(self, settings_key, schema, config_value):
        """
        Validate that the value for a setting of type config_path corresponds to a file in the 
        config folder somewhere
        """        
        if config_value.startswith("/"):
            msg = ("Invalid configuration setting '%s' for %s: "
                   "Config value '%s' starts with a / which is not valid." % (settings_key, 
                                                                              self._display_name,
                                                                              config_value) ) 
            raise TankError(msg)
        
        config_folder = self._tank_api.pipeline_configuration.get_config_location()
        adjusted_value = config_value.replace("/", os.path.sep)
        full_path = os.path.join(config_folder, adjusted_value)

        if not os.path.exists(full_path):
            msg = ("Invalid configuration setting '%s' for %s: "
                   "The specified resource '%s' does not exist." % (settings_key, 
                                                                    self._display_name,
                                                                    full_path) ) 
            raise TankError(msg)

            
    def __validate_new_style_template(self, cur_template, fields_str):
        
        #################################################################################
        # NEW SCHOOL VALIDATION USING fields: context, foo, bar, [baz]
        #
        # format:
        # - context: means that the context will be included
        # - value: the value must exist in the template
        # - [value]: the value can exist in the template and that's okay
        # - * any number of additional fields can exist in the template
        #
        # Examples:
        # context, name, version
        # context, name, version, [width], [height]
        # name, *
        # context, *
        
        # get all values in list
        field_chunks = fields_str.split(",")
        # chop whitespace
        field_chunks = [ x.strip() for x in field_chunks ]
        
        # process
        mandatory = set()
        optional = set()
        star = False
        include_context = False
        for x in field_chunks:
            if x.lower() == "context":
                include_context = True
            elif x == "*":
                star = True
            elif x.startswith("[") and x.endswith("]"):
                optional.add( x[1:-1] )
            else:
                mandatory.add(x)
        
        # validate
        problems = []
        
        # First pass: Ensure all mandatory fields are present in template.
        all_fields = set(cur_template.keys)        
        for m in mandatory:
            if m not in all_fields:
                problems.append("The mandatory field '%s' is missing" % m)

        if len(problems) > 0:
            # one or more mandatory issues. No point checking further
            return problems
        
        if star == True:
            # means an open ended number of fields can be used.
            # no need to do more validation
            return problems
        
        if self._context is None:
            # we don't have the context (we are outside app runtime mode)
            # and cannot do any further validation
            return problems
        
        # Second pass: There are a fixed number of fields that we need to populate so
        # make sure we have populated exactly those fields
        fields_needing_values = set(cur_template.missing_keys({}, skip_defaults=True))
        remaining_fields = fields_needing_values - mandatory
                        
        if include_context:
            # gather all the fields that will be covered by the context object
            context_fields = set( self._context.as_template_fields(cur_template).keys() )
            remaining_fields = remaining_fields - context_fields
            
            for x in remaining_fields:
                if x not in optional:
                    # we have a field that is in the template but which is not 
                    # covered, either in the context nor in the schema fields
                    required_and_optional_str = ", ".join(mandatory | optional)
                    context_fields_str = ", ".join(context_fields)
                    
                    problems.append("The field '%s' is part of the template but %s does not "
                                    "know how to assign a value to it when calculating paths. "
                                    "The code inside %s will populate the following fields: %s. "
                                    "The current context (%s) will populate the following fields: "
                                    "%s." % (x, 
                                             self._display_name, 
                                             self._display_name, 
                                             required_and_optional_str, 
                                             str(self._context),
                                             context_fields_str))
                    
        else:
            # the context is not taken into account.
            for x in remaining_fields:
                if x not in optional:
                    # we have a field that is in the template but which is not 
                    # covered by mandatory or optional
                    required_and_optional_str = ", ".join(mandatory | optional)
                    
                    problems.append("The field '%s' is part of the template but %s does not "
                                    "know how to assign a value to it when calculating paths. "
                                    "The code inside %s will populate the following fields: "
                                    "%s." % (x, 
                                             self._display_name, 
                                             self._display_name, 
                                             required_and_optional_str))
                
        return problems
