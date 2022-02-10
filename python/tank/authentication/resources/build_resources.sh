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

# The path to output all built .py files to:
UI_PYTHON_PATH=../ui

# Remove any problematic profiles from pngs.
for f in *.png; do mogrify $f; done

# Helper functions to build UI files
function build_qt {
    echo " > Building " $2

    # compile ui to python
    $1 $2 > $UI_PYTHON_PATH/$3.py

    # specific replacements
    sed -i $UI_PYTHON_PATH/$3.py -e "s/from PySide2\./from \.qt_abstraction import /g" -e "/# Created:/d"
    sed -i $UI_PYTHON_PATH/$3.py -e "s/from \.qt_abstraction import QtWidgets import \*//g"  -e "/# Created:/d"
    sed -i $UI_PYTHON_PATH/$3.py -e "s/ import \*//g"  -e "/# Created:/d"
    sed -i $UI_PYTHON_PATH/$3.py -e "s/from PySide2 import/from \.qt_abstraction import/g"  -e "/# Created:/d"

    # generic replacements
    sed -i $UI_PYTHON_PATH/$3.py -e "s/QVBoxLayout/QtGui\.QVBoxLayout/g"
    sed -i $UI_PYTHON_PATH/$3.py -e "s/QHBoxLayout/QtGui\.QHBoxLayout/g"
    sed -i $UI_PYTHON_PATH/$3.py -e "s/from  \. import resources_rc/from \. import resources_rc/g"
    sed -i $UI_PYTHON_PATH/$3.py -e "s/QSize(/QtCore.QSize(/g"
    sed -i $UI_PYTHON_PATH/$3.py -e "s/QSizePolicy/QtGui\.QSizePolicy/g"
    sed -i $UI_PYTHON_PATH/$3.py -e "s/QPixmap/QtGui\.QPixmap/g"
    sed -i $UI_PYTHON_PATH/$3.py -e "s/QLabel(/QtGui.QLabel(/g"
    sed -i $UI_PYTHON_PATH/$3.py -e "s/QStackedWidget(/QtGui.QStackedWidget(/g"
    sed -i $UI_PYTHON_PATH/$3.py -e "s/QWidget(/QtGui.QWidget(/g"
    sed -i $UI_PYTHON_PATH/$3.py -e "s/Qt\./QtCore\.Qt\./g"
    sed -i $UI_PYTHON_PATH/$3.py -e "s/QMetaObject/QtCore\.QMetaObject/g"
    sed -i $UI_PYTHON_PATH/$3.py -e "s/QLayout\./QtGui.QLayout\./g"
    sed -i $UI_PYTHON_PATH/$3.py -e "s/QLineEdit\./QtGui.QLineEdit\./g"
    sed -i $UI_PYTHON_PATH/$3.py -e "s/QRect(/QtCore.QRect(/g"
    sed -i $UI_PYTHON_PATH/$3.py -e "s/QSpacerItem(/QtGui.QSpacerItem(/g"
    sed -i $UI_PYTHON_PATH/$3.py -e "s/QCursor(/QtGui.QCursor(/g"
    sed -i $UI_PYTHON_PATH/$3.py -e "s/QPushButton(/QtGui.QPushButton(/g"
    sed -i $UI_PYTHON_PATH/$3.py -e "s/QCoreApplication\.translate/QtGui\.QApplication.translate/g"
    sed -i $UI_PYTHON_PATH/$3.py -e "s/, None))/, None, QtGui\.QApplication\.UnicodeUTF8))/g"
}

function build_ui {
    build_qt "pyside2-uic --from-imports" "$1.ui" "../ui/$1"
}

function build_res {
	# Include the "-g python" flag so that we add the `b` prefix to strings for
	# PySide2 / Python3 compatibility.
    build_qt "pyside2-rcc -g python" "$1.qrc" "../ui/$1_rc"
}

# build UIº's:
echo "building user interfaces..."
build_ui login_dialog

# build resources
echo "building resources..."
build_res resources
