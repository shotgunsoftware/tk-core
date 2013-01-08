#!/bin/bash

find . -name "*.pyc" -delete
python2.5  `dirname $0`/run_tests.py $*
