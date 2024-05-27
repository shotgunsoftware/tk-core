#!/usr/bin/env bash
set -e
#
# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

# The path to output all built .py files to:
UI_PYTHON_PATH=../ui
if [ -z "${PYTHON_BASE}" ]; then
    PYTHON_BASE="/Applications/Shotgun.app/Contents/Resources/Python"
fi

# Helper functions to build UI files
function build_qt {
    # compile ui to python
    echo "$1 $2 > $UI_PYTHON_PATH/$3.py"
    $1 $2 > $UI_PYTHON_PATH/$3.py
    # replace PySide2 imports with local imports and remove line containing Created by date
    sed -i"" -E "/^from PySide2.QtWidgets(\s.*)?$/d; /^\s*$/d" $UI_PYTHON_PATH/$3.py
    sed -i"" -E "s/^(from PySide.\.)(\w*)(.*)$/from .qt_abstraction import \2\nfor name, cls in \2.__dict__.items():\n    if isinstance(cls, type): globals()[name] = cls\n/g" $UI_PYTHON_PATH/$3.py
    sed -i"" -E "s/from PySide2 import/from .qt_abstraction import/g" $UI_PYTHON_PATH/$3.py
}

function build_ui {
    build_qt "$1 -g python --from-imports" "$2.ui" "$2"
}

function build_res {
    build_qt "$1 -g python" "$2.qrc" "$2_rc"
}

while getopts u:r: flag
do
    case "${flag}" in
        u) uic=${OPTARG};;
        r) rcc=${OPTARG};;
    esac
done

if [ -z "$uic" ]; then
    echo "the PySide uic compiler must be specified with the -u parameter"
    exit 1
fi

if [ -z "$rcc" ]; then
    echo "the PySide rcc compiler must be specified with the -r parameter"
    exit 1
fi

uicversion=$(${uic} --version)
rccversion=$(${rcc} --version)


if [ -z "$uicversion" ]; then
    echo "the PySide uic compiler version cannot be determined"
    exit 1
fi

if [ -z "$rccversion" ]; then
    echo "the PySide rcc compiler version cannot be determined"
    exit 1
fi

echo "Using PySide uic compiler version: ${uicversion}"
echo "Using PySide rcc compiler version: ${rccversion}"

# build UI's:
echo "building user interfaces..."
build_ui $uic login_dialog

# build resources
echo "building resources..."
build_res $rcc resources
