"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Runs a tank shell engine.
"""
import os
import sys
from optparse import OptionParser

import tank




def start_engine(work_path=None):
    """Starts tk-shell engine with context based on current location.

    :param work_path: Path to location in project with which to override the current working directory.
    """
    work_path = work_path or os.getcwd()
    work_path = os.path.abspath(work_path)

    tk = tank.tank_from_path(work_path)
    # use current location to get context
    context = tk.context_from_path(work_path)
    tank.platform.start_engine("tk-shell", tk, context)


def _process_command_args(arg_strs):
    """Process arguments representing key word values pairs and lists."""
    processed_args = []
    processed_kwargs = {}
    for arg_str in arg_strs:
        tokens = arg_str.split("=")
        if len(tokens) == 2:
            if "," in tokens[1]:
                processed_kwargs[tokens[0]] = tokens[1].split(",")
            else:
                processed_kwargs[tokens[0]] = tokens[1]
        elif "," in arg_str:
            processed_args.append(arg_str.split(","))
        else:
            processed_args.append(arg_str)
    return processed_args, processed_kwargs


def main():
    retval = 0
    usage =  "%prog <command> [options]\n" 
    usage += "       run_shell.sh <tank root> <command> [options]\n" 
    usage += "       run_shell.bat <tank root> <command> [options]\n\n" 
    usage += "Context will be based on the current working directory unless the work_path\n"
    usage += "option is used. Unless this option is used, this script needs to be run from\n"
    usage += "withing a valid tank project. The context will then be used to determine which\n"
    usage += "commands are registered for use.\n\n"
    usage += "Commands available in all environments:\n"
    usage += "    list - lists commands registered for current environment.\n"
    usage += "    help - print this message. If called with a command as a second argument,\n"
    usage += "           the doc-string for the command is displayed.\n"

    parser = OptionParser()
    parser.set_usage(usage)
    interactive_msg = "Run in interactive mode."
    parser.add_option("-i", 
                      "--interactive",
                      dest="interactive_mode",
                      action="store_true",
                      default=False,
                      help=interactive_msg)
    path_msg = ("Path to use in setting the engine's context." + 
                " Defaults to current working directoty." + 
                " This path must be in a tank project")
    parser.add_option("-w",
                      "--work-path",
                      action="store",
                      type="string",
                      dest="work_path",
                      default=None,
                      help=path_msg)

    options, args = parser.parse_args()
    
    command_name = (len(args) and args[0]) or None
    command_args = (len(args) > 1 and args[1:]) or []
    command_args, command_kwargs = _process_command_args(command_args)


    if command_name == "list":
        start_engine(work_path=options.work_path)
        current_engine = tank.platform.current_engine()
        print "Available commands: %s" % ", ".join(current_engine.commands.keys())

    elif command_name == "help" and command_args:
        start_engine(work_path=options.work_path)
        current_engine = tank.platform.current_engine()

        command = current_engine.commands.get(command_args[0], {}).get("callback")
        if command:
            print command.__doc__
        else:
            print "A command named %s is not registered with Tank in this environment." % command_name
            retval = 2

    elif options.interactive_mode:
        start_engine(work_path=options.work_path)
        current_engine = tank.platform.current_engine()
        if not current_engine.interact(*command_args, **command_kwargs):
            retval = 3

    elif command_name in [None, "help"]:
        parser.print_help()
        return retval

    else:
        start_engine(work_path=options.work_path)
        current_engine = tank.platform.current_engine()
        if not current_engine.run_command(command_name, *command_args, **command_kwargs):
            retval = 3

    return retval


if __name__ == "__main__":
    sys.exit(main())


