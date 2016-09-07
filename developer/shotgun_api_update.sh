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

echo "This script will update the local tk-core with the given version of the Shotgun API."
echo ""
echo "Script syntax: $0 shotgun_api_tag"
echo "For example:   $0 v3.0.31"
echo ""
echo ""
echo "A commit_id file will be written to the tk-core shotgun distribution to "
echo "indicate which version of the shotgun API is being bundled with core."
echo ""
echo "This script is intended to be used by developers and maintainers of the tk-core API."
echo ""
echo ""
echo ""

# ask user to continue
read -p "Ok to proceed? [Y/N] " -n 1 -r
echo    # (optional) move to a new line
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo "exiting."
    exit 1
fi

# check that there is a tag argument
if [ $# -eq 0 ]
  then
    echo ""
    echo "ERROR: No shotgun tag provided! Check script syntax above. Exiting."
    exit 1
fi

echo ""
echo ""

# Stops the script
set -e

# Where we'll temporary create some files.
ROOT=/var/tmp/tmp_dir_`date +%y.%m.%d.%H.%M.%S`

abort()
{
    echo >&2 '
***************
*** ABORTED ***
***************
'
    echo "Cleaning up $ROOT..." >&2
    rm -rf $ROOT
    exit 1
}

trap 'abort' 0

# Git repo we'll clone
SRC_REPO=git@github.com:shotgunsoftware/python-api.git
# Where we'll clone the repo
DEST_REPO=$ROOT/repo
# Zip file that will be generated from that repo
ZIP=$ROOT/tk-core.zip
UNZIPPED=$ROOT/unzipped
SHOTGUN_API_SRC=$UNZIPPED/shotgun_api3
# Destination relative to this script for the files
DEST=`pwd`/../python/tank_vendor/shotgun_api3

# Recreate the folder structure
mkdir $ROOT
mkdir $DEST_REPO

# Strip files from the destination
rm -rf $DEST

# Clone the repo
echo "Cloning the Shotgun API into a temp location, hang on..."
git clone $SRC_REPO $DEST_REPO

# Generate the zip
echo "Archiving tag '$1'..."
git archive --format zip --output $ZIP --remote $DEST_REPO $1

# Unzip the files except for the tests.
echo "unpacking tag..."
unzip $ZIP -d $UNZIPPED

# Move to the git repo to generate the sha and write it to the $DEST
echo "writing commit_id file..."
pushd $DEST_REPO
git rev-parse HEAD > $SHOTGUN_API_SRC/commit_id
popd

echo "copying files to target location..."
cp -R $SHOTGUN_API_SRC $DEST

# Put files in the staging area.
echo "adding new files to git..."
git add -A $DEST

# Cleanup!
echo "cleaning up..."
rm -rf $ROOT

echo ""
echo "All done! The shotgun API in $DEST has been updated to $1."
echo "The changes have been added to git and are ready to be committed."
trap : 0
