import sys

sys.path.append("../../../python")

from sgtk.authentication import ShotgunAuthenticator
from tank_vendor.shotgun_api3.lib import mockgun

print "This script will update the Shotgun schema for Mockgun."
print "Please enter your credentials for the site you wish to clone the schema from."
user = ShotgunAuthenticator().get_user_from_prompt()

print "Cloning the schema..."
mockgun.generate_schema(user.create_sg_connection(), "schema.pickle", "schema_entity.pickle")
print "Schema cloning completed!"
