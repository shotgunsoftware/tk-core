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

from tank_test.tank_test_base import TankTestBase
from tank_test.tank_test_base import setUpModule  # noqa
from tank.util.shotgun.publish_creation import _translate_abstract_fields


class TestShotgunPublishCreation(TankTestBase):
    """
    Test shotgun entity parsing classes and methods.
    """

    def setUp(self):
        """Sets up entities in mocked shotgun database and creates Mock objects
        to pass in as callbacks to Schema.create_folders. The mock objects are
        then queried to see what paths the code attempted to create.
        """
        super(TestShotgunPublishCreation, self).setUp()
        self.setup_fixtures()

    def test_translate_abstract_fields_optional_key_not_in_path(self):
        """
        Test when a template has an optional key with a default value but the specific
        file path does not include that key, no default values are added when translating
        abstract fields
        """
        template = self.tk.templates["path_with_optional_abstract"]
        file_path_no_optional = os.path.join(template.root_path, "media", "scene.mov")
        data = _translate_abstract_fields(self.tk, file_path_no_optional)
        self.assertEqual(data, os.path.join(template.root_path, file_path_no_optional))

    def test_translate_abstract_fields_optional_key_in_path(self):
        """
        Test when a template has an optional key with a default value and the specific
        file path does include that key, the default value is returned as expected
        """
        template = self.tk.templates["path_with_optional_abstract"]
        file_path_no_optional = os.path.join(
            template.root_path, "media", "scene.0001.exr"
        )
        data = _translate_abstract_fields(self.tk, file_path_no_optional)
        self.assertEqual(
            data,
            os.path.join(
                template.root_path, file_path_no_optional.replace("0001", "%04d")
            ),
        )
