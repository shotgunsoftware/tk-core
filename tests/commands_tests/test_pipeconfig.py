# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Unit tests tank pipeline configs.
"""

import os
import tempfile
import shutil
import stat

import sgtk
from tank.errors import TankError
from tank.util import is_windows

from tank_test.tank_test_base import setUpModule  # noqa
from tank_test.tank_test_base import (
    mock,
    TankTestBase,
)

from tank_test.mock_appstore import patch_app_store


class TestPipelineConfig(TankTestBase):
    """
    Perform tests around pipeline configs
    """

    def setUp(self):
        """
        Prepare unit test.
        """
        TankTestBase.setUp(self)

        patcher = patch_app_store()
        self._mock_store = patcher.start()
        self.addCleanup(patcher.stop)

    def test_pc_push(self):
        """
        Test push_configuration command.
        """
        push_cmd = self.tk.get_command("push_configuration")
        # Check that we get an error if trying to push while having a single
        # pipeline config
        self.assertRaisesRegex(
            TankError, "Only one pipeline config", push_cmd.execute, {"target_id": 666}
        )
        # Clone the current pipeline config
        clone_cmd = self.tk.get_command("clone_configuration")
        pc = self.tk.pipeline_configuration
        temp_dir = tempfile.mkdtemp()
        temp_pc_dir = os.path.join(temp_dir, "test_pc_push")
        temp_pc_config_dir = os.path.join(temp_pc_dir, "config")
        cloned_pc_id = clone_cmd.execute(
            {
                "source_id": pc.get_shotgun_id(),
                "name": "test_pc_push",
                "path_mac": temp_pc_dir,
                "path_win": temp_pc_dir,
                "path_linux": temp_pc_dir,
            }
        )
        # Check we can't push on ourself
        self.assertRaisesRegex(
            TankError,
            "The target pipeline config id must be different from the current one",
            push_cmd.execute,
            {"target_id": pc.get_shotgun_id()},
        )
        # Check we can't push with an invalid target id
        self.assertRaisesRegex(
            TankError,
            "Id 6666 is not a valid pipeline config id",
            push_cmd.execute,
            {"target_id": 6666},
        )

        # Push the current pipeline config to the cloned one
        push_cmd.execute({"target_id": cloned_pc_id})
        # Use the pushed configuration to check it is valid
        sgtk.sgtk_from_path(temp_pc_dir)

        # Do it again
        push_cmd.execute({"target_id": cloned_pc_id})
        # Use the pushed configuration to check it is valid
        sgtk.sgtk_from_path(temp_pc_dir)

        # Disable rename being used when backuping the target pipeline configuration
        # by raising an OSError
        unmocked_os_rename = os.rename

        def mocked_rename(src, dst):
            if src == temp_pc_config_dir:
                raise OSError("os.rename is disabled")
            return unmocked_os_rename(src, dst)

        with mock.patch("os.rename", side_effect=mocked_rename):
            # And push again
            push_cmd.execute({"target_id": cloned_pc_id})
            sgtk.sgtk_from_path(temp_pc_dir)
            # Now create an error by adding a file which can't be read in the
            # target pc folder
            rogue_file = os.path.join(temp_pc_config_dir, "rogue.one")
            f = open(rogue_file, "w")
            f.close()
            os.chmod(rogue_file, 0)
            if is_windows():
                # On Windows we can only set the file to "readonly". So the copy
                # will succeed. We use filesystem.safe_delete_folder to remove
                # the folder which handle our test case, so no errors...
                push_cmd.execute({"target_id": cloned_pc_id})
                sgtk.sgtk_from_path(temp_pc_dir)
            else:
                # Pushing should raise an error on Linux/Osx
                self.assertRaisesRegex(
                    TankError,
                    "Permission denied|Access is denied",
                    push_cmd.execute,
                    {"target_id": cloned_pc_id},
                )
                # But the target config should still be valid
                sgtk.sgtk_from_path(temp_pc_dir)
                os.chmod(rogue_file, stat.S_IREAD | stat.S_IWRITE)
                os.remove(rogue_file)

        # Test pushing with symlinks.
        #
        # When the method symlink is present, it means that the current platform
        # supports symlinks.
        #
        # Note that if you are not in Developer mode on Windows, the method will
        # still be present in Python 3, but the symlink call will fail. There is
        # no easy way to detect that edge case from Python, so if you see this
        # test failing on Windows, just update the security settings to For Developers
        # and the test should pass.
        # https://www.howtogeek.com/howto/16226/complete-guide-to-symbolic-links-symlinks-on-windows-or-linux/
        if getattr(os, "symlink", None) is None:
            self.assertRaisesRegex(
                TankError,
                "Symbolic links are not supported",
                push_cmd.execute,
                {"target_id": cloned_pc_id, "use_symlink": True},
            )
        else:
            push_cmd.execute({"target_id": cloned_pc_id, "use_symlink": True})
            sgtk.sgtk_from_path(temp_pc_dir)
        # Let's check things are still alright one last time
        push_cmd.execute({"target_id": cloned_pc_id})
        sgtk.sgtk_from_path(temp_pc_dir)
        # Clean up
        shutil.rmtree(temp_dir, ignore_errors=True)
