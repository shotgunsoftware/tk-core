"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

App configuration and schema validation.

"""
import os
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
    
    if len(required_frameworks) == 0:
        return []

    # get all framework descriptors defined in the environment
    # put a tuple with (name, version) into a list 
    fws_in_env = [] 
    for fw_instance_str in environment.get_frameworks():
        descriptor = environment.get_framework_descriptor(fw_instance_str)
        d_identifier = (descriptor.get_system_name(), descriptor.get_version())
        fws_in_env.append( d_identifier )

    # now check which frameworks are missing
    missing_fws = []
    for fwd in required_frameworks:
        identifier = (fwd["name"], fwd["version"])
        if identifier not in fws_in_env:
            # this descriptor is not available in the environment
            missing_fws.append(fwd)

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
    for x in environment.get_frameworks():
        fw_descriptors[x] = environment.get_framework_descriptor(x)
    
    # check that each framework required by this app is defined in the environment
    required_fw_instance_names = []
    for fw in required_frameworks:
        # the required_frameworks structure in the info.yml
        # is a list of dicts, each dict having a name and a version key
        name = fw.get("name")
        version = fw.get("version")
        found = False
        for d in fw_descriptors:
            if fw_descriptors[d].get_version() == version and fw_descriptors[d].get_system_name() == name:
                found = True
                required_fw_instance_names.append(d)
                break
        if not found:
            msg =  "The framework %s %s required by %s " % (name, version, descriptor)
            msg += "can not be found in environment %s. \n" % str(environment)
            if len(fw_descriptors) == 0:
                msg += "No frameworks are currently installed! \n"
            else:
                msg += "The currently installed frameworks are: \n"
                for x in fw_descriptors:
                    msg += "Name: '%s', Version: '%s'\n" % (fw_descriptors[x].get_system_name(), 
                                                            fw_descriptors[x].get_version())
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

        if "default_value" in schema and not _validate_expected_data_type(data_type, schema["default_value"]):
            params = (settings_key, 
                      self._display_name, 
                      type(schema["default_value"]).__name__, data_type)
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
        # If there's a required_fields key, it should contain a list of strs.
        if "required_fields" in schema and type(schema["required_fields"]) != list:
            params = (settings_key, self._display_name)
            raise TankError("Invalid 'required_fields' list in schema '%s' for '%s'!" % params)

        for field in schema.get("required_fields",[]):
            if type(field) != str:
                params = (field, settings_key, self._display_name)
                raise TankError("Invalid 'required_fields' value '%s' in schema '%s' for '%s'!" % params)

        # If there's an optional_fields key, it should contain a list of strs or be "*"
        if "optional_fields" in schema and type(schema["optional_fields"]) == list:
            for field in schema.get("optional_fields",[]):
                if type(field) != str:
                    params = (field, settings_key, self._display_name)
                    raise TankError("Invalid 'optional_fields' value '%s' in schema '%s' for '%s'!" % params)
        elif "optional_fields" in schema and schema["optional_fields"] != "*":
            params = (settings_key, self._display_name)
            raise TankError("Invalid 'optional_fields' list in schema '%s' for '%s'!" % params)

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
            raise TankError("The Tank Template '%s' referred to by the setting '%s' does "
                            "not exist in the master template config file!" % (template_name, settings_key))

        if isinstance(cur_template, TemplateString):
            # Don't validate template strings
            # TODO add validate_with functionality
            return

        # Check fields 
        required_fields = set(schema.get("required_fields", []))
        # All template fields
        template_fields = set(cur_template.keys)
        # Template field without default values
        no_default_fields = set(key_name for key_name, key in cur_template.keys.items() if key.default is None)
        optional_fields = schema.get("optional_fields", [])

        # check required fields exist in template
        missing_fields = required_fields - template_fields
        if missing_fields:
            raise TankError("The Tank Template '%s' referred to by the setting '%s' does "
                            "not contain required fields '%s'!" % (template_name, settings_key, list(missing_fields)))


        # If optional_fields is "*" then we're done. If optional_fields is a list, then validate 
        # that all keys in the template are satisfied by a required, optional or context field.
        
        # note - only perform this context based valiation if context is not None.
        # this means that it is possible to run a partial (yet extensive) validation 
        # without having access to the context.
        if self._context:        
            if optional_fields != "*" and schema.get("validate_context", True):
                optional_fields = set(optional_fields)
                context_fields = set()
                for field_name, value in self._context.as_template_fields(cur_template).items():
                    if value is not None:
                        context_fields.add(field_name)
    
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
        # if setting is default, assume everything is fine
        if hook_name == constants.TANK_BUNDLE_DEFAULT_HOOK_SETTING:
            return
        
        hooks_folder = constants.get_hooks_folder(self._tank_api.project_path)
        hook_path = os.path.join(hooks_folder, "%s.py" % hook_name)

        if not os.path.exists(hook_path):
            msg = ("Invalid configuration setting '%s' for %s: "
                   "The specified hook file '%s' does not exist." % (settings_key, 
                                                                     self._display_name,
                                                                     hook_path) ) 
            raise TankError(msg)
            
            

  
