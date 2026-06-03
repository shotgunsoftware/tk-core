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
        pass
class TestEq(TestContext):
    def setUp(self):
        pass
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
        pass
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
        pass
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
        pass
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
        pass
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
        pass
    ):
        """
        Test context.from_entity_dictionary - this can contruct a context from
        an entity dictionary looking at linked entities where available.

        Falls back to 'from_entity' if the entity dictionary doesn't contain
        everything needed.
        """
        get_current_user.return_value = self.current_user

        # overload from_entity to ensure it causes a test fail if from_entity_dictionary
        # falls back to it:
        from_entity.return_value = {}

        add_value = {"name": "additional", "id": 3, "type": "add_type"}
        ent_dict = {
            "type": "Task",
            "id": self.task["id"],
            "content": self.task["content"],
            "additional_field": add_value,
        }
        ent_dict["project"] = self.project
        ent_dict["entity"] = self.shot
        ent_dict["step"] = self.step

        result = context.from_entity_dictionary(self.tk, ent_dict)
        self.assertIsNotNone(result)

        self.check_entity(self.project, result.project)
        self.assertEqual(3, len(result.project))

        self.check_entity(self.shot, result.entity)
        self.assertEqual(3, len(result.entity))

        self.check_entity(self.current_user, result.user)

        self.check_entity(self.step, result.step)
        self.assertEqual(3, len(result.step))

        self.assertEqual(self.task["type"], result.task["type"])
        self.assertEqual(self.task["id"], result.task["id"])
        self.assertEqual(self.task["content"], result.task["name"])
        self.assertEqual(3, len(result.task))

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
        pass
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
        pass
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
        pass
    def test_non_primary_entity_paths(self):
        pass
    @mock.patch("tank.util.login.get_current_user")
    def test_non_primary_path(self, get_current_user):
        pass
