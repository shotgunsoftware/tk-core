# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from __future__ import print_function
import sys
import os
import shutil
import pdb # noqa
import subprocess
import tempfile
from optparse import OptionParser


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


def ensure_project(sg):
    print("Looking for integration test project...")
    project = sg.find_one("Project", [["name", "is", PROJECT_NAME]])
    if not project:
        print("Creating new project...")
        project = sg.create("Project", {"name": PROJECT_NAME})
    else:
        print("Project already exists.")
    return project


def setup_logging():
    sgtk.LogManager().initialize_base_file_handler("tk-integration-tests")
    sgtk.LogManager().initialize_custom_handler()


def authenticate(options):
    sa = sgtk.authentication.ShotgunAuthenticator()
    return sa.create_script_user(
        options.api_script,
        options.api_key,
        options.site
    )


def prepare_config(sg, config_core, config_template):
    core_desc_dict = sgtk.descriptor.descriptor_uri_to_dict(
        config_core
    )

    config_descriptor = sgtk.descriptor.create_descriptor(
        sg,
        sgtk.descriptor.Descriptor.CONFIG,
        config_template
    )

    tests_root = os.path.join(tempfile.gettempdir(), "integration_tests")

    if os.path.exists(tests_root):
        shutil.rmtree(tests_root)

    config_template_root = os.path.join(tests_root, "config_template")

    if not os.path.exists(config_template_root):
        os.makedirs(config_template_root)

    config_descriptor.copy(config_template_root)
    with open(os.path.join(config_template_root, "core", "core_api.yml"), "wt") as fh:
        yaml.safe_dump(dict(location=core_desc_dict), fh)

    with open(os.path.join(config_template_root, "core", "shotgun.yml"), "wt") as fh:
        yaml.safe_dump(
            dict(
                site=sg.base_url,
                api_key=sg.config.api_key,
                api_script=sg.config.script_name
            ),
            fh
        )

    return "sgtk:descriptor:path?path={0}".format(config_template_root)


def bootstrap(config_descriptor, user, project):
    manager = sgtk.bootstrap.ToolkitManager(user)
    manager.do_shotgun_config_lookup = False
    manager.progress_callback = progress_callback
    manager.plugin_id = "basic.engine"
    manager.base_configuration = config_descriptor

    return manager.bootstrap_engine("test_engine", project)


def run_tank_command(config_root):
    subprocess.check_call([os.path.join(config_root, "tank")])


def main(options):

    setup_logging()
    user = authenticate(options)
    sg = user.create_sg_connection()
    project = ensure_project(sg)
    config_descriptor = prepare_config(sg, options.config_core, options.config_template)

    # Bootstrap into the configuration.
    engine = bootstrap(config_descriptor, user, project)

    # Ensure the tank command works.
    run_tank_command(engine.sgtk.pipeline_configuration.get_install_location())

    # Now setup a classic Toolkit project.
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

    run_tank_command(INTEGRATION_TESTS_PC_LOCATION)


def parse_options():

    parser = OptionParser()
    parser.add_option(
        "--config-core", help="Location of the core for the configuration."
    )
    parser.add_option(
        "--config-template", help="Location of the configuration to use."
    )
    parser.add_option(
        "--site", help="Site to connect to."
    )
    parser.add_option(
        "--api-script", help="API script to authenticate with."
    )
    parser.add_option(
        "--api-key", help="API key to authenticate with."
    )

    return parser.parse_args()[0]


if __name__ == "__main__":
    options = parse_options()
    import sgtk
    from tank_vendor import yaml

    try:
        main(options)
    except Exception:
        raise # pdb.post_mortem()
