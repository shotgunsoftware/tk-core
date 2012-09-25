#
# Copyright (c) 2012 Shotgun Software, Inc
# ----------------------------------------------------

# Run an action from Shotgun. Expected usage:
#
# run_action.py <project_root> <name of action> <entity type> <comma separated list of entity ids>
#
# For example:
#
# run_action.py bogus_project_root launch_maya Task 9
# run_action.py bogus_project_root create_folders Shot 9,11,13,15

import sys
import logging
import tank

def run_action(proj_root, action_name, entity_type, entity_ids):
    # Instantiate the sg_shotgun engine with an empty context.
    tk = tank.Tank(proj_root)
    context = tk.context_from_path(proj_root)
    tank.platform.start_engine("tk-shotgun", tk, context)
    curr_engine = tank.platform.current_engine()

    ret_value = 0
    cmd = curr_engine.commands.get(action_name)
    if cmd:
        try:
            cmd["callback"](entity_type, entity_ids)
        except Exception:
            curr_engine.log_exception("Encountered error when running the command %s" % action_name)
            ret_value = 1
    else:
        # unknown command
        curr_engine.log_exception("A command named '%s' is not registered with Tank!" % action_name)
        ret_value = 1
    
    return ret_value

if __name__ == "__main__":    
    if ( len(sys.argv) != 5 ):
        print "Invalid number of arguments to run_action.py"
        print "Expecting tank_project action_name entity_type id1,id2,id3"
        sys.exit(1)
    
    proj_root = sys.argv[1]
    action_name = sys.argv[2]
    entity_type = sys.argv[3]
    entity_ids = sys.argv[4].split(",")
    entity_ids = [int(x) for x in entity_ids]   
    
    ret_value = run_action(proj_root, action_name, entity_type, entity_ids)
    sys.exit(ret_value)
    
