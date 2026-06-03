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


KNOWN_SG_ENTITIES = [
    "ActionMenuItem",
    "ApiUser",
    "ApiUser",
    "Asset",
    "AssetLibrary",
    "Attachment",
    "Blendshape",
    "Booking",
    "Camera",
    "Candidate",
    "ClientUser",
    "Composition",
    "Cut",
    "CutItem",
    "Delivery",
    "Department",
    "Element",
    "Episode",
    "EventLogEntry",
    "FilesystemLocation",
    "Group",
    "HumanUser",
    "Icon",
    "Launch",
    "Level",
    "LocalStorage",
    "MocapPass",
    "MocapSetup",
    "MocapTake",
    "MocapTakeRange",
    "Note",
    "Page",
    "PageHit",
    "PageSetting",
    "Performer",
    "PermissionRuleSet",
    "Phase",
    "PhysicalAsset",
    "PipelineConfiguration",
    "Playlist",
    "PlaylistShare",
    "Project",
    "PublishEvent",
    "PublishedFile",
    "PublishedFileDependency",
    "PublishedFileType",
    "Reel",
    "Release",
    "Reply",
    "Revision",
    "Routine",
    "RvLicense",
    "Scene",
    "Sequence",
    "ShootDay",
    "Shot",
    "Slate",
    "Software",
    "Status",
    "Step",
    "Tag",
    "Task",
    "TaskDependency",
    "TaskTemplate",
    "Ticket",
    "TimeLog",
    "Tool",
    "Version",
    "CustomEntity02",
    "CustomNonProjectEntity01",
]


class TestShotgunEntity(TankTestBase):
    """
    Test shotgun entity parsing classes and methods.
    """

    def setUp(self):
        pass
    def test_entity_name_field(self):
        pass
    def test_entity_to_string(self):
        pass
    def test_entity_expression_simple(self):
        pass
    def test_entity_expression_multi_folder(self):
        pass
    def test_entity_expression_optional(self):
        pass
    def test_entity_expression_regex(self):
        pass
