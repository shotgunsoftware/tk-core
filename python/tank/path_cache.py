"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

Methods relating to the Path cache, a central repository where metadata about 
all Tank items in the file system are kept. 

"""

import sqlite3
import os

from . import root
from .errors import TankError 
from platform import constants

class PathCache(object):
    """
    A global cache which holds the mapping between a shotgun entity and a location on disk.
    
    NOTE! This uses sqlite and the db is typically hosted on an NFS storage.
    Ensure that the code is developed with the constraints that this entails in mind.
    """
    
    def __init__(self, project_root, roots=None):
        """
        Constructor
        
        :param project_root: project root for which the database should be loaded
        """
        # make sure that the project root has the right slashes
        self._project_root = project_root.replace("/", os.sep)
        db_path = constants.get_cache_db_location(self._project_root)
        self._init_db(db_path)
        self.roots = roots or root.get_project_roots(project_root)
        
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
        
        self.connection = sqlite3.connect(db_path)
        self.connection.text_factory = str
        
        c = self.connection.cursor()
        c.executescript("""
            CREATE TABLE IF NOT EXISTS path_cache (entity_type text, entity_id integer, entity_name text, root text, path text);
        
            CREATE INDEX IF NOT EXISTS path_cache_entity ON path_cache(entity_type, entity_id);
        
            CREATE UNIQUE INDEX IF NOT EXISTS path_cache_path ON path_cache(root, path);
        
            CREATE UNIQUE INDEX IF NOT EXISTS path_cache_all ON path_cache(entity_type, entity_id, root, path);
        """)
        
        # Check to see if we need to add "root" to the table. Can delete when we're sure everyone has run
        # through the migration.
        ret = c.execute("PRAGMA table_info(path_cache)")
        if "root" not in [x[1] for x in ret.fetchall()]:
            c.executescript("""
                ALTER TABLE path_cache ADD COLUMN root text;

                UPDATE path_cache SET root='primary';
                
                DROP INDEX path_cache_path;
                CREATE UNIQUE INDEX path_cache_path ON path_cache(root, path);
                
                DROP INDEX path_cache_all;
                CREATE UNIQUE INDEX path_cache_all ON path_cache(entity_type, entity_id, root, path);
            """)
            
        self.connection.commit()
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

    def _seperate_root(self, full_path):
        """
        Determines project root path and relative path.

        :returns: root_name, relative_path
        """
        n_path = full_path.replace(os.sep, "/")
        # Deterimine which root
        root_name = None
        relative_path = None
        for cur_root_name, root_path in self.roots.items():
            n_root = root_path.replace(os.sep, "/")
            if n_path.lower().startswith(n_root.lower()):
                root_name = cur_root_name
                # chop off root
                relative_path = full_path[len(root_path):]

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

    def add_mapping(self, entity_type, entity_id, entity_name, path):
        """
        Adds an association to the database.

        Will raise an exception if the entries we are trying to insert are not unique.

        :param entity_type: a shotgun entity type
        :param entity_id: a shotgun entity id
        :param entity_name: a shotgun entity name
        :param path: a path on disk representing the entity.
        """

        c = self.connection.cursor()
        root_name, relative_path = self._seperate_root(path)
        db_path = self._path_to_dbpath(relative_path)

        try:
            c.execute("INSERT INTO path_cache VALUES(?, ?, ?, ?, ?)", (entity_type, 
                                                                    entity_id, 
                                                                    entity_name, 
                                                                    root_name,
                                                                    db_path))
        except sqlite3.IntegrityError, e:
            # Trying to insert the exact value we already have cached isn't an error. But if we insert
            # a different entity for a path we've already cached, that's a problem.
            if e.args[0] == "columns entity_type, entity_id, root, path are not unique":
                # means we are trying to re-insert the same record which is fine!
                pass
            elif e.args[0] == "column path is not unique":
                # means that we have tried to insert the same path twice in the database,
                # but with different values for entity ids etc.
                # this can happen if we reconfigure the config in such a way that a folder
                # that used to represent a folder X now represents a folder Y.
                # definitely and edge case, but good to cover.
                raise TankError("The path %s is currently already connected to an entity in Shotgun, "
                                 "however you are trying to connect it to a different entity. This "
                                 "is not allowed. Please contact the Tank support!" % path)
            else:
                # some error we don't expect. So re-raise it.
                raise e

        self.connection.commit()
        c.close()

    def get_paths(self, entity_type, entity_id):
        """
        Returns a path given a shotgun entity (type/id pair)

        :param entity_type: a Shotgun entity type
        :params entity_id: a Shotgun entity id
        :returns: a path on disk
        """
        paths = []
        c = self.connection.cursor()
        res = c.execute("SELECT root, path FROM path_cache WHERE entity_type = ? AND entity_id = ?", (entity_type, entity_id))

        for row in res:
            root_name = row[0]
            relative_path = row[1]
            
            root_path = self.roots.get(root_name)
            if not root_path:
                # The root name doesn't match a recognized name, so skip this entry
                continue
            
            # assemble path
            path_str = self._dbpath_to_path(root_path, relative_path)
            paths.append(path_str)

        return paths

    def get_entity(self, path):
        """
        Returns an entity given a path.

        :param path: a path on disk
        :returns: Shotgun entity dict, e.g. {"type": "Shot", "name": "xxx", "id": 123} 
                  or None if not found
        """
        c = self.connection.cursor()
        try:
            root_path, relative_path = self._seperate_root(path)
        except TankError:
            # fail gracefully if path is not a valid path
            # eg. doesn't belong to the project
            return None

        db_path = self._path_to_dbpath(relative_path)

        res = c.execute("SELECT entity_type, entity_id, entity_name FROM path_cache WHERE path = ? AND root = ?", (db_path, root_path))

        data = list(res)

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
