#!/bin/bash

find . -name "*.pyc" -delete
python  `dirname $0`/run_tests.py $*
