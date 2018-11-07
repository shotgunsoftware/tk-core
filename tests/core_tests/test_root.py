# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

from __future__ import with_statement

import os
import sys
import copy

from tank_vendor import yaml
from tank_test.tank_test_base import TankTestBase, setUpModule # noqa

import tank
from tank import TankError

class TestGetProjectRoots(TankTestBase):
    
    def setUp(self):
        super(TestGetProjectRoots, self).setUp()

        # Tests are updating the roots.yml file, so we'll turn this into an installed configuration.
        self.setup_fixtures(parameters={"installed_config": True})
        self.root_file_path = os.path.join(self.pipeline_config_root, "config", "core", "roots.yml")

        # TODO make os specific paths
        self.roots = {"primary": {}, "publish": {}, "render": {}}
        for os_name in ["linux_path", "mac_path"]:
            self.roots["primary"][os_name] = os.path.dirname(self.project_root).replace(os.sep, "/")
            self.roots["publish"][os_name] = os.path.join(self.tank_temp, "publish").replace(os.sep, "/")
            self.roots["render"][os_name]  = os.path.join(self.tank_temp, "render").replace(os.sep, "/")
        for os_name in ["windows_path"]:
            self.roots["primary"][os_name] = os.path.dirname(self.project_root).replace(os.sep, "\\")
            self.roots["publish"][os_name] = os.path.join(self.tank_temp, "publish").replace(os.sep, "\\")
            self.roots["render"][os_name]  = os.path.join(self.tank_temp, "render").replace(os.sep, "\\")

        # the roots file will be written by each test

    def test_file_missing(self):
        """Case roots file is not present"""
        expected = {self.primary_root_name: self.project_root}
        # Don't make a root file
        pc = tank.pipelineconfig_factory.from_path(self.project_root)
        result = pc.get_data_roots()
        self.assertEqual(expected, result)

    def test_paths(self):
        """Test paths match those in roots for current os."""
        root_file = open(self.root_file_path, "w")
        root_file.write(yaml.dump(self.roots))
        root_file.close()

        pc = tank.pipelineconfig_factory.from_path(self.project_root)
        result = pc.get_data_roots()
        
        # Determine platform
        system = sys.platform.lower()

        if system == 'darwin':
            platform = "mac_path"
        elif system.startswith('linux'):
            platform = 'linux_path'
        elif system == 'win32':
            platform = 'windows_path'

        project_name = os.path.basename(self.project_root)
        for root_name, root_path in result.items():
            expected_path = os.path.join(self.roots[root_name][platform], project_name)
            self.assertEqual(expected_path, root_path)

    def test_all_paths(self):
        """
        Tests getting storage paths back from a pipeline config. 
        """
        
        # take one path out and mark as undefined
        new_roots = copy.deepcopy(self.roots)
        new_roots["render"]["linux_path"] = None
        
        root_file = open(self.root_file_path, "w")
        root_file.write(yaml.dump(new_roots))
        root_file.close()

        pc = tank.pipelineconfig_factory.from_path(self.project_root)
        result = pc.get_all_platform_data_roots()
        
        platform_lookup = {"win32": "windows_path", "darwin": "mac_path", "linux2": "linux_path"}

        project_name = os.path.basename(self.project_root)
        for root_name, platform_paths in result.items():
            for platform in platform_paths:
                root_path = platform_paths[platform]
                shotgun_path_key = platform_lookup[platform] 
                if new_roots[root_name][shotgun_path_key] is None:
                    expected_path = None
                elif platform == "win32":
                    expected_path = "%s\\%s" % (new_roots[root_name][shotgun_path_key], project_name)
                else:
                    expected_path = "%s/%s" % (new_roots[root_name][shotgun_path_key], project_name)
                self.assertEqual(expected_path, root_path)

    def test_flexible_primary(self):
        """
        Tests getting storage paths back from a pipeline config without a 'primary'
        storage.
        """

        # take one path out and mark as undefined
        new_roots = copy.deepcopy(self.roots)
        new_roots["master"] = new_roots.pop("primary")
        root_file = open(self.root_file_path, "w")
        root_file.write(yaml.dump(new_roots))
        root_file.close()
        # We should get a TankError if we don't have a primary storage in a
        # multi-roots file.
        with self.assertRaisesRegex(TankError, "Could not identify a default storage"):
            pc = tank.pipelineconfig_factory.from_path(self.project_root)
        # Only keep the master storage
        del new_roots["publish"]
        del new_roots["render"]
        root_file = open(self.root_file_path, "w")
        root_file.write(yaml.dump(new_roots))
        root_file.close()
        pc = tank.pipelineconfig_factory.from_path(self.project_root)
        self.assertEqual(pc.get_all_platform_data_roots().keys(), ["master"])
        self.assertEqual(pc.get_data_roots().keys(), ["master"])
        self.assertEqual(self.project_root, pc.get_primary_data_root())


class TestGetPrimaryRoot(TankTestBase):
    def setUp(self):
        super(TestGetPrimaryRoot, self).setUp()
        
        self.setup_multi_root_fixtures()
        
        # create shot and asset data
        self.seq = {"type": "Sequence",
                    "id": 2,
                    "code": "seq_code",
                    "project": self.project}
        self.shot = {"type": "Shot",
                     "id": 1,
                     "code": "shot_code",
                     "sg_sequence": self.seq,
                     "project": self.project}
        self.asset = {"type": "Asset",
                    "id": 4,
                    "sg_asset_type": "assettype",
                    "code": "assetname",
                    "project": self.project}

        # Add these to mocked shotgun
        self.add_to_sg_mock_db([self.shot, self.seq, self.project, self.asset])
        
        # Write path in primary root tree
        self.tk.create_filesystem_structure("Shot", 1)
        # Write path in alternate root tree
        self.tk.create_filesystem_structure("Asset", 4)


    def test_alt_path(self):
        """
        Test input path in alternate project root's tree.
        """
        asset_path = os.path.join(self.alt_root_1, 'assets', 'assettype_assetname')
        pc = tank.pipelineconfig_factory.from_path(asset_path)
        self.assertEqual(self.project_root, pc.get_primary_data_root())
        

    def test_primary(self):
        """
        Test input path is in primary root's tree for multi-root project.
        """
        shot_path = os.path.join(self.project_root, "sequences", "seq_code", "shot_code")
        pc = tank.pipelineconfig_factory.from_path(shot_path)
        self.assertEqual(self.project_root, pc.get_primary_data_root())

    def test_non_project_path(self):
        """
        Test path which is not in the project tree.
        """
        non_project_path = os.path.join(os.path.dirname(self.project_root), "xxxyyyzzzz")
        self.assertRaises(TankError, tank.pipelineconfig_factory.from_path, non_project_path)
