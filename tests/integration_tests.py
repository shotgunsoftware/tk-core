from __future__ import print_function
import sys
import os
import shutil
import pdb # noqa

sys.path.insert(0, "/Users/jfboismenu/gitlocal/tk-core/python")


def progress_callback(value, message):
    print("{0} - {1}".format(int(value * 100), message))


CONFIG_DISK_LOCATION = "/Users/jfboismenu/gitlocal/tk-core/tests/fixtures/integration_tests"
PROJECT_NAME = "ToolkitIntegrationTestProject"

INTEGRATION_TESTS_LOCATION = "/var/tmp/integration_tests"
INTEGRATION_TESTS_PC_LOCATION = os.path.join(INTEGRATION_TESTS_LOCATION, "pipeline")
PRIMARY_LOCATION = "/Users/jfboismenu/shotgun/jf/integrarion_tests"

os.environ["TK_FIXTURES_ROOT"] = "/Users/jfboismenu/gitlocal/tk-core/tests/fixtures"

#
# bootstrap into a config that uses an old core

# new core bootstraps into a project that doesn't do lean configs
# new core bootstraps into a project that understands lean configs
# old core bootstraps into a project that doesn't understand lean configs
# old core bootstraps into a projet that understands lean configs

# from each of these
# run setup_project
# launches the tank command with a command from the engine
# run setup_project_wizard
# launches the tank command with a command from the engine


def bootstrap():
    import sgtk

    sgtk.LogManager().initialize_base_file_handler("tk-integration-tests")
    sgtk.LogManager().initialize_custom_handler()

    sa = sgtk.authentication.ShotgunAuthenticator()
    user = sa.get_user()

    sg = user.create_sg_connection()

    print("Looking for integration test project...")
    project = sg.find_one("Project", [["name", "is", PROJECT_NAME]])
    if not project:
        print("Creating new project...")
        project = sg.create("Project", {"name": PROJECT_NAME})
    else:
        print("Project already exists.")

    print("Starting tests!!!")

    print("Bootstrapping!")

    manager = sgtk.bootstrap.ToolkitManager(user)
    manager.do_shotgun_config_lookup = False
    manager.progress_callback = progress_callback
    manager.plugin_id = "basic.engine"
    manager.base_configuration = "sgtk:descriptor:path?path={0}".format(CONFIG_DISK_LOCATION)

    return manager.bootstrap_engine("test_engine", project), project


def main():

    engine, project = bootstrap()

    import sgtk

    command = engine.sgtk.get_command("setup_project")
    command.set_logger(sgtk.LogManager().root_logger)

    if os.path.exists(INTEGRATION_TESTS_LOCATION):
        shutil.rmtree(INTEGRATION_TESTS_LOCATION)

    os.makedirs(INTEGRATION_TESTS_LOCATION)
    if not os.path.exists(PRIMARY_LOCATION):
        os.makedirs(PRIMARY_LOCATION)

    command.execute({
        "project_id": project["id"],
        "project_folder_name": "integrarion_tests",
        "force": True,
        "config_uri": "/Users/jfboismenu/gitlocal/tk-core/tests/fixtures/config",
        "config_path_mac": INTEGRATION_TESTS_PC_LOCATION if sys.platform == "darwin" else None,
        "config_path_win": INTEGRATION_TESTS_PC_LOCATION if sys.platform == "win32" else None,
        "config_path_linux": INTEGRATION_TESTS_PC_LOCATION if sys.platform.startswith("linux") else None,
    })


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pdb.post_mortem()
