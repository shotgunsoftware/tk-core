#!/usr/bin/env bash
# 
# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

echo "building user interfaces..."
pyside-uic --from-imports tank_dialog.ui > ./ui_tank_dialog.py
pyside-uic --from-imports item.ui > ./ui_item.py

echo "building resources..."
pyside-rcc resources.qrc > ./resources_rc.py
