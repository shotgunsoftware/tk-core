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
import os

from .errors import TankError 


SHOTGUN_ENTITY = "CustomEntity01"

SG_ENTITY_FIELD = "sg_entity"
SG_PATH_FIELD = "sg_path"
SG_IS_PRIMARY_FIELD = "sg_primary"
SG_ENTITY_ID_FIELD = "sg_type_id_creation"
SG_ENTITY_TYPE_FIELD = "sg_type_at_creation"
SG_ENTITY_NAME_FIELD = "code"





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
        return []


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
            self._validate_maping(d["path"], d["entity"], d["primary"])
        
        
    def _validate_maping(self, path, entity, is_primary):
        """
        Consistency checks happening prior to folder creation. May raise a TankError
        if an inconsistency is detected.
        
        :param path: The path calculated
        :param entity: Sg entity dict with keys id, type and name
        """
        
        # Check 1. make sure that there isn't already a record with the same
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
        # we only check for ingoing primary entities, doing the check for secondary
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

    def add_mappings(self, data):
        """
        Adds a collection of mappings to the path cache in case they are not 
        already there. 
        
        :param data: list of dictionaries. Each dictionary contains 
                     the following keys:
                      - entity: a dictionary with keys name, id and type
                      - path: a path on disk
                      - primary: a boolean indicating if this is a primary entry
        """
                
        for d in data:
            self._add_db_mapping(d["path"], d["entity"], d["primary"])

        # now add mappings to shotgun. Pass it as a single request via batch
        sg_batch_data = []
        for d in data:
            
            req = {"request_type":"create", 
                   "entity_type": SHOTGUN_ENTITY, 
                   "data": {SG_ENTITY_FIELD: d["entity"],
                            SG_IS_PRIMARY_FIELD: d["primary"],
                            SG_ENTITY_ID_FIELD: d["entity"]["id"],
                            SG_ENTITY_TYPE_FIELD: d["entity"]["type"],
                            SG_ENTITY_NAME_FIELD: d["entity"]["name"],
                            SG_PATH_FIELD: { "local_path": d["path"] }
                            } }
            sg_batch_data.append(req)
        
        # push to shotgun in a single xact
        try:    
            self._tk.shotgun.batch(sg_batch_data)
        except Exception, e:
            raise TankError("Critical! Could not update Shotgun with the folder "
                            "creation information. Please contact support. Error details: %s" % e)
            
        
        

    def _add_db_mapping(self, path, entity, primary):
        """
        Adds an association to the database. If the association already exists, it will
        do nothing, just return.
        
        If there is another association which conflicts with the association that is 
        to be inserted, a TankError is raised.

        :param path: a path on disk representing the entity.
        :param entity: a shotgun entity dict with keys type, id and name
        :param primary: is this the primary entry for this particular path        
        """
        
        if primary:
            # the primary entity must be unique: path/id/type 
            # see if there are any records for this path
            # note that get_entity does not return secondary entities
            curr_entity = self.get_entity(path)
            
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
                    return
                
        else:
            # secondary entity
            # in this case, it is okay with more than one record for a path
            # but we don't want to insert the exact same record over and over again
            paths = self.get_paths(entity["type"], entity["id"], primary_only=False)
            if path in paths:
                # we already have the association present in the db.
                return

        # there was no entity in the db. So let's create it!
        c = self._connection.cursor()
        root_name, relative_path = self._separate_root(path)
        db_path = self._path_to_dbpath(relative_path)
        c.execute("INSERT INTO path_cache VALUES(?, ?, ?, ?, ?, ?)", (entity["type"], 
                                                                      entity["id"], 
                                                                      entity["name"], 
                                                                      root_name,
                                                                      db_path,
                                                                      primary))
        self._connection.commit()
        c.close()


    
    ############################################################################################
    # database accessor methods

    def get_paths(self, entity_type, entity_id, primary_only=True):
        """
        Returns a path given a shotgun entity (type/id pair)

        :param entity_type: a Shotgun entity type
        :params entity_id: a Shotgun entity id
        :returns: a path on disk
        """
        paths = []
        c = self._connection.cursor()
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
        
        c.close()
        return paths

    def get_entity(self, path):
        """
        Returns an entity given a path.
        
        If this path is made up of nested entities (e.g. has a folder creation expression
        on the form Shot: "{code}_{sg_sequence.Sequence.code}"), the primary entity (in 
        this case the Shot) will be returned.

        :param path: a path on disk
        :returns: Shotgun entity dict, e.g. {"type": "Shot", "name": "xxx", "id": 123} 
                  or None if not found
        """
        c = self._connection.cursor()
        try:
            root_path, relative_path = self._separate_root(path)
        except TankError:
            # fail gracefully if path is not a valid path
            # eg. doesn't belong to the project
            return None

        db_path = self._path_to_dbpath(relative_path)
        res = c.execute("SELECT entity_type, entity_id, entity_name FROM path_cache WHERE path = ? AND root = ? and primary_entity = 1", (db_path, root_path))
        data = list(res)
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
    