#!/usr/bin/env bash
#
# Copyright (c) 2018 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

echo "This script will update the local sso_saml2 package with the requested version."
echo ""
echo "Script syntax: $0 sso_saml2_tag"
echo "For example:   $0 v3.0.31"
echo ""
echo ""
echo "A commit_id file will be written to the sso_saml2 distribution to "
echo "indicate which version of the sso_saml2 API is being bundled with core."
echo ""
echo "This script is intended to be used by developers and maintainers of the sso_saml2 API."
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
    echo "ERROR: No tag provided! Check script syntax above. Exiting."
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
SRC_REPO=git@github.com:shotgunsoftware/sso_saml2.git
# Where we'll clone the repo
DEST_REPO=$ROOT/repo
# Destination relative to this script for the files
DEST=`pwd`/../python/tank/authentication/sso_saml2

# Recreate the folder structure
mkdir $ROOT
mkdir $DEST_REPO
# Strip files from the destination and recreate it.
rm -rf $DEST/*

echo "Cloning the sso_saml2 API into a temp location, hang on..."
# Clone the repo
git clone --depth 1 --branch $1 $SRC_REPO $DEST_REPO

echo "Copying sso_saml2 API to the required location..."

# Copy the files to the destination
cp -R $DEST_REPO/sso_saml2 $DEST/..

echo "Creating the commit_id file"
pushd $DEST_REPO/sso_saml2
git rev-parse HEAD > $DEST/commit_id
popd

# Put files in the staging area.
echo "adding new files to git..."
git add -A $DEST

# Cleanup!
echo "cleaning up..."
rm -rf $ROOT

echo ""
echo "All done! The sso_saml2 API in $DEST has been updated to $1."
echo "The changes have been added to git and are ready to be committed."
trap : 0
