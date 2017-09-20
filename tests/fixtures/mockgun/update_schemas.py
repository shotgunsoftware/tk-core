# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
This script will update the Shotgun schema for Mockgun.
"""

import sys

sys.path.append("../../../python")

from sgtk.authentication import ShotgunAuthenticator
from tank_vendor.shotgun_api3.lib import mockgun

# Log on a site.
print "This script will update the Shotgun schema for Mockgun."
print "Please enter your credentials for the site you wish to clone the schema from. Ideally this would be "\
    "a site that has a clean schema like a new site."
user = ShotgunAuthenticator().get_user_from_prompt()

# Retrieve the schema folder validation
sg = user.create_sg_connection()
schema = sg.schema_read()
schema_entity = sg.schema_entity_read()

print "Validating schema..."
errors = []

# Dictionary of entities that need to be present.
# If the schema has been updated recently and you want to ensure certain fields are present,
# you can set an array of fields to validate for each entity.
schema_requirements = {
    # This is a builtin entity that is disabled by default.
    "Scene": [],
    # Simply turn this one on. Nothing else to do.
    "CustomEntity02": []
}

# Ensure every entity is present and their fields.
for entity, fields in schema_requirements.iteritems():
    if entity not in schema.keys():
        errors.append("Entity '%s' is missing." % entity)

    for field in fields:
        if field not in schema[entity]:
            errors.append("Missing field '%s' on entity 'PipelineConfiguration'." % field)

if errors:
    print "There are problems with the schema:"
    for e in errors:
        print "-", e
else:
    print "Saving schema..."
    mockgun.generate_schema(sg, "schema.pickle", "schema_entity.pickle")
    print "Schema cloning completed!"
