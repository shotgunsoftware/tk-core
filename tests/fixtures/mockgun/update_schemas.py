import sys

sys.path.append("../../../python")

from sgtk.authentication import ShotgunAuthenticator
from tank_vendor.shotgun_api3.lib import mockgun

# Log on a site.
print "This script will update the Shotgun schema for Mockgun."
print "Please enter your credentials for the site you wish to clone the schema from."
user = ShotgunAuthenticator().get_user_from_prompt()

# Retrieve the schema folder validation
sg = user.create_sg_connection()
schema = sg.schema_read()
schema_entity = sg.schema_entity_read()

print "Validating schema..."
errors = []

# Validate certain entities are present.
for entity in ["TankType", "TankDependency", "TankPublishedFile", "Scene", "CustomEntity02"]:
    if entity not in schema.keys():
        errors.append("Entity '%s' is missing." % entity)

for field in ["sg_descriptor", "sg_plugin_ids"]:
    if field not in schema["PipelineConfiguration"]:
        errors.append("Missing field '%s' on entity 'PipelineConfiguration'." % field)

if errors:
    print "There are problems with the schema:"
    for e in errors:
        print "-", e
else:
    print "Saving schema..."
    mockgun.generate_schema(sg, "schema.pickle", "schema_entity.pickle")
    print "Schema cloning completed!"
