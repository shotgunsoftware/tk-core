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
import getopt
from tank import TankError
from tank.deploy import setup_project

CORE_COMMANDS = ["setup_project", "clone", "core", "join", "leave"]
DEFAULT_ENGINE = "tk-shell"

def show_help():
    print("-" * 60)
    print("Welcome to Tank!")
    print("-" * 60)
    print("")
    print("This command lets you run control tank from a shell.")
    print("The following syntaxes are supported:")
    print("")
    print("> tank [context] [engine] [app] [params]")
    print("> tank admin_command [params]")
    
    
    
    print("")
    print("")
    
    


def run_core_command(log, pipeline_config_root, command, args):
    """
    Execute one of the built in commands
    """
    
    log.debug("Running built in command %s" % command)
    log.debug("Arguments passed: %s" % args)
 

    if command == "setup_project":
        # project setup
        setup_project.interactive_setup(log, pipeline_config_root)
        
    elif command == "clone":
        # fork a pipeline config
        pass
            
    elif command == "core":
        # update the core in this pipeline config
        
        # core update > update to latest
        # core        > info about which PCs are using this core + help
        # core info   > info about which PCs are using this core
        # core clone  > get local core
        
        pass
        
    elif command == "join":
        # join this PC
        pass
        
    elif command == "leave":
        # leave this PC
        pass
    
    else:
        raise TankError("Unknown command '%s'!" % command)

def run_engine(log, context_str, args):
    """
    Launches an engine
    """
    log.debug("Will start an engine. Context string passed: '%s'" % context_str)
    log.debug("Arguments passed: %s" % args)
        
    # args
    # -a tk-publish-foo --app=tk-publish-foo
    # -e tk-shotgun --engine=tk-shotgun
    # the rest of the arguments are passed on
    # if no app is given, the specified engine will start in interactive mode
    (optlist, remaining_args) = getopt.getopt(args, "e:a:", ["engine=", "app="])
    
    engine_to_launch = DEFAULT_ENGINE
    app_to_launch = None
    interactive_mode = True
    
    for (arg, value) in optlist:
        if arg == "-e" or arg == "--engine":
            engine_to_launch = value
        elif arg == "-a" or arg == "--app":
            app_to_launch = value
            interactive_mode = False
            log.debug("Will launch specific app %s" % app_to_launch)

    log.debug("Will launch engine: %s" % engine_to_launch)
    
    
    if ":" in context_str:
        # Shot:123 or Shot:foo
        chunks = context_str.split(":")
        



if __name__ == "__main__":    

    # set up logging channel for this script
    log = logging.getLogger("tank.setup_project")
    log.setLevel(logging.INFO)
    
    ch = logging.StreamHandler()
    formatter = logging.Formatter("%(levelname)s %(message)s")
    ch.setFormatter(formatter)
    log.addHandler(ch)

    # the first argument is always the path to the pipeline
    # configuration we are running from.
    if len(sys.argv) == 1:
        log.error("This script needs to be executed from the tank command!")
        sys.exit(1)
    pipeline_config_root = sys.argv[1]
        
    # pass the rest of the args into our checker
    cmd_line = sys.argv[2:] 

    # check if there is a --debug flag anywhere in the args list.
    # in that case turn on debug logging and remove the flag
    if "--debug" in cmd_line:
        log.setLevel(logging.DEBUG)
        log.debug("Running with debug output enabled.")
    cmd_line = [arg for arg in cmd_line if arg != "--debug"]

    log.debug("Full command line passed: %s" % str(sys.argv))
    log.debug("Pipeline Config Root: %s" % pipeline_config_root)

    exit_code = 1
    try:

        if len(cmd_line) == 0:
            # engine mode, shell engine, using CWD
            log.debug("Note: will pick up the context from the CWD.")
            exit_code = run_engine(log, os.getcwd(), [])
         
        elif cmd_line[0] == "-h" or cmd_line[0] == "--help":
            exit_code = show_help()
            
        elif cmd_line[0] in CORE_COMMANDS:
            exit_code = run_core_command(log, 
                                         pipeline_config_root, 
                                         cmd_line[0], 
                                         cmd_line[1:])
        
        elif cmd_line[0].startswith("-"):
            # this is a parameters (-a, --foo=x)
            # meaning that we are running engine mode with 
            # CTX=CWD
            # e.g. ./tank --app=tk-multi-dostuff
            log.debug("Note: will pick up the context from the CWD.")
            exit_code = run_engine(log, os.getcwd(), cmd_line[0:])
            
        else:
            # engine mode, first arg is the context
            log.debug("Will run engine using context string specifically passed via cmd line.")
            exit_code = run_engine(log, cmd_line[0], cmd_line[1:])

    except TankError, e:
        # one line report
        log.error("An error occurred: %s" % e)
        
    except Exception, e:
        # call stack
        log.exception("An error occurred: %s" % e)
    
    log.debug("Exiting with exit code %s" % exit_code)
    sys.exit(exit_code)
