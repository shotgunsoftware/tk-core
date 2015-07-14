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
PYTHON_BASE="/Applications/Shotgun.app/Contents/Frameworks/Python"

# The path to output all built .py files to: 
UI_PYTHON_PATH=.

# Helper functions to build UI files
function build_qt {
    echo " > Building " $2
    
    # compile ui to python
    $1 $2 > $UI_PYTHON_PATH/$3.py
    
    # replace PySide imports with local imports and remove line containing Created by date
    sed -i "" -e "s/from PySide import/from . import/g" -e "/# Created:/d" $UI_PYTHON_PATH/$3.py
}

function build_ui {
    build_qt "${PYTHON_BASE}/bin/python ${PYTHON_BASE}/bin/pyside-uic --from-imports" "$1.ui" "ui_$1"
}  

function build_res {
    build_qt "${PYTHON_BASE}/bin/pyside-rcc" "$1.qrc" "$1_rc"
}


# build UI's:
echo "building user interfaces..."
build_ui tank_dialog
build_ui item
build_ui busy_dialog

# build resources
echo "building resources..."
build_res resources
