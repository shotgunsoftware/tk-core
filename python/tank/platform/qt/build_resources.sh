#!/usr/bin/env bash
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

# The path to where the PySide binaries are installed
UI_PYTHON_PATH=.

# Helper functions to build UI files
function build_qt {
    echo " > Building " $2
    # compile ui to python
    $1 $2 > $UI_PYTHON_PATH/$3.py
    # replace PySide2 imports with tank.authentication.ui.qt_abstraction
    # and then added code to set global variables for each new import.
    sed -i"" -E \
        -e "/^from PySide2.QtWidgets(\s.*)?$/d; /^\s*$/d" \
        -e "s/^(from PySide.\.)(\w*)(.*)$/from tank.authentication.ui.qt_abstraction import \2\nfor name, cls in \2.__dict__.items():\n    if isinstance(cls, type): globals()[name] = cls\n/g" \
        -e "s/from PySide2 import/from tank.authentication.ui.qt_abstraction import/g" \
        $UI_PYTHON_PATH/$3.py
}

function build_ui {
    build_qt "$1 -g python --from-imports" "$2.ui" "ui_$2"
}

function build_res {
    build_qt "$1 -g python" "$2.qrc" "$2_rc"
}

while getopts u:r:p: flag
do
    case "${flag}" in
        u) uic=${OPTARG};;
        r) rcc=${OPTARG};;
        p) pyenv=${OPTARG};;
    esac
done

if [ -z "${pyenv}" ] && [[ -n "${uic}" && -n "${rcc}" ]]; then
    pyenv=""
fi

if [ -z "${pyenv}" ] && [[ -z "${uic}" && -z "${rcc}" ]]; then
    pyenv="Applications/Shotgun.app/Contents/Resources/Python"
fi

if [ -z "${uic}" ] && [ -n "${pyenv}" ]; then
    uic="${pyenv}/pyside2-uic"
fi

if [ -z "${rcc}" ] && [ -n "${pyenv}" ]; then
    rcc="${pyenv}/pyside2-rcc"
fi

if [ -z "$uic" ];  then
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
build_ui $uic tank_dialog
build_ui $uic item
build_ui $uic busy_dialog

# build resources
echo "building resources..."
build_res $rcc resources
