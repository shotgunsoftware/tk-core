import os

from tank.templatekey import StringKey
from tank_test.tank_test_base import ShotgunTestBase, TankTestBase
from tank_test.tank_test_base import setUpModule  # noqa
from tank.platform.validation import *

import tank


class TestValidateSchema(ShotgunTestBase):
    def setUp(self):
        super().setUp()

        # The validation code needs a name for error reporting
        self.app_name = "test_app"

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
        super().setUp()
        # set up data so as to supply a valid context
        seq = {"type": "Sequence", "name": "seq_name", "id": 3}
        seq_path = os.path.join(self.project_root, "sequence/Seq")
        self.add_production_path(seq_path, seq)
        shot = {"type": "Shot", "name": "shot_name", "id": 2, "project": self.project}
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
        self.keys = {"Sequence": StringKey("Sequence"), "Shot": StringKey("Shot")}

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
        super().setUp()
        self.setup_fixtures()

        self.app_name = "test_app"
        self.template_name = "template_name"
        self.config_name = "template_config_name"
        self.config = {self.config_name: self.template_name}
        # set up test data with single sequence and shot
        seq = {"type": "Sequence", "name": "seq_name", "id": 3}
        seq_path = os.path.join(self.project_root, "sequence/Seq")
        self.add_production_path(seq_path, seq)
        shot = {"type": "Shot", "name": "shot_name", "id": 2, "project": self.project}
        shot_path = os.path.join(seq_path, "shot_code")
        self.add_production_path(shot_path, shot)
        # a second shot path without sequence
        shot_path_2 = os.path.join(self.project_root, "shot_code")
        self.add_production_path(shot_path_2, shot)

        # setup context with values for project and shot
        self.context = self.tk.context_from_path(shot_path)

        # Template to metadata
        self.metadata = {self.config_name: {"type": "template", "required_fields": []}}

        # keys for templates
        self.keys = {"Sequence": StringKey("Sequence"), "Shot": StringKey("Shot")}

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
        super().setUp()
        self.setup_fixtures()

        # setup shot
        seq = {"type": "Sequence", "name": "seq_name", "id": 3}
        seq_path = os.path.join(self.project_root, "sequences/Seq")
        self.add_production_path(seq_path, seq)
        shot = {"type": "Shot", "name": "shot_name", "id": 2, "project": self.project}
        shot_path = os.path.join(seq_path, "shot_code")
        self.add_production_path(shot_path, shot)
        step = {"type": "Step", "name": "step_name", "id": 4}
        self.shot_step_path = os.path.join(shot_path, "step_name")
        self.add_production_path(self.shot_step_path, step)

        self.test_env = "test"
        self.test_engine = "test_engine"

    def test_environment(self):
        pass
