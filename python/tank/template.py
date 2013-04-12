"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Management of file and directory templates.

"""

import os
import re

from tank_vendor import yaml

from . import constants
from . import templatekey
from .errors import TankError



class Template(object):
    """
    Object which manages the translation between paths and file templates
    """
    _key_name_regex = "[a-zA-Z_ 0-9]+"
    
    
    @classmethod
    def _keys_from_definition(cls, definition, template_name, keys):
        """Extracts Template Keys from a definition.

        :param definition: Template definition.
        :type  definition: String.
        :param template_name: Name of template.
        :type  template_name: String.
        :param keys: Mapping of key names to keys.
        :type keys: Dictionary.

        :returns: Mapping of key names to keys and collection of keys ordered as they appear in the definition.
        :rtype: List of Dictionaries, List of lists
        """
        names_keys = {}
        ordered_keys = []
        # regular expression to find key names
        regex = r"(?<={)%s(?=})" % cls._key_name_regex
        key_names = re.findall(regex, definition)
        for key_name in key_names:
            key = keys.get(key_name)
            if key is None:
                msg = "Template definition for template %s refers to key {%s}, which does not appear in supplied keys."
                raise TankError(msg % (template_name, key_name))
            else:
                if names_keys.get(key.name, key) != key:
                    # Different keys using same name
                    msg = ("Template definition for template %s uses two keys" +
                           " which use the name '%s'.")
                    raise TankError(msg % (template_name, key.name))
                names_keys[key.name] = key
                ordered_keys.append(key)
        return names_keys, ordered_keys
        
    def __init__(self, definition, keys, name=None):
        """
        :param definition: Template definition.
        :type definition: String.
        :param keys: Mapping of key names to keys
        :type keys: Dictionary 
        :param name: (Optional) name for this template.
        :type name: String.

        """
        self.name = name
        # version for __repr__
        self._repr_def = self._fix_key_names(definition, keys)

        variations = self._definition_variations(definition)
        # We want them most inclusive(longest) version first
        variations.sort(cmp=lambda x, y: cmp(len(x), len(y)), reverse=True)

        # get format keys and types
        self._keys = []
        self._ordered_keys = []
        for variation in variations:
            var_keys, ordered_keys = self._keys_from_definition(variation, name, keys)
            self._keys.append(var_keys)
            self._ordered_keys.append(ordered_keys)

        # substitute aliased key names
        self._definitions = []
        for variation in variations:
            self._definitions.append(self._fix_key_names(variation, keys))

        # get defintion ready for string substitution
        self._cleaned_definitions = []
        for definition in self._definitions:
            self._cleaned_definitions.append(self._clean_definition(definition))

        # string which will be prefixed to definition
        self._prefix = ''
        self._static_tokens = []

    def __repr__(self):
        class_name = self.__class__.__name__
        if self.name:
            return "<Tank %s %s: %s>" % (class_name, self.name, self._repr_def)
        else:
            return "<Tank %s %s>" % (class_name, self._repr_def)

    @property
    def definition(self):
        """
        Property to access Template definition.
        """
        # Use first definition as it should be most inclusive in case of variations
        return self._definitions[0]


    @property
    def keys(self):
        """
        Returns keys for this template.
        
        :returns: a dictionary of TemplateKey objects, keyed by TemplateKey name.
        :rtype: dictionary 
        """
        # First keys should be most inclusive
        return self._keys[0].copy()

    def is_optional(self, key_name):
        """
        Returns true if the given key name is optional for this template.
        
        Example: template: {Shot}[_{name}]
        is_optional("Shot") --> Returns False
        is_optional("name") --> Returns True
        """
        # minimum set of required keys for this template
        required_keys = self.missing_keys({})
        if key_name in required_keys:
            # this key is required
            return False
        else:
            return True

    def missing_keys(self, fields, skip_defaults=False):
        """
        Determines keys required for use of template which do not exist
        in a given fields.
        
        Example:
        
            >>> tk.templates["max_asset_work"].missing_keys({})
            ['Step', 'sg_asset_type', 'Asset', 'version', 'name']
        
        
        :param fields: fields to test
        :type fields: mapping (dictionary or other)
        :param skip_defaults: If true, do not treat keys with default values as missing.
        :type skip_defalts: Bool.
        
        :returns: Fields needed by template which are not in inputs keys or which have
                  values of None.
        :rtype: list
        """
        # find shortest keys dictionary
        keys = min(self._keys)
        return self._missing_keys(fields, keys, skip_defaults)

    def _missing_keys(self, fields, keys, skip_defaults):
        """
        Compares two dictionaries to determine keys in second missing in first.
        """
        if skip_defaults:
            required_keys = [key.name for key in keys.values() if key.default is None]
        else:
            required_keys = keys

        return [x for x in required_keys if (x not in fields) or  (fields[x] is None)]

    def apply_fields(self, fields):
        """
        Creates path using fields. Certain fields may be processed in special ways, for
        example Sequence fields, which can take a "FORMAT" string which will intelligently
        format a image sequence specifier based on the type of data is being handled.
        For more information about special cases, see the main documentation.

        :param fields: Mapping of keys to fields. Keys must match those in template 
                       definition.
        :type fields: Dictionary

        :returns: Path reflecting field values inserted into template definition.
        :rtype: String
        """
        return self._apply_fields(fields)

    def _apply_fields(self, fields, ignore_types=None):
        """
        Creates path using fields.

        :param fields: Mapping of keys to fields. Keys must match those in template 
                       definition.
        :type fields: Dictionary
        :param ignore_type: Keys for whom the defined type is ignored. This 
                            allows setting a Key whose type is int with a string value.
        :type  ignore_type: List of strings.

        :returns: Path reflecting field values inserted into template definition.
        :rtype: String
        """
        ignore_types = ignore_types or []

        # find largest key mapping without missing values
        keys = None
        # index of matching keys will be used to find cleaned_definition
        index = -1
        for index, cur_keys in enumerate(self._keys):
            missing_keys = self._missing_keys(fields, cur_keys, skip_defaults=True)
            if not missing_keys:
                keys = cur_keys
                break

        
        if keys is None:
            raise TankError("Tried to resolve a path from the template %s and a set "
                            "of input fields '%s' but the following required fields were missing "
                            "from the input: %s" % (self, fields, missing_keys))

        # Process all field values through template keys 
        processed_fields = {}
        for key_name, key in keys.items():
            value = fields.get(key_name)
            ignore_type =  key_name in ignore_types
            processed_fields[key_name] = key.str_from_value(value, ignore_type=ignore_type)

        return self._cleaned_definitions[index] % processed_fields

    def _definition_variations(self, definition):
        """
        Determines all possible definition based on combinations of optional sectionals.
        
        "{manne}"               ==> ['{manne}']
        "{manne}_{ludde}"       ==> ['{manne}_{ludde}']
        "{manne}[_{ludde}]"     ==> ['{manne}', '{manne}_{ludde}']
        "{manne}_[{foo}_{bar}]" ==> ['{manne}_', '{manne}_{foo}_{bar}']
        
        """
        # split definition by optional sections
        tokens = re.split("(\[[^]]*\])", definition)

        # seed with empty string
        definitions = ['']
        for token in tokens:
            temp_definitions = []
            # regex return some blank strings, skip them
            if token == '':
                continue
            if token.startswith('['):
                # check that optional contains a key
                if not re.search("{*%s}" % self._key_name_regex, token): 
                    raise TankError("Optional sections must include a key definition.")

                # Add definitions skipping this optional value
                temp_definitions = definitions[:]
                # strip brackets from token
                token = re.sub('[\[\]]', '', token)

            # check non-optional contains no dangleing brackets
            if re.search("[\[\]]", token): 
                raise TankError("Square brackets are not allowed outside of optional section definitions.")

            # make defintions with token appended
            for definition in definitions:
                temp_definitions.append(definition + token)

            definitions = temp_definitions

        return definitions



    def _fix_key_names(self, definition, keys):
        """
        Substitutes key name for name used in definition
        """
        # Substitute key names for original key input names(key aliasing)
        substitutions = [(key_name, key.name) for key_name, key in keys.items() if key_name != key.name]
        for old_name, new_name in substitutions:
            old_def = r"{%s}" % old_name
            new_def = r"{%s}" % new_name
            definition = re.sub(old_def, new_def, definition)
        return definition

    def _clean_definition(self, definition):
        # Create definition with key names as strings with no format, enum or default values
        regex = r"{(%s)}" % self._key_name_regex
        cleaned_definition = re.sub(regex, "%(\g<1>)s", definition)
        return cleaned_definition

    def _calc_static_tokens(self, definition):
        """
        Finds the tokens from a definition which are not involved in defining keys.
        """
        expanded_definition = os.path.join(self._prefix, definition)
        regex = r"{%s}" % self._key_name_regex
        tokens = re.split(regex, expanded_definition.lower())
        # Remove empty strings
        return [x for x in tokens if x]

    @property
    def parent(self):
        """
        Returns Template representing the current Template's parent.
        """
        raise NotImplementedError


    def validate(self, path, fields=None, skip_keys=None):
        """
        Validates that a path fits with a template.

        :param path: Path to validate
        :type path: String
        :param fields: Optional: Mapping of key/values with which to add to the fields
                       extracted from the path before validation happens. 
        :type fields: Dictionary
        :param skip_keys: Optional: Field names whose values should be ignored
        :type skip_keys: List

        :rtype: Bool
        """
        fields = fields or {}
        skip_keys = skip_keys or []
        # Path should split into keys as per template
        try:
            path_fields = self.get_fields(path, skip_keys=skip_keys)
        except TankError:
            return False
        # Check input values match those in path
        for key, value in fields.items():
            if (key not in skip_keys) and (path_fields.get(key) != value):
                return False
        return True

    def get_fields(self, input_path, skip_keys=None):
        """
        Extracts key name, value pairs from a string.
        
        :param input_path: Source path for values
        :type input_path: String
        :param skip_keys: Optional keys to skip
        :type skip_keys: List

        :returns: Values found in the path based on keys in template
        :rtype: Dictionary
        """
        path_parser = None
        fields = None

        for ordered_keys, static_tokens in zip(self._ordered_keys, self._static_tokens):
            path_parser = TemplatePathParser(ordered_keys, static_tokens)
            fields = path_parser.parse_path(input_path, skip_keys)
            if fields:
                break

        if fields is None:
            raise TankError("Template %s: %s" % (str(self), path_parser.last_error))

        return fields


class TemplatePath(Template):
    """
    Class for templates for paths.
    """
    def __init__(self, definition, keys, root_path, name=None):
        """
        :param definition: Template definition.
        :type definition: String.
        :param keys: Mapping of key names to keys
        :type keys: Dictionary 
        :param root_path: Path to project root for this template.
        :type root_path: String.
        :param name: (Optional) name for this template.
        :type name: String.

        """
        super(TemplatePath, self).__init__(definition, keys, name=name)
        self._prefix = root_path

        # Make definition use platform seperator
        for index, rel_definition in enumerate(self._definitions):
            self._definitions[index] = os.path.join(*split_path(rel_definition))

        # get defintion ready for string substitution
        self._cleaned_definitions = []
        for definition in self._definitions:
            self._cleaned_definitions.append(self._clean_definition(definition))

        # split by format strings the definition string into tokens 
        self._static_tokens = []
        for definition in self._definitions:
            self._static_tokens.append(self._calc_static_tokens(definition))

    @property
    def root_path(self):
        return self._prefix

    @property
    def parent(self):
        """
        Creates Template instance for parent directory of current Template. 
        
        :returns: Parent's template
        :rtype: Template instance
        """
        parent_definition = os.path.dirname(self.definition)
        if parent_definition:
            return TemplatePath(parent_definition, self.keys, self.root_path, None)
        return None

    def _apply_fields(self, fields, ignore_types=None):
        relative_path = super(TemplatePath, self)._apply_fields(fields, ignore_types)
        return os.path.join(self.root_path, relative_path)


class TemplateString(Template):
    """
    Template class for templates not representing paths.
    """
    def __init__(self, definition, keys, name=None, validate_with=None):
        super(TemplateString, self).__init__(definition, keys, name=name)
        self.validate_with = validate_with
        self._prefix = "@"

        # split by format strings the definition string into tokens 
        self._static_tokens = []
        for definition in self._definitions:
            self._static_tokens.append(self._calc_static_tokens(definition))
    
    @property
    def parent(self):
        """
        Strings have no parents
        """
        return None


    def get_fields(self, input_path, skip_keys=None):
        """
        Given a path, return mapping of key values based on template.
        
        :param input_path: Source path for values
        :type input_path: String
        :param skip_keys: Optional keys to skip
        :type skip_keys: List

        :returns: Values found in the path based on keys in template
        :rtype: Dictionary
        """
        # add path prefix as origonal design was to require project root
        adj_path = os.path.join(self._prefix, input_path)
        return super(TemplateString, self).get_fields(adj_path, skip_keys=skip_keys)




def split_path(input_path):
    """
    Split a path into tokens.

    :param input_path: path to split
    :type input_path: string

    :returns: tokenized path
    :rtype: list of tokens
    """
    cur_path = os.path.normpath(input_path)
    cur_path = cur_path.replace("\\", "/")
    return cur_path.split("/")


class TemplatePathParser(object):
    """
    Class for parsing a path for a known set of keys, and known set of static
    tokens which should appear between the key values.
    """
    def __init__(self, ordered_keys, static_tokens):
        """
        :param ordered_keys: Template key objects in order that they appear in
                             template definition.
        :param static_tokens: Pieces of definition not representing Template Keys.
        """
        self.ordered_keys = ordered_keys
        self.static_tokens = static_tokens
        self.fields = {}
        self.input_path = None
        self.last_error = "Unable to parse path" 

    def parse_path(self, input_path, skip_keys):
        """
        Moves through a path in a linear fashion determing values for keys.

        :param input_path: Path to parse.
        :type input_path: String.
        :param skip_keys: Keys for whom we do not need to find values.
        :type skip_keys: List of strings.

        :returns: Mapping of key names to values or None. 
        """
        skip_keys = skip_keys or []
        input_path = os.path.normpath(input_path)

        # if no keys, nothing to discover
        if not self.ordered_keys:
            if input_path.lower() == self.static_tokens[0].lower():
                # this is a template where there are no keys
                # but where the static part of the template is matching
                # the input path
                # (e.g. template: foo/bar - input path foo/bar)
                return {}
            else:
                # template with no keys - in this case not matching 
                # the input path. Return for no match.
                return None
            

        self.fields = {}
        last_index = None # end index of last static token
        start_index = None # index of begining of next static token
        end_index = None # end index of next static token
        key_index = 0 # index of key in ordered keys list
        token_index = 0 # index of token in static tokens list
        # crawl through input path
        while last_index < len(input_path):
            # Check if there are keys left to process
            if key_index < len(self.ordered_keys):
                # get next key
                cur_key = self.ordered_keys[key_index]
                key_name = cur_key.name
            else:
                # all keys have been processed
                key_name = None

            # Check that there are static token left to process
            if token_index < len(self.static_tokens):
                cur_token = self.static_tokens[token_index]
                
                start_index = self.find_index_of_token(cur_key, cur_token, input_path, last_index)
                if start_index is None:
                    return None
                
                if cur_key.length is not None:
                    # there is a minimum length imposed on this key
                    if last_index and (start_index-last_index) < cur_key.length:
                        # we may have stopped early. One more click ahead
                        start_index = self.find_index_of_token(cur_key, cur_token, input_path, start_index+1)
                        if start_index is None:
                            return None
                        

                end_index = start_index + len(cur_token)
            else:
                # All static tokens used, go to end of string
                end_index = len(input_path)
                start_index = end_index

            # last index is None on first iteration only
            if last_index is not None:
                # Check we haven't previously processed all keys
                if key_index >= len(self.ordered_keys):
                    msg = ("Tried to extract fields from path '%s'," +
                            "but path does not fit the template.")
                    self.last_error = msg % input_path
                    return None
                
                if key_name not in skip_keys:
                    value_str = input_path[last_index:start_index]
                    processed_value = self._process_value(value_str, cur_key, self.fields)
                    if processed_value is None:
                        return None
                    else:
                        self.fields[key_name] = processed_value

                key_index += 1
            token_index += 1
            last_index = end_index
        return self.fields


    def find_index_of_token(self, key, token, input_path, last_index):
        """
        Determines starting index of a sub-string in the remaining portion of a path.

        If possible, domain knowledge will be used to improve the accuracy.
        :param key: The the key whose value should start after the token.
        :param token: The sub-string whose index we search.
        :param input_path: The path in which to search.
        :param last_index: The index in the path beyond which we shall search.

        :returns: The index of the start of the token.
        """
        # in python 2.5 index into a string cannot be None
        last_index = last_index or 0

        input_path_lower = input_path.lower()
        # Handle keys which already have values (they exist more than once in definition)
        if key.name and key.name in self.fields:
            # value is treated as string as it is compared to input path
            value = str(self.fields[key.name])
            # check that value exists in the remaining input path
            if value in input_path[last_index:]:
                value_index = input_path.index(value, last_index) + len(value)
                # check that token is in path after known value
                if not token in input_path_lower[value_index:]:
                    msg = ("Tried to extract fields from path '%s'," + 
                           "but path does not fit the template.")
                    self.last_error = msg % input_path
                    return None

                start_index = input_path_lower.index(token, value_index)
                if start_index != value_index:
                    msg = "Template %s: Unable to find value for key %s in path %s"
                    self.last_error = msg % (self, key.name, input_path)
                    return None
            else:
                msg = "Template %s: Unable to find value for key %s in path %s"
                self.last_error = msg % (self, key.name, input_path)
                return None
        else:
            # key has not been previously processed
            # Check that the static token exists in the remaining input string
            if not token in input_path_lower[last_index:]:
                msg = "Tried to extract fields from path '%s', but path does not fit the template."
                self.last_error = msg % input_path
                return None

            start_index = input_path_lower.index(token, last_index) 
        return start_index


    def _process_value(self, value_str, cur_key, fields):
        """
        Checks value is valid both for it's key and in relation to existing values for that key.
        """
        value = cur_key.value_from_str(value_str)
        key_name = cur_key.name
        
        if fields.get(key_name, value) != value:
            msg = "%s: Conflicting values found for key %s: %s and %s"
            self.last_error = msg % (self, key_name, fields[key_name], value)
            return None

        if os.path.sep in value_str:
            msg = "%s: Invalid value found for key %s: %s"
            self.last_error = msg % (self, key_name, value)
            return None
        
        return value

def read_templates(primary_project_path, roots, config_path=None):
    """
    Creates templates and keys based on contents of templates file.

    :param primary_project_path: Path to project root containing configuration.
    :param roots: Dictionary of root names to paths
    :param config_path: Path to templates file, overrides primary_project_path.

    :returns: Dictionary of form {template name: template object}
    """
    # Read file
    config_path = config_path or constants.get_content_templates_location(primary_project_path)
    if os.path.exists(config_path):
        config_file = open(config_path, "r")
        try:
            data = yaml.load(config_file) or {}
        finally:
            config_file.close()
    else:
        data = {}
            
    
    # get dictionaries from the templates config file:
    def get_data_section(section_name):
        # support both the case where the section 
        # name exists and is set to None and the case where it doesn't exist
        d = data.get(section_name)
        if d is None:
            d = {}
        return d            
            
    keys             = templatekey.make_keys(get_data_section("keys"))
    template_paths   = make_template_paths(get_data_section("paths"), keys, roots)
    template_strings = make_template_strings(get_data_section("strings"), keys, template_paths)

    # Detect duplicate names across paths and strings
    dup_names =  set(template_paths).intersection(set(template_strings))
    if dup_names:
        raise TankError("Detected paths and strings with the same name: %s" % str(list(dup_names)))

    # Put path and strings together
    templates = template_paths
    templates.update(template_strings)
    return templates


def make_template_paths(data, keys, roots):
    """
    Factory function which creates TemplatePaths.

    :param data: Data from which to construct the template paths.
    :type data:  Dictionary of form: {<template name>: {<option>: <option value>}}
    :param keys: Available keys.
    :type keys:  Dictionary of form: {<key name> : <TemplateKey object>}
    :param roots: Root paths.
    :type roots: Dictionary of form: {<root name> : <root path>}

    :returns: Dictionary of form {<template name> : <TemplatePath object>}
    """
    template_paths = {}
    templates_data = _process_templates_data(data, "path")

    for template_name, template_data in templates_data.items():
        definition = template_data["definition"]
        root_name = template_data["root_name"]
        # to avoid confusion between strings and paths, validate to check
        # that each item contains at least a "/" (#19098)
        if "/" not in definition:
            raise TankError("The template %s (%s) does not seem to be a valid path. A valid "
                            "path needs to contain at least one '/' character. Perhaps this "
                            "template should be in the strings section "
                            "instead?" % (template_name, definition))

        root_path = roots[root_name]
        template_path = TemplatePath(definition, keys, root_path, template_name)
        template_paths[template_name] = template_path

    return template_paths

def make_template_strings(data, keys, template_paths):
    """
    Factory function which creates TemplateStrings.

    :param data: Data from which to construct the template strings.
    :type data:  Dictionary of form: {<template name>: {<option>: <option value>}}
    :param keys: Available keys.
    :type keys:  Dictionary of form: {<key name> : <TemplateKey object>}
    :param template_paths: TemplatePaths available for optional validation.
    :type template_paths: Dictionary of form: {<template name>: <TemplatePath object>}

    :returns: Dictionary of form {<template name> : <TemplateString object>}
    """
    template_strings = {}
    templates_data = _process_templates_data(data, "path")

    for template_name, template_data in templates_data.items():
        definition = template_data["definition"]

        validator_name = template_data.get("validate_with")
        validator = template_paths.get(validator_name)
        if validator_name and not validator:
            msg = "Template %s validate_with is set to undefined template %s."
            raise TankError(msg %(template_name, validator_name))

        template_string = TemplateString(definition,
                                         keys,
                                         template_name,
                                         validate_with=validator)

        template_strings[template_name] = template_string

    return template_strings

def _conform_template_data(template_data, template_name):
    """
    Takes data for single template and conforms it expected data structure.
    """
    if isinstance(template_data, basestring):
        template_data = {"definition": template_data}
    elif not isinstance(template_data, dict):
        raise TankError("template %s has data which is not a string or dictionary." % template_name)

    if "definition" not in template_data:
        raise TankError("Template %s missing definition." % template_name)

    return template_data

def _process_templates_data(data, template_type):
    """
    Conforms templates data and checks for duplicate definitions.

    :param data: Dictionary in form { <template name> : <data> }
    :param template_type: path or string

    :returns: Processed data.
    """
    templates_data = {}
    # Track definition to detect duplicates
    definitions = {}

    for template_name, template_data in data.items():
        cur_data = _conform_template_data(template_data, template_name)
        definition = cur_data["definition"]
        if template_type == "path":
            if "root_name" not in cur_data:
                cur_data["root_name"] = "primary"
            
            root_name = cur_data["root_name"]
        else:
            root_name = None

        # Record this templates definition
        cur_key = (root_name, definition)
        definitions[cur_key] = definitions.get(cur_key, []) + [template_name]

        templates_data[template_name] = cur_data


    dups_msg = ""
    for (root_name, definition), template_names in definitions.items():
        if len(template_names) > 1:
            # We have a duplicate
            dups_msg += "%s: %s\n" % (", ".join(template_names), definition)

    if dups_msg:
        raise TankError("Duplicate definitions: multiple templates found sharing the same defintion.\n%s" %
                         dups_msg)

    return templates_data



