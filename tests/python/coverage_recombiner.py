#!/usr/bin/env python
# Copyright (c) 2018 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from __future__ import print_function

"""
Scripts that sanitizes Toolkit .coverage files.
"""

# This script is necessary because when bootstrapping we unload Toolkit and reload
# it from another location. However, since we're using the same core during our unit
# tests it means we can extract some extract coverage from that new bootstrapped core.
# Just by bootstrapping a simple engine we get 26% with the default core. Once we add
# the coverage after core swapping we get 33%!

import coverage
import re
import os
import sys


def main():

    current_folder = os.path.abspath(sys.argv[1])

    coverage_file = os.path.join(current_folder, ".coverage")

    print("Reading coverage data from '%s'..." % coverage_file)

    # Read in the orignal data
    original_cov_data = coverage.CoverageData()
    original_cov_data.read_file(coverage_file)

    # We're going to combine the results in a new file.
    combiner = coverage.CoverageData()

    # This regular expression
    re_python_roots = re.compile("^.*(python/tank/.*)")

    for measured_file in original_cov_data.measured_files():
        if current_folder in measured_file:
            print("Processing %s" % measured_file)
            combiner.add_lines(
                {measured_file: original_cov_data.lines(measured_file)}
            )
        else:

            # Extracts the python/tank/* part of the file name.
            python_tank_file = re_python_roots.match(measured_file).groups()[0]

            repathed_file = os.path.join(current_folder, python_tank_file)

            print("Processing %s -> %s" % (measured_file, repathed_file))
            combiner.add_lines(
                {repathed_file: original_cov_data.lines(measured_file)}
            )

    print("Writing combined coverage data from '%s'..." % coverage_file)
    combiner.write_file(coverage_file)
    print("Done!")

if __name__ == "__main__":
    main()
