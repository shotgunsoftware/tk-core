Readme for Tank core tests
==========================


Required packages
-----------------
* unittest2
* mock
* coverage (only if coverage option is used)

These are all packaged under `tests/python/third_party`.

Running the test suite
-----------------------
To run the tests on windows run the core/tests/run_tests.bat. To run on linux run the script run_tests.sh. 
Add "-h" to see options.
To run specific test(s), specify module, or module.class or module.class.test:

    $ run_tests.sh test_tank_content.TestValidate.test_valid_path

To run all the tests from a specific file, you can specify both the module or file path:

    $ run_tests.sh tank_module_test.test_module
    $ run_tests.sh tank_module_test/test_module.py

To run tests without using run_tests script:

* Add the tank packages directory ( core/python ) to the PYTHONPATH 
* Use the test runner of your choice:

    `$ nosetests core/tests/` 

    or

    `$ unit2 discover core/tests`

Test suite layout
-----------------
The tests directory follows the package layout of the tank code, with tests for top level tank modules being at the top
level and tests for the `tank.platform` subpackage living in `tests.platform`.

Generally there is one test module per module in tank, with the test modules named with the target modules name pre-pended with "test_".
It is possible to use more than one test module for a single target module if that module has multiple classes which require substantial tests.
In general their is one test case class per method or function, though it is possible to define multiple if there is the need to test the same method with different setups.

TankTestBase
-------------
There is a tank tests module, `tank_test.tank_test_base.py` which contains both a base class from which the test cases inherit, and module level setup and teardown methods. This module handles the creation of test fixture data, including studio level and project level configuration. A partial list of features. Examples of the usage of this module can be found in `tank_util/example_tests.py`. Among other features, this module includes:

###tank_test_base.setUpModule
Module level set up function which determines test data location and sets up studio level directories therein. 

###TankTestBase.setUp
Setup method which creates a project, it's project level directories and mocked shotgun entity.

###TankTestBase.setup_fixtures 
This method copies the config files, test apps and engines from the data directory into the test project.

###TankTestBase.add_production_path
This method adds a fake entity to the mocked shotgun, creates the entities path in test project and registers that entity with that path in the test project's path cache.

Setting up a test
-----------------
* Create a test module in the appropriate section of the tests area. If the module you wish to test is `tank.platform.foo`,
the test module should be `tests.platform.test_foo`. 
* In this module, import the base class, module setup method and module teardown method: `from tank_test.tank_test_base import *`
* Create a test class inheriting from the `TankTestBase` class.
* If a setUp other than the base one is needed, be sure to call super(TestClassName, self).setUp() in order to allow the base class to setup the fixtures.

