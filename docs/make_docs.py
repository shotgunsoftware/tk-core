# Copyright (c) 2015 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Documentation generation script.

Typically launched via make_docs.sh.

This script sets up the environment, primarily
PYTHONPATH, and then kicks off the sphinx-build command
for the given app/engine/framework.
"""

import sys
import os
from optparse import OptionParser

# check that Sphinx and PySide are available
try:
    import sphinx
except ImportError:
    print "Error: Cannot find sphinx. Please install with"
    print "> pip install -U Sphinx"
    print ""
    sys.exit(1)

try:
    import PySide
except ImportError:
    print "Error: Cannot find Pyside."
    sys.exit(1)

def main():
    """
    Script main entry point
    """
    parser = OptionParser()

    parser.add_option("--version",
                      action="store",
                      dest="version", 
                      help="App version.")
    
    parser.add_option("--bundle",
                      action="store",
                      dest="bundle", 
                      help="Toolkit app/engine/framework to generate documentation for.")

    (options, args) = parser.parse_args()

    if options.version is None:
        print "please specify a --version='v1.2.3'"
        return

    # get the current location
    this_folder = os.path.abspath(os.path.dirname(__file__))
    
    # add key locations to PYTHONPATH so that they can be picked up 
    # by sphinx and conf.py once we have started to execute the doc gen. 
    pythonpath = os.environ.get("PYTHONPATH", "").split(":")
    
    # add tk core to the pythonpath 
    core_path = os.path.abspath(os.path.join(this_folder, "..", "python"))
    pythonpath.insert(0, core_path)

    if options.bundle:
        # get key locations for this app/engine/fw
        docs_folder = os.path.join(options.bundle, "docs")
        build_folder = os.path.join(docs_folder, "build")
        # add bundle path to pythonpath (for the app.py)
        pythonpath.insert(0, options.bundle)
        # add python folder to pythonpath (for libraries)
        pythonpath.insert(0, os.path.join(options.bundle, "python"))        
        
    else:        
        # if a bundle isn't specified, default to core
        print("Generating documentation for core.")
        print("To make docs for an app/engine/framework, ")
        print("add a --bundle='/path/to/app' argument")
        docs_folder = os.path.join(this_folder, "tk-core")
        build_folder = os.path.join(docs_folder, "build")  

    if not os.path.exists(docs_folder):
        print "Cannot find folder '%s'!" % docs_folder
        return

    # write out python path
    os.environ["PYTHONPATH"] = ":".join(pythonpath)

    # run build command
    cmd = "sphinx-build -c '%s' -D version='%s' -D release='%s' '%s' '%s'" % (this_folder, options.version, options.version, docs_folder, build_folder)
    os.system(cmd)

    # make sure there is a .nojekyll file in the github repo, otherwise
    # folders beginning with an _ will be ignored
    no_jekyll = os.path.join(docs_folder, "build", ".nojekyll")
    os.system("touch '%s'" % no_jekyll)

if __name__ == "__main__":
    main()

