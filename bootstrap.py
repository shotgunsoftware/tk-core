from __future__ import print_function
import sgtk
import sys

if "--debug" in sys.argv:
    sgtk.LogManager().initialize_custom_handler()

user = sgtk.authentication.ShotgunAuthenticator().get_user()
manager = sgtk.bootstrap.ToolkitManager(user)
manager.caching_policy = sgtk.bootstrap.ToolkitManager.CACHE_FULL
manager.plugin_id = "basic.very"
manager.base_configuration = "sgtk:descriptor:app_store?name=tk-config-default2"

manager.progress_callback = lambda value, msg: print("%s%% - %s" % (int(value * 100), msg))
engine = manager.bootstrap_engine("tk-shell", user.create_sg_connection().find_one("Project", [["name", "is", "Demo: Game"]]))

print(sorted(engine.commands.keys()))
engine.commands["maya_2019"]["callback"]()
