Integration Tests
-----------------

This folder contains tests that need to be run in isolation because they stress
multiple parts of Toolkit. Each file can be run individually from the command-line
and often need special parameters to be able to communicate with a live Shotgun
site.

One common set of environment variables would be:

``SHOTGUN_TEST_SITE_URL``: URL of the live site to use to run the tests.
``SHOTGUN_TEST_API_SCRIPT``: Name of script on that site.
``SHOTGUN_TEST_API_KEY``: Key for said script.

How to write an integration test
--------------------------------

There is currently no framework to write those. You should split your test
in multiple sub-tests that can be run independently, so you can run them one at
a time. You can leverage pyUnit's functionality for that.

Note that pyUnit's documentation says that tests in a tests class are sorted
alphabetically, so you can number your tests functions to order them.

Future work
-----------

We should look for a proper integration test framework. What is implemented here
is a small proof of concept of what could be achieved, but shouldn't become
the way we do things.

The pre-requisites for picking a framework would have to be:

- be open-source or publicly available, as we want this to run on travis
- be able to split a test in multiple steps, which can fail the test early
- be able to run a test one step at a time to debug them
- make it easy to integrate code coverage from subprocesses that are invoked
- make it easy to have a single test folder for multiple tests that is cleaned up on exit