Readme for Tank core tests
==========================

Running the test suite
-----------------------
The tests run with [pytest](https://docs.pytest.org/) through
[tk-toolchain](https://github.com/shotgunsoftware/tk-toolchain). Install
`tk-toolchain` and run `pytest` from the repository root:

```shell
pip install git+https://github.com/shotgunsoftware/tk-toolchain.git
pytest
```

To run a specific test file, class, or test:

```shell
pytest tests/core_tests/test_api.py
pytest tests/core_tests/test_api.py::TestApi::test_something
```

Add `--cov` to enable coverage.

Test suite layout
-----------------
The tests directory follows the package layout of the tank code, with tests for top level tank modules being at the top
level and tests for the `tank.platform` subpackage living in `tests.platform`.

Generally there is one test module per module in tank, with the test modules named with the target modules name pre-pended with "test_".
It is possible to use more than one test module for a single target module if that module has multiple classes which require substantial tests.
In general their is one test case class per method or function, though it is possible to define multiple if there is the need to test the same method with different setups.

TankTestBase
-------------
There is a tank tests module, `tank_test.tank_test_base.py` which contains both a base class from which the test cases inherit and a module level setup. This module handles the creation of test fixture data, including studio level and project level configuration.

ShotgunTestBase
---------------
This is a lighter version of the TankTestBase, which only mocks a Flow Production Tracking connection and does not write anything to disk. If you are testing parts of the API that doesn't need to write to disk, this is a faster option.

### A partial list of features
Among other features, this module includes:

#### tank_test_base.setUpModule
Module level set up function which determines test data location and sets up studio level directories therein.

#### TankTestBase.setUp
Setup method which creates a project, it's project level directories and mocked shotgun entity.

#### TankTestBase.setup_fixtures
This method copies the config files, test apps and engines from the data directory into the test project.

#### TankTestBase.add_production_path
This method adds a fake entity to the mocked shotgun, creates the entities path in test project and registers that entity with that path in the test project's path cache.

Setting up a test
-----------------
* Create a test module in the appropriate section of the tests area. If the module you wish to test is `tank.platform.foo`, the test module should be `tests.platform.test_foo`.
* In this module, import the base class and module setup method: `from tank_test.tank_test_base import setUpModule, TankTestBase`
* Create a test class inheriting from the `TankTestBase` class.
* If a setUp other than the base one is needed, be sure to call `super(TestClassName, self).setUp()` in order to allow the base class to setup the fixtures.
