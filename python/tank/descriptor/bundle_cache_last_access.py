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
from .. import LogManager

# Shotgun field definitions to store the path cache data
SHOTGUN_ENTITY = "FilesystemLocation"
SG_ENTITY_FIELD = "entity"
SG_PATH_FIELD = "path"
SG_METADATA_FIELD = "configuration_metadata"
SG_IS_PRIMARY_FIELD = "is_primary"
SG_ENTITY_ID_FIELD = "linked_entity_id"
SG_ENTITY_TYPE_FIELD = "linked_entity_type"
SG_ENTITY_NAME_FIELD = "code"
SG_PIPELINE_CONFIG_FIELD = "pipeline_configuration"

log = LogManager.get_logger(__name__)


class BundleCacheLastAccess(object):
    """
    A local flat file SQLite-based database tracking bundle cache accesses.
    """

    def __init__(self):
        """
        Constructor.
        """
        self._bundle_cache_root = None
        self._connection = None
        self._database_location = None
        self._init_db()

    def _init_db(self):
        """
        Sets up the database
        """
        # first, make way for the path cache file. This call
        # will ensure that there is a valid folder and file on
        # disk, created with all the right permissions etc.
        path_cache_file = self._get_path_cache_location()

        self._connection = sqlite3.connect(path_cache_file)

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

                # note that because some clients are writing to NFS storage, we
                # up the default page size somewhat (from 4k -> 8k) to improve
                # performance. See https://sqlite.org/pragma.html#pragma_page_size

                c.executescript("""
                    PRAGMA page_size=8192;

                    CREATE TABLE path_cache (entity_type text, entity_id integer, entity_name text, root text, path text, primary_entity integer);

                    CREATE INDEX path_cache_entity ON path_cache(entity_type, entity_id);

                    CREATE INDEX path_cache_path ON path_cache(root, path, primary_entity);

                    CREATE UNIQUE INDEX path_cache_all ON path_cache(entity_type, entity_id, root, path, primary_entity);

                    CREATE TABLE event_log_sync (last_id integer);

                    CREATE TABLE shotgun_status (path_cache_id integer, shotgun_id integer);

                    CREATE UNIQUE INDEX shotgun_status_id ON shotgun_status(path_cache_id);

                    CREATE INDEX shotgun_status_shotgun_id ON shotgun_status(shotgun_id);
                    """)
                self._connection.commit()

            else:

                # we have an existing database! Ensure it is up to date
                if "event_log_sync" not in table_names:
                    # this is a pre-0.15 setup where the path cache does not have event log sync
                    c.executescript("CREATE TABLE event_log_sync (last_id integer);")
                    self._connection.commit()

                if "shotgun_status" not in table_names:
                    # this is a pre-0.15 setup where the path cache does not have the shotgun_status table
                    c.executescript("""CREATE TABLE shotgun_status (path_cache_id integer, shotgun_id integer);
                                       CREATE UNIQUE INDEX shotgun_status_id ON shotgun_status(path_cache_id);""")
                    self._connection.commit()

                # now ensure that some key fields that have been added during the dev cycle are there
                ret = c.execute("PRAGMA table_info(path_cache)")
                field_names = [x[1] for x in ret.fetchall()]

                # check for primary entity field - this was added back in 0.12.x
                if "primary_entity" not in field_names:
                    c.executescript("""
                        ALTER TABLE path_cache ADD COLUMN primary_entity integer;
                        UPDATE path_cache SET primary_entity=1;

                        DROP INDEX IF EXISTS path_cache_path;
                        CREATE INDEX IF NOT EXISTS path_cache_path ON path_cache(root, path, primary_entity);

                        DROP INDEX IF EXISTS path_cache_all;
                        CREATE UNIQUE INDEX IF NOT EXISTS path_cache_all ON path_cache(entity_type, entity_id, root, path, primary_entity);
                        """)

                    self._connection.commit()

        finally:
            c.close()

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
        Close the last access database connection.
        """
        if self._connection is not None:
            self._connection.close()
            self._connection = None


