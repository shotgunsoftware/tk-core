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

from .util import shotgun

# use api json to cover py 2.5
# todo - replace with proper external library  
from tank_vendor import shotgun_api3  
json = shotgun_api3.shotgun.json


from .errors import TankError 

from .util.login import get_current_user 


SHOTGUN_ENTITY = "FilesystemLocation"

SG_ENTITY_FIELD = "entity"
SG_PATH_FIELD = "path"
SG_METADATA_FIELD = "configuration_metadata"
SG_IS_PRIMARY_FIELD = "is_primary"
SG_ENTITY_ID_FIELD = "linked_entity_id"
SG_ENTITY_TYPE_FIELD = "linked_entity_type"
SG_ENTITY_NAME_FIELD = "code"
SG_PIPELINE_CONFIG_FIELD = "pipeline_configuration"

class PathCache(object):
    """
    A global cache which holds the mapping between a shotgun entity and a location on disk.
    
    NOTE! This uses sqlite and the db is typically hosted on an NFS storage.
    Ensure that the code is developed with the constraints that this entails in mind.
    """
    
    def __init__(self, tk):
        """
        Constructor.
        
        :param tk: Toolkit API instance
        """
        db_path = tk.pipeline_configuration.get_path_cache_location()
        self._connection = None
        self._init_db(db_path)
        self._roots = tk.pipeline_configuration.get_data_roots()
        self._tk = tk
        self._sync_with_sg = tk.pipeline_configuration.get_shotgun_path_cache_enabled()
    
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
        # converted to UTF-8 strs, so this text_factory guarantees that any character
        # representation will work for any language, as long as data is either input
        # as UTF-8 (byte string) or unicode. And in the latter case, the returned data
        # will always be unicode.
        self._connection.text_factory = str
        
        c = self._connection.cursor()
        try:
        
            # get a list of tables in the current database
            ret = c.execute("SELECT name FROM main.sqlite_master WHERE type='table';")
            table_names = [x[0] for x in ret.fetchall()]
            
            if len(table_names) == 0:
                # we have a brand new database. Create all tables and indices
                c.executescript("""
                    CREATE TABLE path_cache (entity_type text, entity_id integer, entity_name text, root text, path text, primary_entity integer);
                
                    CREATE INDEX path_cache_entity ON path_cache(entity_type, entity_id);
                
                    CREATE INDEX path_cache_path ON path_cache(root, path, primary_entity);
                
                    CREATE UNIQUE INDEX path_cache_all ON path_cache(entity_type, entity_id, root, path, primary_entity);
                    
                    CREATE TABLE event_log_sync (last_id integer);
                    
                    CREATE TABLE shotgun_status (path_cache_id integer, shotgun_id integer);
                    
                    CREATE UNIQUE INDEX shotgun_status_id ON shotgun_status(path_cache_id);
                    """)
                self._connection.commit()
                
            else:
                
                # we have an existing database! Ensure it is up to date
                if "event_log_sync" not in table_names:
                    # this is a pre-0.14 setup where the path cache does not have event log sync
                    c.executescript("CREATE TABLE event_log_sync (last_id integer);")
                    self._connection.commit()
                
                if "shotgun_status" not in table_names:
                    # this is a pre-0.14 setup where the path cache does not have the shotgun_status table
                    c.executescript("""CREATE TABLE shotgun_status (path_cache_id integer, shotgun_id integer);
                                       CREATE UNIQUE INDEX shotgun_status_id ON shotgun_status(path_cache_id);""")
                    self._connection.commit()

                
                # now ensure that some key fields that have been added during the dev cycle are there
                ret = c.execute("PRAGMA table_info(path_cache)")
                field_names = [ x[1] for x in ret.fetchall() ]
                
                # check for primary entity field - this was added back in 0.12.x
                if "primary_entity" not in field_names:
                    c.executescript("""
                        ALTER TABLE path_cache ADD COLUMN primary_entity integer;
                        UPDATE path_cache SET primary_entity=1;
        
                        DROP INDEX path_cache_path;
                        CREATE INDEX IF NOT EXISTS path_cache_path ON path_cache(root, path, primary_entity);
                        
                        DROP INDEX path_cache_all;
                        CREATE UNIQUE INDEX IF NOT EXISTS path_cache_all ON path_cache(entity_type, entity_id, root, path, primary_entity);
                        """)
        
                    self._connection.commit()
    
        
        finally:
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
            
            storages_str = ",".join( self._roots.values() )
            
            raise TankError("The path '%s' could not be split up into a project centric path for "
                            "any of the storages %s that are associated with this "
                            "project." % (full_path, storages_str))

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

    def synchronize(self, log=None, force=False):
        """
        Ensure the local path cache is in sync with Shotgun. 
        
        :param force: boolean to indicate that a full sync should be carried out.
        :param log: std python logger object.
        
        Returns a list of remote items which were detected, created remotely
        and not existing in this path cache. These are returned as a list of 
        dictionaries, each containing keys:
            - entity
            - metadata 
            - path
        """
        
        if not self._sync_with_sg:
            if log:
                log.info("Path cache synchronization is turned off for this project.")
            return []
        
        
        c = self._connection.cursor()
        
        try:
            # first of all, make sure we don't have any data in this path cache file
            # which isn't already in Shotgun.
            self._ensure_all_in_shotgun(c, log)
            
            # check if we should do a forced sync
            if force:
                return self._do_full_sync(c, log)
            
            # first get the last synchronized event log event.        
            res = c.execute("SELECT max(last_id) FROM event_log_sync")
            # get first item in the data set
            data = list(res)[0]
            
            # expect back something like [(249660,)] for a running cache and [(None,)] for a clear
            if len(data) != 1 or data[0] is None:
                # we should do a full sync
                return self._do_full_sync(c, log)
    
            # we have an event log id - so check if there are any more recent events
            event_log_id = data[0]
            
            project_link = {"type": "Project", 
                            "id": self._tk.pipeline_configuration.get_project_id() }
            
            # note! We search for all events greater than the prev event_log_id-1.
            # this way, the first record returned should be the last record that was 
            # synced. This is a way of detecting that the event log chain is not broken.
            # it could break for example if someone has culled the event log table and in 
            # that case we should fall back on a full sync.
            
            response = self._tk.shotgun.find("EventLogEntry", 
                                             [ ["event_type", "in", ["Toolkit_Folders_Create", 
                                                                     "Toolkit_Folders_Delete"]], 
                                               ["id", "greater_than", (event_log_id - 1)],
                                               ["project", "is", project_link] ],
                                             ["id", "meta", "event_type"] )   
        
            # count creation and deletion entries
            num_deletions = 0
            num_creations = 0
            for r in response:
                if r["event_type"] == "Toolkit_Folders_Create":
                    num_creations += 1
                if r["event_type"] == "Toolkit_Folders_Delete":
                    num_deletions += 1
                    
            if len(response) == 0 or response[0]["id"] != event_log_id:
                # there is either no event log data at all or a gap
                # in the event log. Assume that some culling has occured and
                # fall back on a full sync
                if log:
                    log.info("Cannot locate path cache tracking marker in Shotgun Event Log. "
                             "Falling back onto a full synchronization.")
                return self._do_full_sync(c, log)        
            
            elif len(response) == 1 and response[0]["id"] == event_log_id:
                # nothing has changed since the last sync
                if log:
                    log.info("Path cache syncing not necessary - local folders already up to date!")
                return []
            
            elif num_deletions > 0:
                # some stuff was deleted. fall back on full sync
                return self._do_full_sync(c, log)
            
            elif num_creations > 0:
                # we have a complete trail of increments. 
                # note that we skip the current entity.
                return self._do_incremental_sync(c, log, response[1:])
            
            else:
                # should never be here
                raise Exception("Unknown error - please contact support.")

        finally:       
            c.close()

    def _upload_cache_data_to_shotgun(self, data, event_log_desc, log=None):
        """
        Takes a standard chunk of Shotgun data and uploads it to Shotgun
        using a single batch statement. Then writes a single event log entry record
        which binds the created path records. Returns the id of this event log record.
        
        data needs to be a list of dicts with the following keys:
        - entity - std sg entity dict with name, id and type
        - primary - boolean to indicate if something is primary
        - metadata - metadata dict
        - path - local os path
        - path_cache_row_id - the path cache db row id for the entry
        
        returns: (event_log_id, sg_id_lookup)
        - event_log_id is the id for the event log entry which summarizes the 
          creation event.
        - sg_id_lookup is a dictionary where the keys are path cache row ids 
          and the values are the newly created corresponding shotgun ids 
        """
        
        pc_link = {"type": "PipelineConfiguration",
                   "id": self._tk.pipeline_configuration.get_shotgun_id() }
        
        project_link = {"type": "Project", 
                        "id": self._tk.pipeline_configuration.get_project_id() }
    
        sg_batch_data = []
        for d in data:
                            
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
        if log:
            log.info("Uploading %s path entries to Shotgun..." % len(sg_batch_data))
        
        try:    
            response = self._tk.shotgun.batch(sg_batch_data)
        except Exception, e:
            raise TankError("Critical! Could not update Shotgun with folder "
                            "data. Please contact support. Error details: %s" % e)
        
        # now create a dictionary where input path cache rowid (path_cache_row_id)
        # is mapped to the shotgun ids that were just created
        def _rowid_from_path(path):
            for d in data:
                if d["path"] == path:
                    return d["path_cache_row_id"] 
            raise TankError("Could not resolve row id for path! Please contact support! "
                            "trying to resolve path '%s'. Source data set: %s" % (path, data))
        
        rowid_sgid_lookup = {}
        for sg_obj in response:
            sg_id = sg_obj["id"]
            pc_row_id = _rowid_from_path( sg_obj[SG_PATH_FIELD]["local_path"] )
            rowid_sgid_lookup[pc_row_id] = sg_id
        
        # now register the created ids in the event log
        # this will later on be read by the synchronization            
        # now, based on the entities we just created, assemble a metadata chunk that 
        # the sync calls can use later on.
        meta = {}
        # the api version used is always useful to know
        meta["core_api_version"] = self._tk.version
        # shotgun ids created
        meta["sg_folder_ids"] = [ x["id"] for x in response]
        
        sg_event_data = {}
        sg_event_data["event_type"] = "Toolkit_Folders_Create"
        sg_event_data["description"] = "Toolkit %s: %s" % (self._tk.version, event_log_desc)
        sg_event_data["project"] = project_link
        sg_event_data["entity"] = pc_link
        sg_event_data["meta"] = meta        
        sg_event_data["user"] = get_current_user(self._tk)
    
        try:
            response = self._tk.shotgun.create("EventLogEntry", sg_event_data)
        except Exception, e:
            raise TankError("Critical! Could not update Shotgun with folder data event log "
                            "history marker. Please contact support. Error details: %s" % e)            
        
        # return the event log id which represents this uploaded slab
        return (response["id"], rowid_sgid_lookup)


    def _ensure_all_in_shotgun(self, cursor, log):
        """
        Ensure that all the path cache data in this database is also registered in Shotgun.
        
        This method is primarily to ensure that any data written by pre-014 clients is
        pushed to shotgun automatically. Once a system is fully running 0.14, this method is no
        longer necessary.
        """

        # first determine which records are not yet in Shotgun.
        pc_data = list(cursor.execute("""select pc.rowid,
                                                pc.entity_type, 
                                                pc.entity_id, 
                                                pc.entity_name, 
                                                pc.root, 
                                                pc.path, 
                                                pc.primary_entity 
                                         from path_cache pc
                                         left join shotgun_status ss on pc.rowid = ss.path_cache_id
                                         where ss.path_cache_id is null
                                         """))
                                    

        if len(pc_data) > 0 and log:
            log.info("Detected %s path entries that have not yet been uploaded to Shotgun." % len(pc_data))
        
        # inner loop - push to shotgun in chunks
        # and push each one separately
        BATCH_SIZE = 400
        pc_data_batches = [ pc_data[x:x+BATCH_SIZE] for x in xrange(0, len(pc_data), BATCH_SIZE)]
        
        for curr_batch in pc_data_batches:
            
            try:
                
                # construct data chunk to upload to shotgun
                sg_data = []
                
                for sql_record in curr_batch:
                    
                    # resolve a local path from a root and a generic path
                    root_name = sql_record[4]
                    db_path = sql_record[5]
                    root_path = self._roots.get(root_name)
                    if not root_path:
                        # The root name doesn't match a recognized name, so skip this entry
                        continue                    
                    local_os_path = self._dbpath_to_path(root_path, db_path)
                    
                    # now create sg data chunk
                    sg_record = {}
                    sg_record["entity"] = {}
                    sg_record["entity"]["type"] = sql_record[1]
                    sg_record["entity"]["id"] = sql_record[2]
                    sg_record["entity"]["name"] = sql_record[3]
                    sg_record["path"] = local_os_path
                    sg_record["primary"] = bool(sql_record[6])
                    sg_record["metadata"] = {}
                    sg_record["path_cache_row_id"] = sql_record[0]
                
                    sg_data.append(sg_record)
                
                # event log description
                desc = "Uploaded existing local path cache data to Shotgun."
                
                # and upload
                (event_log_id, sg_id_lookup) = self._upload_cache_data_to_shotgun(sg_data, desc, log)
                
                # all good - now update the database to indicate that these fields have been pushed.
                for (pc_row_id, sg_id) in sg_id_lookup.items():
                    cursor.execute("INSERT INTO shotgun_status(path_cache_id, shotgun_id) "
                                   "VALUES(?, ?)", (pc_row_id, sg_id) )                
            
            except:
                # error processing shotgun. Make sure we roll back the sqlite transaction.
                self._connection.rollback()
                raise
             
            else:
                # ok all good - data has been pushed to shotgun - we can safely commit!
                self._connection.commit()



    def _do_full_sync(self, cursor, log):
        """
        Ensure the local path cache is in sync with Shotgun.
        
        Returns a list of remote items which were detected, created remotely
        and not existing in this path cache. These are returned as a list of 
        dictionaries, each containing keys:
            - entity
            - metadata 
            - path
        """
        if log:
            log.info("Performing a full sync from Shotgun to the local path cache...")
        
        # find the max event log id. Will we store this in the sync db later.
        sg_data = self._tk.shotgun.find_one("EventLogEntry", 
                                            [["event_type", "in", ["Toolkit_Folders_Create", "Toolkit_Folders_Delete"]]], 
                                            ["id"], 
                                            [{"field_name": "id", "direction": "desc"}])

        if sg_data is None:
            # event log was wiped or we haven't done any folder operations
            max_event_log_id = 0
        else:
            max_event_log_id = sg_data["id"]
        
        return self._replay_folder_entities(cursor, log, max_event_log_id)

    def _do_incremental_sync(self, cursor, log, sg_data):
        """
        Ensure the local path cache is in sync with Shotgun.
        
        Patch the existing cache with the events passed via sg_data.
        
        Assumptions:
        - sg_data list always contains some entries
        - sg_data list only contains Toolkit_Folders_Create records
        
        This is a list of dicts ordered by id from low to high (old to new), 
        each with keys
            - id
            - meta
            - attribute_name
        
        Example of items:
        {'event_type': 'Toolkit_Folders_Create', 
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
            return []
        
        # find the max event log id in sg_data. Will we store this in the sync db later.
        max_event_log_id = max( [x["id"] for x in sg_data] )
        
        created_folder_ids = []
        for d in sg_data:
            if d["event_type"] == "Toolkit_Folders_Create":
                # this is a creation request! Replay it on our database
                created_folder_ids.extend( d["meta"]["sg_folder_ids"] )
            else:
                # should never come here
                raise Exception("Unsupported event type '%s'" % d)
                
        if log:
            log.info("Updating path cache - Applying %s updates..." % len(created_folder_ids))

        return self._replay_folder_entities(cursor, log, max_event_log_id, created_folder_ids)


    def _replay_folder_entities(self, cursor, log, max_event_log_id, ids=None):
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

        if log:
            log.info("Retrieving data from Shotgun...")
        
        if ids is None:
            # get all folder data from shotgun
            project_link = {"type": "Project", 
                            "id": self._tk.pipeline_configuration.get_project_id() }
            sg_data = self._tk.shotgun.find(SHOTGUN_ENTITY, 
                                  [["project", "is", project_link]],
                                  ["id",
                                   SG_METADATA_FIELD, 
                                   SG_IS_PRIMARY_FIELD, 
                                   SG_ENTITY_ID_FIELD,
                                   SG_PATH_FIELD,
                                   SG_ENTITY_TYPE_FIELD, 
                                   SG_ENTITY_NAME_FIELD],
                                  [{"field_name": "id", "direction": "asc"},])
        else:
            # get the ids that are missing from shotgun
            # need to use this weird special filter syntax
            id_in_filter = ["id", "in"]
            id_in_filter.extend(ids)
            sg_data = self._tk.shotgun.find(SHOTGUN_ENTITY, 
                                  [id_in_filter],
                                  ["id",
                                   SG_METADATA_FIELD, 
                                   SG_IS_PRIMARY_FIELD, 
                                   SG_ENTITY_ID_FIELD,
                                   SG_PATH_FIELD,
                                   SG_ENTITY_TYPE_FIELD, 
                                   SG_ENTITY_NAME_FIELD],
                                  [{"field_name": "id", "direction": "asc"},])
        
        if log:
            log.info("...Retrieved %s records." % len(sg_data))
        
            
        # now start a single transaction in which we do all our work
        if ids is None:
            # complete sync - clear our tables first
            cursor.execute("DELETE FROM event_log_sync")
            cursor.execute("DELETE FROM shotgun_status")
            cursor.execute("DELETE FROM path_cache")
            
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
            
            new_rowid = self._add_db_mapping(cursor, local_os_path, entity, is_primary)
            if new_rowid != 0:
                # something was inserted into the db!
                # because this record came from shotgun, insert a record in the
                # shotgun_status table to indicate that this record exists in sg
                cursor.execute("INSERT INTO shotgun_status(path_cache_id, shotgun_id) "
                               "VALUES(?, ?)", (new_rowid, x["id"]) )
            
                # and add this entry to our list of new things that we will return later on.
                return_data.append({"entity": entity, 
                                    "path": local_os_path, 
                                    "metadata": SG_METADATA_FIELD})
            
            else:
                # Note: edge case - for some reason there was already an entry in the path cache
                # representing this. This could be because of duplicate entries and is
                # not necessarily an anomaly.
                pass  
            
        # lastly, id of this event log entry for purpose of future syncing
        cursor.execute("DELETE FROM event_log_sync")
        cursor.execute("INSERT INTO event_log_sync(last_id) VALUES(?)", (max_event_log_id, ))
            
        self._connection.commit()

        return return_data

    ############################################################################################
    # pre-insertion validation

    def validate_mappings(self, data):
        """
        Checkcs a series of path mappings to ensure that they don't conflict with
        existing path cache data.
        
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
        :param is_primary: indicates that this is a primary mapping - each folder may have
                           both primary and secondary entity associations - the secondary
                           being more loosely tied to the path.
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
                    # because there is already a folder which represents that item. (although now with 
                    # an incorrect name)

                    msg  = "The path '%s' cannot be processed because it is already associated " % path
                    msg += "with %s '%s' (id %s) in Shotgun. " % (entity_in_db["type"], entity_in_db["name"], entity_in_db["id"])
                    msg += "You are now trying to associate it with %s '%s' (id %s). " % (entity["type"], entity["name"], entity["id"])
                    msg += "If you want to unregister your previously created folders, you can run "
                    msg += "the following command: 'tank %s %s unregister_folders' " % (entity_in_db["type"], entity_in_db["name"])
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
                    msg += "is changed. In order to continue you can either change "
                    msg += "the %s back to its previous name or you can unregister " % entity["type"]
                    msg += "the currently associated folders by running the following command: "
                    msg += "'tank %s %s unregister_folders' and then try again." % (entity["type"], entity["name"])                    
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
                      - metadata: folder configuration metadata
                      
        :param entity_type: sg entity type for the original high level folder creation 
                            request that represents this series of mappings
        :param entity_ids: list of sg entity ids (ints) that represents which objects triggered 
                           the high level folder creation request.
                           
        """        
        
        
        c = self._connection.cursor()
        try:
            data_for_sg = []
            
            for d in data:
                new_rowid = self._add_db_mapping(c, d["path"], d["entity"], d["primary"]) 
                if new_rowid != 0:
                    # this entry wasn't already in the db. So add it to the list to
                    # potentially upload to SG later on
                    data_for_sg.append(d)
                    # append path cache row id to data
                    d["path_cache_row_id"] = new_rowid
                    
                
            
            if self._sync_with_sg:

                # first, a summary of what we are up to for the event log description
                entity_ids = ", ".join([str(x) for x in entity_ids])
                desc = ("Created folders on disk for %ss with id: %s" % (entity_type, entity_ids))

                # now push to shotgun
                (event_log_id, sg_id_lookup) = self._upload_cache_data_to_shotgun(data_for_sg, desc)
                # store insertion marker in the db
                c.execute("DELETE FROM event_log_sync")
                c.execute("INSERT INTO event_log_sync(last_id) VALUES(?)", (event_log_id, ))
                # and indicate in the path cache that all these records have been pushed
                for (pc_row_id, sg_id) in sg_id_lookup.items():
                    c.execute("INSERT INTO shotgun_status(path_cache_id, shotgun_id) "
                              "VALUES(?, ?)", (pc_row_id, sg_id) )
                    

        except:
            # error processing shotgun. Make sure we roll back the sqlite path cache
            # transaction
            self._connection.rollback()
            raise
        
        else:
            # Shotgun insert complete! Now we can commit path cache transaction
            self._connection.commit()
        
        finally:
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
        
        :returns: 0 if nothing was added to the db, otherwise the ROWID for the new row   
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
                    return 0
                
        else:
            # secondary entity
            # in this case, it is okay with more than one record for a path
            # but we don't want to insert the exact same record over and over again
            paths = self.get_paths(entity["type"], entity["id"], primary_only=False, cursor=cursor)

            if path in paths:
                # we already have the association present in the db.
                return 0

        # there was no entity in the db. So let's create it!
        root_name, relative_path = self._separate_root(path)
        db_path = self._path_to_dbpath(relative_path)
        cursor.execute("""INSERT INTO path_cache(entity_type,
                                                 entity_id,
                                                 entity_name,
                                                 root,
                                                 path,
                                                 primary_entity)
                           VALUES(?, ?, ?, ?, ?, ?)""", 
                        (entity["type"], 
                         entity["id"], 
                         entity["name"], 
                         root_name, 
                         db_path, 
                         primary))
                
        return cursor.lastrowid


    
    ############################################################################################
    # database accessor methods

    def get_folder_tree_from_sg_id(self, shotgun_id):
        """
        Returns a list of items making up the subtree below a certain shotgun id
        Each item in the list is a dictionary with keys path and sg_id.
        """
        
        c = self._connection.cursor()
        # first get the path
        res = c.execute("""SELECT pc.root, pc.path 
                          FROM path_cache pc
                          INNER JOIN shotgun_status ss on pc.rowid = ss.path_cache_id
                          WHERE ss.shotgun_id = ? """, (shotgun_id, ))
         
        res = list(res)
        
        if len(res) == 0:
            return []
        
        matches = []
        
        # returns something like [('primary', '/assets/Character/foo')]
        root_name = res[0][0]
        path = res[0][1]
        # first append this match
        matches.append( {"path": self._dbpath_to_path(root_name, path), "sg_id": shotgun_id } )
                         
        
        # now get all paths that are child paths
        like_path = "%s/%%" % path
        res = c.execute("""SELECT pc.root, pc.path, ss.shotgun_id
                          FROM path_cache pc
                          INNER JOIN shotgun_status ss on pc.rowid = ss.path_cache_id
                          WHERE root = ? and path like ?""", (root_name, like_path))
        
        for x in list(res):
            root_name = x[0]
            path = x[1]
            sg_id = x[2]
            # first append this match
            matches.append( {"path": self._dbpath_to_path(root_name, path), "sg_id": sg_id } )
            
        return matches

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
        
        try:
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
        finally:        
            if cursor is None:
                c.close()
        
        return paths

    def get_entity(self, path, cursor=None):
        """
        Returns an entity given a path.
        
        If this path is made up of nested entities (e.g. has a folder creation expression
        on the form Shot: "{code}_{sg_sequence.Sequence.code}"), the primary entity (in 
        this case the Shot) will be returned.

        Note that if the lookup fails, none is returned.

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

        try:
            db_path = self._path_to_dbpath(relative_path)
            res = c.execute("SELECT entity_type, entity_id, entity_name FROM path_cache WHERE path = ? AND root = ? and primary_entity = 1", (db_path, root_path))
            data = list(res)
        finally:
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
        try:
            root_path, relative_path = self._separate_root(path)
        except TankError:
            # fail gracefully if path is not a valid path
            # eg. doesn't belong to the project
            return []

        c = self._connection.cursor()
        try:
            db_path = self._path_to_dbpath(relative_path)
            res = c.execute("SELECT entity_type, entity_id, entity_name FROM path_cache WHERE path = ? AND root = ? and primary_entity = 0", (db_path, root_path))
            data = list(res)
        finally:
            c.close()

        matches = []
        for d in data:        
            # convert to string, not unicode!
            type_str = str(d[0])
            name_str = str(d[2])
            matches.append( {"type": type_str, "id": d[1], "name": name_str } )

        return matches
    