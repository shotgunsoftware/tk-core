"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

The after_project_create file is executed as part of creating a new project.
If your starter config needs to create any data in shotgun or do any other
special configuration, you can add it to this file.

The create() method will be executed as part of the setup and is passed
the following keyword arguments:

* sg -         A shotgun connection
* project_id - The shotgun project id that is being setup
* log -        A logger instance to which progress can be reported via
               standard logger methods (info, warning, error etc)

"""

# list of tank types to create for this starter configuration
REQUIRED_TYPES = ["Maya Anim",
                  "Maya Lighting",
                  "Maya Model",
                  "Maya Rig",
                  "Maya Scene",
                  "Motion Builder FBX",
                  "Nuke Script",
                  "Rendered Image",
                  "Review Quicktime",
                  "Review Sequence",
                  "Stereo Rendered Image",
                  "Diffuse Texture",
                  "Specular Texture"]

def create(sg, project_id, log, **kwargs):
    project = {"type": "Project", "id": project_id}
    entity_name = "TankType"
    cur_entities = sg.find(entity_name, [["project", "is", project]], ["code"])
    existing_types = [x["code"] for x in cur_entities]
    needed_types = set(REQUIRED_TYPES) - set(existing_types)
    for tank_type in needed_types:
        log.info("Creating tank type '%s'" % tank_type)
        sg.create(entity_name, {"code": tank_type, "project": project})

