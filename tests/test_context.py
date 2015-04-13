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

from tank_test.tank_test_base import *

from mock import Mock, patch

from tank import context
from tank.errors import TankError
from tank.template import TemplatePath
from tank.templatekey import StringKey, IntegerKey
from tank_vendor import yaml


class  TestContext(TankTestBase):
    def setUp(self):
        super(TestContext, self).setUp()
        self.setup_multi_root_fixtures()


        self.keys = {"Sequence": StringKey("Sequence"),
                     "Shot": StringKey("Shot"),
                     "Step": StringKey("Step"),
                     "static_key": StringKey("static_key")}

        # set up test data with single sequence, shot, step and human user
        self.seq = {"type":"Sequence", "code":"seq_name", "id":3}
        
        self.shot = {"type":"Shot",
                    "code": "shot_name",
                    "id":2,
                    "extra_field": "extravalue", # used to test query from template
                    "sg_sequence": self.seq,
                    "project": self.project}
        self.step = {"type":"Step", "name": "step_name", "id": 4}

        # One human user not matching the current login
        self.other_user = {"type":"HumanUser", "name":"user_name", "id":1, "login": "user_login"}
        # One human user matching the current login
        self.current_login = tank.util.login.get_login_name()
        self.current_user = {"type":"HumanUser", "name":"user_name", "id":2, "login": self.current_login}
        
        self.seq_path = os.path.join(self.project_root, "sequence/Seq")
        self.add_production_path(self.seq_path, self.seq)
        self.shot_path = os.path.join(self.seq_path, "shot_code")
        self.add_production_path(self.shot_path, self.shot)
        self.step_path = os.path.join(self.shot_path, "step_short_name")
        self.add_production_path(self.step_path, self.step)
        self.other_user_path = os.path.join(self.step_path, "user_login")
        self.add_production_path(self.other_user_path, self.other_user)

        # adding shot path with alternate root 
        seq_path = os.path.join(self.alt_root_1, "sequence/Seq")
        self.add_production_path(seq_path, self.seq)
        self.alt_1_shot_path = os.path.join(seq_path, "shot_code")
        self.add_production_path(self.alt_1_shot_path, self.shot)
        self.alt_1_step_path = os.path.join(self.alt_1_shot_path, "step_short_name")
        self.add_production_path(self.alt_1_step_path, self.step)
        self.alt_1_other_user_path = os.path.join(self.alt_1_step_path, "user_login")
        self.add_production_path(self.alt_1_other_user_path, self.other_user)

        # adding a path with step as the root (step/sequence/shot)
        alt_2_step_path = "step_short_name"
        self.add_production_path(alt_2_step_path, self.step)
        alt_2_seq_path = os.path.join(alt_2_step_path, "Seq")
        self.add_production_path(alt_2_seq_path, self.seq)
        alt_2_shot_path = os.path.join(alt_2_seq_path, "shot_code")
        self.add_production_path(alt_2_shot_path, self.shot)


class TestEq(TestContext):
    def setUp(self):
        super(TestEq, self).setUp()
        # params used in creating contexts
        self.kws = {}
        self.kws["project"] = self.project
        self.kws["entity"] = self.shot
        self.kws["step"] = self.step

    def test_equal(self):
        kws1 = copy.deepcopy(self.kws)
        kws1["entity"]["foo"] = "foo"
        context_1 = context.Context(self.tk, **kws1)
        kws2 = copy.deepcopy(self.kws)
        # other differing fields in the dictionary should be ignored
        kws2["entity"]["foo"] = "bar"
        context_2 = context.Context(self.tk, **kws2)
        self.assertTrue(context_1 == context_2)
        self.assertFalse(context_1 != context_2)

    def test_not_equal(self):
        context_1 = context.Context(self.tk, **self.kws)
        kws2 = copy.deepcopy(self.kws)
        kws2["task"] = {"id":45, "type": "Task"}
        context_2 = context.Context(self.tk, **kws2)
        self.assertFalse(context_1 == context_2)
        self.assertTrue(context_1 != context_2)

    def test_not_equal_with_none(self):
        context_1 = context.Context(self.tk, **self.kws)
        kws2 = copy.deepcopy(self.kws)
        kws2["entity"] = None
        context_2 = context.Context(self.tk, **kws2)
        self.assertFalse(context_1 == context_2)
        self.assertTrue(context_1 != context_2)

    def test_additional_entities_equal(self):
        kws1 = copy.deepcopy(self.kws)
        kws1["additional_entities"] = [
            {"type":"Asset", "id":123, "foo":"bar"}, 
            {"type":"Sequence", "id":456, "foo":"bar"}
        ]
        context_1 = context.Context(self.tk, **kws1)
        kws2 = copy.deepcopy(self.kws)
        kws2["additional_entities"] = [
            # Only type & id difference should matter
            {"type":"Sequence", "id":456, "bar":"foo"},
            {"type":"Asset", "id":123, "bar":"foo"},
            # None entries should be ignored
            None,
            # and ok to have the same entity twice
            {"type":"Sequence", "id":456, "bar":"foo"}
        ]
        context_2 = context.Context(self.tk, **kws2)
        self.assertTrue(context_1 == context_2)
        self.assertFalse(context_1 != context_2)

    def test_additional_entities_not_equal(self):
        kws1 = copy.deepcopy(self.kws)
        kws1["additional_entities"] = [
            {"type":"Asset", "id":123}, 
            {"type":"Sequence", "id":456}
        ]
        context_1 = context.Context(self.tk, **kws1)
        kws2 = copy.deepcopy(self.kws)
        kws1["additional_entities"] = [
            {"type":"Asset", "id":789},
            {"type":"Sequence", "id":456}
        ]
        context_2 = context.Context(self.tk, **kws2)
        self.assertFalse(context_1 == context_2)
        self.assertTrue(context_1 != context_2)
        
    def test_not_context(self):
        context_1 = context.Context(self.tk, **self.kws)
        not_context = object()
        self.assertFalse(context_1 == not_context)
        self.assertTrue(context_1 != not_context)

    @patch("tank.util.login.get_current_user")
    def test_lazy_load_user(self, get_current_user):
        
        get_current_user.return_value = self.current_user
        
        # bug ticket 20272
        context_1 = context.Context(self.tk, **self.kws)
        kws2 = self.kws.copy()
        # force seed the user for one of the contexts 
        kws2["user"] = {"id": self.current_user["id"], 
                        "type": self.current_user["type"], 
                        "name": self.current_user["name"]} 
        # the other context should pick up the context
        # automatically by the equals operator
        context_2 = context.Context(self.tk, **kws2)
        self.assertTrue(context_1 == context_2)
        self.assertFalse(context_1 != context_2)

class TestUser(TestContext):
    def setUp(self):
        super(TestUser, self).setUp()
        kws1 = {}
        kws1["tk"] = self.tk
        kws1["project"] = self.project
        kws1["entity"] = self.shot
        kws1["step"] = self.step
        self.context = context.Context(**kws1)

    @patch("tank.util.login.get_current_user")
    def test_local_login(self, get_current_user):
        """
        Test that if user is not supplied, the human user matching the
        local login is used.
        """
        
        get_current_user.return_value = self.current_user
        
        self.assertEquals(self.current_user["id"], self.context.user["id"])
        self.assertEquals(self.current_user["type"], self.context.user["type"])
        self.assertEquals(len(self.context.user), 3)

class TestCreateEmpty(TestContext):
    def test_empty_context(self):
        empty_context = context.Context(self.tk)
        result = context.create_empty(self.tk)
        self.assertTrue(empty_context, result)


class TestFromPath(TestContext):

    @patch("tank.util.login.get_current_user")
    def test_shot(self, get_current_user):
        
        get_current_user.return_value = self.current_user
        shot_path_abs = os.path.join(self.project_root, self.shot_path)
        result = self.tk.context_from_path(shot_path_abs)

        # check context's attributes
        self.assertEquals(self.shot["id"], result.entity["id"])
        self.assertEquals(self.shot["type"], result.entity["type"])
        self.assertEquals(self.project["id"], result.project["id"])
        self.assertEquals(self.project["type"], result.project["type"])
        self.assertEquals(self.current_user["id"], result.user["id"])
        self.assertEquals(self.current_user["type"], result.user["type"])
        self.assertIsNone(result.step)
        self.assertIsNone(result.task)

    @patch("tank.util.login.get_current_user")
    def test_external_path(self, get_current_user):
        get_current_user.return_value = self.current_user
        shot_path_abs = os.path.abspath(os.path.join(self.project_root, ".."))
        result = self.tk.context_from_path(shot_path_abs)
        # check context's attributes
        self.assertEquals(self.current_user["id"], result.user["id"])
        self.assertEquals(self.current_user["type"], result.user["type"])
        self.assertIsNone(result.entity)
        self.assertIsNone(result.task)
        self.assertIsNone(result.step)
        self.assertIsNone(result.project)


    @patch("tank.util.login.get_current_user")
    def test_non_primary_path(self, get_current_user):
        """Check that path which is not child of primary root create context."""
        get_current_user.return_value = self.current_user
        
        result = self.tk.context_from_path(self.alt_1_shot_path)
        # check context's attributes
        self.assertEquals(self.shot["id"], result.entity["id"])
        self.assertEquals(self.shot["type"], result.entity["type"])
        self.assertEquals(self.project["id"], result.project["id"])
        self.assertEquals(self.project["type"], result.project["type"])
        self.assertEquals(self.current_user["id"], result.user["id"])
        self.assertEquals(self.current_user["type"], result.user["type"])

        self.assertIsNone(result.step)
        self.assertIsNone(result.task)

    def test_user_path(self):
        """Check other_user is set when contained in the path."""
        result = self.tk.context_from_path(self.other_user_path)
        

        # check context's attributes
        self.assertEquals(self.shot["id"], result.entity["id"])
        self.assertEquals(self.shot["type"], result.entity["type"])
        self.assertEquals(self.project["id"], result.project["id"])
        self.assertEquals(self.project["type"], result.project["type"])
        self.assertEquals(self.step["id"], result.step["id"])
        self.assertEquals(self.step["type"], result.step["type"])
        self.assertEquals(self.other_user["id"], result.user["id"])
        self.assertEquals(self.other_user["type"], result.user["type"])
        
        self.assertIsNone(result.task)



class TestFromPathWithPrevious(TestContext):

    @patch("tank.util.login.get_current_user")
    def test_shot(self, get_current_user):

        get_current_user.return_value = self.current_user
        
        # Add data to mocked shotgun
        self.task = {"id": 1,
                     "type": "Task",
                     "content": "task_content",
                     "project": self.project,
                     "entity": self.shot,
                     "step": self.step}
        
        self.add_to_sg_mock_db(self.task)
        
        
        prev_ctx = context.from_entity(self.tk, self.task["type"], self.task["id"])


        shot_path_abs = os.path.join(self.project_root, self.shot_path)
        result = self.tk.context_from_path(shot_path_abs, prev_ctx)

        # check context's attributes
        self.assertEquals(self.shot["id"], result.entity["id"])
        self.assertEquals(self.shot["type"], result.entity["type"])
        self.assertEquals(self.project["id"], result.project["id"])
        self.assertEquals(self.project["type"], result.project["type"])
        self.assertEquals("Step", result.step["type"])
        self.assertEquals(self.step["id"], result.step["id"])
        self.assertEquals("Task", result.task["type"])
        self.assertEquals(self.task["id"], result.task["id"])
        self.assertEquals(self.current_user["id"], result.user["id"])
        self.assertEquals(self.current_user["type"], result.user["type"])


class TestUrl(TestContext):

    def setUp(self):
        super(TestUrl, self).setUp()

        # Add task data to mocked shotgun
        self.task = {"id": 1,
                     "type": "Task",
                     "content": "task_content",
                     "project": self.project,
                     "entity": self.shot,
                     "step": self.step}
        
        self.add_to_sg_mock_db(self.task)

    def test_project(self):
        result =  context.from_entity(self.tk, self.project["type"], self.project["id"])
        self.assertEquals(result.shotgun_url, "http://unit_test_mock_sg/detail/Project/1" )

    def test_empty(self):
        result =  context.create_empty(self.tk)
        self.assertEquals(result.shotgun_url, "http://unit_test_mock_sg" )

    def test_entity(self):
        result =  context.from_entity(self.tk, self.shot["type"], self.shot["id"])
        self.assertEquals(result.shotgun_url, "http://unit_test_mock_sg/detail/Shot/2" )
        
    def test_task(self):
        """
        Case that all data is found from shotgun query
        Note that additional field is specified in a
        context_additional_entities hook.
        """
        # add additional field value to task
        add_value = {"name":"additional", "id": 3, "type": "add_type"}
        self.task["additional_field"] = add_value
        
        result = context.from_entity(self.tk, self.task["type"], self.task["id"])
        self.assertEquals(result.shotgun_url, "http://unit_test_mock_sg/detail/Task/1" )


class TestFromEntity(TestContext):

    def setUp(self):
        super(TestFromEntity, self).setUp()

        # Add task data to mocked shotgun
        self.task = {"id": 1,
                     "type": "Task",
                     "content": "task_content",
                     "project": self.project,
                     "entity": self.shot,
                     "step": self.step}
        
        self.add_to_sg_mock_db(self.task)

    
        

    @patch("tank.util.login.get_current_user")
    def test_entity_from_cache(self, get_current_user):
        
        get_current_user.return_value = self.current_user
        
        result =  context.from_entity(self.tk, self.shot["type"], self.shot["id"])

        self.check_entity(self.project, result.project)
        self.assertEquals(3, len(result.project))

        self.check_entity(self.shot, result.entity)
        self.assertEquals(3, len(result.entity))
                
        self.check_entity(self.current_user, result.user)

        self.assertEquals(None, result.task)
        
        self.check_entity(self.step, result.step)
        self.assertEquals(3, len(result.step))

    
    @patch("tank.util.login.get_current_user")
    def test_step_higher_entity(self, get_current_user):
        """
        Case that step appears in path above entity.
        """
        
        get_current_user.return_value = self.current_user
        
        # Add shot below step
        step_path = os.path.join(self.seq_path, "step_short_name")
        shot_path = os.path.join(step_path, "shot_code")
        self.add_production_path(step_path, self.step)
        self.add_production_path(shot_path, self.shot)

        result =  context.from_entity(self.tk, self.shot["type"], self.shot["id"])
        self.check_entity(self.step, result.step)
        self.check_entity(self.shot, result.entity)
        self.check_entity(self.current_user, result.user)

    @patch("tank.util.login.get_current_user")
    def test_task_from_sg(self, get_current_user):
        """
        Case that all data is found from shotgun query
        Note that additional field is specified in a
        context_additional_entities hook.
        """
        get_current_user.return_value = self.current_user
        
        # add additional field value to task
        add_value = {"name":"additional", "id": 3, "type": "add_type"}
        self.task["additional_field"] = add_value
        
        # store the find call count
        num_finds_before = self.tk.shotgun.finds

        result = context.from_entity(self.tk, self.task["type"], self.task["id"])
        self.check_entity(self.project, result.project)
        self.assertEquals(3, len(result.project))

        self.check_entity(self.shot, result.entity)
        self.assertEquals(3, len(result.entity))

        self.check_entity(self.step, result.step)
        self.assertEquals(3, len(result.step))

        self.check_entity(self.current_user, result.user)

        self.assertEquals(self.current_user["id"], result.user["id"])
        self.assertEquals(self.current_user["type"], result.user["type"])

        self.assertEquals(self.task["type"], result.task["type"])
        self.assertEquals(self.task["id"], result.task["id"])
        self.assertEquals(self.task["content"], result.task["name"])
        self.assertEquals(3, len(result.task))

        add_result = result.additional_entities[0]
        self.check_entity(add_value, add_result)

        # Check that the shotgun method find_one was used
        num_finds_after = self.tk.shotgun.finds
        self.assertTrue( (num_finds_after-num_finds_before) == 1 )


    @patch("tank.util.login.get_current_user")
    def test_data_missing_non_task(self, get_current_user):
        """
        Case that entity does not exist on local cache or in shotgun
        """
        get_current_user.return_value = self.current_user
        
        # Use entity we have not setup in path cache not in mocked sg
        shot = {"type": "Shot", "id": 13, "name": "never_seen_me_before"}
        result = context.from_entity(self.tk, shot["type"], shot["id"])

        self.assertEquals(shot["id"], result.entity["id"])
        self.assertEquals(shot["type"], result.entity["type"])
        self.check_entity(self.project, result.project)
        self.assertEquals(self.current_user["id"], result.user["id"])
        self.assertEquals(self.current_user["type"], result.user["type"])
        # Everything else should be none
        self.assertIsNone(result.step)
        self.assertIsNone(result.task)


    def test_data_missing_task(self):
        """
        Case that entity does not exist on local cache or in shotgun
        """
        # Use task we have not setup in path cache not in mocked sg
        task = {"type": "Task", "id": 13, "name": "never_seen_me_before", "content": "no_content"}
        self.assertRaises(TankError, context.from_entity, self.tk, task["type"], task["id"])

    def check_entity(self, first_entity, second_entity):
        "Checks two entity dictionaries have the same values for keys type, id and name."
        self.assertEquals(first_entity["type"], second_entity["type"])
        self.assertEquals(first_entity["id"],   second_entity["id"])
        self.assertEquals(first_entity["name"], second_entity["name"])


class TestAsTemplateFields(TestContext):
    def setUp(self):
        super(TestAsTemplateFields, self).setUp()
        # create a context obj using predefined data
        kws = {}
        kws["tk"] = self.tk
        kws["project"] = self.project
        kws["entity"]  = self.shot
        kws["step"]    = self.step
        self.ctx = context.Context(**kws)

        # create a template with which to filter
        self.keys = {"Sequence": StringKey("Sequence"),
                     "Shot": StringKey("Shot"),
                     "Step": StringKey("Step"),
                     "static_key": StringKey("static_key")}

        template_def =  "/sequence/{Sequence}/{Shot}/{Step}/work"
        self.template = TemplatePath(template_def, self.keys, self.project_root)

    def test_query_from_template(self):
        query_key = StringKey("shot_extra", shotgun_entity_type="Shot", shotgun_field_name="extra_field")
        self.keys["shot_extra"] = query_key
        # shot_extra cannot be gotten from path cache
        template_def = "/sequence/{Sequence}/{Shot}/{Step}/work/{shot_extra}.ext"
        template = TemplatePath(template_def, self.keys, self.project_root)
        result = self.ctx.as_template_fields(template)
        self.assertEquals("extravalue", result["shot_extra"])

    def test_step_first_template(self):
        """
        Check that as_template_fields returns all fields for a template that 
        starts with Step and has no static folders
        """
        template_def = "{Step}/{Sequence}/{Shot}"
        template = TemplatePath(template_def, self.keys, self.project_root)
        result = self.ctx.as_template_fields(template)
        self.assertEquals("step_short_name", result["Step"])
        self.assertEquals("Seq", result["Sequence"])
        self.assertEquals("shot_code", result["Shot"])

    def test_entity_field_query(self):
        """
        Test template query to field linking to an entity.
        """
        query_key = StringKey("shot_seq", shotgun_entity_type="Shot", shotgun_field_name="sg_sequence")
        self.keys["shot_seq"] = query_key
        # shot_extra cannot be gotten from path cache
        template_def = "/sequence/{Sequence}/{Shot}/{Step}/work/{shot_seq}.ext"
        template = TemplatePath(template_def, self.keys, self.project_root)
        result = self.ctx.as_template_fields(template)
        self.assertEquals("seq_name", result["shot_seq"])

    def test_template_query_invalid(self):
        """
        Check case that value returned from shotgun is invalid.
        """
        query_key = IntegerKey("shot_seq", shotgun_entity_type="Shot", shotgun_field_name="sg_sequence")
        self.keys["shot_seq"] = query_key
        template_def = "/sequence/{Sequence}/{Shot}/{Step}/work/{shot_seq}.ext"
        template = TemplatePath(template_def, self.keys, self.project_root)
        self.assertRaises(TankError, self.ctx.as_template_fields, template)

    def test_template_query_none(self):
        """
        Case that shogun returns None as value.
        """
        # set field value to None
        self.shot["sg_sequence"] = None
        query_key = StringKey("shot_seq", shotgun_entity_type="Shot", shotgun_field_name="sg_sequence")
        self.keys["shot_seq"] = query_key
        template_def = "/sequence/{Sequence}/{Shot}/{Step}/work/{shot_seq}.ext"
        template = TemplatePath(template_def, self.keys, self.project_root)
        fields = self.ctx.as_template_fields(template)
        self.assertEquals(fields['shot_seq'], None)

    def test_query_cached(self):
        """
        Test that if same key query is run more than once, the 
        value is cached.
        """
        query_key = StringKey("shot_extra", shotgun_entity_type="Shot", shotgun_field_name="extra_field")
        self.keys["shot_extra"] = query_key
        # shot_extra cannot be gotten from path cache
        template_def = "/sequence/{Sequence}/{Shot}/{Step}/work/{shot_extra}.ext"
        template = TemplatePath(template_def, self.keys, self.project_root)
        result = self.ctx.as_template_fields(template)
        self.assertEquals("extravalue", result["shot_extra"])

        # clear mock history so we can check it.
        finds = self.tk.shotgun.finds

        # do same query again
        result = self.ctx.as_template_fields(template)
        self.assertEquals("extravalue", result["shot_extra"])

        # Check that the shotgun method find_one was not used
        self.assertEqual(finds, self.tk.shotgun.finds)

    def test_shot_step(self):
        expected_step_name = "step_short_name"
        expected_shot_name = "shot_code"
        result = self.ctx.as_template_fields(self.template)
        self.assertEquals(expected_step_name, result['Step'])
        self.assertEquals(expected_shot_name, result['Shot'])

    def test_double_step(self):
        """
        Case that step has multiple locations cached.
        """
        # Add another shot with same step
        shot = {"type":"Shot",
                "name": "shot_name_3",
                "id":3,
                "project": self.project}
        shot_path = os.path.join(self.seq_path, "shot_code_3")
        self.add_production_path(shot_path, shot)
        step_path = os.path.join(shot_path, "step_short_name")
        self.add_production_path(step_path, self.step)
        expected_step_name = "step_short_name"
        expected_shot_name = "shot_code"
        result = self.ctx.as_template_fields(self.template)
        self.assertEquals(expected_step_name, result['Step'])
        self.assertEquals(expected_shot_name, result['Shot'])



    def test_list_field_step_above_entity(self):
        """
        Case that list field, such as asset type, and step are above the entity.
        """
        # Add asset paths for same step different asset_type
        asset_type = "Character"
        asset_code = "asset_code"
        step_short_name = "step_short_name"
        asset_1 = {"type": "Asset",
                   "id": 1,
                   "code": asset_code,
                   "name": "asset_name",
                   "project": self.project,
                   "asset_type": asset_type}

        step_path = os.path.join(self.project_root, asset_type, step_short_name)
        self.add_production_path(step_path, self.step)

        asset_path = os.path.join(step_path, asset_code)
        self.add_production_path(asset_path, asset_1)

        # second asset with different asset type
        asset_type_2 = "Prop"
        asset_2 = {"type": "Asset",
                   "id": 2,
                   "code": "asset_code_2",
                   "name": "asset_name_2",
                   "project": self.project,
                   "asset_type": asset_type_2}

        alt_step_path = os.path.join(self.project_root, asset_type_2, step_short_name)
        self.add_production_path(alt_step_path, self.step)

        asset_2_path = os.path.join(alt_step_path, asset_2["code"])

        ctx = self.tk.context_from_path(asset_path)

        # create template for this setup
        self.keys["asset_type"] = StringKey("asset_type")
        self.keys["Asset"] = StringKey("Asset")
        definition = "{asset_type}/{Step}/{Asset}/work"
        template = TemplatePath(definition, self.keys, self.project_root)

        result = ctx.as_template_fields(template)
        self.assertEquals(asset_type, result["asset_type"])
        self.assertEquals(step_short_name, result["Step"])
        self.assertEquals(asset_code, result["Asset"])






    def test_non_context(self):
        """
        Test that fields that have no value in the context are assigned a value.
        """
        expected =  "Seq"
        result = self.ctx.as_template_fields(self.template)
        self.assertEquals(expected, result.get("Sequence"))

    def test_static(self):
        """
        Tests that values for keys which do not map to entities are found.
        """
        # Set up a shot with static value in path
        shot = {"type": "Shot", "id": 3, "name": "shot_3"}
        shot_path = os.path.join(self.project_root, "static", "shot_3")
        self.add_production_path(shot_path, shot)
        template_def =  "/{static_key}/{Shot}"
        template = TemplatePath(template_def, self.keys, self.project_root)

        # Create context for this shot
        kws = {}
        kws["tk"] = self.tk
        kws["project"] = self.project
        kws["entity"]  = shot
        kws["step"]    = self.step
        ctx = context.Context(**kws)
        result = ctx.as_template_fields(template)

        # Check for non-entity value
        self.assertEquals("static", result["static_key"])


    def test_static_ambiguous(self):
        """
        Tests that in case that static values are amiguous, no value is returned for that key.
        """
        # Set up a shot with different static values in paths
        shot = {"type": "Shot", "id": 3, "name": "shot_3"}
        shot_path_1 = os.path.join(self.project_root, "static_1", "shot_3")
        shot_path_2 = os.path.join(self.project_root, "static_2", "shot_3")
        self.add_production_path(shot_path_1, shot)
        self.add_production_path(shot_path_2, shot)

        template_def =  "/{static_key}/{Shot}"
        template = TemplatePath(template_def, self.keys, self.project_root)

        # Create context for this shot
        kws = {}
        kws["tk"] = self.tk
        kws["project"] = self.project
        kws["entity"]  = shot
        kws["step"]    = self.step
        ctx = context.Context(**kws)
        result = ctx.as_template_fields(template)

        # Check for non-entity value
        self.assertIsNone(result["static_key"])


    def test_multifield_leaf(self):
        """
        Tests using template to filter when there is more than one
        location for a given entity which is represented as a leaf in a
        path.
        """
        edit_step = os.path.join(self.project_root, "editorial", "seq_folder", "shot_name", "step_short_name_ed")
        self.add_production_path(edit_step, self.step)

        expected_step_name = "step_short_name"
        expected_shot_name = "shot_code"
        result = self.ctx.as_template_fields(self.template)
        self.assertEquals(expected_step_name, result['Step'])
        self.assertEquals(expected_shot_name, result['Shot'])

    def test_multifield_intermediate(self):
        """
        Tests using template to filter when there is more than one
        location for a given entity which is not a leaf in it's path(s).
        """
        shot_ed = os.path.join(self.project_root, "editorial", "seq_folder", "shot_name")
        self.add_production_path(shot_ed, self.shot)

        expected_step_name = "step_short_name"
        expected_shot_name = "shot_code"
        result = self.ctx.as_template_fields(self.template)
        self.assertEquals(expected_step_name, result['Step'])
        self.assertEquals(expected_shot_name, result['Shot'])

    def test_ambiguous_entity_location(self):
        """
        Test case that entity has two locations on disk which are both valid for a template.
        """
        # add a second shot location
        shot_path_2 = os.path.join(self.seq_path, "shot_code_2")
        self.add_production_path(shot_path_2, self.shot)
        definition  = "sequence/{Sequence}/{Shot}"
        template = tank.template.TemplatePath(definition, self.keys, self.project_root)
        self.assertRaises(TankError, self.ctx.as_template_fields, template)

    def test_template_without_entity(self):
        """
        Test Case that template has definition which does not contain keys(fields) which map
        to the context's entities.
        """
        definition = "sequence/{Sequence}"
        template = tank.template.TemplatePath(definition, self.keys, self.project_root)
        result = self.ctx.as_template_fields(template)
        expected = os.path.basename(self.seq_path)
        self.assertEquals(expected, result.get("Sequence"))

    def test_non_primary_entity_paths(self):
        """
        Test case that entities have paths in path cache which have roots other than the primary
        project root.
        """
        # Template using alt root
        template_def =  "/sequence/{Sequence}/{Shot}/{Step}/work"
        template = TemplatePath(template_def, self.keys, self.alt_root_1)
        expected_step_name = "step_short_name"
        expected_shot_name = "shot_code"
        result = self.ctx.as_template_fields(template)
        self.assertEquals(expected_step_name, result['Step'])
        self.assertEquals(expected_shot_name, result['Shot'])


    def test_user_ctx(self):
        """Check other_user is set when contained in the path."""
        
        # get a context containing a user
        ctx = self.tk.context_from_path(self.other_user_path)

        # check context's attributes
        self.assertEquals(self.shot["id"], ctx.entity["id"])
        self.assertEquals(self.shot["type"], ctx.entity["type"])
        self.assertEquals(self.project["id"], ctx.project["id"])
        self.assertEquals(self.project["type"], ctx.project["type"])
        self.assertEquals(self.step["id"], ctx.step["id"])
        self.assertEquals(self.step["type"], ctx.step["type"])
        self.assertEquals(self.other_user["id"], ctx.user["id"])
        self.assertEquals(self.other_user["type"], ctx.user["type"])
        self.assertIsNone(ctx.task)
        
        # create a template that uses user
        self.keys["HumanUser"] = StringKey("HumanUser")
        template_def = "/sequence/{Sequence}/{Shot}/{Step}/{HumanUser}"
        template = TemplatePath(template_def, self.keys, self.project_root)

        # pull out fields and test that we have everythign we expect
        fields = ctx.as_template_fields(template)

        self.assertEquals(fields["HumanUser"], "user_login")
        self.assertEquals(fields["Shot"], "shot_code")
        self.assertEquals(fields["Sequence"], "Seq")
        self.assertEquals(fields["Step"], "step_short_name")
        self.assertEquals(len(fields), 4)




class TestSerailize(TestContext):
    def setUp(self):
        super(TestSerailize, self).setUp()
        # params used in creating contexts
        self.kws = {}
        self.kws["tk"] = self.tk
        self.kws["project"] = self.project
        self.kws["entity"] = self.shot
        self.kws["step"] = self.step
        self.kws["task"] = {"id": 45, "type": "Task"}

    def test_equal_yml(self):
        context_1 = context.Context(**self.kws)
        serialized = yaml.dump(context_1)
        context_2 = yaml.load(serialized)
        self.assertTrue(context_1 == context_2)

    def test_equal_custom(self):
        context_1 = context.Context(**self.kws)
        serialized = tank.context.serialize(context_1)
        context_2 = tank.context.deserialize(serialized)
        self.assertTrue(context_1 == context_2)
