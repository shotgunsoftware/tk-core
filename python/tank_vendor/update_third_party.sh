#!/bin/bash -e

cwd=$(dirname "$0")

if [ -z "$1" ]; then
    export PIP=pip3
else
    export PIP=$1
fi

echo "Removing all existing third party libraries from the repo."
echo "=========================================================="
rm -rf third_party/*
echo "Done!"

echo
echo "Installing all third party libraries into 'third_party' folder."
echo "==============================================================="
echo Launching $PIP
touch $cwd/third_party/__init__.py
$PIP install --target=$cwd/third_party -r $cwd/requirements.txt
rm -rf $cwd/third_party/*.dist-info