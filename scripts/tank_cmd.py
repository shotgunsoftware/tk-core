#
# Copyright (c) 2012 Shotgun Software, Inc
# ----------------------------------------------------


####################################################################################
# possible modes
# 
# tank -h, --help              ----> help menu
# tank core_command args       ----> core command special stuff
#
# tank /foo/bar [params]       ----> context from path
# tank Shot:34 [params]        ----> context from entity
# tank Shot:foo [params]       ----> context from entity
# tank [params]                ----> context from CWD
#
# params are always on the form -x xyz or --xx=xyz



import sys
import os
import logging
import tank

CORE_COMMANDS = ["setup_project", "fork", "install_core", "update_core", "join", "leave"]

def show_help(log):
    log.info("help")



def run_core_command(log, command, args):
    log.info("Core command %s %s" % (command, str(args)))

def run_engine(log, context_str, args):
    log.info("context: %s" %context_str)
    log.info("args:    %s" % str(args))

if __name__ == "__main__":    

    # set up logging channel for this script
    log = logging.getLogger("tank.setup_project")
    log.setLevel(logging.INFO)
    
    ch = logging.StreamHandler()
    formatter = logging.Formatter("%(levelname)s %(message)s")
    ch.setFormatter(formatter)
    log.addHandler(ch)

    if len(sys.argv) == 1:
        # engine mode, shell engine, using CWD
        run_engine(log, os.getcwd(), [])
     
    elif sys.argv[1] == "-h" or sys.argv[1] == "--help":
        show_help(log)
        
    elif sys.argv[1] in CORE_COMMANDS:
        run_core_command(log, sys.argv[1], sys.argv[2:])
    
    else:
        # engine mode
        run_engine(log, sys.argv[1], sys.argv[2:])
        

    
    
    
