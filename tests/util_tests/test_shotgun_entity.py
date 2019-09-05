# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import sgtk
import tank
from tank_test.tank_test_base import TankTestBase, ShotgunTestBase, setUpModule  # noqa
from tank.util.shotgun_entity import get_sg_entity_name_field, sg_entity_to_string


class TestShotgunEntity(TankTestBase):
    """
    Test shotgun entity parsing classes and methods.
    """

    def setUp(self):
        """Sets up entities in mocked shotgun database and creates Mock objects
        to pass in as callbacks to Schema.create_folders. The mock objects are
        then queried to see what paths the code attempted to create.
        """
        super(TestShotgunEntity, self).setUp()
        self.setup_fixtures()

    def test_entity_name_field(self):
        """
        Test retrieving the right "name" field for various entity types.
        """
        # Test most standard entities, and check that custom entities use "code"
        for entity_type in ["Sequence", "Shot", "Asset", "CustomXXXXEntity"]:
            self.assertEqual(
                get_sg_entity_name_field(entity_type), "code"
            )
        # Test most standard entities where the name is in a "name" field.
        for entity_type in ["HumanUser", "Project", "Department"]:
            self.assertEqual(
                get_sg_entity_name_field(entity_type), "name"
            )

        self.assertEqual(get_sg_entity_name_field("Task"), "content")
        self.assertEqual(get_sg_entity_name_field("Note"), "subject")
        self.assertEqual(get_sg_entity_name_field("Delivery"), "title")

    def test_entity_to_string(self):
        """
        Tests converting sg data into string format
        """
        # project fields are allowed to have slashes for folder creation purposes.
        self.assertEqual(
            sg_entity_to_string(
                self.tk,
                sg_entity_type="Project",
                sg_id=123,
                sg_field_name="tank_name",
                data="foo/bar&"
            ),
            "foo/bar-"
        )
        # other ETs are not.
        self.assertEqual(
            sg_entity_to_string(
                self.tk,
                sg_entity_type="Shot",
                sg_id=123,
                sg_field_name="code",
                data="foo/bar&"
            ),
            "foo-bar-"
        )

        # basic conversion of other types
        self.assertEqual(
            sg_entity_to_string(
                self.tk,
                sg_entity_type="Shot",
                sg_id=123,
                sg_field_name="int_field",
                data=123
            ),
            "123"
        )

        self.assertEqual(
            sg_entity_to_string(
                self.tk,
                sg_entity_type="Shot",
                sg_id=123,
                sg_field_name="link_field",
                data={"type": "Shot", "id": 123, "name": "foo"}
            ),
            "foo"
        )

        self.assertEqual(
            sg_entity_to_string(
                self.tk,
                sg_entity_type="Shot",
                sg_id=123,
                sg_field_name="link_field",
                data=[{"name": "foo"}, {"name": "bar"}]
            ),
            "foo_bar"
        )

    def test_entity_expression_simple(self):
        """
        Tests basic expressions for entity objects
        """
        ee = sgtk.util.shotgun_entity.EntityExpression(self.tk, "Shot", "{code}")
        self.assertEqual(ee.get_shotgun_fields(), set(["code"]))
        self.assertEqual(ee.get_shotgun_link_fields(), set())
        self.assertEqual(ee.generate_name({"code": "foo", "extra": "data"}), "foo")

        ee = sgtk.util.shotgun_entity.EntityExpression(self.tk, "Shot", "{code}_{entity}")
        self.assertEqual(ee.get_shotgun_fields(), set(["code", "entity"]))
        self.assertEqual(ee.get_shotgun_link_fields(), set())
        self.assertEqual(
            ee.generate_name({"code": "foo", "entity": {"type:": "Asset", "id": 123, "name": "NAB"}}),
            "foo_NAB"
        )

        ee = sgtk.util.shotgun_entity.EntityExpression(self.tk, "Shot", "{code}_{sg_sequence.Sequence.code}")
        self.assertEqual(ee.get_shotgun_fields(), set(["code", "sg_sequence.Sequence.code"]))
        self.assertEqual(ee.get_shotgun_link_fields(), set(["sg_sequence"]))
        self.assertEqual(
            ee.generate_name(
                {"code": "foo",
                 "sg_sequence.Sequence.code": "NAB",
                 "sg_sequence": {"type:": "Sequence", "id": 123, "name": "NAB"}}
            ),
            "foo_NAB"
        )

        # raise exception when fields are not supplied
        ee = sgtk.util.shotgun_entity.EntityExpression(self.tk, "Shot", "{code}")
        self.assertRaises(
            tank.errors.TankError,
            ee.generate_name,
            {"extra": "data"}
        )

    def test_entity_expression_multi_folder(self):
        """
        Tests that expressions can contain slashes
        """
        ee = sgtk.util.shotgun_entity.EntityExpression(self.tk, "Shot", "{code}/{code2}")
        self.assertEqual(ee.generate_name({"code": "foo", "code2": "bar"}), "foo/bar")

        # make sure that we don't have any empty tokens - in static syntax
        ee = sgtk.util.shotgun_entity.EntityExpression(self.tk, "Shot", "{code}//{code2}")
        self.assertRaises(
            tank.errors.TankError,
            ee.generate_name,
            {"code": "foo", "code2": "bar"}
        )

        # make sure that we don't have any empty tokens - in dynamic syntax
        ee = sgtk.util.shotgun_entity.EntityExpression(self.tk, "Shot", "{code}/{code2}")
        self.assertRaises(
            tank.errors.TankError,
            ee.generate_name,
            {"code": "foo", "code2": ""}
        )

    def test_entity_expression_optional(self):
        """
        Tests basic expressions for entity objects with optional tokens
        """
        ee = sgtk.util.shotgun_entity.EntityExpression(self.tk, "Shot", "{code}[_{entity}]")
        self.assertEqual(ee.get_shotgun_fields(), set(["code", "entity"]))
        self.assertEqual(ee.get_shotgun_link_fields(), set())
        self.assertEqual(
            ee.generate_name({"code": "foo", "entity": {"type:": "Asset", "id": 123, "name": "NAB"}}),
            "foo_NAB"
        )

        # setting entity to none omits the optional field
        self.assertEqual(ee.generate_name({"code": "foo", "entity": None}), "foo")

        # omitting the field raises an exception
        self.assertRaises(
            tank.errors.TankError,
            ee.generate_name,
            {"code": "foo"}
        )

        # setting the required field raises an exception
        self.assertRaises(
            tank.errors.TankError,
            ee.generate_name,
            {"code": None, "entity": {"type:": "Asset", "id": 123, "name": "NAB"}, }
        )

        # verify that deep links work with optional expressions
        ee = sgtk.util.shotgun_entity.EntityExpression(self.tk, "Shot", "{code}[_{sg_sequence.Sequence.code}]")
        self.assertEqual(ee.get_shotgun_fields(), set(["code", "sg_sequence.Sequence.code"]))
        self.assertEqual(ee.get_shotgun_link_fields(), set(["sg_sequence"]))
        self.assertEqual(
            ee.generate_name({"code": "foo", "sg_sequence.Sequence.code": "NAB"}),
            "foo_NAB"
        )

    def test_entity_expression_regex(self):
        """
        Tests regex entity expressions
        """
        # test simple
        ee = sgtk.util.shotgun_entity.EntityExpression(self.tk, "Shot", "{code:^([^_]+)}")
        self.assertEqual(ee.get_shotgun_fields(), set(["code"]))
        self.assertEqual(ee.get_shotgun_link_fields(), set())
        self.assertEqual(ee.generate_name({"code": "foo_bar"}), "foo")

        # test that multiple regex expressions get concatenated
        ee = sgtk.util.shotgun_entity.EntityExpression(self.tk, "Shot", "{code:^([^_]+)_(.+)$}")
        self.assertEqual(ee.generate_name({"code": "foo_the_rest"}), "foothe_rest")

        # test that this works with optional expressions
        ee = sgtk.util.shotgun_entity.EntityExpression(self.tk, "Shot", "{code:^([^_]+)}[XXX{status:^([^_]+)}]")
        self.assertEqual(ee.generate_name({"code": "foo_bar", "status": "baz_boo"}), "fooXXXbaz")
        self.assertEqual(ee.generate_name({"code": "foo_bar", "status": None}), "foo")

        # test that we can repeat a token
        ee = sgtk.util.shotgun_entity.EntityExpression(self.tk, "Shot", "{code:^(.)}/{code}")
        self.assertEqual(ee.generate_name({"code": "hello"}), "h/hello")

        # test what happens when regex fails to match
        ee = sgtk.util.shotgun_entity.EntityExpression(self.tk, "Shot", "{code:^([A-Z]+)}")
        self.assertEqual(ee.generate_name({"code": "Toolkitty"}), "T")
        self.assertRaises(
            tank.errors.TankError,
            ee.generate_name,
            {"code": "toolkitty"}
        )

