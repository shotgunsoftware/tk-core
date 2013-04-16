"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------
Classes for fields on TemplatePaths and TemplateStrings
"""
import re

from .errors import TankError

FRAMESPEC_FORMAT_INDICATOR = "FORMAT:"

VALID_FORMAT_STRINGS = ["%d", "#", "@", "$F"]

class TemplateKey(object):
    """Base class for template keys. Should not be used directly."""
    def __init__(self,
                 name,
                 default=None,
                 choices=None,
                 shotgun_entity_type=None,
                 shotgun_field_name=None,
                 exclusions=None,
                 abstract=False, 
                 length = None):
        """
        :param name: Key's name.
        :param default: Default value for this key.
        :param choices: List of possible values for this key.
        :param shotgun_entity_type: For keys directly linked to a shotgun field, the entity type.
        :param shotgun_field_name: For keys directly linked to a shotgun field, the field name.
        :param exclusions: List of values which are not allowed.
        :param abstract: Bool, should this key be treated as abstract.
        :param length: int, should this key be fixed length
        """
        self.name = name
        self.default = default
        self.choices = choices or []
        self.exclusions = exclusions or []
        self.shotgun_entity_type = shotgun_entity_type
        self.shotgun_field_name = shotgun_field_name
        self.is_abstract = abstract
        self.length = length
        self._last_error = ""

        # Validation
        if self.shotgun_field_name and not self.shotgun_entity_type:
            raise TankError("%s: Shotgun field requires a shotgun entity be set." % self)

        if self.is_abstract and self.default is None:
            raise TankError("%s: Fields marked as abstract needs to have a default value!" % self)

        if not ((self.default is None) or self.validate(default)):
            raise TankError(self._last_error)
        
        if not all(self.validate(choice) for choice in self.choices):
            raise TankError(self._last_error)
    
    def str_from_value(self, value=None, ignore_type=False):
        """
        Returns a string version of a value as appropriate for the key's setting.

        :param value: (Optional) Value to process. Will use key's default if value is None.
        :ignore_type: (Optional) Returns casts value to a string with no validation.

        :returns: String version of value as processed by the key.
        :throws: TankError if value is not valid for the key.
        """
        if value is None:
            if self.default is None:
                raise TankError("No value provided and no default available for %s" % self)
            else:
                value = self.default
        elif ignore_type:
            return str(value)

        if self.validate(value):
            return self._as_string(value)
        else:
            raise TankError(self._last_error)

    def value_from_str(self, str_value):
        """
        Validates and translates a string into an appropriate value for this key.

        :param str_value: The string to translate.

        :returns: The translated value.
        """
        if self.validate(str_value):
            value = self._as_value(str_value)
        else:
            raise TankError(self._last_error)
        return value

    def validate(self, value):
        """
        Test if a value is valid for this key.

        :param value: Value to test.

        :returns: Bool
        """

        # We are not case sensitive
        if str(value).lower() in [str(x).lower() for x in self.exclusions]:
            self._last_error = "%s Illegal value: %s is forbidden for this key." % (self, value)
            return False

        if not((value is None) or (self.choices == [])):
            if str(value).lower() not in [str(x).lower() for x in self.choices]:
                self._last_error = "%s Illegal value: '%s' not in choices: %s" % (self, value, str(self.choices))
                return False
        
        if self.length is not None and len(str(value)) != self.length:
            self._last_error = ("%s Illegal value: '%s' does not have a length of "
                                "%d characters." % (self, value, self.length))
            return False
                        
        return True

    def _as_string(self, value):
        raise NotImplementedError

    def _as_value(self, str_value):
        return str_value

    def __repr__(self):
        return "<Tank %s %s>" % (self.__class__.__name__, self.name)

    @property
    def has_abstraction(self):
        return hasattr(self, "_abstractor")


class StringKey(TemplateKey):
    """
    Keys whose values are strings.
    """
    def __init__(self,
                 name,
                 default=None,
                 choices=None,
                 filter_by=None,
                 shotgun_entity_type=None,
                 shotgun_field_name=None, 
                 exclusions=None,
                 abstract=False, 
                 length=None):
        """
        :param name: Name by which the key will be refered.
        :param default: Default value for the key.
        :param choices: List of possible values for this key.
        :parma filter_by: Name of filter type to limit values for string. Currently
                          only accepted values are 'alphanumeric' and None.
        :param shotgun_entity_type: For keys directly linked to a shotgun field, the entity type.
        :param shotgun_field_name: For keys directly linked to a shotgun field, the field name.
        :param exclusions: List of forbidden values.
        :param abstract: Bool, should this key be treated as abstract.
        :param length: int, should this key be fixed length
        """
        self.filter_by = filter_by
        if self.filter_by == "alphanumeric":
            self._filter_regex = re.compile("[^a-zA-Z0-9]")
        else: 
            self._filter_regex = None

        super(StringKey, self).__init__(name,
                                        default=default,
                                        choices=choices,
                                        shotgun_entity_type=shotgun_entity_type,
                                        shotgun_field_name=shotgun_field_name,
                                        exclusions=exclusions,
                                        abstract=abstract,
                                        length=length)

    def validate(self, value):
        if self._filter_regex and self._filter_regex.search(value):
            self._last_error = "%s Illegal value '%s' does not fit filter" % (self, value)
            return False
        else:
            return super(StringKey, self).validate(value)

    def _as_string(self, value):
        return str(value)


class IntegerKey(TemplateKey):
    """
    Key whose value is an integer.
    """
    def __init__(self,
                 name,
                 default=None,
                 choices=None,
                 format_spec=None,
                 shotgun_entity_type=None,
                 shotgun_field_name=None,
                 exclusions=None,
                 abstract=False,
                 length=None):
        """
        :param name: Key's name.
        :param default: Default value for this key.
        :param choices: List of possible values for this key.
        :param format_spec: Specification for formating when casting to a string.
                            The form is a zero followed the number of spaces to pad
                            the value.
        :param shotgun_entity_type: For keys directly linked to a shotgun field, the entity type.
        :param shotgun_field_name: For keys directly linked to a shotgun field, the field name.
        :param exclusions: List of forbidden values.
        :param abstract: Bool, should this key be treated as abstract.
        :param length: int, should this key be fixed length
        """
        super(IntegerKey, self).__init__(name,
                                         default=default,
                                         choices=choices,
                                         shotgun_entity_type=shotgun_entity_type,
                                         shotgun_field_name=shotgun_field_name,
                                         exclusions=exclusions,
                                         abstract=abstract,
                                         length=length)

        if not(format_spec is None or isinstance(format_spec, basestring)):
            msg = "Format_spec for TemplateKey %s is not of type string: %s"
            raise TankError(msg % (name, str(format_spec)))

        self.format_spec = format_spec

    def validate(self, value):

        if value is not None:
            if not (isinstance(value, int) or value.isdigit()):
                self._last_error = "%s Illegal value %s, expected an Integer" % (self, value)
                return False
            else:
                return super(IntegerKey, self).validate(value)
        return True

    def _as_string(self, value):
        if self.format_spec:
            # insert format spec into string
            return ("%%%sd" % self.format_spec) % value
        return "%d" % value

    def _as_value(self, str_value):
        return int(str_value)

class SequenceKey(IntegerKey):
    """
    Key whose value is a integer sequence.
    """
    def __init__(self,
                 name,
                 default=None,
                 choices=None,
                 format_spec='01',
                 shotgun_entity_type=None,
                 shotgun_field_name=None,
                 exclusions=None):

        # determine the actual frame specs given the padding (format_spec)
        # and the allowed formats
        self._frame_specs = [ _resolve_frame_spec(x, format_spec) for x in VALID_FORMAT_STRINGS ]

        # all sequences are abstract by default and have a default value of %0Xd
        abstract = True
        if default is None:
            # default value is %d form
            default = _resolve_frame_spec("%d", format_spec)
        
        super(SequenceKey, self).__init__(name,
                                          default=default,
                                          choices=choices,
                                          format_spec=format_spec,
                                          shotgun_entity_type=shotgun_entity_type,
                                          shotgun_field_name=shotgun_field_name,
                                          exclusions=exclusions,
                                          abstract=abstract)


    def validate(self, value):

        # use a std error message
        full_format_strings = ["%s %s" % (FRAMESPEC_FORMAT_INDICATOR, x) for x in VALID_FORMAT_STRINGS]
        error_msg = "%s Illegal value '%s', expected an Integer, a frame spec or format spec.\n" % (self, value)
        error_msg += "Valid frame specs: %s\n" % str(self._frame_specs)
        error_msg += "Valid format strings: %s\n" % full_format_strings
        

        if isinstance(value, basestring) and value.startswith(FRAMESPEC_FORMAT_INDICATOR):
            # FORMAT: YXZ string - check that XYZ is in VALID_FORMAT_STRINGS
            pattern = _extract_format_string(value)        
            if pattern in VALID_FORMAT_STRINGS:
                return True
            else:
                self._last_error = error_msg
                return False
                
        elif not(isinstance(value, int) or value.isdigit()):
            # not a digit - so it must be a frame spec! (like %05d)
            # make sure that it has the right length and formatting.
            if value in self._frame_specs:
                return True
            else:
                self._last_error = error_msg
                return False
                
        else:
            return super(SequenceKey, self).validate(value)

    def _as_string(self, value):
        
        if isinstance(value, basestring) and value.startswith(FRAMESPEC_FORMAT_INDICATOR):
            # this is a FORMAT: XYZ - convert it to the proper resolved frame spec
            pattern = _extract_format_string(value)
            return _resolve_frame_spec(pattern, self.format_spec)

        if value in self._frame_specs:
            # a frame spec like #### @@@@@ or %08d
            return value
        
        else:
            return super(SequenceKey, self)._as_string(value)

    def _as_value(self, str_value):
        if str_value in self._frame_specs:
            return str_value
        else:
            return super(SequenceKey, self)._as_value(str_value)




def _extract_format_string(value):
    """
    Returns XYZ given the string "FORMAT:    XYZ"
    """
    if isinstance(value, basestring) and value.startswith(FRAMESPEC_FORMAT_INDICATOR):
        pattern = value.replace(FRAMESPEC_FORMAT_INDICATOR, "").strip()
    else:
        # passthrough
        pattern = value
    return pattern

def _resolve_frame_spec(format_string, format_spec):
    """
    Turns a format_string %d and a format_spec "03" into a sequence identifier (%03d)
    """
    
    error_msg = "Illegal format pattern for framespec: '%s'. " % format_string
    error_msg += "Legal patterns are: %s" % ", ".join(VALID_FORMAT_STRINGS)

    
    if format_string not in VALID_FORMAT_STRINGS:
        raise TankError(error_msg)
    
    if format_spec.startswith("0") and format_spec != "01":
        use_zero_padding = True
    else: 
        use_zero_padding = False
    
    places = int(format_spec)
    
    if use_zero_padding:
        if format_string == "%d":
            frame_spec = "%%0%dd" % places
        elif format_string == "#":
            frame_spec = "#"*places
        elif format_string == "@":
            frame_spec = "@"*places
        elif format_string == "$F":
            frame_spec = "$F%d" % places
        else:
            raise TankError(error_msg)
    else:
        # non zero padded rules
        if format_string == "%d":
            frame_spec = "%d"
        elif format_string == "#":
            frame_spec = "#"
        elif format_string == "@":
            frame_spec = "@"
        elif format_string == "$F":
            frame_spec = "$F"
        else:
            raise TankError(error_msg)
            
    return frame_spec
        




def make_keys(data):
    """
    Factory method for instantiating template keys.

    :param data: Key data.
    :type data: Dictionary of the form: {<key name>: {'type': <key type>, <option>: <option value}
     
    :returns: Dictionary of the form: {<key name>: <TemplateKey object>}
    """
    keys = {}
    names_classes = {"str": StringKey, "int": IntegerKey, "sequence": SequenceKey}
    for initial_key_name, key_data in data.items():
        # We need to remove data before passing in as arguments, so copy it.
        prepped_data = key_data.copy()

        class_name = prepped_data.pop("type")
        KeyClass = names_classes.get(class_name)
        if not KeyClass:
            raise TankError("Invalid type: '%s'. Valid types are: %s" % (class_name, names_classes.keys()))

        if "alias" in prepped_data:
            # The alias becomes the key's name and is used internally by Templates as the key's name
            key_name = prepped_data.pop("alias")
        else:
            key_name = initial_key_name

        key = KeyClass(key_name, **prepped_data)
        keys[initial_key_name] = key
    return keys

