"""
Copyright (c) 2012 Shotgun Software, Inc
"""
import sys
import os
from optparse import OptionParser
import unittest2 as unittest

# prepend tank_vendor location to PYTHONPATH to make sure we are running
# the tests against the vendor libs, not local libs on the machine
python_path = os.path.abspath(os.path.join( os.path.dirname(__file__), "..", "python"))
print "Adding tank location to python_path: %s" % python_path
sys.path = [python_path] + sys.path

# prepend tank_vendor location to PYTHONPATH to make sure we are running
# the tests against the vendor libs, not local libs on the machine
python_path = os.path.abspath(os.path.join( os.path.dirname(__file__), "python"))
print "Adding tests/python location to python_path: %s" % python_path
sys.path = [python_path] + sys.path


class TankTestRunner(object):
    def __init__(self):
        file_path = os.path.abspath(__file__)
        self.test_path = os.path.dirname(file_path)
        self.packages_path = os.path.join(os.path.dirname(self.test_path), "python")
        sys.path.append(self.packages_path)
        sys.path.append(self.test_path)
        self.suite = None

    def setup_suite(self, test_name):
        # args used to specify specific module.TestCase.test
        if test_name:
            self.suite = unittest.loader.TestLoader().loadTestsFromName(test_name)
        else:
            self.suite = unittest.loader.TestLoader().discover(self.test_path)

    def run_tests_with_coverage(self, test_name):
        import coverage
        shotgun_path = os.path.join(self.packages_path, "shotgun_api3")
        shotgun_path = shotgun_path + os.path.sep + "*"
        cov = coverage.coverage(source=["tank"], omit=shotgun_path)
        cov.start()
        self.setup_suite(test_name)
        result = unittest.TextTestRunner(verbosity=2).run(self.suite)
        cov.stop()
        cov.report()
        cov.xml_report(outfile="coverage.xml")
        return result

    def run_tests(self, test_name):
        self.setup_suite(test_name)
        return unittest.TextTestRunner(verbosity=2).run(self.suite)


if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("--with-coverage",
                      action="store_true",
                      dest="coverage", 
                      help="run with coverage (requires coverage is installed)")
    (options, args) = parser.parse_args()
    test_name = None
    if args:
        test_name = args[0]
     
    tank_test_runner = TankTestRunner()

    if options.coverage:
        ret_val = tank_test_runner.run_tests_with_coverage(test_name)
    else:
        ret_val = tank_test_runner.run_tests(test_name)

    # Exit value determined by failures and errors
    exit_val = 0
    if ret_val.errors or ret_val.failures:
        exit_val = 1
    sys.exit(exit_val)

