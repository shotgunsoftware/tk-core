"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------
Management of multiple root locations.
"""
import os
import sys

from tank_vendor import yaml

from .errors import TankError
from . import constants

def get_project_roots(project_root):
    """Returns a mapping of project root names to root paths based on roots file.
    
    :param project_root: Path to primary project root.
    
    :returns: Dictionary of project root names to project root paths"""
    
    roots = {}
    roots_data = _read_roots_file(project_root)

    platform_name = _determine_platform()
    project_name = os.path.basename(project_root)
    
    for root_name, platform_paths in roots_data.items():
        # Use platform appropriate root path
        platform_path = platform_paths[platform_name]
        roots[root_name] = os.path.join(platform_path, project_name)

    # Use argument to check/set primary root
    if roots.get("primary", project_root) != project_root:
        err_msg = ("Primary root defined in roots.yml file does not match that passed as argument" + 
                  " (likely from Tank local storage): \n%s\n%s" % (roots["primary"], project_root))
        raise TankError(err_msg)
    roots["primary"] = project_root
    
    return roots

def platform_paths_for_root(root_name, project_root):
    """
    Returns root paths for all platform for specified root.

    :param root_name: Name of root whose paths are to be returned.
    :param project_root: Path of primary project root.
    """
    project_name = os.path.basename(project_root)
    roots_data = _read_roots_file(project_root)
    root_data = roots_data.get(root_name, {})
    # Add project directory
    for key, value in root_data.items():
        root_data[key] = os.path.join(value, project_name)
    return root_data


def _read_roots_file(project_root):
    root_file_path = constants.get_roots_file_location(project_root)
    if os.path.exists(root_file_path):
        root_file = open(root_file_path, "r")
        try:
            roots_data = yaml.load(root_file)
        finally:
            root_file.close()
    else: 
        roots_data = {}
    return roots_data

def get_primary_root(input_path):
    """
    Returns path to the primary project root.

    :param input_path: A path in the project.

    :returns: Path to primary project root
    :raises: TankError if input_path is not part of a tank project tree.
    """
    # find tank config directory
    cur_path = input_path
    while True:
        config_path = os.path.join(cur_path, "tank", "config")
        # need to test for something in project vs studio config
        if os.path.exists(config_path):
            break
        parent_path = os.path.dirname(cur_path)
        if parent_path == cur_path:
            # Topped out without finding config
            raise TankError("Path is not part of tank a project: %s" % input_path)
        cur_path = parent_path

    primary_roots_file = os.path.join(config_path, "primary_project.yml")
    if os.path.exists(primary_roots_file):
        # Get path from file
        open_file = open(primary_roots_file, "r")
        try:
            primary_paths = yaml.load(open_file)
        finally:
            open_file.close()
        platform_name = _determine_platform()
        return primary_paths.get(platform_name)
    else:
        schema_path = os.path.join(config_path, "core", "schema")
        # primary root file missing, check if it's project or studio path
        if os.path.exists(schema_path):
            return cur_path
        raise TankError("Path is not part of tank a project: %s" % input_path)


def write_primary_root(config_path, project_root):
    """
    Write a primary root file.

    :param config_path: Directory into which to write the file.
    :param project_root: Project root from which to read roots file.
    """
    primary_roots_file = os.path.join(config_path, "primary_project.yml")
    if not os.path.exists(primary_roots_file) and os.path.exists(config_path):
        primary_roots = platform_paths_for_root("primary", project_root)
        open_file = open(primary_roots_file, "w")
        open_file.write(yaml.dump(primary_roots))
        open_file.close()



            
def _determine_platform():
    system = sys.platform.lower()

    if system == 'darwin':
        platform_name = "mac_path"
    elif system.startswith('linux'):
        platform_name = 'linux_path'
    elif system == 'win32':
        platform_name = 'windows_path'
    else:
        raise TankError("Unable to determine operating system.")
    return platform_name
