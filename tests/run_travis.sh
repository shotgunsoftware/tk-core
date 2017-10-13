#!/usr/bin/env bash
set -e

python -m compileall python/tank
python -m compileall tests/*.py
python -m compileall tests/*/*.py

if [[ $SHOTGUN_COMPILE_ONLY -eq 1 ]]; then
    exit 0
fi

PYTHONPATH=tests/python/third_party python tests/python/third_party/coverage run tests/run_tests.py
