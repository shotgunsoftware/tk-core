# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Shotgun utilities

"""

import os
import urllib
import urllib2
import urlparse

from tank_vendor import yaml

# use api json to cover py 2.5
from tank_vendor import shotgun_api3
json = shotgun_api3.shotgun.json
from tank_vendor.shotgun_authentication import ShotgunAuthenticator, AuthenticationModuleError

from ..errors import TankError, TankAuthenticationError
from .. import hook
from ..platform import constants
from . import login
from .defaults_manager import DefaultsManager


def __get_api_core_config_location():
    """

    Walk from the location of this file on disk to the config area.
    this operation is guaranteed to work on any valid tank installation

    Pipeline Configuration / Studio Location
       |
       |- Install
       |     \- Core
       |          \- Python
       |                \- tank
       |
       \- Config
             \- Core
    """
    # local import to avoid cyclic references
    from ..pipelineconfig_utils import get_path_to_current_core
    core_api_root = get_path_to_current_core()
    core_cfg = os.path.join(core_api_root, "config", "core")

    if not os.path.exists(core_cfg):
        full_path_to_file = os.path.abspath(os.path.dirname(__file__))
        raise TankError("Cannot resolve the core configuration from the location of the Sgtk Code! "
                        "This can happen if you try to move or symlink the Sgtk API. The "
                        "Sgtk API is currently picked up from %s which is an "
                        "invalid location." % full_path_to_file)

    return core_cfg

def __get_sg_config():
    """
    Returns the site sg config yml file for this install
    
    :returns: full path to to shotgun.yml config file
    """
    core_cfg = __get_api_core_config_location()
    return os.path.join(core_cfg, "shotgun.yml")

def get_project_name_studio_hook_location():
    """
    Returns the studio level hook that is used to compute the default project name
    
    :returns: The path to the studio level project naming hook.
    """
    
    # NOTE! This code is located here because it needs to be able to run without a project.
    # the natural place would probably have been to put this inside the pipeline configuration
    # class, however this object assumes a project that exists.
    #
    # @todo longterm we should probably establish a place in the code where we define 
    # an API or set of functions which can be executed outside the remit of a 
    # pipeline configuration/Toolkit project.
    
    core_cfg = __get_api_core_config_location()
    return os.path.join(core_cfg, constants.STUDIO_HOOK_PROJECT_NAME)

def __get_sg_config_data(shotgun_cfg_path, user="default"):
    """
    Returns the shotgun configuration yml parameters given a config file.
    
    The shotgun.yml may look like:

        host: str
        api_script: str
        api_key: str
        http_proxy: str
    
        or may now look like:
    
        <User>:
            host: str
            api_script: str
            api_key: str
            http_proxy: str
    
        <User>:
            host: str
            api_script: str
            api_key: str
            http_proxy: str

    The optional user param refers to the <User> in the shotgun.yml.
    If a user is not found the old style is attempted.    
    
    :param shotgun_cfg_path: path to config file
    :param user: Optional user to pass when a multi-user config is being read 
    :returns: dictionary with keys host, api_script, api_key and optionally http_proxy
    """
    
    # read in settings from shotgun.yml
    if not os.path.exists(shotgun_cfg_path):
        raise TankError("Could not find shotgun configuration file '%s'!" % shotgun_cfg_path)

    # load the config file
    try:
        open_file = open(shotgun_cfg_path)
        try:
            file_data = yaml.load(open_file)
        finally:
            open_file.close()
    except Exception, error:
        raise TankError("Cannot load config file '%s'. Error: %s" % (shotgun_cfg_path, error))

    return _parse_config_data(file_data, user, shotgun_cfg_path)


def _parse_config_data(file_data, user, shotgun_cfg_path):
    """
    Parses configuration data and overrides it with the studio level hook's result if available.
    :param file_data: Dictionnary with all the values from the configuration data.
    :param user: Picks the configuration for a specific user in the configuration data.
    :param shotgun_cfg_path: Path the configuration was loaded from.
    :raises: TankError if there are missing fields in the configuration. The accepted configurations are:
            - host
            - host, api_script, api_key
            In both cases, http_proxy is optional.
    :returns: A dictionary holding the configuration data.
    """
    if user in file_data:
        # new config format!
        # we have explicit users defined!
        config_data = file_data[user]
    else:
        # old format - not grouped by user
        config_data = file_data

    # now check if there is a studio level override hook which want to refine these settings
    sg_hook_path = os.path.join(__get_api_core_config_location(), constants.STUDIO_HOOK_SG_CONNECTION_SETTINGS)

    if os.path.exists(sg_hook_path):
        # custom hook is available!
        config_data = hook.execute_hook(sg_hook_path,
                                        parent=None,
                                        config_data=config_data,
                                        user=user,
                                        cfg_path=shotgun_cfg_path)

    def _raise_missing_key(key):
        raise TankError(
            "Missing required field '%s' in config '%s' for script user authentication." % (key, shotgun_cfg_path)
        )

    if not config_data.get("host"):
        _raise_missing_key("host")

    # The script authentication credentials need to be complete in order to work. They can be completely
    # omitted or fully specified, but not halfway configured.
    if config_data.get("api_script") and not config_data.get("api_key"):
        _raise_missing_key("api_key")
    if not config_data.get("api_script") and config_data.get("api_key"):
        _raise_missing_key("api_script")

    return config_data


def __create_sg_connection(config_data=None):
    """
    Creates a standard Toolkit shotgun connection.

    :param shotgun_cfg_path: Configuration data. If None, the authentication module will be responsible
                             for determining which credentials to use.
    :returns: A Shotgun connection.
    """

    try:
        if config_data:
            # Credentials were passed in, so let's run the legacy authentication mechanism for script user.
            sg = shotgun_api3.Shotgun(
                config_data["host"],
                script_name=config_data["api_script"], api_key=config_data["api_key"],
                http_proxy=config_data.get("http_proxy")
            )
        else:
            from .. import api
            # We're not running any special code for Psyop, so run the new Toolkit authentication code.

            user = api.get_current_user()
            if not user:
                sa = ShotgunAuthenticator(DefaultsManager())
                # This is needed for backwards compatibility with scripts that were written before
                # authentication was put in place.
                user = sa.get_user()
            if not user:
                raise TankAuthenticationError("No current Shotgun user available.")
            return user.create_sg_connection()
    except AuthenticationModuleError, e:
        raise TankAuthenticationError(str(e))

    # bolt on our custom user agent manager
    sg.tk_user_agent_handler = ToolkitUserAgentHandler(sg)

    return sg


def download_url(sg, url, location):
    """
    Convenience method that downloads a file from a given url.
    This method will take into account any proxy settings which have
    been defined in the Shotgun connection parameters.
    
    :param sg: sg API to get proxy connection settings from
    :param url: url to download
    :param location: path on disk where the payload should be written.
                     this path needs to exists and the current user needs
                     to have write permissions
    :returns: nothing
    """

    # now build the appropriate urrlib2 opener object.
    # this code is the same as in the Shotgun API, meaning that 
    # we can re-use the proxy configuration from the shotgun config 
    if sg.config.proxy_server:
        # handle proxy auth
        if sg.config.proxy_user and sg.config.proxy_pass:
            auth_string = "%s:%s@" % (sg.config.proxy_user, sg.config.proxy_pass)
        else:
            auth_string = ""
        proxy_addr = "http://%s%s:%d" % (auth_string, sg.config.proxy_server, sg.config.proxy_port)
        proxy_support = urllib2.ProxyHandler({"http" : proxy_addr, "https" : proxy_addr})
        opener = urllib2.build_opener(proxy_support)
        urllib2.install_opener(opener)
        
    # ok so the thumbnail was not in the cache. Get it.
    try:
        response = urllib2.urlopen(url)
        f = open(location, "wb")
        try:
            f.write(response.read())
        finally:
            f.close()
    except Exception, e:
        raise TankError("Could not download contents of url '%s'. Error reported: %s" % (url, e))
    
    
def get_associated_sg_base_url():
    """
    Returns the shotgun url which is associated with this Toolkit setup.
    This is an optimization, allowing code to get the Shotgun site URL
    without having to create a shotgun connection and then inspecting
    the base_url property.
    
    This method is equivalent to calling:
    
    create_sg_connection().base_url
    
    :returns: The base url for the associated Shotgun site
    """
    return get_associated_sg_config_data()["host"]


def get_associated_sg_config_data():
    """
    Returns the shotgun configuration which is associated with this Toolkit setup.
    :returns: The configuration data dictionary
    """
    cfg = __get_sg_config()
    return __get_sg_config_data(cfg)

    
g_sg_cached_connection = None
def get_sg_connection():
    """
    Returns a shotgun connection and maintains a global, cached connection so that only one
    object is ever returned, no matter how many times this call is made.
    
    If you have access to a tk API handle, DO NOT USE THIS METHOD! Instead, use the 
    tk.shotgun handle, which is also optimal and doesn't keep creating new instances.
    
    For all methods where no tk API handle is available (pre-init stuff and global 
    tk commands for example), this method is useful for performance reasons.
    
    Whenever a Shotgun API instance is created, it pings the server to check that 
    it is running the right versions etc. This is slow and inefficient and means that
    there will be a delay every time create_sg_connection is called.

    This method caches a global (non-threadsafe!) sg instance and thereby avoids
    the penalty of connecting to sg every single time the method is called.
    
    :return: SG API handle    
    """
    
    global g_sg_cached_connection
    if g_sg_cached_connection is None:
        g_sg_cached_connection = create_sg_connection()
    return g_sg_cached_connection

def create_sg_connection(user="default"):
    """
    Creates a standard tank shotgun connection.
    
    Note! This method returns *a brand new sg API instance*. It is slow.
    Always consider using tk.shotgun and if you don't have a tk instance,
    consider using get_sg_connection(). 
    
    Whenever a Shotgun API instance is created, it pings the server to check that 
    it is running the right versions etc. This is slow and inefficient and means that
    there will be a delay every time create_sg_connection is called.
    
    :param user: Optional shotgun config user to use when connecting to shotgun, as defined in shotgun.yml
    :returns: SG API instance
    """
    # The "user" parameter was introduced by Psyop for Psyop. We will be supporting it in legacy
    # code paths, but not in new ones.
    if user != "default":
        config_data = __get_sg_config_data(__get_sg_config(), user)
        api_handle = __create_sg_connection(config_data)
    else:
        api_handle = __create_sg_connection()
    return api_handle

g_app_store_connection = None
def create_sg_app_store_connection():
    """
    Creates a shotgun connection that can be used to access the Toolkit app store.

    :returns: (sg, dict) where the first item is the shotgun api instance and the second 
              is an sg entity dictionary (keys type/id) corresponding to to the user used
              to connect to the app store.
    """
    global g_app_store_connection

    # maintain a cache for performance
    if g_app_store_connection is not None:
        return g_app_store_connection

    config_data = __get_app_store_connection_information()

    # get connection parameters
    sg = __create_sg_connection(config_data)

    script_user = None

    # determine the script user running currently
    # get the API script user ID from shotgun
    script_user = sg.find_one(
        "ApiUser",
        [["firstname", "is", config_data["api_script"]]],
        fields=["type", "id"]
    )
    if script_user is None:
        raise TankError("Could not evaluate the current App Store User! Please contact support.")

    g_app_store_connection = sg, script_user

    return g_app_store_connection


def __get_app_store_connection_information():
    """
    Get app store connection information
    :returns: A dictionary with host, api_key, api_script and http_proxy
    """
    client_site_sg = get_sg_connection()
    (script_name, script_key) = __get_app_store_key_from_shotgun(client_site_sg)

    # connect to the app store
    config_data = {}
    config_data["host"] = constants.SGTK_APP_STORE
    config_data["api_script"] = script_name
    config_data["api_key"] = script_key
    config_data["http_proxy"] = client_site_sg.config.raw_http_proxy

    return config_data


def __get_app_store_key_from_shotgun(sg_connection):
    """
    Given a Shotgun url and script credentials, fetch the app store key
    for this shotgun instance using a special controller method.
    Returns a tuple with (app_store_script_name, app_store_auth_key)

    :param sg_connection: SG connection to the client site for which
                          app store credentials should be retrieved.
    :returns: tuple of strings with contents (script_name, script_key)
    """
    # handle proxy setup by pulling the proxy details from the main shotgun connection
    if sg_connection.config.proxy_handler:
        opener = urllib2.build_opener(sg_connection.config.proxy_handler)
        urllib2.install_opener(opener)

    # now connect to our site and use a special url to retrieve the app store script key
    session_token = sg_connection.get_session_token()
    post_data = {"session_token": session_token}
    response = urllib2.urlopen("%s/api3/sgtk_install_script" % sg_connection.base_url, urllib.urlencode(post_data)) 
    html = response.read()
    data = json.loads(html)

    return(data["script_name"], data["script_key"])


g_entity_display_name_lookup = None

def get_entity_type_display_name(tk, entity_type_code):
    """
    Returns the display name for an entity type given its type name.
    For example, if a custom entity is named "Workspace" in the
    Shotgun preferences, but is addressed as CustomEntity03 in the
    Shotgun API, this method will resolve
    CustomEntity03 -> Workspace.

    :param tk: tank handle
    :param entity_type code: API entity type name
    :returns: display name
    """

    global g_entity_display_name_lookup

    if g_entity_display_name_lookup is None:
        # now resolve the entity types into display names using the schema_entity_read method.
        g_entity_display_name_lookup = tk.shotgun.schema_entity_read()
        # returns a dictionary on the following form:
        # { 'Booking': {'name': {'editable': False, 'value': 'Booking'}}, ... }

    display_name = entity_type_code
    try:
        if entity_type_code in g_entity_display_name_lookup:
            display_name = g_entity_display_name_lookup[entity_type_code]["name"]["value"]
    except:
        pass

    return display_name

def find_publish(tk, list_of_paths, filters=None, fields=None):
    """
    Finds publishes in Shotgun given paths on disk.
    This method is similar to the find method in the Shotgun API,
    except that instead of an Entity type, a list of files is
    passed into the function.

    In addition to a list of files, shotgun filters can also be specified.
    This may be useful if for example all publishes with a certain status
    should be retrieved.

    By default, the shotgun id is returned for each successfully identified path.
    If you want to retrieve additional fields, you can specify these using
    the fields parameter.

    The method will return a dictionary, keyed by path. The value will be
    a standard shotgun query result dictionary, for example

    {
        "/foo/bar" : { "id": 234, "type": "TankPublishedFile", "code": "some data" },
        "/foo/baz" : { "id": 23,  "type": "TankPublishedFile", "code": "some more data" }
    }

    Fields that are not found, or filtered out by the filters parameter,
    are not returned in the dictionary.

    :param tk: Sgtk API Instance
    :param list_of_paths: List of full paths for which information should be retrieved
    :param filters: Optional list of shotgun filters to apply.
    :param fields: Optional list of fields from the matched entities to
                   return. Defaults to id and type.
    :returns: dictionary keyed by path
    """
    # Map path caches to full paths, grouped by storage
    # in case of sequences, there will be more than one file
    # per path cache
    # {<storage name>: { path_cache: [full_path, full_path]}}
    storages_paths = _group_by_storage(tk, list_of_paths)

    filters = filters or []
    fields = fields or []

    # make copy
    sg_fields = fields[:]
    # add these parameters to the fields list - they are needed for the internal processing
    # of the result set.
    sg_fields.append("created_at")
    sg_fields.append("path_cache")

    # PASS 1
    # because the file locations are split for each publish in shotgun into two fields
    # - the path_cache which is a storage relative, platform agnostic path
    # - a link to a storage entity
    # ...we need to group the paths per storage and then for each storage do a
    # shotgun query on the form find all records where path_cache, in, /foo, /bar, /baz etc.
    published_files = {}

    # get a list of all storages that we should look up.
    # for 0.12 backwards compatibility, add the Tank Storage.
    local_storage_names = storages_paths.keys()
    if constants.PRIMARY_STORAGE_NAME in local_storage_names:
        local_storage_names.append("Tank")

    published_file_entity_type = get_published_file_entity_type(tk)
    for local_storage_name in local_storage_names:

        local_storage = tk.shotgun.find_one("LocalStorage", [["code", "is", local_storage_name]])
        if not local_storage:
            # fail gracefully here - it may be a storage which has been deleted
            published_files[local_storage_name] = []
            continue

        # make copy
        sg_filters = filters[:]
        path_cache_filter = ["path_cache", "in"]

        # now get the list of normalized files for this storage
        # 0.12 backwards compatibility: if the storage name is Tank,
        # this is the same as the primary storage.
        if local_storage_name == "Tank":
            normalized_paths = storages_paths[constants.PRIMARY_STORAGE_NAME].keys()
        else:
            normalized_paths = storages_paths[local_storage_name].keys()

        # add all of those to the query filter
        for path_cache_path in normalized_paths:
            path_cache_filter.append(path_cache_path)

        sg_filters.append(path_cache_filter)
        sg_filters.append( ["path_cache_storage", "is", local_storage] )

        # organize the returned data by storage
        published_files[local_storage_name] = tk.shotgun.find(published_file_entity_type, sg_filters, sg_fields)


    # PASS 2
    # take the published_files structure, containing the shotgun data
    # grouped by storage, and turn that into the final data structure
    #
    matches = {}

    for local_storage_name, publishes in published_files.items():

        # get a dictionary which maps shotgun paths to file system paths
        if local_storage_name == "Tank":
            normalized_path_lookup_dict = storages_paths[constants.PRIMARY_STORAGE_NAME]
        else:
            normalized_path_lookup_dict = storages_paths[local_storage_name]

        # now go through all publish entities found for current storage
        for publish in publishes:

            path_cache = publish["path_cache"]

            # get the list of real paths matching this entry
            for full_path in normalized_path_lookup_dict.get(path_cache, []):

                if full_path not in matches:
                    # this path not yet in the list of matching publish entity data
                    matches[full_path] = publish

                else:
                    # found a match! This is most likely because the same file
                    # has been published more than once. In this case, we return
                    # the entity data for the file that is more recent.
                    existing_publish = matches[full_path]
                    if existing_publish["created_at"] < publish["created_at"]:
                        matches[full_path] = publish

    # PASS 3 -
    # clean up resultset
    # note that in order to do this we have pulled in additional fields from
    # shotgun (path_cache, created_at etc) - unless these are specifically asked for
    # by the caller, get rid of them.
    #
    for path in matches:
        delete_fields = []
        # find fields
        for field in matches[path]:
            if field not in fields and field not in ("id", "type"):
                # field is not the id field and was not asked for.
                delete_fields.append(field)
        # remove fields
        for f in delete_fields:
            del matches[path][f]

    return matches


def _group_by_storage(tk, list_of_paths):
    """
    Given a list of paths on disk, groups them into a data structure suitable for
    shotgun. In shotgun, the path_cache field contains an abstracted representation
    of the publish field, with a normalized path and the storage chopped off.

    This method aims to process the paths to make them useful for later shotgun processing.

    Returns a dictionary, keyed by storage name. Each storage in the dict contains another dict,
    with an item for each path_cache entry.


    Examples:

    ['/studio/project_code/foo/bar.0003.exr', '/secondary_storage/foo/bar']

    {'Tank':
        {'project_code/foo/bar.%04d.exr': ['/studio/project_code/foo/bar.0003.exr'] }

     'Secondary_Storage':
        {'foo/bar': ['/secondary_storage/foo/bar'] }
    }


    ['c:\studio\project_code\foo\bar', '/secondary_storage/foo/bar']

    {'Tank':
        {'project_code/foo/bar': ['c:\studio\project_code\foo\bar'] }

     'Secondary_Storage':
        {'foo/bar': ['/secondary_storage/foo/bar'] }
    }

    """
    storages_paths = {}

    for path in list_of_paths:

        # use abstracted path if path is part of a sequence
        abstract_path = _translate_abstract_fields(tk, path)
        root_name, dep_path_cache = _calc_path_cache(tk, abstract_path)

        # make sure that the path is even remotely valid, otherwise skip
        if dep_path_cache is None:
            continue

        # Update data for this storage
        storage_info = storages_paths.get(root_name, {})
        paths = storage_info.get(dep_path_cache, [])
        paths.append(path)
        storage_info[dep_path_cache] = paths
        storages_paths[root_name] = storage_info

    return storages_paths


def create_event_log_entry(tk, context, event_type, description, metadata=None):
    """
    Creates an event log entry inside of Shotgun.
    Event log entries can be handy if you want to track a process or a sequence of events.

    :param tk: Sgtk API instance

    :param context: Context which will be used to associate the event log entry

    :param event_type: String which defines the event type. The Shotgun standard suggests
                       that this should be on the form Company_Item_Action. Examples include:

                       Shotgun_Asset_New
                       Shotgun_Asset_Change
                       Shotgun_User_Login

    :param description: A verbose description explaining the meaning of this event.

    :param metadata: A dictionary of metadata information which will be attached to the event
                     log record in Shotgun. This dictionary may only contain simple data types
                     such as ints, strings etc.

    :returns: The newly created shotgun record
    """

    data = {}
    data["description"] = description
    data["event_type"] = event_type
    data["entity"] = context.entity
    data["project"] = context.project
    data["meta"] = metadata

    sg_user = login.get_current_user(tk)
    if sg_user:
        data["user"] = sg_user

    return tk.shotgun.create("EventLogEntry", data)

def get_published_file_entity_type(tk):
    """
    Return the Published File entity type
    currently being used in Shotgun
    """
    return tk.pipeline_configuration.get_published_file_entity_type()

def register_publish(tk, context, path, name, version_number, **kwargs):
    """
    Creates a Tank Published File in Shotgun.

    Required parameters:

        tk - a Sgtk API instance

        context - the context we want to associate with the publish

        path - the path to the file or sequence we want to publish. If the
               path is a sequence path it will be abstracted so that
               any sequence keys are replaced with their default values.

        name - a name, without version number, which helps distinguish
               this publish from other publishes. This is typically
               used for grouping inside of Shotgun so that all the
               versions of the same "file" can be grouped into a cluster.
               For example, for a maya publish, where we track only
               the scene name, the name would simply be that: the scene
               name. For something like a render, it could be the scene
               name, the name of the AOV and the name of the render layer.

        version_number - the version numnber of the item we are publishing.

    Optional arguments:

        task - a shotgun entity dictionary with id and type (which should always be Task).
               if no value is specified, the task will be grabbed from the context object.

        comment - a string containing a description of the comment

        thumbnail_path - a path to a thumbnail (png or jpeg) which will be uploaded to shotgun
                         and associated with the publish.

        dependency_paths - a list of file system paths that should be attempted to be registered
                           as dependencies. Files in this listing that do not appear as publishes
                           in shotgun will be ignored.

        dependency_ids - a list of publish ids which should be registered as dependencies.

        published_file_type - a tank type in the form of a string which should match a tank type
                            that is registered in Shotgun.

        update_entity_thumbnail - push thumbnail up to the attached entity

        update_task_thumbnail - push thumbnail up to the attached task

        created_by - override for the user that will be marked as creating the publish.  This should
                    be in the form of shotgun entity, e.g. {"type":"HumanUser", "id":7}

        created_at - override for the date the publish is created at.  This should be a python
                    datetime object
                    
        version_entity - the Shotgun version entity this published file should be linked to 

    """
    # get the task from the optional args, fall back on context task if not set
    task = kwargs.get("task")
    if task is None:
        task = context.task

    thumbnail_path = kwargs.get("thumbnail_path")
    comment = kwargs.get("comment")
    dependency_paths = kwargs.get('dependency_paths', [])
    dependency_ids = kwargs.get('dependency_ids', [])
    published_file_type = kwargs.get("published_file_type")
    if not published_file_type:
        # check for legacy name:
        published_file_type = kwargs.get('tank_type')
    update_entity_thumbnail = kwargs.get("update_entity_thumbnail", False)
    update_task_thumbnail = kwargs.get("update_task_thumbnail", False)
    created_by_user = kwargs.get("created_by")
    created_at = kwargs.get("created_at")
    version_entity = kwargs.get("version_entity")

    # convert the abstract fields to their defaults
    path = _translate_abstract_fields(tk, path)

    published_file_entity_type = get_published_file_entity_type(tk)

    sg_published_file_type = None
    # query shotgun for the published_file_type
    if published_file_type:
        if not isinstance(published_file_type, basestring):
            raise TankError("published_file_type must be a string")

        if published_file_entity_type == "PublishedFile":
            filters = [["code", "is", published_file_type]]
            sg_published_file_type = tk.shotgun.find_one('PublishedFileType', filters=filters)

            if not sg_published_file_type:
                # create a published file type on the fly
                sg_published_file_type = tk.shotgun.create("PublishedFileType", {"code": published_file_type})
        else:# == TankPublishedFile
            filters = [ ["code", "is", published_file_type], ["project", "is", context.project] ]
            sg_published_file_type = tk.shotgun.find_one('TankType', filters=filters)

            if not sg_published_file_type:
                # create a tank type on the fly
                sg_published_file_type = tk.shotgun.create("TankType", {"code": published_file_type, "project": context.project})

    # create the publish
    entity = _create_published_file(tk, 
                                    context, 
                                    path, 
                                    name, 
                                    version_number, 
                                    task, 
                                    comment, 
                                    sg_published_file_type, 
                                    created_by_user, 
                                    created_at, 
                                    version_entity)

    # upload thumbnails
    if thumbnail_path and os.path.exists(thumbnail_path):

        # publish
        tk.shotgun.upload_thumbnail(published_file_entity_type, entity["id"], thumbnail_path)

        # entity
        if update_entity_thumbnail == True and context.entity is not None:
            tk.shotgun.upload_thumbnail(context.entity["type"],
                                        context.entity["id"],
                                        thumbnail_path)

        # task
        if update_task_thumbnail == True and task is not None:
            tk.shotgun.upload_thumbnail("Task", task["id"], thumbnail_path)

    else:
        # no thumbnail found - instead use the default one
        this_folder = os.path.abspath(os.path.dirname(__file__))
        no_thumb = os.path.join(this_folder, "no_preview.jpg")
        tk.shotgun.upload_thumbnail(published_file_entity_type, entity.get("id"), no_thumb)


    # register dependencies
    _create_dependencies(tk, entity, dependency_paths, dependency_ids)

    return entity

def _translate_abstract_fields(tk, path):
    """
    Translates abstract fields for a path into the default abstract value.
    For example, the path /foo/bar/xyz.0003.exr will be transformed into
    /foo/bar/xyz.%04d.exr
    """
    template = tk.template_from_path(path)
    if template:

        abstract_key_names = [k.name for k in template.keys.values() if k.is_abstract]

        if len(abstract_key_names) > 0:
            # we want to use the default values for abstract keys
            cur_fields = template.get_fields(path)
            for abstract_key_name in abstract_key_names:
                del(cur_fields[abstract_key_name])
            path = template.apply_fields(cur_fields)
    return path

def _create_dependencies(tk, publish_entity, dependency_paths, dependency_ids):
    """
    Creates dependencies in shotgun from a given entity to
    a list of paths and ids. Paths not recognized are skipped.
    
    :param tk: API handle
    :param publish_entity: The publish entity to set the dependencies for. This is a dictionary
                           with keys type and id.
    :param dependency_paths: List of paths on disk. List of strings.
    :param dependency_ids: List of publish entity ids to associate. List of ints
    
    """
    published_file_entity_type = get_published_file_entity_type(tk)

    publishes = find_publish(tk, dependency_paths)

    # create a single batch request for maximum speed
    sg_batch_data = []

    for dependency_path in dependency_paths:
        
        # did we manage to resolve this file path against
        # a publish in shotgun?
        published_file = publishes.get(dependency_path)
        
        if published_file:
            if published_file_entity_type == "PublishedFile":

                req = {"request_type": "create", 
                       "entity_type": "PublishedFileDependency", 
                       "data": {"published_file": publish_entity,
                                "dependent_published_file": published_file
                                }
                        } 
                sg_batch_data.append(req)    
            
            else:# == "TankPublishedFile"

                req = {"request_type": "create", 
                       "entity_type": "TankDependency", 
                       "data": {"tank_published_file": publish_entity,
                                "dependent_tank_published_file": published_file
                                }
                        } 
                sg_batch_data.append(req)


    for dependency_id in dependency_ids:
        if published_file_entity_type == "PublishedFile":

            req = {"request_type": "create", 
                   "entity_type": "PublishedFileDependency", 
                   "data": {"published_file": publish_entity,
                            "dependent_published_file": {"type": "PublishedFile", 
                                                         "id": dependency_id }
                            }
                    } 
            sg_batch_data.append(req)
            
        else:# == "TankPublishedFile"
            
            req = {"request_type": "create", 
                   "entity_type": "TankDependency", 
                   "data": {"tank_published_file": publish_entity,
                            "dependent_tank_published_file": {"type": "TankPublishedFile", 
                                                              "id": dependency_id }
                            }
                    } 
            sg_batch_data.append(req)


    # push to shotgun in a single xact
    if len(sg_batch_data) > 0:
        tk.shotgun.batch(sg_batch_data)
                

def _create_published_file(tk, context, path, name, version_number, task, comment, published_file_type, 
                           created_by_user, created_at, version_entity):
    """
    Creates a publish entity in shotgun given some standard fields.
    """
    published_file_entity_type = get_published_file_entity_type(tk)

    # Check if path is a url or a straight file path.  Path
    # is assumed to be a url if it has a scheme or netloc, e.g.:
    #
    #     scheme://netloc/path
    #
    path_is_url = False
    res = urlparse.urlparse(path)
    if res.scheme:
        # handle windows drive letters - note this adds a limitation
        # but one that is not likely to be a problem as single-character
        # schemes are unlikely!
        if len(res.scheme) > 1 or not res.scheme.isalpha():
            path_is_url = True
    elif res.netloc:
        path_is_url = True
        
    code = ""
    if path_is_url:
        code = os.path.basename(res.path)
    else:
        code = os.path.basename(path)

    # if the context does not have an entity, link it up to the project
    if context.entity is None:
        linked_entity = context.project
    else:
        linked_entity = context.entity

    data = {
        "code": code,
        "description": comment,
        "name": name,
        "project": context.project,
        "entity": linked_entity,
        "task": task,
        "version_number": version_number,
    }

    if path_is_url:
        data["path"] = { "url":path }
    else:
        # Make path platform agnostic.
        _, path_cache = _calc_path_cache(tk, path)
        
        data["path"] = { "local_path": path }
        data["path_cache"] = path_cache        

    if created_by_user:
        data["created_by"] = created_by_user
    else:
        # use current user
        sg_user = login.get_current_user(tk)
        if sg_user:
            data["created_by"] = sg_user

    if created_at:
        data['created_at'] = created_at

    if published_file_type:
        if published_file_entity_type == "PublishedFile":
            data["published_file_type"] = published_file_type
        else:# == TankPublishedFile
            data["tank_type"] = published_file_type

    if version_entity:
        data["version"] = version_entity

    # now call out to hook just before publishing
    data = tk.execute_core_hook(constants.TANK_PUBLISH_HOOK_NAME, shotgun_data=data, context=context)

    return tk.shotgun.create(published_file_entity_type, data)

def _calc_path_cache(tk, path):
    """
    Calculates root path name and relative path (including project directory).
    returns (root_name, path_cache)

    If the location cannot be computed, because the path does not belong
    to a valid root, (None, None) is returned.
    """
    # paths may be c:/foo in maya on windows - don't rely on os.sep here!

    # normalize input path first c:\foo -> c:/foo
    norm_path = path.replace(os.sep, "/")

    # get roots - don't assume data is returned on any particular form
    # may return c:\foo, c:/foo or /foo - assume that we need to normalize this path
    roots = tk.pipeline_configuration.get_data_roots()

    for root_name, root_path in roots.items():
        norm_root_path = root_path.replace(os.sep, "/")

        if norm_path.lower().startswith(norm_root_path.lower()):
            norm_parent_dir = os.path.dirname(norm_root_path)
            # Remove parent dir plus "/" - be careful to handle the case where
            # the parent dir ends with a '/', e.g. 'T:/' for a Windows drive
            path_cache = norm_path[len(norm_parent_dir):].lstrip("/")
            return root_name, path_cache
    # not found, return None values
    return None, None



#################################################################################################
# wrappers around the shotgun API's http header API methods

    
class ToolkitUserAgentHandler(object):
    """
    Convenience wrapper to handle the user agent management
    """
    
    def __init__(self, sg):
        self._sg = sg
        
        self._app = None
        self._framework = None
        self._engine = None
        
        self._core_version = None
        
    def __clear_bundles(self):
        """
        Resets the currently active bundle.
        """
        self._app = None
        self._framework = None
        self._engine = None

        
    def set_current_app(self, name, version, engine_name, engine_version):
        """
        Update the user agent headers for the currently active app 
        """
        # first clear out the other bundle settings - there can only
        # be one active bundle at a time
        self.__clear_bundles()

        # populate the currently running bundle data        
        self._app = (name, version)
        self._engine = (engine_name, engine_version)
        
        # push to shotgun
        self.__update()
        
    def set_current_framework(self, name, version, engine_name, engine_version):
        """
        Update the user agent headers for the currently active framework 
        """
        # first clear out the other bundle settings - there can only
        # be one active bundle at a time
        self.__clear_bundles()

        # populate the currently running bundle data        
        self._framework = (name, version)
        self._engine = (engine_name, engine_version)
        
        # push to shotgun
        self.__update()

    def set_current_engine(self, name, version):
        """
        Update the user agent headers for the currently active engine 
        """
        # first clear out the other bundle settings - there can only
        # be one active bundle at a time
        self.__clear_bundles()

        # populate the currently running bundle data        
        self._engine = (name, version)
        
        # push to shotgun
        self.__update()

    def set_current_core(self, core_version):
        """
        Update the user agent headers for the currently active core
        """
        self._core_version = core_version
        self.__update()
        
    def __update(self):
        """
        Perform changes to the Shotgun API
        """
        # note that because of shortcomings in the API, 
        # we have to reference the member variable directly.
        #
        # sg._user_agents is a list of strings. By default,
        # its value is [ "shotgun-json (1.2.3)" ] 
        
        # First, remove any old Toolkit settings
        new_agents = []
        for x in self._sg._user_agents:
            if x.startswith("tk-core") or \
               x.startswith("tk-app") or \
               x.startswith("tk-engine") or \
               x.startswith("tk-fw"):
                continue
            new_agents.append(x)
         
        # Add new Toolkit settings
        if self._core_version:
            new_agents.append("tk-core (%s)" % self._core_version)

        if self._engine:
            new_agents.append("tk-engine (%s %s)" % self._engine)
        
        if self._app:
            new_agents.append("tk-app (%s %s)" % self._app)

        if self._framework:
            new_agents.append("tk-fw (%s %s)" % self._framework)

        # and update shotgun
        self._sg._user_agents = new_agents
