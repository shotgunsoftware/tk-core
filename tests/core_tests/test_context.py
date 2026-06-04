# -*- coding: utf-8 -*-

# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import copy
import datetime
from sgtk.util import pickle
import json

from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import (
    mock,
    TankTestBase,
)

import tank
from tank import context
from tank.errors import TankError, TankContextDeserializationError
from tank.template import TemplatePath
from tank.templatekey import StringKey, IntegerKey
from tank_vendor import yaml
from tank.authentication import ShotgunAuthenticator

USER_NAME = "Üser Ñâme AñoVolvió JiříVyčítal"


class TestContext(TankTestBase):
    def setUp(self):
        super().setUp()

        self.keys = {
            "Sequence": StringKey("Sequence"),
            "Shot": StringKey("Shot"),
            "Step": StringKey("Step"),
            "static_key": StringKey("static_key"),
        }

        # set up test data with single sequence, shot, step and human user
        self.seq = {"type": "Sequence", "code": "seq_name", "id": 3}

        self.shot = {
            "type": "Shot",
            "code": "shot_name",
            "id": 2,
            "extra_field": "extravalue",  # used to test query from template
            "sg_sequence": self.seq,
            "project": self.project,
        }

        self.step = {"type": "Step", "code": "step_name", "id": 4}

        self.shot_alt = {
            "type": "Shot",
            "code": "shot_name_alt",
            "id": 123,
            "sg_sequence": self.seq,
            "project": self.project,
        }

        # One human user not matching the current login
        self.other_user = {
            "type": "HumanUser",
            "name": USER_NAME,
            "id": 1,
            "login": "user_login",
        }
        # One human user matching the current login
        self.current_login = tank.util.login.get_login_name()
        self.current_user = {
            "type": "HumanUser",
            "name": USER_NAME,
            "id": 2,
            "login": self.current_login,
        }

        self.seq_path = os.path.join(self.project_root, "sequence/Seq")
        self.add_production_path(self.seq_path, self.seq)
        self.shot_path = os.path.join(self.seq_path, "shot_code")
        self.add_production_path(self.shot_path, self.shot)
        self.shot_path_alt = os.path.join(self.seq_path, "shot_code_alt")
        self.add_production_path(self.shot_path_alt, self.shot_alt)
        self.step_path = os.path.join(self.shot_path, "step_short_name")
        self.add_production_path(self.step_path, self.step)
        self.other_user_path = os.path.join(self.step_path, "user_login")
        self.add_production_path(self.other_user_path, self.other_user)

        # adding a path with step as the root (step/sequence/shot)
        alt_2_step_path = "step_short_name"
        self.add_production_path(alt_2_step_path, self.step)
        alt_2_seq_path = os.path.join(alt_2_step_path, "Seq")
        self.add_production_path(alt_2_seq_path, self.seq)
        alt_2_shot_path = os.path.join(alt_2_seq_path, "shot_code")
        self.add_production_path(alt_2_shot_path, self.shot)


class TestEq(TestContext):
    def setUp(self):
        super().setUp()
        # params used in creating contexts
        self.kws = {}
        self.kws["project"] = self.project
        self.kws["entity"] = self.shot
        self.kws["step"] = self.step

    def test_equal(self):
        pass
    def test_not_equal(self):
        pass
    def test_not_equal_with_none(self):
        pass
    def test_additional_entities_equal(self):
        pass
    def test_additional_entities_not_equal(self):
        pass
    def test_not_context(self):
        pass
    @mock.patch("tank.util.login.get_current_user")
    def test_lazy_load_user(self, get_current_user):
        pass
class TestUser(TestContext):
    def setUp(self):
        super().setUp()
        kws1 = {}
        kws1["tk"] = self.tk
        kws1["project"] = self.project
        kws1["entity"] = self.shot
        kws1["step"] = self.step
        self.context = context.Context(**kws1)

    @mock.patch("tank.util.login.get_current_user")
    def test_local_login(self, get_current_user):
        pass
class TestCreateEmpty(TestContext):
    def test_empty_context(self):
        pass
class TestFromPath(TestContext):
    @mock.patch("tank.util.login.get_current_user")
    def test_shot(self, get_current_user):
        pass
    @mock.patch("tank.util.login.get_current_user")
    def test_external_path(self, get_current_user):
        pass
    def test_user_path(self):
        pass
class TestFromPathWithPrevious(TestContext):
    @mock.patch("tank.util.login.get_current_user")
    def test_shot(self, get_current_user):
        pass
class TestUrl(TestContext):
    def setUp(self):
        super().setUp()

        # Add task data to mocked shotgun
        self.task = {
            "id": 1,
            "type": "Task",
            "content": "task_content",
            "project": self.project,
            "entity": self.shot,
            "step": self.step,
        }

        self.add_to_sg_mock_db(self.task)

    def test_project(self):
        pass
    def test_empty(self):
        pass
    def test_entity(self):
        pass
    def test_task(self):
        pass
class TestStringRepresentation(TestContext):
    """
    Tests string representation of context
    """

    def setUp(self):
        super().setUp()

        # Add task data to mocked shotgun
        self.task = {
            "id": 1,
            "type": "Task",
            "content": "task_content",
            "project": self.project,
            "entity": self.shot,
            "step": self.step,
        }

        self.add_to_sg_mock_db(self.task)

    def test_site(self):
        pass
    def test_project(self):
        pass
    def test_entity_with_step(self):
        pass
    def test_entity(self):
        pass
    def test_task(self):
        pass
class TestFromEntity(TestContext):
    def setUp(self):
        super().setUp()

        # Add task data to mocked shotgun
        self.task = {
            "id": 1,
            "type": "Task",
            "content": "task_content",
            "project": self.project,
            "entity": self.shot,
            "step": self.step,
        }

        self.publishedfile = dict(
            id=2,
            type="PublishedFile",
            project=self.project,
            entity=self.shot,
            task=self.task,
        )

        self.add_to_sg_mock_db(self.task)
        self.add_to_sg_mock_db(self.publishedfile)

    @mock.patch("tank.util.login.get_current_user")
    def test_from_linked_entity_types(self, get_current_user):
        pass
    @mock.patch("tank.util.login.get_current_user")
    def test_entity_from_cache(self, get_current_user):
        pass
    @mock.patch("tank.util.login.get_current_user")
    def test_step_higher_entity(self, get_current_user):
        pass
    @mock.patch("tank.util.login.get_current_user")
    def test_task_from_sg(self, get_current_user):
        pass
    @mock.patch("tank.util.login.get_current_user")
    def test_data_missing_non_task(self, get_current_user):
        pass
    def test_data_missing_task(self):
        pass
    @mock.patch("tank.context.from_entity")
    @mock.patch("tank.util.login.get_current_user")
    def test_from_entity_dictionary(self, get_current_user, from_entity):
        pass
    @mock.patch("tank.context.from_entity")
    @mock.patch("tank.util.login.get_current_user")
    def test_from_entity_dictionary_additional_entities(
        self, get_current_user, from_entity
    ):
        pass
    def check_entity(self, first_entity, second_entity, check_name=True):
        "Checks two entity dictionaries have the same values for keys type, id and name."
        self.assertEqual(first_entity["type"], second_entity["type"])
        self.assertEqual(first_entity["id"], second_entity["id"])
        if check_name:
            self.assertEqual(first_entity["name"], second_entity["name"])

    def test_bad_entities(self):
        pass
class TestAsTemplateFields(TestContext):
    def setUp(self):
        super().setUp()
        # create a context obj using predefined data
        kws = {}
        kws["tk"] = self.tk
        kws["project"] = self.project
        kws["entity"] = self.shot
        kws["step"] = self.step
        self.ctx = context.Context(**kws)

        # create a template with which to filter
        self.keys = {
            "Sequence": StringKey("Sequence"),
            "Shot": StringKey("Shot"),
            "Step": StringKey("Step"),
            "static_key": StringKey("static_key"),
            "shotgun_field": StringKey(
                "shotgun_field",
                shotgun_entity_type="Shot",
                shotgun_field_name="shotgun_field",
            ),
        }

        template_def = "/sequence/{Sequence}/{Shot}/{Step}/work"
        self.template = TemplatePath(template_def, self.keys, self.project_root)

    def test_bad_path_cache_entry(self):
        pass
    def test_validate_parameter(self):
        pass
    def test_query_from_template(self):
        pass
    def test_step_first_template(self):
        pass
    @mock.patch(
        "tank.context.Context._get_project_roots",
        return_value=["{0}{0}foo{0}bar".format(os.path.sep)],
    )
    @mock.patch(
        "tank.context.Context.entity_locations",
        new_callable=mock.PropertyMock(
            return_value=["{0}{0}foo{0}bar{0}baz".format(os.path.sep)]
        ),
    )
    def test_fields_from_entity_paths_with_unc_project_root(self, *args):
        pass
    def test_entity_field_query(self):
        pass
    def test_template_query_invalid(self):
        pass
    def test_template_query_none(self):
        pass
    def test_query_cached(self):
        pass
    def test_shot_step(self):
        pass
    def test_double_step(self):
        pass
    def test_list_field_step_above_entity(self):
        pass
    def test_non_context(self):
        pass
    def test_static(self):
        pass
    def test_static_ambiguous(self):
        pass
    def test_multifield_leaf(self):
        pass
    def test_multifield_intermediate(self):
        pass
    def test_ambiguous_entity_location(self):
        pass
    def test_template_without_entity(self):
        pass
    def test_user_ctx(self):
        pass
    def test_missing_shotgun_field(self):
        pass
class TestSerialize(TestContext):
    def setUp(self):
        super().setUp()
        # params used in creating contexts
        # Add data to mocked shotgun
        self.task = self.mockgun.create(
            "Task",
            {
                "content": "task_content",
                "project": self.project,
                "entity": self.shot,
                "step": self.step,
            },
        )

        self.version = self.mockgun.create(
            "Version", {"code": "version_code", "project": self.project}
        )

        self.user = self.mockgun.create("HumanUser", {"name": USER_NAME})

        self.kws = {}
        self.kws["tk"] = self.tk
        self.kws["project"] = self.project
        self.kws["entity"] = self.shot
        self.kws["step"] = self.step
        self.kws["task"] = self.task
        # FIXME: Mockgun does not properly set the name field on a
        # Task so pass it in.
        self.kws["task"]["name"] = "task_content"
        self.kws["user"] = self.user
        self.kws["additional_entities"] = [self.seq]
        self.kws["source_entity"] = self.version

        # self._auth_user differs from self.kws["user"], because self._auth_user
        # is the user we are authenticated as when talking to Shotgun
        # while self.kws["user"] is the user associated with the current
        # context.
        self._auth_user = ShotgunAuthenticator().create_script_user(
            "script_user", "script_key", "https://abc.shotgunstudio.com"
        )

    def test_from_dict(self):
        pass
    def test_dict_cleanup(self):
        pass
    def test_equal_yml(self):
        pass
    def test_equal_custom(self):
        pass
    def _assert_same_user(self, user_1, user_2):
        """
        Asserts that the two users are both script users with the same name.
        """
        self.assertEqual(user_1.impl.get_script(), user_2.impl.get_script())

    def test_serialize_with_user(self):
        pass
    def test_serialize_with_user_using_json(self):
        pass
    def test_serialize_without_user(self):
        pass
    def test_serialize_to_dict(self):
        pass
    def _assert_equal_contexts(self, ctx_1, ctx_2):
        """
        Ensures two contexts are equal.
        Note that source_entity is not part of the equality comparison,
        but since we're interested into making sure everything gets serialized
        property we'll add the value there.
        """
        self.assertEqual(ctx_1, ctx_2)
        # Context equality (__eq__) only considers the entity type and id.
        # However, source_entity is not included in that check,
        # so we explicitly compare it to ensure full fidelity after serialization.
        self.assertEqual(ctx_1.source_entity["type"], ctx_2.source_entity["type"])
        self.assertEqual(ctx_1.source_entity["id"], ctx_2.source_entity["id"])

    def test_deserialized_invalid_data(self):
        pass
class TestMultiRoot(TestContext):
    def setUp(self):
        super().setUp()

        self.setup_multi_root_fixtures()

        # adding shot path with alternate root
        seq_path = os.path.join(self.alt_root_1, "sequence/Seq")
        self.add_production_path(seq_path, self.seq)
        self.alt_1_shot_path = os.path.join(seq_path, "shot_code")
        self.add_production_path(self.alt_1_shot_path, self.shot)
        self.alt_1_step_path = os.path.join(self.alt_1_shot_path, "step_short_name")
        self.add_production_path(self.alt_1_step_path, self.step)
        self.alt_1_other_user_path = os.path.join(self.alt_1_step_path, "user_login")
        self.add_production_path(self.alt_1_other_user_path, self.other_user)

    def test_non_primary_entity_paths(self):
        pass
    @mock.patch("tank.util.login.get_current_user")
    def test_non_primary_path(self, get_current_user):
        pass
