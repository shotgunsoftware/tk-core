import os

from tank.templatekey import StringKey
from tank_test.tank_test_base import ShotgunTestBase, TankTestBase
from tank_test.tank_test_base import setUpModule  # noqa
from tank.platform.validation import *

import tank


class TestValidateSchema(ShotgunTestBase):
    def setUp(self):
        pass
    def test_invalid_schema_type(self):
        pass
    def test_invalid_default_value(self):
        pass
    def test_list_invalid_schema(self):
        pass
    def test_dict_invalid_schema(self):
        pass
    def test_template_invalid_schema(self):
        pass
class TestValidateSettings(TankTestBase):
    def setUp(self):
        pass
    def test_value_type_doesnt_match_schema(self):
        pass
    def test_required_field_missing(self):
        pass
    def test_hook_does_not_exist(self):
        pass
    def test_invalid_hook_syntax(self):
        pass
    def test_template_missing_in_mastertemplates(self):
        pass
    def test_required_fields_not_in_template_keys(self):
        pass
    def test_required_field_missing_in_dict(self):
        pass
    def test_skip_validate_context(self):
        pass
    def test_list_good_values(self):
        pass
    def test_list_bad_values(self):
        pass
    def test_template_allows_empty(self):
        pass
class TestValidateContext(TankTestBase):
    """Tests related to validating context through the config.validate_and_populate_config function.

    These tests are seperated so as to enable different setup.
    """

    def setUp(self):
        pass
    def test_required_fields(self):
        pass
    def test_fields_from_context(self):
        pass
    def test_context_missing_fields(self):
        pass
    def test_context_determines_fields(self):
        pass
    def test_default_values_detected(self):
        pass
    def test_optional_fields_in_template(self):
        pass
    def test_optional_fields_not_in_template(self):
        pass
class TestValidateFixtures(TankTestBase):
    """Integration test running validation on test fixtures."""

    def setUp(self):
        pass
    def test_environment(self):
        pass
