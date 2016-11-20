# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Base class for engine and app testing
"""

import sys
import os
import time
import shutil
import pprint
import threading
import tempfile
import uuid
import contextlib

from tank_vendor.shotgun_api3.lib import mockgun

import unittest2 as unittest
import mock

import sgtk
import tank
from tank import path_cache, pipelineconfig_factory
from tank_vendor import yaml
from tank.util.user_settings import UserSettings

TANK_TEMP = None

__all__ = ['setUpModule', 'TankTestBase', 'tank', 'interactive', 'skip_if_pyside_missing']


def interactive(func):
    """
    Decorator that allows to skip a test if the interactive flag is not set
    on the command line.
    :param func: Function to be decorated.
    :returns: The decorated function.
    """
    interactive_in_argv = "--interactive" not in sys.argv
    return unittest.skipIf(
        interactive_in_argv,
        "add --interactive on the command line to run this test."
    )(func)


def _is_git_missing():
    """
    Tests is git is available in PATH
    :returns: True is git is available, False otherwise.
    """
    git_missing = True
    try:
        output = sgtk.util.process.subprocess_check_output(["git", "--version"])
        git_missing = False
    except:
        # no git!
        pass
    return git_missing


def skip_if_git_missing(func):
    """
    Decorated that allows to skips a test if PySide is missing.
    :param func: Function to be decorated.
    :returns: The decorated function.
    """
    return unittest.skipIf(_is_git_missing(), "git is missing from PATH")(func)


def _is_pyside_missing():
    """
    Tests is PySide is available.
    :returns: True is PySide is available, False otherwise.
    """
    try:
        import PySide
        return False
    except ImportError:
        return True


def skip_if_pyside_missing(func):
    """
    Decorated that allows to skips a test if PySide is missing.
    :param func: Function to be decorated.
    :returns: The decorated function.
    """
    return unittest.skipIf(_is_pyside_missing(), "PySide is missing")(func)


@contextlib.contextmanager
def temp_env_var(**kwargs):
    """
    Scope the life-scope of temporary environment variable within a ``with`` block.

    :param \**kwargs: key-value pairs of environment variables to set.
    """
    backup_values = {}
    for k, v in kwargs.iteritems():
        if k in os.environ:
            backup_values[k] = os.environ[k]
        os.environ[k] = v

    try:
        yield
    finally:
        for k, v in kwargs.iteritems():
            if k in backup_values:
                os.environ[k] = backup_values[k]
            else:
                del os.environ[k]


def setUpModule():
    """
    Creates studio level directories in temporary location for tests.
    """
    global TANK_TEMP

    # determine tests root location
    temp_dir = tempfile.gettempdir()
    # make a unique test dir for each file
    temp_dir_name = "tankTemporaryTestData"
    # Append a random string to the temp directory name to make it unique. time.time
    # doesn't have enough resolution!!!
    temp_dir_name += "_%s" % (uuid.uuid4(),)

    TANK_TEMP = os.path.join(temp_dir, temp_dir_name)
    # print out the temp data location
    msg = "Toolkit test data location: %s" % TANK_TEMP
    print "\n" + "="*len(msg)
    print msg
    print "=" * len(msg) + "\n"

    # move tank directory if left by previous tests
    _move_data(TANK_TEMP)
    os.makedirs(TANK_TEMP)

    # create studio level tank directories
    studio_tank = os.path.join(TANK_TEMP, "tank")

    # make studio level subdirectories
    os.makedirs(os.path.join(studio_tank, "config", "core"))
    install_dir = os.path.join(studio_tank, "install")

    # copy tank engine code into place
    os.makedirs(os.path.join(install_dir, "engines"))


class TankTestBase(unittest.TestCase):
    """
    Test base class which manages fixtures for tank related tests.
    """

    SHOTGUN_HOME = "SHOTGUN_HOME"

    def __init__(self, *args, **kws):

        super(TankTestBase, self).__init__(*args, **kws)

        # Below are attributes which will be set during setUp

        # Path to temp directory
        self.tank_temp = None
        # fake project entity dictionary
        self.project = None
        self.project_root = None
        # alternate project roots for multi-root tests
        self.alt_root_1 = None
        self.alt_root_2 = None
        # project level config directories
        self.project_config = None

        # path to the tk-core repo root point
        self.tank_source_path = os.path.abspath(os.path.join( os.path.dirname(__file__), "..", "..", ".."))

        # where to go for test data
        self.fixtures_root = os.environ["TK_TEST_FIXTURES"]

    def setUp(self, parameters=None):
        """
        Sets up a Shotgun Mockgun instance with a project and a basic project scaffold on
        disk.

        :param parameters: Dictionary with additional parameters to control the setup.
                           The method currently supports the following parameters:

                           - 'project_tank_name': 'name' - Set the tank_name of the project to
                                                  something explicit. If not specified, this
                                                  will default to 'project_code'

                           - 'mockgun_schema_path': '/path/to/file' - Pass a specific schema to use with mockgun.
                                                    If not specified, the tk-core fixture schema
                                                    will be used.

                           - 'mockgun_schema_entity_path': '/path/to/file' - Pass a specific entity schema to use with
                                                           mockgun. If not specified, the tk-core fixture schema
                                                           will be used.


        """
        # Override SHOTGUN_HOME so that unit tests can be sandboxed.
        self._old_shotgun_home = os.environ.get(self.SHOTGUN_HOME)
        os.environ[self.SHOTGUN_HOME] = TANK_TEMP

        # Make sure the global settings instance has been reset so anything from a previous test doesn't
        # leak into the next one.
        UserSettings.clear_singleton()

        parameters = parameters or {}

        if "project_tank_name" in parameters:
            project_tank_name = parameters["project_tank_name"]
        else:
            # default project name
            project_tank_name = "project_code"

        # now figure out mockgun location
        # 1. see if we have it explicitly specified in the parameters
        # 2. if not, check if the fixtures location has a mockgun folder
        # 3. if not, fall back on built in mockgun fixtures

        if "mockgun_schema_path" in parameters:
            mockgun_schema_path = parameters["mockgun_schema_path"]

        elif os.path.exists(os.path.join(self.fixtures_root, "mockgun")):
            mockgun_schema_path = os.path.join(
                self.fixtures_root,
                "mockgun",
                "schema.pickle"
            )

        else:
            # use the std core fixtures
            mockgun_schema_path = os.path.join(
                self.tank_source_path,
                "tests",
                "fixtures",
                "mockgun",
                "schema.pickle"
            )


        if "mockgun_schema_entity_path" in parameters:
            mockgun_schema_entity_path = parameters["mockgun_schema_entity_path"]

        elif os.path.exists(os.path.join(self.fixtures_root, "mockgun")):
            mockgun_schema_entity_path = os.path.join(
                self.fixtures_root,
                "mockgun",
                "schema_entity.pickle"
            )

        else:
            # use the std core fixtures
            mockgun_schema_entity_path = os.path.join(
                self.tank_source_path,
                "tests",
                "fixtures",
                "mockgun",
                "schema_entity.pickle"
            )

        # set up mockgun to use our schema
        mockgun.Shotgun.set_schema_paths(mockgun_schema_path, mockgun_schema_entity_path)

        self.tank_temp = TANK_TEMP

        self.cache_root = os.path.join(self.tank_temp, "cache_root")

        # Mock this so that authentication manager works even tough we are not in a config.
        # If we don't mock it than the path cache calling get_current_user will fail.
        self._mock_return_value(
            "tank.util.shotgun.get_associated_sg_config_data",
            {"host": "https://somewhere.shotguntudio.com"}
        )

        # define entity for test project
        self.project = {"type": "Project",
                        "id": 1,
                        "tank_name": project_tank_name,
                        "name": "project_name"}

        self.project_root = os.path.join(self.tank_temp, self.project["tank_name"].replace("/", os.path.sep) )

        self.pipeline_config_root = os.path.join(self.tank_temp, "pipeline_configuration")

        # move away previous data
        self._move_project_data()

        # create new structure
        os.makedirs(self.project_root)
        os.makedirs(self.pipeline_config_root)

        # project level config directories
        self.project_config = os.path.join(self.pipeline_config_root, "config")

        # create project cache directory
        project_cache_dir = os.path.join(self.pipeline_config_root, "cache")
        os.mkdir(project_cache_dir)

        # define entity for pipeline configuration
        self.sg_pc_entity = {"type": "PipelineConfiguration",
                             "code": "Primary",
                             "id": 123,
                             "project": self.project,
                             "windows_path": self.pipeline_config_root,
                             "mac_path": self.pipeline_config_root,
                             "linux_path": self.pipeline_config_root}



        # add files needed by the pipeline config
        pc_yml = os.path.join(self.pipeline_config_root, "config", "core", "pipeline_configuration.yml")
        pc_yml_data = ("{ project_name: %s, use_shotgun_path_cache: true, pc_id: %d, "
                       "project_id: %d, pc_name: %s}\n\n" % (self.project["tank_name"],
                                                             self.sg_pc_entity["id"],
                                                             self.project["id"],
                                                             self.sg_pc_entity["code"]))
        self.create_file(pc_yml, pc_yml_data)

        loc_yml = os.path.join(self.pipeline_config_root, "config", "core", "install_location.yml")
        loc_yml_data = "Windows: '%s'\nDarwin: '%s'\nLinux: '%s'" % (self.pipeline_config_root, self.pipeline_config_root, self.pipeline_config_root)
        self.create_file(loc_yml, loc_yml_data)

        # inject this file which toolkit is probing for to determine
        # if an installation has been localized.
        localize_token_file = os.path.join(self.pipeline_config_root, "install", "core", "_core_upgrader.py")
        self.create_file(localize_token_file, "foo bar")

        roots = {"primary": {}}
        for os_name in ["windows_path", "linux_path", "mac_path"]:
            #TODO make os specific roots
            roots["primary"][os_name] = self.tank_temp
        roots_path = os.path.join(self.pipeline_config_root, "config", "core", "roots.yml")
        roots_file = open(roots_path, "w")
        roots_file.write(yaml.dump(roots))
        roots_file.close()

        # clear bundle in-memory cache
        sgtk.descriptor.io_descriptor.factory.g_cached_instances = {}

        self.pipeline_configuration = sgtk.pipelineconfig_factory.from_path(self.pipeline_config_root)
        self.tk = tank.Tank(self.pipeline_configuration)

        # set up mockgun and make sure shotgun connection calls route via mockgun
        self.mockgun = mockgun.Shotgun("http://unit_test_mock_sg", "mock_user", "mock_key")
        # fake a version response from the server
        self.mockgun.server_info = {"version": (7, 0, 0)}

        self._mock_return_value("tank.util.shotgun.get_associated_sg_base_url", "http://unit_test_mock_sg")
        self._mock_return_value("tank.util.shotgun.create_sg_connection", self.mockgun)

        # add project to mock sg and path cache db
        self.add_production_path(self.project_root, self.project)

        # add pipeline configuration
        self.add_to_sg_mock_db(self.sg_pc_entity)

        # add local storage
        self.primary_storage = {"type": "LocalStorage",
                                "id": 7777,
                                "code": "primary",
                                "windows_path": self.tank_temp,
                                "linux_path": self.tank_temp,
                                "mac_path": self.tank_temp }

        self.add_to_sg_mock_db(self.primary_storage)

        # back up the authenticated user in case a unit test doesn't clean up correctly.
        self._authenticated_user = sgtk.get_authenticated_user()

    def _mock_return_value(self, to_mock, return_value):
        """
        Mocks a method with to return a specified return value.

        :param to_mock: Path to the method to mock
        :param return_value: Value to return from the mocked method.
        """
        patch = mock.patch(to_mock, return_value=return_value)
        patch.start()
        self.addCleanup(patch.stop)

    def tearDown(self):
        """
        Cleans up after tests.
        """
        try:
            sgtk.set_authenticated_user(self._authenticated_user)

            # get rid of path cache from local ~/.shotgun storage
            pc = path_cache.PathCache(self.tk)
            path_cache_file = pc._get_path_cache_location()
            pc.close()
            if os.path.exists(path_cache_file):
                os.remove(path_cache_file)

            # clear global shotgun accessor
            tank.util.shotgun._g_sg_cached_connections = threading.local()

            # get rid of init cache
            if os.path.exists(pipelineconfig_factory._get_cache_location()):
                os.remove(pipelineconfig_factory._get_cache_location())

            # move project scaffold out of the way
            self._move_project_data()
            # important to delete this to free memory
            self.tk = None
        finally:
            if self._old_shotgun_home is not None:
                os.environ[self.SHOTGUN_HOME] = self._old_shotgun_home
            else:
                del os.environ[self.SHOTGUN_HOME]

    def setup_fixtures(self, name='config', parameters=None):
        """
        Helper method which sets up a standard toolkit configuration
        given a configuration template.

        :param name: Name of the fixture to use. This is useful if you want to have multiple
                     toolkit configurations to test against. By default, the fixtures will look for
                     a `config` folder under the fixtures location, but if you for example wanted to
                     have a `vfx_config` fixture and a `games_config` fixture to run your tests against,
                     simply specify the name parameter.
        :param parameters: Dictionary with additional parameters to control the fixtures.
                           The method currently supports the following parameters:

                           - 'core': 'foo/bar' - This makes it possible to override
                                                 the path to the core location within the config.
                                                 As the fixtures are being set up, the foo/bar folder
                                                 will be copied into the core location of the final
                                                 fixtures config.

                           - 'skip_template_reload': True - Tell the fixtures loader not to reload
                                                            templates. This is useful if you need to
                                                            do post processing of your fixtures or config
                                                            and don't want to load templates into the tk
                                                            instance just yet.
        """

        parameters = parameters or {}

        # figure out root point of fixtures config
        config_root = os.path.join(self.fixtures_root, name)

        # first figure out core location
        if "core" in parameters:
            # convert slashes to be windows friendly
            core_path_suffix = parameters["core"].replace("/", os.sep)
            core_source = os.path.join(config_root, core_path_suffix)
        else:
            # use the default core fixture
            core_source = os.path.join(config_root, "core")

        # copy core over to target
        core_target = os.path.join(self.project_config, "core")
        self._copy_folder(core_source, core_target)

        # now copy the rest of the config fixtures
        for config_folder in ["env", "hooks", "bundles"]:
            config_source = os.path.join(config_root, config_folder)
            if os.path.exists(config_source):
                config_target = os.path.join(self.project_config, config_folder)
                self._copy_folder(config_source, config_target)

        if not ("skip_template_reload" in parameters and parameters["skip_template_reload"]):
            # no skip_template_reload flag set to true. So go ahead and reload
            self.tk.reload_templates()


    def setup_multi_root_fixtures(self):
        """
        Helper method which sets up a standard multi-root set of fixtures
        """
        self.setup_fixtures(parameters = {"core": "core.override/multi_root_core",
                                          "skip_template_reload": True})

        # Add multiple project roots
        project_name = os.path.basename(self.project_root)
        self.alt_root_1 = os.path.join(self.tank_temp, "alternate_1", project_name)
        self.alt_root_2 = os.path.join(self.tank_temp, "alternate_2", project_name)

        # add local storages to represent the alternate root points
        self.alt_storage_1 = {"type": "LocalStorage",
                              "id": 7778,
                              "code": "alternate_1",
                              "windows_path": os.path.join(self.tank_temp, "alternate_1"),
                              "linux_path": os.path.join(self.tank_temp, "alternate_1"),
                              "mac_path": os.path.join(self.tank_temp, "alternate_1") }
        self.add_to_sg_mock_db(self.alt_storage_1)

        self.alt_storage_2 = {"type": "LocalStorage",
                              "id": 7779,
                              "code": "alternate_2",
                              "windows_path": os.path.join(self.tank_temp, "alternate_2"),
                              "linux_path": os.path.join(self.tank_temp, "alternate_2"),
                              "mac_path": os.path.join(self.tank_temp, "alternate_2") }
        self.add_to_sg_mock_db(self.alt_storage_2)

        # Write roots file
        roots = {"primary": {}, "alternate_1": {}, "alternate_2": {}}
        for os_name in ["windows_path", "linux_path", "mac_path"]:
            #TODO make os specific roots
            roots["primary"][os_name]     = os.path.dirname(self.project_root)
            roots["alternate_1"][os_name] = os.path.dirname(self.alt_root_1)
            roots["alternate_2"][os_name] = os.path.dirname(self.alt_root_2)
        roots_path = os.path.join(self.pipeline_config_root, "config", "core", "roots.yml")
        roots_file = open(roots_path, "w")
        roots_file.write(yaml.dump(roots))
        roots_file.close()

        # need a new pipeline config object that is using the
        # new roots def file we just created
        self.pipeline_configuration = sgtk.pipelineconfig_factory.from_path(self.pipeline_config_root)
        # push this new pipeline config into the tk api
        self.tk._Sgtk__pipeline_config = self.pipeline_configuration

        # force reload templates
        self.tk.reload_templates()

        # add project root folders
        # primary path was already added in base setUp
        self.add_production_path(self.alt_root_1, self.project)
        self.add_production_path(self.alt_root_2, self.project)

        self.tk.create_filesystem_structure("Project", self.project["id"])

    def add_production_path(self, path, entity=None):
        """
        Creates project directories, populates path cache and mocked shotgun from a
        path an entity.

        :param path: Path of directory to create, relative to it's project.
        :param entity: Entity to add to path cache, mocked shotgun and for which
                       to write an entity file. Should be dictionary with 'type',
                       'name', and 'id' keys.
        """
        full_path = os.path.join(self.project_root, path)
        if not os.path.exists(full_path):
            # create directories
            os.makedirs(full_path)
        if entity:
            # add to path cache
            self.add_to_path_cache(full_path, entity)
            # populate mock sg
            self.add_to_sg_mock_db(entity)

    def add_to_path_cache(self, path, entity):
        """
        Adds a path and entity to the path cache sqlite db.

        :param path: Absolute path to add.
        :param entity: Entity dictionary with values for keys 'id', 'name', and 'type'
        """

        # fix name/code discrepancy
        if "code" in entity:
            entity["name"] = entity["code"]

        path_cache = tank.path_cache.PathCache(self.tk)

        data = [ {"entity": {"id": entity["id"],
                             "type": entity["type"],
                             "name": entity["name"]},
                  "metadata": [],
                  "path": path,
                  "primary": True } ]
        path_cache.add_mappings(data, None, [])

        # On windows path cache has persisted, interfering with teardowns, so get rid of it.
        path_cache.close()
        del(path_cache)

    def debug_dump(self):
        """
        Prints out the contents of the mockgun shotgun database and the path cache
        """
        print ""
        print "-----------------------------------------------------------------------------"
        print " Shotgun contents:"

        print pprint.pformat(self.tk.shotgun._db)
        print ""
        print ""
        print "Path Cache contents:"

        path_cache = tank.path_cache.PathCache(self.tk)
        c = path_cache._connection.cursor()
        for x in list(c.execute("select * from path_cache" )):
            print x
        c.close()
        path_cache.close()

        print "-----------------------------------------------------------------------------"
        print ""

    def add_to_sg_mock_db(self, entities):
        """
        Adds an entity or entities to the mocked shotgun database.

        :param entities: A shotgun style dictionary with keys for id, type, and name
                         defined. A list of such dictionaries is also valid.
        """
        # make sure it's a list
        if isinstance(entities, dict):
            entities = [entities]
        for entity in entities:
            # entity: {"id": 2, "type":"Shot", "name":...}
            # wedge it into the mockgun database
            et = entity["type"]
            eid = entity["id"]

            # special retired flag for mockgun
            entity["__retired"] = False

            # turn any dicts into proper type/id/name refs
            for x in entity:
                # special case: EventLogEntry.meta is not an entity link dict
                if isinstance(entity[x], dict) and x != "meta":
                    # make a std sg link dict with name, id, type
                    link_dict = {"type": entity[x]["type"], "id": entity[x]["id"] }

                    # most basic case is that there already is a name field,
                    # in that case we are done
                    if "name" in entity[x]:
                        link_dict["name"] = entity[x]["name"]

                    elif entity[x]["type"] == "Task":
                        # task has a 'code' field called content
                        link_dict["name"] = entity[x]["content"]

                    elif "code" not in entity[x]:
                        # auto generate a code field
                        link_dict["name"] = "mockgun_autogenerated_%s_id_%s" % (entity[x]["type"], entity[x]["id"])

                    else:
                        link_dict["name"] = entity[x]["code"]

                    # print "Swapping link dict %s -> %s" % (entity[x], link_dict)
                    entity[x] = link_dict

            self.tk.shotgun._db[et][eid] = entity

    def create_file(self, file_path, data=""):
        """
        Creates a file on disk with specified data. First the file's directory path will be
        created, and then a file with contents matching input data.

        :param file_path: Absolute path to the file.
        :param data: (Optional)Data to be written in the file.
        """
        if not file_path.startswith(self.tank_temp):
            raise Exception("Only files in the test data area should be created with this method.")

        dir_path = os.path.dirname(file_path)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

        open_file = open(file_path, "w")
        open_file.write(data)
        open_file.close()

    def check_error_message(self, Error, message, func, *args, **kws):
        """
        Check that the correct exception is raised with the correct message.

        :param Error: The exception that is expected.
        :param message: The expected message on the exception.
        :param func: The function to call.
        :param args: Arguments to be passed to the function.
        :param kws: Keyword arguments passed to the function.

        :rasies: Exception if correct exception is not raised, or the message on the exception
                 does not match that specified.
        """
        self.assertRaises(Error, func, *args, **kws)

        try:
            func(*args, **kws)
        except Error, e:
            self.assertEquals(message, e.message)

    def _move_project_data(self):
        """
        Calls _move_data for all project roots.
        """
        _move_data(self.pipeline_config_root)
        _move_data(self.project_root)
        _move_data(self.alt_root_1)
        _move_data(self.alt_root_2)

    def _copy_folder(self, src, dst):
        """
        Alternative implementation to shutil.copytree
        Copies recursively with very open permissions.
        Creates folders if they don't already exist.
        """
        files = []

        if not os.path.exists(dst):
            os.mkdir(dst, 0777)

        names = os.listdir(src)
        for name in names:

            srcname = os.path.join(src, name)
            dstname = os.path.join(dst, name)

            if os.path.isdir(srcname):
                files.extend( self._copy_folder(srcname, dstname) )
            else:
                shutil.copy(srcname, dstname)
                files.append(srcname)
                # if the file extension is sh, set executable permissions
                if dstname.endswith(".sh") or dstname.endswith(".bat"):
                    # make it readable and executable for everybody
                    os.chmod(dstname, 0777)

        return files


def _move_data(path):
    """
    Rename directory to backup name, if backup currently exists replace it.
    """
    if path and os.path.exists(path):
        dirname, basename = os.path.split(path)
        new_basename = "%s.old" % basename
        backup_path = os.path.join(dirname, new_basename)
        if os.path.exists(backup_path):
            shutil.rmtree(backup_path)

        try:
            os.rename(path, backup_path)
        except WindowsError:
            # On windows intermittent problems with sqlite db file occur
            tk = sgtk.sgtk_from_path(path)
            pc = path_cache.PathCache(tk)
            db_path = pc._get_path_cache_location()
            if os.path.exists(db_path):
                print 'Removing db %s' % db_path
                # Importing pdb allows the deletion of the sqlite db sometimes...
                import pdb
                # try multiple times, waiting longer in between
                for count in range(5):
                    try:
                        os.remove(db_path)
                        break
                    except WindowsError:
                        time.sleep(count*2)
            os.rename(path, backup_path)
