import os

from tank.templatekey import StringKey
from tank_test.tank_test_base import ShotgunTestBase, TankTestBase
from tank_test.tank_test_base import setUpModule # noqa
from tank.platform.validation import *

import tank


class TestValidateSchema(ShotgunTestBase):
    def setUp(self):
        super(TestValidateSchema, self).setUp()
        
        # The validation code needs a name for error reporting
        self.app_name = "test_app"
    
    def test_invalid_schema_type(self):
        key = "test_setting"
        bad_type = "bogus"
        schema = {key:{"type":bad_type}}
        
        params = (bad_type, key, self.app_name)
        expected_msg = "Invalid type '%s' in schema '%s' for '%s'!" % params
    
        self.check_error_message(TankError, expected_msg, validate_schema, self.app_name, schema)
        
    def test_invalid_default_value(self):
        # Test invalid default value type
        key = "test_setting"
        value = {"type":"str","default_value":123}
        schema = {key:value}
        
        params = (key, self.app_name, "int", "str")
        expected_msg = "Invalid type for default value in schema '%s' for '%s' - found '%s', expected '%s'" % params
        self.check_error_message(TankError, expected_msg, validate_schema, self.app_name, schema) 

        # Test invalid default value type in list values
        value = {"type":"list","values":{"type":"str","default_value":123}}
        schema = {key:value}

        params = (key, self.app_name, "int", "str")
        expected_msg = "Invalid type for default value in schema '%s' for '%s' - found '%s', expected '%s'" % params
        self.check_error_message(TankError, expected_msg, validate_schema, self.app_name, schema)
        
        # Test invalid default value type in dict items
        value = {"type":"dict","items":{"test_dict":{"type":"str","default_value":123}}}
        schema = {key:value}

        params = (key, self.app_name, "int", "str")
        expected_msg = "Invalid type for default value in schema '%s' for '%s' - found '%s', expected '%s'" % params
        self.check_error_message(TankError, expected_msg, validate_schema, self.app_name, schema)

    def test_list_invalid_schema(self):
        key = "test_setting"
        bad_type = "bogus" 
        list_value = {"type":"list","values":{"type":bad_type}}
        schema = {key:list_value}

        # Test a bad value type
        expected_msg = "Invalid type '%s' in schema '%s' for '%s'!" % (bad_type, key, self.app_name)
        self.check_error_message(TankError, expected_msg, validate_schema, self.app_name, schema)

        # Test missing type
        list_value = {"type":"list","values":{}}
        schema = {key:list_value}

        expected_msg = "Missing type in schema '%s' for '%s'!" % (key, self.app_name)
        self.check_error_message(TankError, expected_msg, validate_schema, self.app_name, schema)

        # Test missing "values" key
        list_value = {"type":"list"}
        schema = {key:list_value}

        expected_msg = "Missing or invalid 'values' dict in schema '%s' for '%s'!" % (key, self.app_name)
        self.check_error_message(TankError, expected_msg, validate_schema, self.app_name, schema)

        # Test bad type for "values" key
        list_value = {"type":"list","values":"bogus"}
        schema = {key:list_value}

        expected_msg = "Missing or invalid 'values' dict in schema '%s' for '%s'!" % (key, self.app_name)
        self.check_error_message(TankError, expected_msg, validate_schema, self.app_name, schema)
        
        # Test bad type for "allows_empty" key
        list_value = {"type":"list","values":{},"allows_empty":"bogus"}
        schema = {key:list_value}

        expected_msg = "Invalid 'allows_empty' bool in schema '%s' for '%s'!" % (key, self.app_name)
        self.check_error_message(TankError, expected_msg, validate_schema, self.app_name, schema)
        
    def test_dict_invalid_schema(self):
        # Test bad type for "items" key
        key = "test_setting"
        dict_value = {"type":"dict","items":"bogus"}
        schema = {key:dict_value}

        expected_msg = "Invalid 'items' dict in schema '%s' for '%s'!" % (key, self.app_name)
        self.check_error_message(TankError, expected_msg, validate_schema, self.app_name, schema)
        
        # Test bad item in "items"
        dict_value = {"type":"dict","items":{"bogus":"bogus"}}
        schema = {key:dict_value}
        
        expected_msg = "Invalid 'bogus' dict in schema '%s' for '%s'" % (key, self.app_name)
        self.check_error_message(TankError, expected_msg, validate_schema, self.app_name, schema)
    
    def test_template_invalid_schema(self):
        # Test bad type for "required_fields"
        key = "test_setting"
        dict_value = {"type":"template","required_fields":"bogus"}
        schema = {key:dict_value}

        expected_msg = "Invalid 'required_fields' list in schema '%s' for '%s'!" % (key, self.app_name)
        self.check_error_message(TankError, expected_msg, validate_schema, self.app_name, schema)

        # Test bad value in "required_fields" list
        dict_value = {"type":"template","required_fields":["bogus",123]}
        schema = {key:dict_value}

        expected_msg = "Invalid 'required_fields' value '123' in schema '%s' for '%s'!" % (key, self.app_name)
        self.check_error_message(TankError, expected_msg, validate_schema, self.app_name, schema)
        
        # Test bad type for "optional_fields"
        dict_value = {"type":"template","optional_fields":"bogus"}
        schema = {key:dict_value}

        expected_msg = "Invalid 'optional_fields' list in schema '%s' for '%s'!" % (key, self.app_name)
        self.check_error_message(TankError, expected_msg, validate_schema, self.app_name, schema)
        
        # Test bad value in "optional_fields" list
        dict_value = {"type":"template","optional_fields":["bogus",123]}
        schema = {key:dict_value}

        expected_msg = "Invalid 'optional_fields' value '123' in schema '%s' for '%s'!" % (key, self.app_name)
        self.check_error_message(TankError, expected_msg, validate_schema, self.app_name, schema)

        # Test bad type for "allows_empty" key
        list_value = {"type":"template","values":{},"allows_empty":"bogus"}
        schema = {key:list_value}

        expected_msg = "Invalid 'allows_empty' bool in schema '%s' for '%s'!" % (key, self.app_name)
        self.check_error_message(TankError, expected_msg, validate_schema, self.app_name, schema)


class TestValidateSettings(TankTestBase):
    def setUp(self):
        super(TestValidateSettings, self).setUp()
        # set up data so as to supply a valid context
        seq = {"type":"Sequence", "name":"seq_name", "id":3}
        seq_path = os.path.join(self.project_root, "sequence/Seq")
        self.add_production_path(seq_path, seq)
        shot = {"type":"Shot",
                "name": "shot_name",
                "id":2,
                "project": self.project}
        shot_path = os.path.join(seq_path, "shot_code")
        self.add_production_path(shot_path, shot)
        # a second shot path without sequence
        shot_path_2 = os.path.join(self.project_root, "shot_code")
        self.add_production_path(shot_path_2, shot)

        # setup context with values for project and shot
        self.context = self.tk.context_from_path(shot_path)

        # The validation code needs a name for error reporting
        self.app_name = "test_app"

        # keys for templates
        self.keys = {"Sequence": StringKey("Sequence"),
                     "Shot": StringKey("Shot")}

    def test_value_type_doesnt_match_schema(self):
        key = "test_setting"
        settings = {key:99}
        schema = {key:{"type":"str"}}


        params = (key, self.app_name, "int", "str")
        expected_msg = "Invalid type for value in setting '%s' for '%s' - found '%s', expected '%s'" % params
        self.check_error_message(TankError, expected_msg, validate_settings, self.app_name, self.tk, self.context, schema, settings)

        settings = {key:None}

        params = (key, self.app_name, "NoneType", "str")
        expected_msg = "Invalid type for value in setting '%s' for '%s' - found '%s', expected '%s'" % params
        self.check_error_message(TankError, expected_msg, validate_settings, self.app_name, self.tk, self.context, schema, settings)

    def test_required_field_missing(self):
        settings = {}
        key = "some_name"
        schema = {key:{"type":"str"}}

        expected_msg = "Could not determine value for key '%s' in settings! No specified value and no default value." % key
        self.check_error_message(TankError, expected_msg, validate_settings, self.app_name, self.tk, self.context, schema, settings)

    def test_hook_does_not_exist(self):
        hook_name = "hook_fake"
        hook_value = "no_such_file"
        tk = None
        settings = {hook_name:hook_value}
        schema = {hook_name:{"type":"hook"}}
        hooks_location = os.path.join(self.pipeline_config_root, "config", "hooks")

        self.assertRaises(TankError, validate_settings, self.app_name, self.tk, self.context, schema, settings)

    def test_invalid_hook_syntax(self):

        hook_name = "hook_bad_synax"
        hook_value = "{config}/tmp_hook.py:default"

        # make sure the fake hook exists on disk so that it passes the exists check
        hooks_dir = os.path.join(
            self.pipeline_config_root,
            "config",
            "hooks",
        )
        os.makedirs(hooks_dir)
        hooks_file = os.path.join(hooks_dir, "tmp_hook.py")
        open(hooks_file, 'a').close()

        settings = {hook_name:hook_value}
        schema = {hook_name:{"type":"hook"}}

        self.assertRaises(TankError, validate_settings, self.app_name, self.tk, self.context, schema, settings)

    def test_template_missing_in_mastertemplates(self):
        """Test that template refered to in config exists in Tank instances templates attrubute."""
        # Tank instance with no templates
        self.tk.templates = {}
        # name of template in config
        config_name = "this_template"
        # actual name of template
        cfg_val = "template name"
        # config from environment
        settings = {config_name: cfg_val}
        # set up metadata about entry
        schema = {config_name:{"type":"template"}}

        expected_msg = ("The Template '%s' referred to by the setting '%s' does "
                        "not exist in the master template config file!" % (cfg_val, config_name))
        self.check_error_message(TankError, expected_msg, validate_settings, self.app_name, self.tk, self.context, schema, settings)

    def test_required_fields_not_in_template_keys(self):
        """Test that fields designated as required in the config exist as keys of the template."""
        template = tank.template.TemplatePath("{Shot}/work", self.keys, self.project_root)
        cfg_val = "template name"
        self.tk.templates = {cfg_val: template}
        
        # set up environment config
        config_name = "this_template"
        config = {config_name: cfg_val}
        
        # set up meta data
        required = ["required_field"]
        config_data = {"type":"template", "required_fields": required}
        schema = {config_name: config_data}

        expected_msg = ("The Template '%s' referred to by the setting '%s' does "
                        "not contain required fields '%s'!" % (cfg_val, config_name, required))
        self.check_error_message(TankError, expected_msg, validate_settings, self.app_name, self.tk, self.context, schema, config)

    def test_required_field_missing_in_dict(self):
        key = "some_name"
        missing_key = "some_key"
        schema = {
            key: {
                "type": "dict",
                "items": {
                    missing_key: { "type": "str" }
                }
            }
        }
        settings = {key:{}}

        params = (missing_key,key,self.app_name)
        expected_msg = "Missing required key '%s' in setting '%s' for '%s'" % params
        self.check_error_message(TankError, expected_msg, validate_settings, self.app_name, self.tk, self.context, schema, settings)

    def test_skip_validate_context(self):
        """Test that required templates with the skip validate flag set to true will not validate against the context."""
        # non-path template
        template = tank.template.TemplatePath("name-{Shot}-somthing", self.keys, self.project_root)
        cfg_val = "template name"
        self.tk.templates={cfg_val: template}
        # set up environment config
        config_name = "this_template"
        config = {config_name: cfg_val}
        # set up meta data
        config_data = {"type":"template", "required_fields": [], "validate_context":False}
        schema = {config_name:config_data}

        # If no error, success
        validate_settings(self.app_name, self.tk, self.context, schema, config)

    def test_list_good_values(self):
        key = "test_setting"
        bad_type = "bogus" 
        list_value = {"type":"list","allows_empty":True,"values":{"type":"str"}}
        schema = {key:list_value}
        settings = {key:[]}

        # Test an empty list with allows_empty=True
        validate_settings(self.app_name, self.tk, self.context, schema, settings)

        # Test data type validation of list values
        settings = {key:["a","b"]}
        validate_settings(self.app_name, self.tk, self.context, schema, settings)

        # Test a list inside list
        list_value = {"type":"list","values":{"type":"list","values":{"type":"int"}}}
        schema = {key:list_value}
        settings = {key:[[123],[234,345]]}

        validate_settings(self.app_name, self.tk, self.context, schema, settings)

    def test_list_bad_values(self):
        key = "test_setting"
        list_value = {"type":"list","values":{"type":"str"}}
        schema = {key:list_value}
        settings = {key:[]}

        # Test that a list can't be empty
        expected_msg = "The list in setting '%s' for '%s' can not be empty!" % (key, self.app_name)
        self.check_error_message(TankError, expected_msg, validate_settings, self.app_name, self.tk, self.context, schema, settings)

        # Test data type validation of list values
        settings = {key:[99,123]}

        params = (key, self.app_name, "int", "str")
        expected_msg = "Invalid type for value in setting '%s' for '%s' - found '%s', expected '%s'" % params
        self.check_error_message(TankError, expected_msg, validate_settings, self.app_name, self.tk, self.context, schema, settings)

        # Test a list inside list
        list_value = {"type":"list","values":{"type":"list","values":{"type":"int"}}}
        schema = {key:list_value}
        settings = {key:[["a"],["b","c"]]}

        params = (key, self.app_name, "str", "int")
        expected_msg = "Invalid type for value in setting '%s' for '%s' - found '%s', expected '%s'" % params
        self.check_error_message(TankError, expected_msg, validate_settings, self.app_name, self.tk, self.context, schema, settings)

    def test_template_allows_empty(self):
        key = "test_setting"
        schema = {key: {"type": "template", "allows_empty": True}}
        settings = {key: None}
        params = (key, self.app_name, "NoneType", "template")
        expected_msg = "Invalid type for value in setting '%s' for '%s' - found '%s', expected '%s'" % params

        # Test a None template with allows_empty=True
        validate_settings(self.app_name, self.tk, self.context, schema, settings)

        # Test a None template with allows_empty=False
        schema = {key: {"type": "template", "allows_empty": False}}
        self.check_error_message(TankError, expected_msg, validate_settings, self.app_name, self.tk, self.context, schema, settings)

        # Test a None template with default/unspecified allows_empty (should default to False)
        schema = {key: {"type": "template"}}
        self.check_error_message(TankError, expected_msg, validate_settings, self.app_name, self.tk, self.context, schema, settings)


class TestValidateContext(TankTestBase):
    """Tests related to validating context through the config.validate_and_populate_config function. 

    These tests are seperated so as to enable different setup.
    """
    def setUp(self):
        super(TestValidateContext, self).setUp()
        self.setup_fixtures()

        self.app_name = "test_app"
        self.template_name = "template_name"
        self.config_name = "template_config_name"
        self.config = {self.config_name: self.template_name}
        # set up test data with single sequence and shot
        seq = {"type":"Sequence", "name":"seq_name", "id":3}
        seq_path = os.path.join(self.project_root, "sequence/Seq")
        self.add_production_path(seq_path, seq)
        shot = {"type":"Shot",
                "name": "shot_name",
                "id":2,
                "project": self.project}
        shot_path = os.path.join(seq_path, "shot_code")
        self.add_production_path(shot_path, shot)
        # a second shot path without sequence
        shot_path_2 = os.path.join(self.project_root, "shot_code")
        self.add_production_path(shot_path_2, shot)

        # setup context with values for project and shot
        self.context = self.tk.context_from_path(shot_path)
        
        # Template to metadata
        self.metadata = {self.config_name:{"type":"template", "required_fields":[]}}

        # keys for templates
        self.keys = {"Sequence": StringKey("Sequence"),
                     "Shot": StringKey("Shot")}

    def test_required_fields(self):
        """
        Fields listed as required do not need to be specified in the context.
        """
        # template with fields not in required fields or context
        field_name = "field_1"
        self.keys[field_name] = StringKey(field_name)
        template = tank.template.TemplatePath("{%s}" % field_name, self.keys, self.project_root)
        
        # tank instance with this template
        self.tk.templates={self.template_name:template}
        
        # add field to required list in meta data
        self.metadata[self.config_name]["required_fields"] = [field_name]

        # If no error, then success
        validate_settings(self.app_name, self.tk, self.context, self.metadata, self.config)

    def test_fields_from_context(self):
        """
        Case that a template's fields that are not part of the metadata's 
        required fields have value in the context.
        """
        # template with fields matching context attributes
        field_name = "Shot"

        template = tank.template.TemplatePath("{%s}" % field_name, self.keys, self.project_root)
        # tank instance with this template
        self.tk.templates={self.template_name:template}
        
        # If no error, then success
        validate_settings(self.app_name, self.tk, self.context, self.metadata, self.config)

    def test_context_missing_fields(self):
        """
        Case that a template's fields(keys) that are not part of the metadata's 
        required fields are have no value in the context.
        """
        # template with fields not in required fields or context
        field_name = "field_2"
        self.keys[field_name] = StringKey(field_name)
        self.keys["sppk"] = StringKey("sppk")
        template = tank.template.TemplatePath("{%s}{sppk}" % field_name, self.keys, self.project_root)
        # tank instance with this template
        self.tk.templates={self.template_name:template}
        
        expected_msg = "Context %s can not determine value for fields %s needed by template %s" % (self.context, ["sppk"], template)

        self.check_error_message(TankError, 
                                 expected_msg, 
                                 validate_settings, 
                                 self.app_name, 
                                 self.tk, 
                                 self.context, 
                                 self.metadata, 
                                 self.config)
        
    def test_context_determines_fields(self):
        """
        Case that field has no direct value in the context, but does have a value
        when calling Context.as_template_fields.
        """
        # template with fields not in required fields or context's attributes
        field_name = "Sequence"
        template = tank.template.TemplatePath("sequence/{%s}" % field_name, self.keys, self.project_root)
        # tank instance with this template
        self.tk.templates={self.template_name:template}
        
        # If no error, then success
        validate_settings(self.app_name, 
                          self.tk, 
                          self.context, 
                          self.metadata, 
                          self.config)

    def test_default_values_detected(self):
        """
        Case that field's value cannot be determined by the context, but field has a default value.
        """
        # template with field with default value
        field_name = "field_1"
        self.keys[field_name] = StringKey(field_name, default="default")

        template = tank.template.TemplatePath("{%s}" % field_name, self.keys, self.project_root)
        # tank instance with this template
        self.tk.templates={self.template_name:template}
        
        # If no error, then success
        validate_settings(self.app_name, self.tk, self.context, self.metadata, self.config)

    def test_optional_fields_in_template(self):
        """
        Case that optional fields are specified in the metadata but not available from context.
        """
        field_name = "optional_field"
        self.keys[field_name] = StringKey(field_name)
        schema = {self.config_name:{"type":"template", "required_fields":[], "optional_fields": [field_name]}}
        # Template with the optional field
        template = tank.template.TemplatePath("{%s}" % field_name, self.keys, self.project_root)
        # tank instance with this template
        self.tk.templates={self.template_name:template}
        
        # If no error, then success
        validate_settings(self.app_name, self.tk, self.context, schema, self.config)
        
    def test_optional_fields_not_in_template(self):
        """
        Case that optional fields are specified, but not available in the template.
        """
        field_name = "optional_field"
        self.keys[field_name] = StringKey(field_name)
        schema = {self.config_name:{"type":"template", "required_fields":[], "optional_fields": [field_name]}}
        # Template without the optional field
        template = tank.template.TemplatePath("{Shot}", self.keys, self.project_root)
        # tank instance with this template
        self.tk.templates={self.template_name:template}
        
        # If no error, then success
        validate_settings(self.app_name, self.tk, self.context, schema, self.config)


class TestValidateFixtures(TankTestBase):
    """Integration test running validation on test fixtures."""
    def setUp(self):
        super(TestValidateFixtures, self).setUp()
        self.setup_fixtures()

        # setup shot
        seq = {"type":"Sequence", "name":"seq_name", "id":3}
        seq_path = os.path.join(self.project_root, "sequences/Seq")
        self.add_production_path(seq_path, seq)
        shot = {"type":"Shot",
                "name": "shot_name",
                "id":2,
                "project": self.project}
        shot_path = os.path.join(seq_path, "shot_code")
        self.add_production_path(shot_path, shot)
        step = {"type":"Step", "name":"step_name", "id":4}
        self.shot_step_path = os.path.join(shot_path, "step_name")
        self.add_production_path(self.shot_step_path, step)
        
        self.test_env = "test"
        self.test_engine = "test_engine"

    def test_environment(self):
        context = self.tk.context_from_path(self.shot_step_path)
        
        env = self.tk.pipeline_configuration.get_environment(self.test_env, context)

        # make sure our tmp file exists on disk for the disk_path property
        self.test_resource = os.path.join(self.pipeline_config_root, "config", "foo", "bar.png")
        os.makedirs(os.path.dirname(self.test_resource))
        fh = open(self.test_resource, "wt")
        fh.write("test")
        fh.close()        

        for app_name in env.get_apps(self.test_engine):
            schema = env.get_app_descriptor(self.test_engine, app_name).configuration_schema
            settings = env.get_app_settings(self.test_engine, app_name)
            validate_settings(app_name, self.tk, context, schema, settings)
