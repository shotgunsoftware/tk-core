"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------
"""
import os
import sys

from tank_vendor import yaml
from tank_test.tank_test_base import *

from tank import root
from tank import TankError

class TestGetProjectRoots(TankTestBase):
    def setUp(self):
        super(TestGetProjectRoots, self).setUp()
        self.setup_fixtures()
        self.root_file_path = os.path.join(self.project_config, "core", "roots.yml")
        project_name = os.path.basename(self.project_root)
        #TODO make os specific paths
        
        self.roots = {"primary":{}, "publish": {}, "render": {}}
        for os_name in ["windows_path", "linux_path", "mac_path"]:
            self.roots["primary"][os_name] = os.path.dirname(self.project_root)
            self.roots["publish"][os_name] = os.path.join(self.tank_temp, "publish")
            self.roots["render"][os_name]  = os.path.join(self.tank_temp, "render")
        # the roots file will be written by each test

    def test_file_missing(self):
        """Case roots file is not present"""
        expected = {"primary": self.project_root}
        # Don't make a root file
        result = root.get_project_roots(self.project_root)
        self.assertEqual(expected, result)

    def test_primary_missing(self):
        """Case roots file does not define primary root"""
        del(self.roots["primary"])
        with open(self.root_file_path, "w") as root_file:
            root_file.write(yaml.dump(self.roots))
        # expect primary will be set using primary argument
        result = root.get_project_roots(self.project_root)
        self.assertEqual(self.project_root, result["primary"])

    def test_primary_mismatch(self):
        """Case that file primary path does not match primary path argument"""
        bad_path = os.path.join(self.tank_temp, "other_root")
        for os_name in ["mac_path", "windows_path", "linux_path"]:
            self.roots["primary"][os_name] = bad_path
        with open(self.root_file_path, "w") as root_file:
            root_file.write(yaml.dump(self.roots))
        
        with self.assertRaises(tank.errors.TankError) as tank_error:
            root.get_project_roots(self.project_root)
            expected = ("Primary root defined in roots.yml file does not match that passed as argument" + 
                       " (likely from Tank local storage): \n%s\n%s" % (bad_path, self.project_root))
            self.assertEqual(expected, tank_error.message)

    def test_paths(self):
        """Test paths match those in roots for current os."""
        with open(self.root_file_path, "w") as root_file:
            root_file.write(yaml.dump(self.roots))
        result = root.get_project_roots(self.project_root)
        
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

class TestGetPrimaryRoot(TankTestBase):
    def setUp(self):
        super(TestGetPrimaryRoot, self).setUp()
        self.setup_multi_root_fixtures()
        self.tk = tank.Tank(self.project_root)
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
        self.assertEqual(self.project_root, root.get_primary_root(asset_path))
        

    def test_primary(self):
        """
        Test input path is in primary root's tree for multi-root project.
        """
        shot_path = os.path.join(self.project_root, "sequences", "seq_code", "shot_code")
        self.assertEqual(self.project_root, root.get_primary_root(shot_path))


    def test_non_project_path(self):
        """
        Test path which is not in the project tree.
        """
        non_project_path = os.path.join(os.path.dirname(self.project_root), "bogus")
        self.assertRaises(TankError, root.get_primary_root, non_project_path)
        
