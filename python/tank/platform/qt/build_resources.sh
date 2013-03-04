#!/usr/bin/env bash
# 
# Copyright (c) 2008 Shotgun Software, Inc
# ----------------------------------------------------

echo "building user interfaces..."
pyside-uic --from-imports tank_dialog.ui > ./ui_tank_dialog.py
pyside-uic --from-imports item.ui > ./ui_item.py

echo "building resources..."
pyside-rcc resources.qrc > ./resources_rc.py
