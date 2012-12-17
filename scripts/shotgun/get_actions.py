#
# Copyright (c) 2012 Shotgun Software, Inc
# ----------------------------------------------------
#
# get_tank_actions.py <project_root>

import os
import sys
import logging
import tank

def main():
    if ( len(sys.argv) != 2 ):
        print "Invalid number of arguments to get_tank_actions.py"
        print "Expecting tank_project"
        sys.exit(1)
        
    proj_root = sys.argv[1]
    
    # Instantiate the sg_shotgun engine with an empty context.
    tk = tank.Tank(proj_root)
    context = tk.context_from_path(proj_root)
    tank.platform.start_engine("tk-shotgun", tk, context)
    curr_engine = tank.platform.current_engine()
    
    # Get the action list
    res = curr_engine.get_actions()
    
    # Write to cache file
    path = os.path.join(proj_root, "tank", "cache", "shotgun-actions.txt")
    f = open(path, "w")
    f.write(res)
    f.close()
    

if __name__ == "__main__":
    main()
    
