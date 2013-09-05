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
Methods relating to the Path cache, a central repository where metadata about 
all Tank items in the file system are kept. 

"""

import sqlite3
import sys
import os

# use api json to cover py 2.5
# todo - replace with proper external library  
from tank_vendor import shotgun_api3  
json = shotgun_api3.shotgun.json


from .errors import TankError 

from .util.login import get_current_user 


SHOTGUN_ENTITY = "CustomEntity01"

SG_ENTITY_FIELD = "sg_entity"
SG_PATH_FIELD = "sg_path"
SG_METADATA_FIELD = "sg_configuration_metadata"
SG_IS_PRIMARY_FIELD = "sg_primary"
SG_ENTITY_ID_FIELD = "sg_id_at_creation"
SG_ENTITY_TYPE_FIELD = "sg_type_at_creation"
SG_ENTITY_NAME_FIELD = "code"
SG_PIPELINE_CONFIG_FIELD = "sg_pipeline_configuration"

MAX_EVENTS_BEFORE_FULL_SYNC = 100



class PathCache(object):
    """
    A global cache which holds the mapping between a shotgun entity and a location on disk.
    
    NOTE! This uses sqlite and the db is typically hosted on an NFS storage.
    Ensure that the code is developed with the constraints that this entails in mind.
    """
    
    def __init__(self, tk):
        """
        Constructor
        :param pipeline_configuration: pipeline config object
        """
        db_path = tk.pipeline_configuration.get_path_cache_location()
        self._connection = None
        self._init_db(db_path)
        self._roots = tk.pipeline_configuration.get_data_roots()
        self._tk = tk
    
    def _init_db(self, db_path):
        """
        Sets up the database
        """
        
        # first check that the cache folder exists
        # note that the cache folder is inside of the tank folder
        # so no need to attempt a recursive creation here.
        cache_folder = os.path.dirname(db_path)
        if not os.path.exists(cache_folder):
            old_umask = os.umask(0)
            try:
                os.mkdir(cache_folder, 0777)
            finally:
                os.umask(old_umask)            
        
        # make sure to set open permissions on the db file if we are the first ones 
        # to create it
        db_file_created = False
        if not os.path.exists(db_path):
            db_file_created = True
        
        self._connection = sqlite3.connect(db_path)
        
        # this is to handle unicode properly - make sure that sqlite returns 
        # str objects for TEXT fields rather than unicode. Note that any unicode
        # objects that are passed into the database will be automatically
        # converted to UTF-8 strs, so this text_factory guarantuees that any character
        # representation will work for any language, as long as data is either input
        # as UTF-8 (byte string) or unicode. And in the latter case, the returned data
        # will always be unicode.
        self._connection.text_factory = str
        
        c = self._connection.cursor()
        c.executescript("""
            CREATE TABLE IF NOT EXISTS path_cache (entity_type text, entity_id integer, entity_name text, root text, path text, primary_entity integer);
        
            CREATE INDEX IF NOT EXISTS path_cache_entity ON path_cache(entity_type, entity_id);
        
            CREATE INDEX IF NOT EXISTS path_cache_path ON path_cache(root, path, primary_entity);
        
            CREATE UNIQUE INDEX IF NOT EXISTS path_cache_all ON path_cache(entity_type, entity_id, root, path, primary_entity);
            
            CREATE TABLE IF NOT EXISTS event_log_sync (last_id integer);
        """)
        
        ret = c.execute("PRAGMA table_info(path_cache)")
        
        # check for primary field
        if "primary_entity" not in [x[1] for x in ret.fetchall()]:
            c.executescript("""
                ALTER TABLE path_cache ADD COLUMN primary_entity integer;
                UPDATE path_cache SET primary_entity=1;

                DROP INDEX path_cache_path;
                CREATE INDEX IF NOT EXISTS path_cache_path ON path_cache(root, path, primary_entity);
                
                DROP INDEX path_cache_all;
                CREATE UNIQUE INDEX IF NOT EXISTS path_cache_all ON path_cache(entity_type, entity_id, root, path, primary_entity);
                
            """)

        self._connection.commit()
        c.close()
        
        # and open up permissions if the file was just created
        if db_file_created:
            old_umask = os.umask(0)
            try:
                os.chmod(db_path, 0666)
            finally:
                os.umask(old_umask)            
    
    def _path_to_dbpath(self, relative_path):
        """
        converts a  relative path to a db path form

        /foo/bar --> /foo/bar
        \foo\bar --> /foo/bar
        """
        # normalize the path before checking the project
        # some tools on windows the / others \

        # normalize
        norm_path = relative_path.replace(os.sep, "/")
        return norm_path

    def _separate_root(self, full_path):
        """
        Determines project root path and relative path.

        :returns: root_name, relative_path
        """
        n_path = full_path.replace(os.sep, "/")
        # Deterimine which root
        root_name = None
        relative_path = None
        for cur_root_name, root_path in self._roots.items():
            n_root = root_path.replace(os.sep, "/")
            if n_path.lower().startswith(n_root.lower()):
                root_name = cur_root_name
                # chop off root
                relative_path = full_path[len(root_path):]
                break

        if not root_name:
            raise TankError("The path '%s' does not belong to the project!" % full_path)

        return root_name, relative_path


    def _dbpath_to_path(self, root_path, dbpath):
        """
        converts a dbpath to path for the local platform

        linux:    /foo/bar --> /studio/proj/foo/bar
        windows:  /foo/bar --> \\studio\proj\foo\bar         

        :param root_path: Project root path
        :param db_path: Relative path
        """
        # first make sure dbpath doesn't start with a /
        if dbpath.startswith("/"):
            dbpath = dbpath[1:]
        # convert slashes
        path_sep = dbpath.replace("/", os.sep)
        # and join with root
        full_path = os.path.join(root_path, path_sep)
        return os.path.normpath(full_path)

    def close(self):
        """
        Close the database connection.
        """
        if self._connection is not None:
            self._connection.close()
            self._connection = None
                
    ############################################################################################
    # shotgun synchronization (SG data pushed into path cache database)

    def synchronize(self):
        """
        Ensure the local path cache is in sync with Shotgun.
        
        Returns a list of remote items which were detected, created remotely
        and not existing in this path cache. These are returned as a list of 
        dictionaries, each containing keys:
            - entity
            - metadata 
            - path
        """
        
        # first get the last synchronized event log event.
        c = self._connection.cursor()
        res = c.execute("SELECT max(last_id) FROM event_log_sync")
        # get first item in the data set
        data = list(res)[0]
        c.close()
        
        print "Got last event log id from path cache: %s" % data
        
        # expect back something like [(249660,)] for a running cache and [(None,)] for a clear
        if len(data) != 1 or data[0] is None:
            # we should do a full sync
            return self._do_full_sync()

        # we have an event log id - so check if there are any more recent events
        event_log_id = data[0]
        
        project_link = {"type": "Project", 
                        "id": self._tk.pipeline_configuration.get_project_id() }
        
        
        response = self._tk.shotgun.find("EventLogEntry", 
                                         [ ["event_type", "is", "Toolkit_Folders"], 
                                           ["id", "greater_than", event_log_id],
                                           ["project", "is", project_link] ],
                                         ["id", "meta", "attribute_name"] )   
    
        # todo - maybe do a time check here too to say that if our last sync date
        # more than a month ago or something, then fall back on full sync.
    
        if len(response) > MAX_EVENTS_BEFORE_FULL_SYNC:
            # lots of activity since last sync. Fall back on a full refresh
            return self._do_full_sync()
                
        else:
            # small amount of change. Patch the cache
            return self._do_incremental_sync(response)


    def _do_full_sync(self):
        """
        Ensure the local path cache is in sync with Shotgun.
        
        Returns a list of remote items which were detected, created remotely
        and not existing in this path cache. These are returned as a list of 
        dictionaries, each containing keys:
            - entity
            - metadata 
            - path
        """
        print "doing full sync!"
        
        # find the max event log id. Will we store this in the sync db later.
        sg_data = self._tk.shotgun.find_one("EventLogEntry", 
                                            [], 
                                            ["id"], 
                                            [{"field_name": "id", "direction": "desc"},])
        max_event_log_id = sg_data["id"]
        
        return self._replay_folder_entities(max_event_log_id)

    def _do_incremental_sync(self, sg_data):
        """
        Ensure the local path cache is in sync with Shotgun.
        
        Patch the existing cache with the events passed via sg_data.
        
        This is a list of dicts ordered by id from low to high (old to new), 
        each with keys
            - id
            - meta
            - attribute_name
        
        Example of item:
        {'attribute_name': 'Create', 
         'meta': {'core_api_version': 'HEAD', 
                  'sg_folder_ids': [123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133]}, 
         'type': 'EventLogEntry', 
         'id': 249240}
        
        Returns a list of remote items which were detected, created remotely
        and not existing in this path cache. These are returned as a list of 
        dictionaries, each containing keys:
            - entity
            - metadata
            - path
        """
        
        if len(sg_data) == 0:
            # nothing to do!
            print "no syncing needed - path cache is up to date!"
            return []
        
        print "doing incremental sync: %s" % sg_data
        
        # find the max event log id in sg_data. Will we store this in the sync db later.
        max_event_log_id = max( [x["id"] for x in sg_data] )
        
        all_folder_ids = []
        
        for d in sg_data:
            if d["attribute_name"] == "Create":
                # this is a creation request! Replay it on our database
                all_folder_ids.extend( d["meta"]["sg_folder_ids"] )

        return self._replay_folder_entities(max_event_log_id, all_folder_ids)

    def _replay_folder_entities(self, max_event_log_id, ids=None):
        """
        Does the actual download from shotgun and pushes those changes
        to the path cache. If ids is None, this indicates a full sync, and 
        the path cache db table is cleared first. If not, the table
        is appended to.
        
        Returns a list of remote items which were detected, created remotely
        and not existing in this path cache. These are returned as a list of 
        dictionaries, each containing keys:
            - entity
            - metadata 
            - path
        
        """
        
        if ids is None:
            # get all folder data from shotgun
            print "getting all path data from shotgun."
            
            project_link = {"type": "Project", 
                            "id": self._tk.pipeline_configuration.get_project_id() }
            
            sg_data = self._tk.shotgun.find(SHOTGUN_ENTITY, 
                                  [["project", "is", project_link]],
                                  [SG_METADATA_FIELD, 
                                   SG_IS_PRIMARY_FIELD, 
                                   SG_ENTITY_ID_FIELD,
                                   SG_PATH_FIELD,
                                   SG_ENTITY_TYPE_FIELD, 
                                   SG_ENTITY_NAME_FIELD],
                                  [{"field_name": "id", "direction": "asc"},])
        else:
            # get the ids that are missing from shotgun
            print "getting path data from shotgun. Ids: %s" % ids
            # need to use this weird special filter syntax
            id_in_filter = ["id", "in"]
            id_in_filter.extend(ids)
            sg_data = self._tk.shotgun.find(SHOTGUN_ENTITY, 
                                  [id_in_filter],
                                  [SG_METADATA_FIELD, 
                                   SG_IS_PRIMARY_FIELD, 
                                   SG_ENTITY_ID_FIELD,
                                   SG_PATH_FIELD,
                                   SG_ENTITY_TYPE_FIELD, 
                                   SG_ENTITY_NAME_FIELD],
                                  [{"field_name": "id", "direction": "asc"},])
            
        print "...done! Got %s records" % len(sg_data)
            
        c = self._connection.cursor()
        
        # now start a single transaction in which we do all our work
        if ids is None:
            # complete sync - clear our table first
            c.execute("DELETE FROM event_log_sync")
            
        return_data = []
            
        for x in sg_data:
            
            # get the local path from our attachment entity dict
            sg_local_storage_os_map = {"linux2": "local_path_linux", 
                                       "win32": "local_path_windows", 
                                       "darwin": "local_path_mac" }
            local_os_path_field = sg_local_storage_os_map[sys.platform]
            local_os_path = x[SG_PATH_FIELD][local_os_path_field]
            
            entity = {"id": x[SG_ENTITY_ID_FIELD], 
                      "name": x[SG_ENTITY_NAME_FIELD], 
                      "type": x[SG_ENTITY_TYPE_FIELD]}
            is_primary = x[SG_IS_PRIMARY_FIELD]
            
            if self._add_db_mapping(c, local_os_path, entity, is_primary):
                # add db mapping returned true. Means it wasn't in the path cache db
                # and we should return it
                print "sg->path sync: added path %s" % local_os_path
                return_data.append({"entity": entity, 
                                    "path": local_os_path, 
                                    "metadata": SG_METADATA_FIELD})
            else:
                print "sg->path sync: didn't add path %s" % local_os_path
            
        # lastly, id of this event log entry for purpose of future syncing
        c.execute("INSERT INTO event_log_sync VALUES(?)", (max_event_log_id, ))
            
        self._connection.commit()
        c.close()

        return return_data

    ############################################################################################
    # pre-insertion validation

    def validate_mappings(self, data):
        """
        Adds a collection of mappings to the path cache in case they are not 
        already there. 
        
        :param data: list of dictionaries. Each dictionary should contain 
                     the following keys:
                      - entity: a dictionary with keys name, id and type
                      - path: a path on disk
                      - primary: a boolean indicating if this is a primary entry
                      - metadata: configuration metadata
        """
        for d in data:
            self._validate_mapping(d["path"], d["entity"], d["primary"])
        
        
    def _validate_mapping(self, path, entity, is_primary):
        """
        Consistency checks happening prior to folder creation. May raise a TankError
        if an inconsistency is detected.
        
        :param path: The path calculated
        :param entity: Sg entity dict with keys id, type and name
        """
        
        # Make sure that there isn't already a record with the same
        # name in the database and file system, but with a different id.
        # We only do this for primary items - for secondary items, multiple items can exist
        if is_primary:
            entity_in_db = self.get_entity(path)
            
            if entity_in_db is not None:
                if entity_in_db["id"] != entity["id"] or entity_in_db["type"] != entity["type"]:
                    
                    # there is already a record in the database for this path,
                    # but associated with another entity! Display an error message
                    # and ask that the user investigates using special tank commands.
                    #
                    # Note! We are only comparing against the type and the id
                    # not against the name. It should be perfectly valid to rename something
                    # in shotgun and if folders are then recreated for that item, nothing happens
                    # because there is already a folder which repreents that item. (although now with 
                    # an incorrect name)

                    msg  = "The path '%s' cannot be processed because it is already associated " % path
                    msg += "with %s '%s' (id %s) in Shotgun. " % (entity_in_db["id"], entity_in_db["type"], entity_in_db["name"])
                    msg += "You are now trying to associate it with %s '%s' (id %s). " % (entity["type"], entity["id"], entity["name"])
                    msg += "Please run the command 'tank check_folders %s %s' " % (entity["type"], entity["id"])
                    msg += "to get a more detailed overview of why you are getting this message "
                    msg += "and what you can do to resolve this situation."
                    raise TankError(msg)
                
        # Check 2. Check if a folder for this shot has already been created,
        # but with another name. This can happen if someone
        # - creates a shot AAA
        # - creates folders on disk for Shot AAA
        # - renamed the shot to BBB
        # - tries to create folders. Now we don't want to create folders for BBB,
        #   since we already have a location on disk for this shot. 
        #
        # note: this can also happen if the folder creation rules change.
        #
        # we only check for primary entities, doing the check for secondary
        # would only be to carry out the same check twice.
        if is_primary:
            for p in self.get_paths(entity["type"], entity["id"], primary_only=False):
                # so we got a path that matches our entity
                if p != path and os.path.dirname(p) == os.path.dirname(path):
                    # this path is identical to our path we are about to create except for the name. 
                    # there is still a folder on disk. Abort folder creation
                    # with a descriptive error message
                    msg  = "The path '%s' cannot be created because another " % path
                    msg += "path '%s' is already associated with %s %s. " % (p, entity["type"], entity["name"])
                    msg += "This typically happens if an item in Shotgun is renamed or "
                    msg += "if the path naming in the folder creation configuration "
                    msg += "is changed. "
                    msg += "Please run the command 'tank check_folders %s %s' " % (entity["type"], entity["id"])
                    msg += "to get a more detailed overview of why you are getting this message "
                    msg += "and what you can do to resolve this situation."
                    
                    raise TankError(msg)



    ############################################################################################
    # database insertion methods

    def add_mappings(self, data, entity_type, entity_ids):
        """
        Adds a collection of mappings to the path cache in case they are not 
        already there. 
        
        :param data: list of dictionaries. Each dictionary contains 
                     the following keys:
                      - entity: a dictionary with keys name, id and type
                      - path: a path on disk
                      - primary: a boolean indicating if this is a primary entry
                      
        :param entity_type: sg entity type for the original high level folder creation 
                            request that represents this series of mappings
        :param entity_ids: list of sg entity ids (ints) that represents this series of
                           path mappings
        """
        
        data_for_sg = []        
        
        c = self._connection.cursor()
        for d in data:
            if self._add_db_mapping(c, d["path"], d["entity"], d["primary"]):
                # add db mapping returned true. Means it wasn't in the path cache db
                # and we should add it to shotgun too!
                data_for_sg.append(d)
                
        self._connection.commit()
        c.close()
                

        # now add mappings to shotgun. Pass it as a single request via batch
        sg_batch_data = []
        for d in data_for_sg:
            
            pc_link = {"type": "PipelineConfiguration",
                       "id": self._tk.pipeline_configuration.get_shotgun_id() }
            
            project_link = {"type": "Project", 
                            "id": self._tk.pipeline_configuration.get_project_id() }
            
            # get a name for the clickable url in the path field
            # this will include the name of the storage
            root_name, relative_path = self._separate_root(d["path"])
            db_path = self._path_to_dbpath(relative_path)
            path_display_name = "[%s] %s" % (root_name, db_path) 
            
            req = {"request_type":"create", 
                   "entity_type": SHOTGUN_ENTITY, 
                   "data": {"project": project_link,
                            "created_by": get_current_user(self._tk),
                            SG_ENTITY_FIELD: d["entity"],
                            SG_IS_PRIMARY_FIELD: d["primary"],
                            SG_PIPELINE_CONFIG_FIELD: pc_link,
                            SG_METADATA_FIELD: json.dumps(d["metadata"]),
                            SG_ENTITY_ID_FIELD: d["entity"]["id"],
                            SG_ENTITY_TYPE_FIELD: d["entity"]["type"],
                            SG_ENTITY_NAME_FIELD: d["entity"]["name"],
                            SG_PATH_FIELD: { "local_path": d["path"], "name": path_display_name }
                            } }
            
            sg_batch_data.append(req)
        
        # push to shotgun in a single xact
        if len(sg_batch_data) > 0:
            try:    
                response = self._tk.shotgun.batch(sg_batch_data)
            except Exception, e:
                raise TankError("Critical! Could not update Shotgun with the folder "
                                "creation information. Please contact support. Error details: %s" % e)
            
            # now register the created ids in the event log
            # this will later on be read by the synchronization
            
            # first, a summary of what we are up to
            entity_ids = ", ".join([str(x) for x in entity_ids])
            desc = ("Toolkit %s: Created folders on disk for "
                    "%ss with id: %s" % (self._tk.version, entity_type, entity_ids))
            
            # now, based on the entities we just created, assemble a metadata chunk that 
            # the sync calls can use later on.
            meta = {}
            # the api version used is always useful to know
            meta["core_api_version"] = self._tk.version
            # shotgun ids created
            meta["sg_folder_ids"] = [ x["id"] for x in response]
            
            data = {}
            data["event_type"] = "Toolkit_Folders"
            data["attribute_name"] = "Create"
            data["description"] = desc
            data["project"] = project_link
            data["entity"] = pc_link
            data["meta"] = meta        
            data["user"] = get_current_user(self._tk)
        
            response = self._tk.shotgun.create("EventLogEntry", data)
            
            # lastly, id of this event log entry for purpose of future syncing
            event_log_id = response["id"]        
            c = self._connection.cursor()
            c.execute("INSERT INTO event_log_sync VALUES(?)", (event_log_id, ))
            self._connection.commit()
            c.close()



    def _add_db_mapping(self, cursor, path, entity, primary):
        """
        Adds an association to the database. If the association already exists, it will
        do nothing, just return.
        
        If there is another association which conflicts with the association that is 
        to be inserted, a TankError is raised.

        :param cursor: database cursor to use
        :param path: a path on disk representing the entity.
        :param entity: a shotgun entity dict with keys type, id and name
        :param primary: is this the primary entry for this particular path     
        
        :returns: True if an entry was added to the database, False if it was not necessary   
        """
        
        if primary:
            # the primary entity must be unique: path/id/type 
            # see if there are any records for this path
            # note that get_entity does not return secondary entities
            curr_entity = self.get_entity(path, cursor)
            
            if curr_entity is not None:
                # this path is already registered. Ensure it is connected to
                # our entity! 
                #
                # Note! We are only comparing against the type and the id
                # not against the name. It should be perfectly valid to rename something
                # in shotgun and if folders are then recreated for that item, nothing happens
                # because there is already a folder which repreents that item. (although now with 
                # an incorrect name)
                # 
                # also note that we have already done this once as part of the validation checks -
                # this time round, we are doing it more as an integrity check.
                #                
                if curr_entity["type"] != entity["type"] or curr_entity["id"] != entity["id"]:    
                    raise TankError("Database concurrency problems: The path '%s' is " 
                                    "already associated with Shotgun entity %s. Please re-run "
                                    "folder creation to try again." % (path, str(curr_entity) ))
                    
                else:   
                    # the entry that exists in the db matches what we are trying to insert so skip it
                    return False
                
        else:
            # secondary entity
            # in this case, it is okay with more than one record for a path
            # but we don't want to insert the exact same record over and over again
            paths = self.get_paths(entity["type"], entity["id"], primary_only=False, cursor=cursor)
            if path in paths:
                # we already have the association present in the db.
                return False

        # there was no entity in the db. So let's create it!
        
        root_name, relative_path = self._separate_root(path)
        db_path = self._path_to_dbpath(relative_path)
        cursor.execute("INSERT INTO path_cache VALUES(?, ?, ?, ?, ?, ?)", (entity["type"], 
                                                                           entity["id"], 
                                                                           entity["name"], 
                                                                           root_name,
                                                                           db_path,
                                                                           primary))
        
        return True


    
    ############################################################################################
    # database accessor methods

    def get_paths(self, entity_type, entity_id, primary_only, cursor=None):
        """
        Returns a path given a shotgun entity (type/id pair)

        :param entity_type: a Shotgun entity type
        :params entity_id: a Shotgun entity id
        :returns: a path on disk
        """
        paths = []
        
        if cursor is None:
            c = self._connection.cursor()
        else:
            c = cursor
        
        if primary_only:
            res = c.execute("SELECT root, path FROM path_cache WHERE entity_type = ? AND entity_id = ? and primary_entity = 1", (entity_type, entity_id))
        else:
            res = c.execute("SELECT root, path FROM path_cache WHERE entity_type = ? AND entity_id = ?", (entity_type, entity_id))

        for row in res:
            root_name = row[0]
            relative_path = row[1]
            
            root_path = self._roots.get(root_name)
            if not root_path:
                # The root name doesn't match a recognized name, so skip this entry
                continue
            
            # assemble path
            path_str = self._dbpath_to_path(root_path, relative_path)
            paths.append(path_str)
        
        if cursor is None:
            c.close()
        
        return paths

    def get_entity(self, path, cursor=None):
        """
        Returns an entity given a path.
        
        If this path is made up of nested entities (e.g. has a folder creation expression
        on the form Shot: "{code}_{sg_sequence.Sequence.code}"), the primary entity (in 
        this case the Shot) will be returned.

        :param path: a path on disk
        :returns: Shotgun entity dict, e.g. {"type": "Shot", "name": "xxx", "id": 123} 
                  or None if not found
        """
            
        try:
            root_path, relative_path = self._separate_root(path)
        except TankError:
            # fail gracefully if path is not a valid path
            # eg. doesn't belong to the project
            return None

        if cursor is None:
            c = self._connection.cursor()
        else:
            c = cursor

        db_path = self._path_to_dbpath(relative_path)
        res = c.execute("SELECT entity_type, entity_id, entity_name FROM path_cache WHERE path = ? AND root = ? and primary_entity = 1", (db_path, root_path))
        data = list(res)
        
        if cursor is None:
            c.close()
        
        if len(data) > 1:
            # never supposed to happen!
            raise TankError("More than one entry in path database for %s!" % path)
        elif len(data) == 1:
            # convert to string, not unicode!
            type_str = str(data[0][0])
            name_str = str(data[0][2])
            return {"type": type_str, "id": data[0][1], "name": name_str }
        else:
            return None

    def get_secondary_entities(self, path):
        """
        Returns all the secondary entities for a path.
        
        :param path: a path on disk
        :returns: list of shotgun entity dicts, e.g. [{"type": "Shot", "name": "xxx", "id": 123}] 
                  or [] if no entities associated.
        """
        c = self._connection.cursor()
        try:
            root_path, relative_path = self._separate_root(path)
        except TankError:
            # fail gracefully if path is not a valid path
            # eg. doesn't belong to the project
            return []

        db_path = self._path_to_dbpath(relative_path)
        res = c.execute("SELECT entity_type, entity_id, entity_name FROM path_cache WHERE path = ? AND root = ? and primary_entity = 0", (db_path, root_path))
        data = list(res)
        c.close()

        matches = []
        for d in data:        
            # convert to string, not unicode!
            type_str = str(d[0])
            name_str = str(d[2])
            matches.append( {"type": type_str, "id": d[1], "name": name_str } )

        return matches
    