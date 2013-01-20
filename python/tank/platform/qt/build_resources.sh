#!/usr/bin/env bash
# 
# Copyright (c) 2008 Shotgun Software, Inc
# ----------------------------------------------------

echo "building user interfaces..."
pyside-uic --from-imports tank_dialog.ui > ./ui_tank_dialog.py

echo "building resources..."
pyside-rcc resources.qrc > ./resources_rc.py
