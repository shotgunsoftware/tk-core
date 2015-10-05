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
Classes for fields on TemplatePaths and TemplateStrings
"""

import re
import datetime
import time
from .platform import constants
from .errors import TankError

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
        :param default: Default value for this key. If the default is a callable, it will be invoked
                        without any parameters whenever a default value is required.
        :param choices: List of possible values for this key.  Can be either a list or a dictionary
                        of choice:label pairs.
        :param shotgun_entity_type: For keys directly linked to a shotgun field, the entity type.
        :param shotgun_field_name: For keys directly linked to a shotgun field, the field name.
        :param exclusions: List of values which are not allowed.
        :param abstract: Bool, should this key be treated as abstract.
        :param length: int, should this key be fixed length
        """
        self.name = name
        self._default = default

        # special handling for choices:
        if isinstance(choices, dict):
            # new style choices dictionary containing choice:label pairs:
            self._choices = choices
        elif isinstance(choices, list) or isinstance(choices, set):
            # old style choices - labels and choices are the same:
            self._choices = dict(zip(choices, choices))
        else:
            self._choices = {}

        self.exclusions = exclusions or []
        self.shotgun_entity_type = shotgun_entity_type
        self.shotgun_field_name = shotgun_field_name
        self.is_abstract = abstract
        self.length = length
        self._last_error = ""

        # check that the key name doesn't contain invalid characters
        if not re.match(r"^%s$" % constants.TEMPLATE_KEY_NAME_REGEX, name):
            raise TankError("%s: Name contains invalid characters. "
                            "Valid characters are %s." % (self, constants.VALID_TEMPLATE_KEY_NAME_DESC))

        # Validation
        if self.shotgun_field_name and not self.shotgun_entity_type:
            raise TankError("%s: Shotgun field requires a shotgun entity be set." % self)

        if self.is_abstract and self.default is None:
            raise TankError("%s: Fields marked as abstract needs to have a default value!" % self)

        if not ((self.default is None) or self.validate(self.default)):
            raise TankError(self._last_error)
        
        if not all(self.validate(choice) for choice in self.choices):
            raise TankError(self._last_error)

    def _get_default(self):
        """
        Returns the default value for this key. If the default argument was specified
        as a callable in the constructor, it is invoked and assumed to take no parameters.

        :returns: The default value.
        """
        if callable(self._default):
            return self._default()
        else:
            return self._default

    def _set_default(self, value):
        """
        Sets the default value for this key.

        :param value: New default value for the key. Can be None.
        """
        self._default = value

    # Python 2.5 doesn't support @default.setter so use old style property.
    default = property(_get_default, _set_default)

    @property
    def choices(self):
        """
        :returns:   List of choices available for this key - retained for backwards
                    compatibility
        """
        return self._choices.keys()
    
    @property
    def labelled_choices(self):
        """
        :returns:   Dictionary of choices together with their labels that are available 
                    for this key
        """
        return self._choices
    
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
            return value if isinstance(value, basestring) else str(value)

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
        
        str_value = value if isinstance(value, basestring) else str(value)

        # We are not case sensitive
        if str_value.lower() in [str(x).lower() for x in self.exclusions]:
            self._last_error = "%s Illegal value: %s is forbidden for this key." % (self, value)
            return False

        if value is not None and self.choices:
            if str_value.lower() not in [str(x).lower() for x in self.choices]:
                self._last_error = "%s Illegal value: '%s' not in choices: %s" % (self, value, str(self.choices))
                return False
        
        if self.length is not None and len(str_value) != self.length:
            self._last_error = ("%s Illegal value: '%s' does not have a length of "
                                "%d characters." % (self, value, self.length))
            return False
                        
        return True

    def _as_string(self, value):
        raise NotImplementedError

    def _as_value(self, str_value):
        return str_value

    def __repr__(self):
        return "<Sgtk %s %s>" % (self.__class__.__name__, self.name)

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
        :param filter_by: Name of filter type to limit values for string. Currently
                          only accepted values are 'alphanumeric', 'alpha', None and a regex string.
        :param shotgun_entity_type: For keys directly linked to a shotgun field, the entity type.
        :param shotgun_field_name: For keys directly linked to a shotgun field, the field name.
        :param exclusions: List of forbidden values.
        :param abstract: Bool, should this key be treated as abstract.
        :param length: int, should this key be fixed length
        """
        self.filter_by = filter_by

        # Build regexes for alpha and alphanumeric filter_by clauses
        #
        # Note that we cannot use a traditional [^a-zA-Z0-9] regex since we want
        # to support unicode and not just ascii. \W covers "Non-word characters",
        # which is basically the international equivalent of 7-bit ascii 
        #        
        self._filter_regex_u = None
        self._custom_regex_u = None

        if self.filter_by == "alphanumeric":
            self._filter_regex_u = re.compile(u"[\W_]", re.UNICODE)
        
        elif self.filter_by == "alpha":
            self._filter_regex_u = re.compile(u"[\W_0-9]", re.UNICODE)
        
        elif self.filter_by is not None:
            # filter_by is a regex
            self._custom_regex_u = re.compile(self.filter_by, re.UNICODE)
        

        super(StringKey, self).__init__(name,
                                        default=default,
                                        choices=choices,
                                        shotgun_entity_type=shotgun_entity_type,
                                        shotgun_field_name=shotgun_field_name,
                                        exclusions=exclusions,
                                        abstract=abstract,
                                        length=length)

    def validate(self, value):

        u_value = value
        if not isinstance(u_value, unicode):
            # handle non-ascii characters correctly by
            # decoding to unicode assuming utf-8 encoding
            u_value = value.decode("utf-8")

        if self._filter_regex_u:                
            # first check our std filters. These filters are negated
            # so here we are checking that there are occurances of 
            # that pattern in the string
            if self._filter_regex_u.search(u_value):
                self._last_error = "%s Illegal value '%s' does not fit filter_by '%s'" % (self, value, self.filter_by)
                return False
        
        elif self._custom_regex_u:
            # check for any user specified regexes
            if self._custom_regex_u.match(u_value) is None:
                self._last_error = "%s Illegal value '%s' does not fit filter_by '%s'" % (self, value, self.filter_by)
                return False
            
        return super(StringKey, self).validate(value)

    def _as_string(self, value):
        return value if isinstance(value, basestring) else str(value)


class TimestampKey(TemplateKey):
    """
    Key whose value is a time string formatted with strftime.
    """

    def __init__(
        self,
        name,
        default=None,
        format_spec="%Y-%m-%d-%H-%M-%S"
    ):
        """
        Constructor
        :param name: Name by which the key will be refered.
        :param default: Default value for this field. Acceptable values are
                            - None
                            - a string formatted according to the format_spec
                            - utc_now, which means the current time in the UTC timezone will be used
                              as the default value.
                            - now, which means the current time in the local timezone will be used
                              as the default value.
        :param format_spec: Specification for formating when casting to/from a string.
                            The format follows the convention of strftime and strptime. The
                            default value is "%Y-%m-%d-%H-%M-%S". Given June 24th, 2015 at
                            9:20:30 PM, this will yield 2015-06-24-21-20-30
        """

        # Can't use __repr__ because of a chicken and egg problem. The base class validates the
        # default value, so format_spec needs to be set first. But if I am testing format_spec
        # before calling the base class, then repr will crash since self.name won't have been set
        # yet.
        if isinstance(format_spec, basestring) is False:
            raise TankError("format_spec for <Sgtk TimestampKey %s> is not of type string: %s" %
                            (name, format_spec.__class__.__name__))
        self.format_spec = format_spec

        if isinstance(default, basestring):
            # if the user passes in now or utc, we'll generate the current time as the default time.
            if default.lower() == "now":
                default = self.__get_current_time
            elif default.lower() == "utc_now":
                default = self.__get_current_utc_time
            else:
                # Normally the base class is the one to validate, but in this case we need to
                # convert the string value into an actual value because the default is expected to
                # be a value and not a string, so we'll validate right away.
                if not self.validate(default):
                    raise TankError(self._last_error)
                # If we are here everything went well, so convert the string to an actual value.
                default = datetime.datetime.strptime(default, self.format_spec)
            # Base class will validate other values using the format specifier.
        elif default is not None:
            raise TankError("default for <Sgtk TimestampKey %s> is not of type string or None: %s" %
                            (name, default.__class__.__name__))

        super(TimestampKey, self).__init__(
            name,
            default=default
        )

    def __get_current_time(self):
        """
        Returns the current time as a datetime.datetime instance.

        Do not streamline the code so the __init__ method simply passesd the datetime.datetime.now method,
        we can't mock datetime.now since it's builtin and will make unit tests more complicated to
        write.

        :returns: A datetime object representing the current time in the local timezone.
        """
        return datetime.datetime.now()

    def __get_current_utc_time(self):
        """
        Returns the current utc time as a datetime.datetime instance.

        Do not streamline the code so the __init__ method simply passesd the datetime.datetime.utcnow method,
        we can't mock datatime.datetime.utcnow since it's builtin and will make unit tests more complicated to
        write.

        :returns: A datetime object representing time current time in the UTC timezone.
        """
        return datetime.datetime.utcnow()

    def validate(self, value):
        """
        Test if a value is valid for this key.

        :param value: Value to test.

        :returns: Bool
        """
        if isinstance(value, basestring):
            # If we have a string we have to actually try to convert the string to see it if matches
            # the expected format.
            try:
                datetime.datetime.strptime(value, self.format_spec)
                return True
            except ValueError, e:
                # Bad value, report the error to the client code.
                self._last_error = "Invalid string: %s" % e.message
                return False
        elif isinstance(value, datetime.datetime):
            return True
        else:
            self._last_error = "Invalid type: expecting string or datetime.datetime, not %s" % value.__class__.__name__
            return False

    def _as_string(self, value):
        """
        Converts a given value as string.

        :param value: A datetime.datetime object that will be converted to a string according to the
                      format specification.

        :returns: A string formatted according to the format_spec.
        """
        return value.strftime(self.format_spec)

    def _as_value(self, str_value):
        """
        Converts a string into a datetime.datetime.

        :param str_value: String to convert.

        :returns: A datetime representation of str_value parsed according to the format_spec.
        """
        return datetime.datetime.strptime(str_value, self.format_spec)


class IntegerKey(TemplateKey):
    """
    Key whose value is an integer.
    """
    # Matches one non-zero digit follow by any number of digits.
    _NON_ZERO_POSITIVE_INTEGER_EXP = "[1-9]\d*"
    # For the next two regular expressions, the ^ and $ are important to prevent partial matches.
    # Matches an optional 0 followed by a non zero positive integer.
    _FORMAT_SPEC_RE = re.compile("^(0?)(%s)$" % _NON_ZERO_POSITIVE_INTEGER_EXP)
    # Matches a non zero positive integer.
    _NON_ZERO_POSITIVE_INTEGER_RE = re.compile("^%s$" % _NON_ZERO_POSITIVE_INTEGER_EXP)

    def __init__(self,
                 name,
                 default=None,
                 choices=None,
                 format_spec=None,
                 shotgun_entity_type=None,
                 shotgun_field_name=None,
                 exclusions=None,
                 abstract=False,
                 length=None,
                 strict_matching=None):
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
        :param strict_matching: Bool, indicates if the padding should be matching exactly the
                                format_spec when parsing a string. Default behavior is to match
                                exactly the padding when a format_spec is provided.
        """
        self._zero_padded = None
        self._minimum_width = None
        self.format_spec = None
        self.strict_matching = None
        # Validate and set up formatting details
        self._init_format_spec(name, format_spec)
        # Validate and set up strict matching defailts
        self._init_strict_matching(name, strict_matching)
        super(IntegerKey, self).__init__(name,
                                         default=default,
                                         choices=choices,
                                         shotgun_entity_type=shotgun_entity_type,
                                         shotgun_field_name=shotgun_field_name,
                                         exclusions=exclusions,
                                         abstract=abstract,
                                         length=length)

    def _init_format_spec(self, name, format_spec):
        """
        Asserts that the format_spec parameter is a valid value.

        :param name: Name of this template key.
        :param format_spec: Parameter to be validated.

        :raises TankError: Raised when the parameter is not a string that maching a %d format
                           option.
        """
        # No format spec means no formatting options.
        if format_spec is None:
            return

        if not isinstance(format_spec, basestring):
            msg = "format_spec for IntegerKey %s is not of type string: %s"
            raise TankError(msg % (name, format_spec))

        if len(format_spec) == 0:
            raise TankError("format_spec can't be empty.")

        matches = self._FORMAT_SPEC_RE.match(format_spec)
        if not matches:
            raise TankError("format_spec for <Sgtk IntegerKey %s> has to either be a number (e.g. '3') or "
                            "a 0 followed by a number (e.g. '03'), not '%s'" % (name, format_spec))

        groups = matches.groups()
        # groups[0] is either '' or '0', in which case the padding is ' '
        self._zero_padded = groups[0] == "0"
        # groups[1] is the minimum width of the number.
        self._minimum_width = int(groups[1])
        self.format_spec = format_spec

    def _init_strict_matching(self, name, strict_matching):
        """
        Asserts that the strict_matching parameter is a valid value.

        :param name: Name of this template key.
        :param strict_matching: Parameter to be validated.

        :raises TankError: Raised when the parameter is not a boolean.
        """
        # make sure that strict_matching is not set or that it is a boolean
        if not(strict_matching is None or isinstance(strict_matching, bool)):
            msg = "strict_matching for <Sgtk IntegerKey %s> is not of type boolean: %s"
            raise TankError(msg % (name, str(strict_matching)))

        # If there is a format and strict_matching is set, there's an error, since there
        # is no format to enforce or not.
        if self.format_spec is None and strict_matching is not None:
            raise TankError("strict_matching can't be set if there is no format_spec")

        # By default, if strict_matching is not set but there is a format spec, we'll
        # strictly match.
        if strict_matching is None and self.format_spec is not None:
            strict_matching = True

        if strict_matching:
            # This regular expression is blind to the actual length of the string for performance
            # reasons. Code that uses it should test that the string's length is of
            # self._minimum_width first. It first matches up to n-1 padding characters. It then
            # matches either a single 0, or an actual multiple digit number that doesn't start with
            # 0.
            self._strict_validation_re = re.compile("^%s{0,%d}((%s)|0)$" % (
                "0" if self._zero_padded else ' ',
                self._minimum_width - 1,
                self._NON_ZERO_POSITIVE_INTEGER_EXP)
            )
        else:
            self._strict_validation_re = None

        self.strict_matching = strict_matching

    def validate(self, value):
        """
        Validates the value.

        :param value: Value to validate.

        :returns: True is the validation was succesful, False otherwise.
        """
        if value is not None:
            if isinstance(value, basestring):
                # We have a string, make sure it loosely or strictly matches the format.
                if self.strict_matching and not self._strictly_matches(value):
                    return False
                elif not self.strict_matching and not self._loosely_matches(value):
                    return False
            elif not isinstance(value, int):
                self._last_error = "%s Illegal value '%s', expected an Integer" % (self, value)
                return False
            return super(IntegerKey, self).validate(value)
        return True

    def _loosely_matches(self, value):
        """
        Checks if the value loosely matches. The value loosely matches if it can be turned into an
        int.

        For a given format_spec of "03", here are examples of loosely matching values:
        - '1'        (missing padding)
        - '00000001' (too much padding)
        - '       1' (too much padding)

        :param value: String to test

        :returns: True if it loosely matches, False otherwise.
        """
        # This is the extent of what was tested before strict matching. We're actually a bit more permissive,
        # because the user could have specified a format specifier that uses spaces for padding, but isdigit will
        # fail if spaces are at the beginning of a string, so strip them out.
        if not self._zero_padded:
            value = value.lstrip()
        # Is digit is how we tested for a number before strict_matching was introduced, so don't change that behaviour
        if not value.isdigit():
            self._last_error = "%s Illegal value '%s', expected an Integer" % (self, value)
            return False
        return True

    def _strictly_matches(self, value):
        """
        Checks if the value strictly matches the format_spec. A value strictly matches the format
        it is at least as wide as the minimum character length. If the string is wider, it must
        be a non zero positive number. If it is as wide, is must be a padded positive integer.

        :param value: Value to test

        :returns: True if the value strictly matches the format spec, False otherwise.
        """
        error_msg = "%s Illegal value '%s', does not match format spec '%s'" % (self, value, self.format_spec)
        # If there are more characters than the minimum size, we should have a non zero positive number
        if len(value) > self._minimum_width:
            if not self._NON_ZERO_POSITIVE_INTEGER_RE.match(value):
                self._last_error = error_msg
                return False
            return True

        # If there are less characters than the minimum size, then then there is no strict matching.
        if len(value) < self._minimum_width:
            self._last_error = error_msg
            return False

        # If there are many characters as the format_spec requires, we'll validate that things are
        # padded accordingly. Example of things that will fail are.
        # - '01a'
        # - '0 1'
        # - ' 01'
        matches = self._strict_validation_re.match(value)
        if not matches:
            self._last_error = error_msg
            return False
        return True

    def _as_string(self, value):
        """
        Converts value into a string.

        :returns: String representation of the value according to the optional format_spec.
        """
        if self.format_spec:
            # insert format spec into string
            return ("%%%sd" % self.format_spec) % value
        return "%d" % value

    def _as_value(self, str_value):
        """
        Converts value into a string.

        :returns: String representation of the value according to the optional format_spec.
        """
        return int(str_value)


class SequenceKey(IntegerKey):
    """
    Key whose value is a integer sequence.
    """
    
    # special keywork used when format is specified directly in value
    FRAMESPEC_FORMAT_INDICATOR = "FORMAT:"
    # valid format strings that can be used with this Key type
    VALID_FORMAT_STRINGS = ["%d", "#", "@", "$F", "<UDIM>", "$UDIM"]
    # flame sequence pattern regex ('[1234-5434]')
    FLAME_PATTERN_REGEX = "^\[[0-9]+-[0-9]+\]$"
    
    def __init__(self,
                 name,
                 default=None,
                 choices=None,
                 format_spec='01',
                 shotgun_entity_type=None,
                 shotgun_field_name=None,
                 exclusions=None):
        """
        Construction
        
        :param name: Key's name.
        :param default: Default value for this key.
        :param choices: List of possible values for this key.
        :param format_spec: Specification for formating when casting to a string.
                            The form is a zero followed the number of spaces to pad
                            the value.
        :param shotgun_entity_type: For keys directly linked to a shotgun field, the entity type.
        :param shotgun_field_name: For keys directly linked to a shotgun field, the field name.
        :param exclusions: List of forbidden values.
        """

        # determine the actual frame specs given the padding (format_spec)
        # and the allowed formats
        self._frame_specs = [ self._resolve_frame_spec(x, format_spec) for x in self.VALID_FORMAT_STRINGS ]

        # all sequences are abstract by default and have a default value of %0Xd
        abstract = True
        if default is None:
            # default value is %d form
            default = self._resolve_frame_spec("%d", format_spec)
        
        super(SequenceKey, self).__init__(name,
                                          default=default,
                                          choices=choices,
                                          strict_matching=False,
                                          format_spec=format_spec,
                                          shotgun_entity_type=shotgun_entity_type,
                                          shotgun_field_name=shotgun_field_name,
                                          exclusions=exclusions,
                                          abstract=abstract)


    def validate(self, value):

        # use a std error message
        full_format_strings = ["%s %s" % (self.FRAMESPEC_FORMAT_INDICATOR, x) for x in self.VALID_FORMAT_STRINGS]
        error_msg = "%s Illegal value '%s', expected an Integer, a frame spec or format spec.\n" % (self, value)
        error_msg += "Valid frame specs: %s\n" % str(self._frame_specs)
        error_msg += "Valid format strings: %s\n" % full_format_strings
        

        if isinstance(value, basestring) and value.startswith(self.FRAMESPEC_FORMAT_INDICATOR):
            # FORMAT: YXZ string - check that XYZ is in VALID_FORMAT_STRINGS
            pattern = self._extract_format_string(value)        
            if pattern in self.VALID_FORMAT_STRINGS:
                return True
            else:
                self._last_error = error_msg
                return False
                
        elif isinstance(value, basestring) and re.match(self.FLAME_PATTERN_REGEX, value):
            # value is matching the flame-style sequence pattern
            # [1234-5678]
            return True
                
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
        
        if isinstance(value, basestring) and value.startswith(self.FRAMESPEC_FORMAT_INDICATOR):
            # this is a FORMAT: XYZ - convert it to the proper resolved frame spec
            pattern = self._extract_format_string(value)
            return self._resolve_frame_spec(pattern, self.format_spec)

        if isinstance(value, basestring) and re.match(self.FLAME_PATTERN_REGEX, value):
            # this is a flame style sequence token [1234-56773]
            return value

        if value in self._frame_specs:
            # a frame spec like #### @@@@@ or %08d
            return value
        
        # resolve it via the integerKey base class
        return super(SequenceKey, self)._as_string(value)

    def _as_value(self, str_value):
        
        if str_value in self._frame_specs:
            return str_value
        
        if re.match(self.FLAME_PATTERN_REGEX, str_value):
            # this is a flame style sequence token [1234-56773]
            return str_value
    
        # resolve it via the integerKey base class
        return super(SequenceKey, self)._as_value(str_value)

    def _extract_format_string(self, value):
        """
        Returns XYZ given the string "FORMAT:    XYZ"
        """
        if isinstance(value, basestring) and value.startswith(self.FRAMESPEC_FORMAT_INDICATOR):
            pattern = value.replace(self.FRAMESPEC_FORMAT_INDICATOR, "").strip()
        else:
            # passthrough
            pattern = value
        return pattern
    
    def _resolve_frame_spec(self, format_string, format_spec):
        """
        Turns a format_string %d and a format_spec "03" into a sequence identifier (%03d)
        """
        
        error_msg = "Illegal format pattern for framespec: '%s'. " % format_string
        error_msg += "Legal patterns are: %s" % ", ".join(self.VALID_FORMAT_STRINGS)
    
        
        if format_string not in self.VALID_FORMAT_STRINGS:
            raise TankError(error_msg)
        
        if format_spec.startswith("0") and format_spec != "01":
            use_zero_padding = True
        else: 
            use_zero_padding = False
        
        places = int(format_spec) if format_spec.isdigit() else 1
        
        if use_zero_padding:
            if format_string == "%d":
                frame_spec = "%%0%dd" % places
            elif format_string == "#":
                frame_spec = "#"*places
            elif format_string == "@":
                frame_spec = "@"*places
            elif format_string == "$F":
                frame_spec = "$F%d" % places
            elif format_string in ("<UDIM>", "$UDIM"):
                # UDIM's aren't padded!
                frame_spec = format_string
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
            elif format_string in ("<UDIM>", "$UDIM"):
                # UDIM's aren't padded!
                frame_spec = format_string
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
    names_classes = {
        "str": StringKey,
        "int": IntegerKey,
        "sequence": SequenceKey,
        "timestamp": TimestampKey
    }
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
