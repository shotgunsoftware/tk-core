Integration Tests
-----------------

This folder contains tests that need to be run in isolation because they stress
multiple parts of Toolkit. Each file can be run individually from the command-line
and often need special parameters to be able to communicate with a live Shotgun
site.

These variables, which are also set on our CI servers, should be set before running the tests.

`SHOTGUN_HOST`: URL of the live site to use to run the tests.
`SHOTGUN_SCRIPT_NAME`: Name of script on that site.
`SHOTGUN_SCRIPT_KEY`: Key for said script.

How to run an integration test
------------------------------
 - set the three environment variables
 - add `<tk-core>/python` and `<tk-core>/tests/python` in the `PYTHONPATH`
 - launch a test by typing `python <test_name>.py`.

How to write an integration test
--------------------------------

There is a special class to write integration tests named SgtkIntegrationTest and is importable through

    from sgtk_integration_test import SgtkIntegrationTest

This test class will take care of sandboxing your test in a way that multiple continuous integration
should be able to run in parallel without having the tests step on each other's toes. See `SgtkIntegrationTest`s
documentation to learn more how the class can help you sandbox tests.

Adding your test to continous integration
-----------------------------------------
For CI to run your test, you need to manually add it to `tests/run_travis.sh` 
and `tests/run_appveyor.bat`.


Future work
-----------

We should look for a proper integration test framework. What is implemented here
is a small proof of concept of what could be achieved, but shouldn't become
the way we do things.

The pre-requisites for picking a framework would have to be:

- be open-source or publicly available, as we want this to run on travis
- be able to split a test in multiple steps, which can fail the test early
- be able to run a test one step at a time to debug them
    - this is complicated right now, you need to comment out the `safe_delete_folder` call in the
      base integration class and add an underscore in front of steps you want to skip.
- make it easy to integrate code coverage from subprocesses that are invoked
    - right now the coverage is captured but can't be merged, as you can see from travis's coveralls
      command.
- make it easy to have a single test folder for multiple tests that is cleaned up on exit
