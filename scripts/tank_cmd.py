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


if __name__ == "__main__":    

    print "hello from tank.py!"
    print sys.argv
    
    
    
