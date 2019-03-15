from __future__ import print_function
import sgtk

sgtk.LogManager().initialize_custom_handler()

user = sgtk.authentication.ShotgunAuthenticator().get_user()
manager = sgtk.bootstrap.ToolkitManager(user)
manager.do_shotgun_config_lookup = False
manager.base_configuration = "sgtk:descriptor:path?path=~/gitlocal/tk-config-default2"

manager.progress_callback = lambda value, msg: print("%s%% - %s" % (int(value * 100), msg))
engine = manager.bootstrap_engine("tk-shell", user.create_sg_connection().find_one("Project", [["name", "is", "Demo: Game"]]))
