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

class PathCache(object):
    """
    A global cache which holds the mapping between a shotgun entity and a location on disk.
    
    NOTE! This uses sqlite and the db is typically hosted on an NFS storage.
    Ensure that the code is developed with the constraints that this entails in mind.
    """
    
    def __init__(self, pipeline_configuration):
        """
        Constructor
        :param pipeline_configuration: pipeline config object
        """
        self._connection = None
        
        if pipeline_configuration.has_associated_data_roots():
            db_path = pipeline_configuration.get_path_cache_location()
            self._path_cache_disabled = False
            self._init_db(db_path)
            self._roots = pipeline_configuration.get_data_roots()

        else:
            # no primary location found. Path cache therefore does not exist!
            # go into a no-path-cache-mode
            self._path_cache_disabled = True
        
    
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
        
        # this is to handle unicode properly - make sure that sqlite returns str objects
        # for TEXT fields rather than unicode.
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
        
    def delete_path_tree(self, path):
        """
        Deletes all records that are associated with the given path.
        """
        if self._path_cache_disabled:
            # no path cache file, so just return. This is consistent with 
            # the behaviour of running delete_path_tree("foo") on a db
            # with no "foo" entries.
            return
            
        # there was no entity in the db. So let's create it!
        c = self._connection.cursor()
        root_name, relative_path = self._separate_root(path)
        db_path = self._path_to_dbpath(relative_path)
        query = "DELETE FROM path_cache where root=? and path like '%s%%'" % db_path
        c.execute(query, (root_name,) )
        self._connection.commit()
        c.close()
        

    def add_mapping(self, entity_type, entity_id, entity_name, path, primary=True):
        """
        Adds an association to the database. If the association already exists, it will
        do nothing, just return.
        
        If there is another association which conflicts with the association that is 
        to be inserted, a TankError is raised.

        :param entity_type: a shotgun entity type
        :param entity_id: a shotgun entity id
        :param primary: is this the primary entry for this particular path
        :param entity_name: a shotgun entity name
        :param path: a path on disk representing the entity.
        """
        
        if self._path_cache_disabled:
            raise TankError("You are currently running a configuration which does not have any "
                            "capabilities of storing path entry lookups. There is no path cache "
                            "file defined for this project.")
        
        if primary:
            # the primary entity must be unique: path/id/type 
            # see if there are any records for this path
            # note that get_entity does not return secondary entities
            curr_entity = self.get_entity(path)
            new_entity = {"id": entity_id, "type": entity_type, "name": entity_name}
            
            if curr_entity is not None:
                # this path is already registered. Ensure it is connected to
                # our entity! Note! We are only comparing against the type and the id
                # not against the name. It should be perfectly valid to rename something
                # in shotgun and if folders are then recreated for that item, nothing happens
                # because there is already a folder which repreents that item. (although now with 
                # an incorrect name)
                if curr_entity["type"] != entity_type or curr_entity["id"] != entity_id:
    
                    # format entities nicely for error message
                    curr_nice_name = "%s %s (id %s)" % (curr_entity["type"], curr_entity["name"], curr_entity["id"])
                    new_nice_name = "%s %s (id %s)" % (new_entity["type"], new_entity["name"], new_entity["id"])
    
                    raise TankError("The path '%s' is already associated with Shotgun "
                                    "%s. You are trying to associate the same "
                                    "path with %s. This typically happens "
                                    "when shots have been relinked to new sequences, if you are "
                                    "trying to create two shots with the same name or if "
                                    "you have made big changes to the folder configuration. "
                                    "Please contact support on toolkitsupport@shotgunsoftware.com "
                                    "if you need help or advice!" % (path, curr_nice_name, new_nice_name ))
                    
                else:
                    # the entry that exists in the db matches what we are trying to insert
                    # so skip it
                    return
                
        else:
            # secondary entity
            # in this case, it is okay with more than one record for a path
            # but we don't want to insert the exact same record over and over again
            paths = self.get_paths(entity_type, entity_id, primary_only=False)
            if path in paths:
                # we already have the association present in the db.
                return

        # there was no entity in the db. So let's create it!
        c = self._connection.cursor()
        root_name, relative_path = self._separate_root(path)
        db_path = self._path_to_dbpath(relative_path)
        c.execute("INSERT INTO path_cache VALUES(?, ?, ?, ?, ?, ?)", (entity_type, 
                                                                entity_id, 
                                                                entity_name, 
                                                                root_name,
                                                                db_path,
                                                                primary))
        self._connection.commit()
        c.close()

    def get_paths(self, entity_type, entity_id, primary_only=True):
        """
        Returns a path given a shotgun entity (type/id pair)

        :param entity_type: a Shotgun entity type
        :params entity_id: a Shotgun entity id
        :returns: a path on disk
        """
        
        if self._path_cache_disabled:
            # no entries because we don't have a path cache
            return []
        
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

        Note that if the lookup fails, none is returned.

        :param path: a path on disk
        :returns: Shotgun entity dict, e.g. {"type": "Shot", "name": "xxx", "id": 123} 
                  or None if not found
        """
        
        if self._path_cache_disabled:
            # no entries because we don't have a path cache
            return None
        
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
        
        if self._path_cache_disabled:
            # no entries because we don't have a path cache
            return []
        
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
    
