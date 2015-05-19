# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import sys
import os
from optparse import OptionParser

# prepend tank_vendor location to PYTHONPATH to make sure we are running
# the tests against the vendor libs, not local libs on the machine
python_path = os.path.abspath(os.path.join( os.path.dirname(__file__), "..", "python"))
sys.path = [python_path] + sys.path

# prepend tank_vendor location to PYTHONPATH to make sure we are running
# the tests against the vendor libs, not local libs on the machine
python_path = os.path.abspath(os.path.join( os.path.dirname(__file__), "python"))
sys.path = [python_path] + sys.path

from tank_test.mockgun import *

if __name__ == "__main__":
    usage = "usage: %prog URL [options]"
    parser = OptionParser(usage)

    parser.add_option("--script", help="Script name to authenticate with.")
    parser.add_option("--key", help="Script key to authenticate with.")
    parser.add_option("--schema", help="Name of the schema to add/modify..", default="test")

    (options, args) = parser.parse_args()

    if len(args) < 1:
        parser.error("No URL provided. Don't know where to get the schema from...")

    if len(args) > 1:
        parser.error("Too many arguments provided. Just need the URL for the site to get the schema from...")

    url = args[0]

    if options.script == None or options.key == None:
        parser.error("No credentials provided to connect to %s."% url);

    try:
        schema_file = "%s.pickle" % options.schema
        schema_file_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "python", "tank_test", "schemas", schema_file))

        schema_entity_file = "%s_entity.pickle" % options.schema
        schema_entity_file_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "python", "tank_test", "schemas", schema_entity_file))

        print "Getting schema from: ", url
        generate_schema( url, options.script, options.key, schema_file_path, schema_entity_file_path)
        print ""
        print "Done!"
        print ""
        print "Schema file put here:%s"%schema_file_path
        print "Schema entity file put here:%s"%schema_entity_file_path
        exit_val = 0

    except Exception, e:
        print "Something when wrong: %s"%e
        exit_val = 1

    sys.exit(exit_val)

