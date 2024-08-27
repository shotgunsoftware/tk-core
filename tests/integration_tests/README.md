Integration Tests
-----------------

This folder contains tests that need to be run in isolation because they stress multiple parts of Toolkit. Each file can be run individually from the command-line and often need special parameters to be able to communicate with a live Flow Production Tracking site.

These variables, which are also set on our CI servers, should be set before running the tests.

`SHOTGUN_HOST`: URL of the live site to use to run the tests.
`SHOTGUN_SCRIPT_NAME`: Name of script on that site.
`SHOTGUN_SCRIPT_KEY`: Key for said script.

There are also two optional environment variables:

`SHOTGUN_TEST_TEMP`: When set, Toolkit will write all it's configuration files at this location and the data will not be erased after a test ends. This is useful for debugging.
`SHOTGUN_TEST_COVERAGE`: When set, code coverage for tk-core will be generated and result into multiple `.coverage.<machine-name>.<uuid>` files containing coverage for each test run. Note that the test folder is not deleted so `coverage combine` can get line information properly.

To run the tests you must first configure your Personal Access Token (PAT). If you have not yet configured your PAT you might not be able to run the tests. For more information on how to configure your Personal Access Token, please visit [this page](https://knowledge.autodesk.com/support/shotgrid/learn-explore/caas/CloudHelp/cloudhelp/ENU/SG-Migration/files/mi-migration/SG-Migration-mi-migration-account-mi-end-user-account-html-html.html?us_oa=akn-us&us_si=e1612a29-78a6-4503-9349-2ec30fc72e28&us_st=Personal%20Access%20Tokens).

How to run an integration test
------------------------------
Once the 3 main environment variables have been set, you can run the tests using `run_integration_tests.py`. This will run all the tests. If you only want to run one or more test, you can do so like this:

    python run_integration_tests.py first_test.py second_test.py

How to write an integration test
--------------------------------

There is a special class to write integration tests named SgtkIntegrationTest and is importable through

    from sgtk_integration_test import SgtkIntegrationTest

This test class will take care of sandboxing your test in a way that multiple continuous integration
should be able to run in parallel without having the tests step on each other's toes. See `SgtkIntegrationTest`s
documentation to learn more how the class can help you sandbox tests.

Future work
-----------

We should look for a proper integration test framework. What is implemented here
is a small proof of concept of what could be achieved, but shouldn't become
the way we do things.

The pre-requisites for picking a framework would have to be:

- be open-source or publicly available, as we want this to run on Azure Pipelines
- be able to split a test in multiple steps, which can fail the test early
- be able to run a test one step at a time to debug them
- make it easy to have a single test folder for multiple tests that is cleaned up on exit
